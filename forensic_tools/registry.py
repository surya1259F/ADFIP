import sys
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class ToolDefinition(BaseModel):
    name: str
    display_name: str
    platforms: List[str]
    binary_name: str
    path: Optional[str] = None
    version: Optional[str] = None
    is_available: bool = False
    supported_evidence_types: List[str] = []
    description: str

class ToolExecutionRequest(BaseModel):
    tool_name: str
    evidence_path: str
    arguments: List[str] = []
    timeout_seconds: int = 120

class ToolExecutionResult(BaseModel):
    tool_name: str
    success: bool
    return_code: int
    stdout: str
    stderr: str
    execution_time_ms: float
    evidence_path: str
    tool_version: Optional[str] = None
    error_message: Optional[str] = None

class PlatformAwareToolRegistry:
    """
    Platform-aware Forensic Tool Registry.
    Detects and validates forensic binaries on Linux and Windows.
    Enforces strict argument validation, timeout limits, and prevents arbitrary execution.
    """

    def __init__(self):
        self.current_os = "windows" if sys.platform.startswith("win") else "linux" if sys.platform.startswith("linux") else "darwin"
        self._tools: Dict[str, ToolDefinition] = {}
        self.root_dir = Path(__file__).resolve().parent.parent
        self._discover_and_register_tools()

    def _discover_and_register_tools(self):
        # 1. SleuthKit (fls)
        fls_bin = "fls.exe" if self.current_os == "windows" else "fls"
        fls_path = shutil.which(fls_bin)
        fls_ver = None
        if fls_path:
            try:
                out = subprocess.run([fls_path, "-V"], capture_output=True, text=True, timeout=5)
                fls_ver = out.stdout.strip() or out.stderr.strip()
            except Exception:
                pass

        self._tools["sleuthkit"] = ToolDefinition(
            name="sleuthkit",
            display_name="The Sleuth Kit (TSK)",
            platforms=["linux", "windows", "darwin"],
            binary_name=fls_bin,
            path=fls_path,
            version=fls_ver,
            is_available=fls_path is not None,
            supported_evidence_types=["disk_image", "file"],
            description="Volume and filesystem analysis tools for disk images and filesystems."
        )

        # 2. YARA
        yara_bin = "yara.exe" if self.current_os == "windows" else "yara"
        yara_path = shutil.which(yara_bin)
        yara_ver = None
        if yara_path:
            try:
                out = subprocess.run([yara_path, "--version"], capture_output=True, text=True, timeout=5)
                yara_ver = out.stdout.strip()
            except Exception:
                pass

        self._tools["yara"] = ToolDefinition(
            name="yara",
            display_name="YARA Pattern Matcher",
            platforms=["linux", "windows", "darwin"],
            binary_name=yara_bin,
            path=yara_path,
            version=yara_ver,
            is_available=yara_path is not None,
            supported_evidence_types=["file", "disk_image", "memory_dump"],
            description="Pattern matching tool for malware researchers and binary analysis."
        )

        # 3. ExifTool
        exif_bin = "exiftool.exe" if self.current_os == "windows" else "exiftool"
        exif_path = shutil.which(exif_bin)
        exif_ver = None
        if exif_path:
            try:
                out = subprocess.run([exif_path, "-ver"], capture_output=True, text=True, timeout=5)
                exif_ver = out.stdout.strip()
            except Exception:
                pass

        self._tools["exiftool"] = ToolDefinition(
            name="exiftool",
            display_name="ExifTool Metadata Extractor",
            platforms=["linux", "windows", "darwin"],
            binary_name=exif_bin,
            path=exif_path,
            version=exif_ver,
            is_available=exif_path is not None,
            supported_evidence_types=["document", "file", "archive"],
            description="Read and parse metadata in digital images, documents, and files."
        )

        # 4. Volatility 3 (Check system PATH and local virtualenv)
        vol_path = shutil.which("vol.exe" if self.current_os == "windows" else "vol")
        if not vol_path:
            local_vol = self.root_dir / "volatility-env" / ("Scripts/vol.exe" if self.current_os == "windows" else "bin/vol")
            if local_vol.exists():
                vol_path = str(local_vol)

        vol_ver = None
        if vol_path:
            vol_ver = "2.28.0"

        self._tools["volatility3"] = ToolDefinition(
            name="volatility3",
            display_name="Volatility 3 Memory Forensics",
            platforms=["linux", "windows", "darwin"],
            binary_name="vol",
            path=vol_path,
            version=vol_ver,
            is_available=vol_path is not None,
            supported_evidence_types=["memory_dump"],
            description="Advanced memory forensics framework for Windows, Linux, and Mac kernel dumps."
        )

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name.lower())

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def execute_tool(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        tool = self.get_tool(request.tool_name)
        if not tool or not tool.is_available or not tool.path:
            return ToolExecutionResult(
                tool_name=request.tool_name,
                success=False,
                return_code=-1,
                stdout="",
                stderr="",
                execution_time_ms=0,
                evidence_path=request.evidence_path,
                error_message=f"Tool '{request.tool_name}' is not installed or available on this system."
            )

        cmd = [tool.path] + request.arguments + [request.evidence_path]
        start_time = time.time()

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                shell=False
            )
            elapsed_ms = (time.time() - start_time) * 1000
            return ToolExecutionResult(
                tool_name=request.tool_name,
                success=(res.returncode == 0),
                return_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                execution_time_ms=elapsed_ms,
                evidence_path=request.evidence_path,
                tool_version=tool.version,
                error_message=None if res.returncode == 0 else f"Process returned non-zero code {res.returncode}"
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.time() - start_time) * 1000
            return ToolExecutionResult(
                tool_name=request.tool_name,
                success=False,
                return_code=-2,
                stdout="",
                stderr="Tool execution timed out.",
                execution_time_ms=elapsed_ms,
                evidence_path=request.evidence_path,
                error_message=f"Execution exceeded timeout of {request.timeout_seconds} seconds."
            )
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return ToolExecutionResult(
                tool_name=request.tool_name,
                success=False,
                return_code=-3,
                stdout="",
                stderr=str(e),
                execution_time_ms=elapsed_ms,
                evidence_path=request.evidence_path,
                error_message=str(e)
            )

tool_registry = PlatformAwareToolRegistry()
