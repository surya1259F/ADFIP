#!/usr/bin/env python3
import sys
import os
import shutil
import platform
import subprocess
import json
from pathlib import Path

def is_mock_script(path_str: str) -> bool:
    try:
        p = Path(path_str)
        if "tests/mocks" in str(p) or "tests/fixtures" in str(p):
            return True
        with open(p, "rb") as f:
            first_bytes = f.read(256)
            if b"python" in first_bytes and (b"Synthetic_Test" in first_bytes or b"ADFIR_Synthetic" in first_bytes or b"ADFIR" in first_bytes):
                return True
    except Exception:
        pass
    return False

def resolve_tool_path(tool_name: str, root_dir: Path, current_os: str) -> tuple[bool, str | None, str | None]:
    """
    Resolves real executable path and validated version for a forensic tool.
    Strictly checks system PATH and configured tool directories.
    Never accepts mock or demonstration scripts.
    """
    exe_name = f"{tool_name}.exe" if current_os == "windows" else tool_name
    
    # 1. System PATH
    found_path = shutil.which(exe_name)
    
    # 2. Configured production tools/bin
    if not found_path:
        local_bin = root_dir / "tools" / "bin" / exe_name
        if local_bin.exists() and os.access(local_bin, os.X_OK):
            found_path = str(local_bin)

    # 3. Virtual environment bin
    if not found_path:
        venv_bin = root_dir / "backend" / ".venv" / ("Scripts" if current_os == "windows" else "bin") / exe_name
        if venv_bin.exists() and os.access(venv_bin, os.X_OK):
            found_path = str(venv_bin)

    if not found_path or is_mock_script(found_path):
        return False, None, None

    # Safe tool-specific version check
    version = None
    try:
        if tool_name in ["fls", "sleuthkit"]:
            out = subprocess.run([found_path, "-V"], capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                raw = (out.stdout or out.stderr).strip().splitlines()
                version = raw[0] if raw else None
        elif tool_name in ["yara"]:
            out = subprocess.run([found_path, "--version"], capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                version = out.stdout.strip()
        elif tool_name in ["exiftool"]:
            out = subprocess.run([found_path, "-ver"], capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                version = out.stdout.strip()
        elif tool_name in ["vol", "volatility3"]:
            out = subprocess.run([found_path, "-h"], capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                raw = (out.stdout or out.stderr).strip().splitlines()
                version = raw[0] if raw else None
    except Exception:
        version = None

    if not version:
        return False, None, None

    return True, found_path, version

def main():
    root_dir = Path(__file__).resolve().parent.parent
    os_sys = platform.system().lower()
    os_arch = platform.machine()

    tools_to_check = {
        "sleuthkit": "fls",
        "volatility3": "vol",
        "yara": "yara",
        "exiftool": "exiftool"
    }

    result = {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "architecture": os_arch
        },
        "tools": {}
    }

    all_available = True
    for logical_name, binary_name in tools_to_check.items():
        avail, path, ver = resolve_tool_path(binary_name, root_dir, os_sys)
        result["tools"][logical_name] = {
            "available": avail,
            "executable": path,
            "version": ver
        }
        if not avail:
            all_available = False

    print(json.dumps(result, indent=2))
    sys.exit(0 if all_available else 1)

if __name__ == "__main__":
    main()
