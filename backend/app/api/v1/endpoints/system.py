from fastapi import APIRouter
import shutil
from pathlib import Path
from backend.app.core.config import settings

router = APIRouter()

@router.get("/health")
def health_check():
    return {"status": "online", "project": settings.PROJECT_NAME, "version": settings.VERSION}

@router.get("/info")
def system_info():
    fls_path = shutil.which("fls")
    yara_path = shutil.which("yara")
    vol_path = str(settings.VOLATILITY_CLI) if Path(settings.VOLATILITY_CLI).exists() else None

    return {
        "app_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "OPERATIONAL",
        "forensic_tools": {
            "sleuthkit": {"available": fls_path is not None, "path": fls_path},
            "yara": {"available": yara_path is not None, "path": yara_path},
            "volatility3": {"available": vol_path is not None, "path": vol_path},
        },
        "llm_providers_available": ["gemini", "local_llm", "openrouter"]
    }
