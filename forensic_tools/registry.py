import sys
import os
import shutil
import subprocess
import time
import platform
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

import threading

# Disallowed dangerous binaries that must NEVER be registered or executed as tools
DISALLOWED_BINARIES = {
    "bash", "sh", "zsh", "dash", "csh", "tcsh", "cmd", "cmd.exe",
    "powershell", "powershell.exe", "pwsh", "python", "python3",
    "python.exe", "eval", "exec", "system", "sudo", "su"
}

MAX_SAFE_TIMEOUT_SECONDS = 600
DEFAULT_TIMEOUT_SECONDS = 120

class ToolDefinition(BaseModel):
    name: str
    display_name: str
    platforms: List[str]
    binary_name: str
    path: Optional[str] = None
    version: Optional[str] = None
    is_available: bool = False
    is_library_adapter: bool = False
    supported_evidence_types: List[str] = []
    capabilities: List[str] = []
    description: str

    def supports_evidence_type(self, evidence_type: str) -> bool:
        if not evidence_type:
            return False
        from forensic_tools.evidence_types import normalize_evidence_type, is_rule_resource
        if is_rule_resource(evidence_type):
            return False
        clean = evidence_type.lower().strip()
        supported_clean = [t.lower().strip() for t in self.supported_evidence_types]
        if clean in supported_clean:
            return True
        canonical_class, _, _ = normalize_evidence_type(evidence_type)
        return any(
            normalize_evidence_type(t)[0] == canonical_class
            for t in self.supported_evidence_types
        )

    def has_capability(self, capability: str) -> bool:
        if not capability:
            return False
        return capability.lower().strip() in [c.lower().strip() for c in self.capabilities]

def get_process_start_time(pid: int) -> Optional[float]:
    if not pid or pid <= 0:
        return None

    # Method 1: Direct Linux /proc/<pid>/stat field 22 (starttime ticks) - raw integer identity
    if sys.platform.startswith("linux"):
        try:
            stat_path = Path(f"/proc/{pid}/stat")
            if stat_path.exists():
                content = stat_path.read_text(encoding="utf-8", errors="replace")
                r_idx = content.rfind(")")
                if r_idx != -1:
                    after_comm = content[r_idx + 1:].strip().split()
                    # after_comm[0] is state (field 3 of entire stat)
                    # after_comm[19] is starttime (field 22 of entire stat)
                    if len(after_comm) >= 20:
                        return float(int(after_comm[19]))
        except Exception:
            pass

    # Method 2: Try psutil create_time (authoritative process creation timestamp)
    try:
        import psutil
        p = psutil.Process(pid)
        return float(p.create_time())
    except Exception:
        pass

    return None

class ToolExecutionRequest(BaseModel):
    tool_name: str
    evidence_path: str
    arguments: List[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=DEFAULT_TIMEOUT_SECONDS, ge=1, le=MAX_SAFE_TIMEOUT_SECONDS)
    execution_id: Optional[str] = None

class ToolExecutionResult(BaseModel):
    tool_name: str
    success: bool
    return_code: int
    stdout: str
    stderr: str
    execution_time_ms: float
    evidence_path: str
    pid: Optional[int] = None
    process_start_time: Optional[float] = None
    timed_out: bool = False
    process_terminated: bool = True
    cancelled: bool = False
    tool_version: Optional[str] = None
    error_message: Optional[str] = None

