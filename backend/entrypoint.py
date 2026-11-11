import os
import sys
import multiprocessing
from pathlib import Path

# Ensure application root directory is available in sys.path
if getattr(sys, "frozen", False):
    root_dir = Path(getattr(sys, "_MEIPASS", sys.executable))
    exe_dir = Path(sys.executable).parent
    if str(exe_dir) not in sys.path:
        sys.path.insert(0, str(exe_dir))
    # In PyInstaller 6+ onedir mode, modules can be in _internal
    internal_dir = exe_dir / "_internal"
    if internal_dir.exists() and str(internal_dir) not in sys.path:
        sys.path.insert(0, str(internal_dir))
else:
    root_dir = Path(__file__).resolve().parent.parent

if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

def main():
    try:
        import uvicorn
        from backend.app.main import app
        from backend.app.core.config import get_backend_port

        port = get_backend_port()
        is_frozen = getattr(sys, "frozen", False)
        if is_frozen:
            uvicorn.run(app, host="127.0.0.1", port=port, reload=False, log_level="info")
        else:
            uvicorn.run("backend.app.main:app", host="127.0.0.1", port=port, reload=True)
    except Exception as exc:
        import traceback
        traceback.print_exc(file=sys.stderr)
        try:
            sys.stderr.flush()
        except Exception:
            pass
        try:
            with open("backend_crash.log", "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

