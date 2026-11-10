from fastapi import APIRouter, Request, HTTPException, status, Header
import shutil
import os
import sys
import hmac
import signal
import asyncio
from typing import Optional
from pathlib import Path
from backend.app.core.config import settings

router = APIRouter()

@router.get("/health")
def health_check():
    return {"status": "online", "project": settings.PROJECT_NAME, "version": settings.VERSION}

@router.get("/system/health")
def health_check_alias():
    return health_check()

@router.get("/info")
@router.get("/system/info")
def system_info():
    fls_bin = "fls.exe" if sys.platform.startswith("win") else "fls"
    yara_bin = "yara.exe" if sys.platform.startswith("win") else "yara"
    fls_path = shutil.which(fls_bin)
    yara_path = shutil.which(yara_bin)
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

@router.post("/shutdown")
@router.post("/system/shutdown")
async def shutdown_backend(
    request: Request,
    x_adfir_bootstrap_secret: Optional[str] = Header(None, alias="X-ADFIR-Bootstrap-Secret"),
    x_adfip_bootstrap_secret: Optional[str] = Header(None, alias="X-ADFIP-Bootstrap-Secret")
):
    secret = os.getenv("ADFIP_INTERNAL_SECRET") or os.getenv("ADFIR_INTERNAL_SECRET") or settings.ADFIP_INTERNAL_SECRET or settings.ADFIR_INTERNAL_SECRET
    if not secret or not secret.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shutdown endpoint is only available when desktop bootstrap secret is configured."
        )

    provided_secret = x_adfip_bootstrap_secret or x_adfir_bootstrap_secret
    if not provided_secret or not hmac.compare_digest(provided_secret.encode("utf-8"), secret.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing desktop bootstrap secret."
        )

    async def delayed_shutdown():
        await asyncio.sleep(0.3)
        if not os.getenv("ADFIP_TESTING") and not os.getenv("PYTEST_CURRENT_TEST"):
            os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(delayed_shutdown())

    return {
        "status": "SHUTTING_DOWN",
        "message": "Backend shutdown initiated cleanly for this process.",
        "pid": os.getpid()
    }