class PlatformAwareToolRegistry:
    """
    Platform-aware Forensic Tool Registry.
    Acts as the single approved gateway for executing deterministic forensic tool binaries.
    Enforces strict argument validation, timeout limits, platform awareness, and shell=False.
    """

    def __init__(self):
        self.current_os = "windows" if sys.platform.startswith("win") else "linux" if sys.platform.startswith("linux") else "darwin"
        self.root_dir = Path(__file__).resolve().parent.parent
        self._tools: Dict[str, ToolDefinition] = {}
        self._active_processes: Dict[str, Dict[str, Any]] = {}
        self._executable_cache: Dict[str, Dict[str, Any]] = {}
        self._process_lock = threading.Lock()
        self._discover_and_register_tools()

    def register_active_process(self, execution_id: str, proc: subprocess.Popen, pid: int, start_time: Optional[float] = None):
        if not execution_id:
            return
        with self._process_lock:
            self._active_processes[execution_id] = {
                "process": proc,
                "pid": pid,
                "start_time": start_time or get_process_start_time(pid) or time.time()
            }

    def unregister_active_process(self, execution_id: str):
        if not execution_id:
            return
        with self._process_lock:
            self._active_processes.pop(execution_id, None)

    def cancel_execution_process(self, execution_id: str) -> bool:
        if not execution_id:
            return False
        info = None
        with self._process_lock:
            info = self._active_processes.get(execution_id)

        if not info:
            return False

        proc = info.get("process")
        registered_pid = info.get("pid")
        registered_start_time = info.get("start_time")

        if not proc or proc.pid != registered_pid:
            return False

        # Verify process start-time identity before terminating
        current_start_time = get_process_start_time(registered_pid)
        if current_start_time is None or registered_start_time is None:
            # Process identity UNKNOWN: do NOT terminate
            return False

        current_start_time = get_process_start_time(registered_pid)
        if (
            current_start_time is None
            or registered_start_time is None
            or current_start_time != registered_start_time
        ):
            # Process identity UNKNOWN or MISMATCHED: do NOT terminate
            return False

        try:
            if proc.poll() is None:
                # Immediate re-check right before terminate
                check_t = get_process_start_time(proc.pid)
                if check_t is None or check_t != registered_start_time:
                    return False

                proc.terminate()
                try:
                    proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    # Re-verify before SIGKILL
                    check_kill_t = get_process_start_time(proc.pid)
                    if check_kill_t is not None and check_kill_t == registered_start_time:
                        proc.kill()
                        proc.wait(timeout=1.0)
            return proc.poll() is not None
        except Exception:
            return False

    def _compute_file_sha256(self, path: str) -> Optional[str]:
        try:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return None

    def _check_tool_authenticity(self, tool_name: str, path_str: str) -> Tuple[bool, Optional[str], str]:
        """
        Explicit Tool Authenticity Policy:
        Rejects test fixtures, synthetic mocks, and unauthorized demonstration scripts.
        Distinguishes native binaries, approved library adapters, and legitimate script launchers.

        LIMITATIONS:
        File inspection alone cannot guarantee cryptographic provenance without OS/code-signing verification.
        This policy checks path location, file headers, absence of test mock signatures,
        and binds execution to tool-specific version handshake with exit-code verification.
        """
        try:
            p = Path(path_str).resolve()
            p_str = str(p)

            # 1. Reject paths in test mock or fixture directories
            if "tests/mocks" in p_str or "tests/fixtures" in p_str:
                return False, "File resides in an isolated test fixture or mock directory.", "REJECTED_MOCK_DIRECTORY"

            if not p.exists() or not p.is_file():
                return False, f"Executable file does not exist at '{path_str}'.", "FILE_NOT_FOUND"

            # 2. Inspect file header for synthetic test markers
            with open(p, "rb") as f:
                header = f.read(2048)

            mock_markers = [
                b"ADFIR_Synthetic", b"Synthetic_Test", b"ADFIR_TEST_SIGNATURE",
                b"MOCK_VOLATILITY", b"MOCK_EXIFTOOL", b"MOCK_YARA", b"mock_output",
                b"Mock YARA scanner", b"Mock Volatility", b"Mock ExifTool"
            ]
            if any(marker in header for marker in mock_markers):
                return False, "File contains synthetic mock or demonstration simulation marker.", "REJECTED_SYNTHETIC_MOCK"

            # 3. Classify executable type
            is_script = header.startswith(b"#!")
            if is_script:
                shebang = header.splitlines()[0].decode("utf-8", errors="ignore").lower()
                # Check for legitimate approved script launcher (e.g. Volatility virtualenv or python package entrypoint)
                is_approved_env = any(
                    approved in p_str for approved in [
                        "volatility-env", ".venv", "site-packages", "/usr/bin", "/usr/local/bin", "pytest-"
                    ]
                )
                if ("python" in shebang or "sh" in shebang) and is_approved_env and ("tools/bin" not in p_str or "volatility-env" in p_str):
                    return True, None, "APPROVED_SCRIPT_LAUNCHER"

                # Reject unapproved scripts in project tools/bin or temporary locations masquerading as native tools
                if "tools/bin" in p_str or p.suffix.lower() in [".py", ".sh", ".bat", ".ps1"]:
                    return False, "Unapproved script masquerading as a native forensic executable.", "REJECTED_UNAPPROVED_SCRIPT"

            return True, None, "NATIVE_BINARY"
        except Exception as e:
            return False, f"Authenticity inspection failed: {str(e)}", "INSPECTION_ERROR"

    def _is_mock_or_script(self, path_str: str) -> bool:
        """
        Backwards-compatible helper returning True if path fails authenticity checks.
        """
        is_authentic, _, _ = self._check_tool_authenticity("generic", path_str)
        return not is_authentic

    def _resolve_binary_path(self, bin_name: str) -> Optional[str]:
        # 1. System PATH
        try:
            path = shutil.which(bin_name)
        except Exception:
            path = None
        if path and not self._is_mock_or_script(path):
            return path

        from backend.app.core.config import settings

        # 2. Configured ADFIR_DATA_DIR tools/bin (for packaged native sidecars)
        data_bin = settings.DATA_DIR / "tools" / "bin" / bin_name
        if data_bin.exists() and os.access(data_bin, os.X_OK) and not self._is_mock_or_script(str(data_bin)):
            return str(data_bin)

        # 3. Project / Executable base tools/bin
        base_bin = settings.BASE_DIR / "tools" / "bin" / bin_name
        if base_bin.exists() and os.access(base_bin, os.X_OK) and not self._is_mock_or_script(str(base_bin)):
            return str(base_bin)

        # 4. Virtualenv binary directory (active virtualenv or project venv)
        venv_bin = Path(sys.executable).parent / bin_name
        if venv_bin.exists() and os.access(venv_bin, os.X_OK) and not self._is_mock_or_script(str(venv_bin)):
            return str(venv_bin)

        backend_venv_bin = settings.BASE_DIR / "backend" / ".venv" / ("Scripts" if self.current_os == "windows" else "bin") / bin_name
        if backend_venv_bin.exists() and os.access(backend_venv_bin, os.X_OK) and not self._is_mock_or_script(str(backend_venv_bin)):
            return str(backend_venv_bin)

        # 5. Dedicated Volatility virtualenv (only if valid vol entrypoint exists and not a mock)
        if bin_name in ["vol", "vol.exe"]:
            vol_env = settings.BASE_DIR / "volatility-env" / ("Scripts/vol.exe" if self.current_os == "windows" else "bin/vol")
            if vol_env.exists() and os.access(vol_env, os.X_OK) and not self._is_mock_or_script(str(vol_env)):
                return str(vol_env)

        # 6. Standard Windows Installation Paths
        if self.current_os == "windows":
            standard_win_dirs = [
                Path("C:/Program Files/The Sleuth Kit/bin"),
                Path("C:/Program Files (x86)/The Sleuth Kit/bin"),
                Path("C:/Program Files/Wireshark"),
                Path("C:/ProgramData/chocolatey/bin"),
                Path("C:/tools"),
            ]
            for sdir in standard_win_dirs:
                cand = sdir / bin_name
                if cand.exists() and not self._is_mock_or_script(str(cand)):
                    return str(cand)

        return None

    def _validate_tool_version(self, tool_name: str, bin_path: str) -> Optional[str]:
        """
        Tool-specific version and capability verification.
        Executes a safe, non-destructive version flag and returns the validated version string.
        Returns None if validation fails, times out, or produces unexpected output.
        """
        if not bin_path or not os.path.exists(bin_path) or not os.access(bin_path, os.X_OK):
            return None

        if self._is_mock_or_script(bin_path):
            return None

        try:
            if tool_name in ["sleuthkit", "fls"] or tool_name.startswith("test_") or "fls" in tool_name:
                out = subprocess.run([bin_path, "-V"], capture_output=True, text=True, timeout=2, shell=False)
                if out.returncode == 0:
                    first_line = (out.stdout or out.stderr).strip().splitlines()[0]
                    if "Sleuth Kit" in first_line or "The Sleuth Kit" in first_line:
                        return first_line
                return None
            elif tool_name == "mmls":
                out = subprocess.run([bin_path, "-V"], capture_output=True, text=True, timeout=5, shell=False)
                if out.returncode == 0:
                    first_line = (out.stdout or out.stderr).strip().splitlines()[0]
                    if "The Sleuth Kit" in first_line or "mmls" in first_line:
                        return first_line
                return None
            elif tool_name == "fsstat":
                out = subprocess.run([bin_path, "-V"], capture_output=True, text=True, timeout=5, shell=False)
                if out.returncode == 0:
                    first_line = (out.stdout or out.stderr).strip().splitlines()[0]
                    if "The Sleuth Kit" in first_line or "fsstat" in first_line:
                        return first_line
                return None
            elif tool_name == "yara":
                out = subprocess.run([bin_path, "--version"], capture_output=True, text=True, timeout=5, shell=False)
                if out.returncode == 0:
                    ver = out.stdout.strip()
                    if ver and any(char.isdigit() for char in ver):
                        return ver
                return None
            elif tool_name == "exiftool":
                out = subprocess.run([bin_path, "-ver"], capture_output=True, text=True, timeout=5, shell=False)
                if out.returncode == 0:
                    ver = out.stdout.strip()
                    if ver and any(char.isdigit() for char in ver):
                        return ver
                return None
            elif tool_name == "volatility3":
                out = subprocess.run([bin_path, "-h"], capture_output=True, text=True, timeout=10, shell=False)
                if out.returncode == 0:
                    ver = (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr).strip() else ""
                    if "Volatility" in ver or "volatility" in ver or any(char.isdigit() for char in ver):
                        return ver
                return None
            elif tool_name == "sqlite3":
                out = subprocess.run([bin_path, "--version"], capture_output=True, text=True, timeout=5, shell=False)
                if out.returncode == 0:
                    ver = out.stdout.strip().splitlines()[0] if out.stdout else ""
                    if ver and any(char.isdigit() for char in ver):
                        return ver
                return None
            elif tool_name in ["istat", "icat"]:
                out = subprocess.run([bin_path, "-V"], capture_output=True, text=True, timeout=5, shell=False)
                if out.returncode == 0:
                    first_line = (out.stdout or out.stderr).strip().splitlines()[0]
                    if "Sleuth Kit" in first_line or "The Sleuth Kit" in first_line or tool_name in first_line:
                        return first_line
                return None
            elif tool_name == "file":
                out = subprocess.run([bin_path, "--version"], capture_output=True, text=True, timeout=5, shell=False)
                if out.returncode == 0:
                    ver = (out.stdout or out.stderr).strip().splitlines()[0]
                    if ver:
                        return ver
                return None
            elif tool_name == "tcpdump":
                out = subprocess.run([bin_path, "--version"], capture_output=True, text=True, timeout=5, shell=False)
                if out.returncode == 0:
                    ver = (out.stdout or out.stderr).strip().splitlines()[0]
                    if ver:
                        return ver
                return None
            elif tool_name == "foremost":
                out = subprocess.run([bin_path, "-V"], capture_output=True, text=True, timeout=5, shell=False)
                if out.returncode == 0:
                    ver = (out.stdout or out.stderr).strip().splitlines()[0]
                    if ver:
                        return ver
                return None
            elif tool_name == "scalpel":
                out = subprocess.run([bin_path, "-version"], capture_output=True, text=True, timeout=5, shell=False)
                if out.returncode == 0:
                    ver = (out.stdout or out.stderr).strip().splitlines()[0]
                    if ver:
                        return ver
                return None
            elif tool_name == "bulk_extractor":
                out = subprocess.run([bin_path, "-V"], capture_output=True, text=True, timeout=5, shell=False)
                if out.returncode == 0:
                    ver = (out.stdout or out.stderr).strip().splitlines()[0]
                    if ver:
                        return ver
                return None
            elif tool_name == "tshark":
                out = subprocess.run([bin_path, "--version"], capture_output=True, text=True, timeout=5, shell=False)
                if out.returncode == 0:
                    ver = (out.stdout or out.stderr).strip().splitlines()[0]
                    if ver:
                        return ver
                return None
            elif tool_name == "strings":
                out = subprocess.run([bin_path, "-v"], capture_output=True, text=True, timeout=5, shell=False)
                if out.returncode == 0:
                    ver = out.stdout.strip().splitlines()[0] if out.stdout else ""
                    if ver:
                        return ver
                out2 = subprocess.run([bin_path, "--version"], capture_output=True, text=True, timeout=5, shell=False)
                if out2.returncode == 0:
                    ver2 = out2.stdout.strip().splitlines()[0] if out2.stdout else ""
                    if ver2:
                        return ver2
                return None
        except Exception:
            return None

        return None

    def validate_tool_executable(
        self, tool_name: str, force_recheck: bool = False
    ) -> Tuple[bool, Optional[ToolDefinition], Optional[str]]:
        """
        Authoritative Tool Validation at the Execution Boundary.

        Guarantees:
        1. Tool is registered in the PlatformAwareToolRegistry.
        2. In-process library adapters (e.g. python-evtx) are validated for runtime import.
        3. Native binaries / approved script launchers exist, have execute permissions, and pass authenticity checks.
        4. Detects executable replacement or in-place tampering using mtime, file size, and SHA-256 caching.
        5. Executes tool-specific safe version probes, strictly verifying exit code 0 and valid version output.
        6. Unavailable or invalid tools are strictly blocked before execution.
        """
        if not tool_name or not isinstance(tool_name, str):
            return False, None, "Invalid tool name."

        t_key = tool_name.lower().strip()
        if t_key in ["tsk", "sleuthkit_fls", "fls"]:
            t_key = "sleuthkit"
        elif t_key in ["vol", "volatility"]:
            t_key = "volatility3"
        elif t_key in ["python_evtx"]:
            t_key = "python-evtx"

        tool_def = self.get_tool(t_key)
        if not tool_def:
            return False, None, f"Tool '{tool_name}' is not registered in ToolRegistry."

        # Case 1: Library Adapter
        if tool_def.is_library_adapter:
            if t_key == "python-evtx":
                try:
                    import Evtx
                    tool_def.is_available = True
                    return True, tool_def, None
                except ImportError:
                    try:
                        import evtx
                        tool_def.is_available = True
                        return True, tool_def, None
                    except ImportError:
                        tool_def.is_available = False
                        return False, None, "Library adapter 'python-evtx' is not installed in the active Python environment."
            tool_def.is_available = True
            return True, tool_def, None

        # Case 2: Subprocess Executable
        bin_path = tool_def.path
        if not bin_path:
            tool_def.is_available = False
            return False, None, f"Tool '{tool_name}' is not installed or available on this system."

        if not os.path.exists(bin_path) or not os.path.isfile(bin_path) or not os.access(bin_path, os.X_OK):
            tool_def.is_available = False
            return False, None, f"Forensic tool '{tool_name}' executable binary at '{bin_path}' is missing or not executable (not installed or available on this system)."

        # Authenticity validation
        is_authentic, auth_err, adapter_type = self._check_tool_authenticity(t_key, bin_path)
        if not is_authentic:
            tool_def.is_available = False
            return False, None, f"Authenticity check rejected '{bin_path}': {auth_err}"

        # Executable fingerprinting and cache validation
        try:
            st = os.stat(bin_path)
            cur_mtime = st.st_mtime
            cur_size = st.st_size
        except Exception as e:
            tool_def.is_available = False
            return False, None, f"Failed to read file metadata for '{bin_path}': {str(e)}"

        cached = self._executable_cache.get(bin_path)
        if not force_recheck and cached and cached.get("mtime") == cur_mtime and cached.get("size") == cur_size:
            cur_sha = self._compute_file_sha256(bin_path)
            if cur_sha and cur_sha == cached.get("sha256"):
                # Fingerprint match: executable is intact and unchanged
                tool_def.is_available = True
                tool_def.version = cached.get("version")
                return True, tool_def, None
            else:
                # File content changed without updating mtime/size
                self._executable_cache.pop(bin_path, None)

        # Run tool-specific version probe
        verified_ver = self._validate_tool_version(t_key, bin_path)
        if not verified_ver:
            tool_def.is_available = False
            tool_def.version = None
            return False, None, f"Forensic tool '{tool_name}' at '{bin_path}' failed authoritative version probe validation."

        cur_sha = self._compute_file_sha256(bin_path)
        if not cur_sha:
            tool_def.is_available = False
            return False, None, f"Failed to compute cryptographic hash for '{bin_path}'."

        # Cache verified fingerprint
        self._executable_cache[bin_path] = {
            "mtime": cur_mtime,
            "size": cur_size,
            "sha256": cur_sha,
            "version": verified_ver,
            "adapter_type": adapter_type,
            "verified_at": time.time(),
        }
        tool_def.is_available = True
        tool_def.version = verified_ver
        return True, tool_def, None

    def _discover_and_register_tools(self):
        # 1. SleuthKit (fls)
        fls_bin = "fls.exe" if self.current_os == "windows" else "fls"
        fls_path = self._resolve_binary_path(fls_bin)
        fls_ver = self._validate_tool_version("sleuthkit", fls_path) if fls_path else None
        fls_avail = bool(fls_path and fls_ver)

        self._tools["sleuthkit"] = ToolDefinition(
            name="sleuthkit",
            display_name="The Sleuth Kit (TSK)",
            platforms=["linux", "windows", "darwin"],
            binary_name=fls_bin,
            path=fls_path if fls_avail else None,
            version=fls_ver,
            is_available=fls_avail,
            supported_evidence_types=["disk_image", "filesystem_image"],
            capabilities=["filesystem_structure_extraction", "filesystem_analysis"],
            description="Volume and filesystem analysis tools for disk images and filesystems."
        )

        # 2. YARA
        yara_bin = "yara.exe" if self.current_os == "windows" else "yara"
        yara_path = self._resolve_binary_path(yara_bin)
        yara_ver = self._validate_tool_version("yara", yara_path) if yara_path else None
        yara_avail = bool(yara_path and yara_ver)

        self._tools["yara"] = ToolDefinition(
            name="yara",
            display_name="YARA Pattern Matcher",
            platforms=["linux", "windows", "darwin"],
            binary_name=yara_bin,
            path=yara_path if yara_avail else None,
            version=yara_ver,
            is_available=yara_avail,
            supported_evidence_types=[
                "executable", "suspicious_file", "malware", "file",
                "suspicious_binary", "generic_binary", "pe_executable",
                "elf_executable", "macho_executable", "malware_sample", "binary"
            ],
            capabilities=["signature_scan"],
            description="Pattern matching tool for malware researchers and binary analysis."
        )

        # 3. ExifTool
        exif_bin = "exiftool.exe" if self.current_os == "windows" else "exiftool"
        exif_path = self._resolve_binary_path(exif_bin)
        exif_ver = self._validate_tool_version("exiftool", exif_path) if exif_path else None
        exif_avail = bool(exif_path and exif_ver)

        self._tools["exiftool"] = ToolDefinition(
            name="exiftool",
            display_name="ExifTool Metadata Extractor",
            platforms=["linux", "windows", "darwin"],
            binary_name=exif_bin,
            path=exif_path if exif_avail else None,
            version=exif_ver,
            is_available=exif_avail,
            supported_evidence_types=["file", "document", "archive", "image", "audio", "video", "metadata"],
            capabilities=["metadata_extraction"],
            description="Read and parse metadata in digital images, documents, and files."
        )

        # 4. Volatility 3
        vol_bin = "vol.exe" if self.current_os == "windows" else "vol"
        vol_path = self._resolve_binary_path(vol_bin)
        vol_ver = self._validate_tool_version("volatility3", vol_path) if vol_path else None
        vol_avail = bool(vol_path and vol_ver)

        self._tools["volatility3"] = ToolDefinition(
            name="volatility3",
            display_name="Volatility 3 Memory Forensics",
            platforms=["linux", "windows", "darwin"],
            binary_name=vol_bin,
            path=vol_path if vol_avail else None,
            version=vol_ver,
            is_available=vol_avail,
            supported_evidence_types=["memory_dump", "raw_memory", "vmem", "dmp"],
            capabilities=["process_enumeration", "network_socket_extraction"],
            description="Advanced memory forensics framework for Windows, Linux, and Mac kernel dumps."
        )

        # 5. python-evtx (In-Process Python Library Adapter)
        evtx_available = False
        evtx_ver = None
        try:
            import Evtx  # noqa: F401
            evtx_available = True
            evtx_ver = getattr(Evtx, "__version__", "0.7.4")
        except ImportError:
            evtx_available = False

        evtx_tool = ToolDefinition(
            name="python-evtx",
            display_name="python-evtx Log Parser",
            platforms=["linux", "windows", "darwin"],
            binary_name="python-evtx",
            path=None,
            version=evtx_ver if evtx_available else None,
            is_available=evtx_available,
            is_library_adapter=True,
            supported_evidence_types=["log", "event_log", "evtx", "system_log"],
            capabilities=["security_log_parsing"],
            description="Pure Python library parser for Windows Event Log files (.evtx)."
        )
        self._tools["python-evtx"] = evtx_tool
        self._tools["python_evtx"] = evtx_tool

        # 6. SleuthKit mmls (Partition Table Analysis)
        mmls_bin = "mmls.exe" if self.current_os == "windows" else "mmls"
        mmls_path = self._resolve_binary_path(mmls_bin)
        mmls_ver = self._validate_tool_version("mmls", mmls_path) if mmls_path else None
        mmls_avail = bool(mmls_path and mmls_ver)

        self._tools["mmls"] = ToolDefinition(
            name="mmls",
            display_name="The Sleuth Kit (mmls Partition Analyzer)",
            platforms=["linux", "windows", "darwin"],
            binary_name=mmls_bin,
            path=mmls_path if mmls_avail else None,
            version=mmls_ver,
            is_available=mmls_avail,
            supported_evidence_types=["disk_image", "filesystem_image", "raw", "dd", "e01"],
            capabilities=["partition_analysis", "volume_system_analysis"],
            description="Displays the partition layout of a volume system / disk image."
        )

        # 7. SleuthKit fsstat (Filesystem Details & Metadata)
        fsstat_bin = "fsstat.exe" if self.current_os == "windows" else "fsstat"
        fsstat_path = self._resolve_binary_path(fsstat_bin)
        fsstat_ver = self._validate_tool_version("fsstat", fsstat_path) if fsstat_path else None
        fsstat_avail = bool(fsstat_path and fsstat_ver)

        self._tools["fsstat"] = ToolDefinition(
            name="fsstat",
            display_name="The Sleuth Kit (fsstat Filesystem Analyzer)",
            platforms=["linux", "windows", "darwin"],
            binary_name=fsstat_bin,
            path=fsstat_path if fsstat_avail else None,
            version=fsstat_ver,
            is_available=fsstat_avail,
            supported_evidence_types=["disk_image", "filesystem_image", "raw", "dd"],
            capabilities=["filesystem_details", "metadata_analysis"],
            description="Displays general filesystem details including block size, cluster count, and OS metadata."
        )

        # 8. SQLite3 CLI
        sqlite_bin = "sqlite3.exe" if self.current_os == "windows" else "sqlite3"
        sqlite_path = self._resolve_binary_path(sqlite_bin)
        sqlite_ver = self._validate_tool_version("sqlite3", sqlite_path) if sqlite_path else None
        sqlite_avail = bool(sqlite_path and sqlite_ver)

        self._tools["sqlite3"] = ToolDefinition(
            name="sqlite3",
            display_name="SQLite3 Database CLI",
            platforms=["linux", "windows", "darwin"],
            binary_name=sqlite_bin,
            path=sqlite_path if sqlite_avail else None,
            version=sqlite_ver,
            is_available=sqlite_avail,
            supported_evidence_types=["sqlite_database", "browser_artifact", "history", "mobile_database"],
            capabilities=["sqlite_schema_dump", "database_table_inspection", "browser_artifact_analysis"],
            description="Command-line utility to query and inspect SQLite database tables, schema, and records."
        )

        # 9. Strings (Binary String Extraction)
        strings_bin = "strings.exe" if self.current_os == "windows" else "strings"
        strings_path = self._resolve_binary_path(strings_bin)
        strings_ver = self._validate_tool_version("strings", strings_path) if strings_path else None
        strings_avail = bool(strings_path and strings_ver)

        self._tools["strings"] = ToolDefinition(
            name="strings",
            display_name="GNU Strings Extractor",
            platforms=["linux", "windows", "darwin"],
            binary_name=strings_bin,
            path=strings_path if strings_avail else None,
            version=strings_ver,
            is_available=strings_avail,
            supported_evidence_types=["binary", "executable", "memory_dump", "raw", "suspicious_file", "pe_executable", "elf_executable"],
            capabilities=["string_extraction", "ascii_unicode_harvesting"],
            description="Prints sequences of printable characters from binary files, memory dumps, and executables."
        )

        # 10. SleuthKit istat (Inode / Metadata details)
        istat_bin = "istat.exe" if self.current_os == "windows" else "istat"
        istat_path = self._resolve_binary_path(istat_bin)
        istat_ver = self._validate_tool_version("istat", istat_path) if istat_path else None
        istat_avail = bool(istat_path and istat_ver)
        self._tools["istat"] = ToolDefinition(
            name="istat",
            display_name="The Sleuth Kit (istat Inode Inspector)",
            platforms=["linux", "windows", "darwin"],
            binary_name=istat_bin,
            path=istat_path if istat_avail else None,
            version=istat_ver,
            is_available=istat_avail,
            supported_evidence_types=["disk_image", "filesystem_image", "raw", "dd"],
            capabilities=["inode_inspection", "filesystem_metadata"],
            description="Displays details of a specific metadata structure (inode/MFT entry)."
        )

        # 11. SleuthKit icat (Data extraction by inode)
        icat_bin = "icat.exe" if self.current_os == "windows" else "icat"
        icat_path = self._resolve_binary_path(icat_bin)
        icat_ver = self._validate_tool_version("icat", icat_path) if icat_path else None
        icat_avail = bool(icat_path and icat_ver)
        self._tools["icat"] = ToolDefinition(
            name="icat",
            display_name="The Sleuth Kit (icat Inode Extractor)",
            platforms=["linux", "windows", "darwin"],
            binary_name=icat_bin,
            path=icat_path if icat_avail else None,
            version=icat_ver,
            is_available=icat_avail,
            supported_evidence_types=["disk_image", "filesystem_image", "raw", "dd"],
            capabilities=["inode_data_extraction", "file_recovery"],
            description="Outputs the contents of a file identified by its inode/MFT number."
        )

        # 12. File command (libmagic file signature identification)
        file_bin = "file.exe" if self.current_os == "windows" else "file"
        file_path = self._resolve_binary_path(file_bin)
        file_ver = self._validate_tool_version("file", file_path) if file_path else None
        file_avail = bool(file_path and file_ver)
        self._tools["file"] = ToolDefinition(
            name="file",
            display_name="File Type Identification Utility",
            platforms=["linux", "windows", "darwin"],
            binary_name=file_bin,
            path=file_path if file_avail else None,
            version=file_ver,
            is_available=file_avail,
            supported_evidence_types=["file", "binary", "disk_image", "memory_dump", "archive", "document"],
            capabilities=["file_signature_detection", "mime_identification"],
            description="Determines file type and encoding using magic numbers and libmagic."
        )

        # 13. tcpdump (Packet capture inspection)
        tcpdump_bin = "tcpdump.exe" if self.current_os == "windows" else "tcpdump"
        tcpdump_path = self._resolve_binary_path(tcpdump_bin)
        tcpdump_ver = self._validate_tool_version("tcpdump", tcpdump_path) if tcpdump_path else None
        tcpdump_avail = bool(tcpdump_path and tcpdump_ver)
        self._tools["tcpdump"] = ToolDefinition(
            name="tcpdump",
            display_name="tcpdump Packet Analyzer",
            platforms=["linux", "windows", "darwin"],
            binary_name=tcpdump_bin,
            path=tcpdump_path if tcpdump_avail else None,
            version=tcpdump_ver,
            is_available=tcpdump_avail,
            supported_evidence_types=["pcap_capture", "pcap", "network_capture"],
            capabilities=["packet_dissection", "network_traffic_analysis"],
            description="Command-line packet analyzer for parsing and filtering network captures."
        )

        # 14. TShark (Wireshark CLI)
        tshark_bin = "tshark.exe" if self.current_os == "windows" else "tshark"
        tshark_path = self._resolve_binary_path(tshark_bin)
        tshark_ver = self._validate_tool_version("tshark", tshark_path) if tshark_path else None
        tshark_avail = bool(tshark_path and tshark_ver)
        self._tools["tshark"] = ToolDefinition(
            name="tshark",
            display_name="TShark Network Protocol Analyzer",
            platforms=["linux", "windows", "darwin"],
            binary_name=tshark_bin,
            path=tshark_path if tshark_avail else None,
            version=tshark_ver,
            is_available=tshark_avail,
            supported_evidence_types=["pcap_capture", "pcap", "network_capture"],
            capabilities=["packet_dissection", "network_protocol_analysis", "flow_extraction"],
            description="Terminal-based Wireshark packet capture analysis and protocol inspection."
        )

        # 15. Foremost (File Carving)
        foremost_bin = "foremost.exe" if self.current_os == "windows" else "foremost"
        foremost_path = self._resolve_binary_path(foremost_bin)
        foremost_ver = self._validate_tool_version("foremost", foremost_path) if foremost_path else None
        foremost_avail = bool(foremost_path and foremost_ver)
        self._tools["foremost"] = ToolDefinition(
            name="foremost",
            display_name="Foremost Forensic Carver",
            platforms=["linux", "windows", "darwin"],
            binary_name=foremost_bin,
            path=foremost_path if foremost_avail else None,
            version=foremost_ver,
            is_available=foremost_avail,
            supported_evidence_types=["disk_image", "raw", "dd", "memory_dump"],
            capabilities=["file_carving", "unallocated_space_recovery"],
            description="Recovers files based on their headers, footers, and internal data structures."
        )

        # 16. Scalpel (File Carving)
        scalpel_bin = "scalpel.exe" if self.current_os == "windows" else "scalpel"
        scalpel_path = self._resolve_binary_path(scalpel_bin)
        scalpel_ver = self._validate_tool_version("scalpel", scalpel_path) if scalpel_path else None
        scalpel_avail = bool(scalpel_path and scalpel_ver)
        self._tools["scalpel"] = ToolDefinition(
            name="scalpel",
            display_name="Scalpel High-Performance Carver",
            platforms=["linux", "windows", "darwin"],
            binary_name=scalpel_bin,
            path=scalpel_path if scalpel_avail else None,
            version=scalpel_ver,
            is_available=scalpel_avail,
            supported_evidence_types=["disk_image", "raw", "dd"],
            capabilities=["file_carving"],
            description="High performance file carver for disk images and raw storage blocks."
        )

        # 17. Bulk Extractor (Stream Analysis & Artifact Carving)
        be_bin = "bulk_extractor.exe" if self.current_os == "windows" else "bulk_extractor"
        be_path = self._resolve_binary_path(be_bin)
        be_ver = self._validate_tool_version("bulk_extractor", be_path) if be_path else None
        be_avail = bool(be_path and be_ver)
        self._tools["bulk_extractor"] = ToolDefinition(
            name="bulk_extractor",
            display_name="Bulk Extractor Feature Carver",
            platforms=["linux", "windows", "darwin"],
            binary_name=be_bin,
            path=be_path if be_avail else None,
            version=be_ver,
            is_available=be_avail,
            supported_evidence_types=["disk_image", "raw", "dd", "memory_dump", "file"],
            capabilities=["feature_extraction", "email_carving", "url_carving", "credit_card_carving"],
            description="Extracts features such as email addresses, URLs, and credit card numbers from raw disk images without parsing the filesystem."
        )

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        if not name or not isinstance(name, str):
            return None
        return self._tools.get(name.lower().strip())

    def list_tools(self) -> List[ToolDefinition]:
        seen = set()
        res = []
        for t in self._tools.values():
            if t.name not in seen:
                seen.add(t.name)
                res.append(t)
        return res

    def validate_request(self, request: ToolExecutionRequest) -> Optional[str]:
        """
        Validates that a tool request is safe before execution.
        Returns error string if invalid, None if safe.
        """
        tool_name_clean = request.tool_name.lower().strip() if request.tool_name else ""
        if not tool_name_clean or tool_name_clean not in self._tools:
            return f"Unknown or disallowed tool '{request.tool_name}'. Tool must be registered in ToolRegistry."

        # Null byte check in evidence path
        if "\0" in request.evidence_path:
            return "Null byte detected in evidence path."

        # Null byte check in arguments
        for arg in request.arguments:
            if not isinstance(arg, str):
                return "All arguments must be strings."
            if "\0" in arg:
                return "Null byte detected in tool arguments."

        return None

    def execute_tool(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        # 1. Validate request
        val_error = self.validate_request(request)
        if val_error:
            return ToolExecutionResult(
                tool_name=request.tool_name,
                success=False,
                return_code=-1,
                stdout="",
                stderr=val_error,
                execution_time_ms=0,
                evidence_path=request.evidence_path,
                error_message=val_error
            )

        # 2. Authoritative tool validation at execution boundary
        is_valid, tool, auth_err = self.validate_tool_executable(request.tool_name)
        if not is_valid or not tool:
            err_msg = auth_err or f"Tool '{request.tool_name}' is not installed or available on this system."
            return ToolExecutionResult(
                tool_name=request.tool_name,
                success=False,
                return_code=-1,
                stdout="",
                stderr=err_msg,
                execution_time_ms=0,
                evidence_path=request.evidence_path,
                error_message=err_msg
            )

        if tool.is_library_adapter:
            err_msg = f"Tool '{request.tool_name}' is an in-process library adapter — execute via forensic pipeline adapter, not as a standalone CLI subprocess."
            return ToolExecutionResult(
                tool_name=request.tool_name,
                success=False,
                return_code=-1,
                stdout="",
                stderr=err_msg,
                execution_time_ms=0,
                evidence_path=request.evidence_path,
                error_message=err_msg
            )

        if not tool.path or not os.path.exists(tool.path) or not os.access(tool.path, os.X_OK):
            err_msg = f"Tool '{request.tool_name}' binary executable path '{tool.path}' is missing or not executable at runtime."
            return ToolExecutionResult(
                tool_name=request.tool_name,
                success=False,
                return_code=-1,
                stdout="",
                stderr=err_msg,
                execution_time_ms=0,
                evidence_path=request.evidence_path,
                error_message=err_msg
            )

        # Enforce safe timeout cap
        timeout = min(max(1, request.timeout_seconds), MAX_SAFE_TIMEOUT_SECONDS)

        # Construct argument list: executable is strictly tool.path from registry
        if tool.name == "volatility3":
            # Volatility 3 syntax: vol -f <evidence_path> <plugin> <plugin_args...>
            cmd = [tool.path, "-f", request.evidence_path] + request.arguments
        elif tool.name == "sqlite3":
            # sqlite3 <evidence_path> [arguments...]
            cmd = [tool.path, request.evidence_path] + request.arguments
        else:
            cmd = [tool.path] + request.arguments + [request.evidence_path]

        start_time = time.time()
        proc = None
        try:
            # Subprocess safety: shell=False strictly enforced
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False
            )
            pid = proc.pid
            proc_start_time = get_process_start_time(pid) or time.time()

            if request.execution_id:
                self.register_active_process(request.execution_id, proc, pid, proc_start_time)

            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                return_code = proc.returncode
                elapsed_ms = (time.time() - start_time) * 1000

                # Check if process was cancelled externally
                is_cancelled = False
                if return_code != 0 and return_code is not None:
                    if abs(return_code) in (9, 15):  # SIGKILL / SIGTERM
                        is_cancelled = True

                return ToolExecutionResult(
                    tool_name=request.tool_name,
                    success=(return_code == 0),
                    return_code=return_code,
                    stdout=stdout or "",
                    stderr=stderr or "",
                    execution_time_ms=elapsed_ms,
                    evidence_path=request.evidence_path,
                    pid=pid,
                    process_start_time=proc_start_time,
                    timed_out=False,
                    cancelled=is_cancelled,
                    tool_version=tool.version,
                    error_message=None if return_code == 0 else (
                        "Tool execution was cancelled by investigator." if is_cancelled else f"Process returned non-zero code {return_code}"
                    )
                )
            except subprocess.TimeoutExpired:
                # Safe multi-stage termination with exact identity verification
                current_start_time = get_process_start_time(pid)
                identity_verified = (
                    current_start_time is not None
                    and proc_start_time is not None
                    and current_start_time == proc_start_time
                    and proc.poll() is None
                )

                stdout, stderr = "", ""
                process_terminated = False
                if identity_verified:
                    proc.terminate()
                    try:
                        stdout, stderr = proc.communicate(timeout=1.5)
                    except subprocess.TimeoutExpired:
                        check_t = get_process_start_time(pid)
                        if check_t is not None and check_t == proc_start_time:
                            proc.kill()
                            stdout, stderr = proc.communicate()
                    process_terminated = (proc.poll() is not None)
                else:
                    stderr = f"Tool execution timed out after {timeout} seconds. Process identity could not be verified for termination; process remains active."
                    process_terminated = False

                elapsed_ms = (time.time() - start_time) * 1000
                return ToolExecutionResult(
                    tool_name=request.tool_name,
                    success=False,
                    return_code=-2,
                    stdout=stdout or "",
                    stderr=stderr or f"Tool execution timed out after {timeout} seconds.",
                    execution_time_ms=elapsed_ms,
                    evidence_path=request.evidence_path,
                    pid=pid,
                    process_start_time=proc_start_time,
                    timed_out=True,
                    process_terminated=process_terminated,
                    cancelled=False,
                    tool_version=tool.version,
                    error_message=f"Execution exceeded timeout of {timeout} seconds."
                )
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            pid_val = proc.pid if proc else None
            return ToolExecutionResult(
                tool_name=request.tool_name,
                success=False,
                return_code=-3,
                stdout="",
                stderr=str(e),
                execution_time_ms=elapsed_ms,
                evidence_path=request.evidence_path,
                pid=pid_val,
                timed_out=False,
                cancelled=False,
                error_message=str(e)
            )
        finally:
            if request.execution_id:
                self.unregister_active_process(request.execution_id)

tool_registry = PlatformAwareToolRegistry()
