import os
import sys
import multiprocessing
from pathlib import Path

# Ensure application root directory is available in sys.path
if getattr(sys, "frozen", False):
    root_dir = Path(getattr(sys, "_MEIPASS", sys.executable))
    # In PyInstaller 6+ onedir mode, modules can be in _internal
    internal_dir = Path(sys.executable).parent / "_internal"
    if internal_dir.exists() and str(internal_dir) not in sys.path:
        sys.path.insert(0, str(internal_dir))
else:
    root_dir = Path(__file__).resolve().parent.parent

if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import uvicorn
from backend.app.main import app
from backend.app.core.config import get_backend_port

def main():
    try:
        port = get_backend_port()
        is_frozen = getattr(sys, "frozen", False)
        if is_frozen:
            uvicorn.run(app, host="127.0.0.1", port=port, reload=False, log_level="info")
        else:
            uvicorn.run("backend.app.main:app", host="127.0.0.1", port=port, reload=True)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

