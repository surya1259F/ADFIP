import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.core.database import engine
from backend.app.api.endpoints import investigations, audit, tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ADFIR_API")

# Initialize database schema via Alembic migrations
from backend.app.core.migrations import run_db_migrations
run_db_migrations(engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-Assisted Digital Forensic Investigation Platform (ADFIR) Desktop Backend",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs"
)

import hmac
import os
from backend.app.core.config import get_backend_port

def get_allowed_origins() -> list:
    custom_origins = os.getenv("ADFIR_ALLOWED_ORIGINS")
    if custom_origins:
        return [o.strip() for o in custom_origins.split(",") if o.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ]

# Hardened Cross-Origin Resource Sharing for Desktop/Tauri
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-ADFIR-Bootstrap-Secret", "Accept"],
)

# Desktop Bootstrap Secret Trust Boundary Middleware
@app.middleware("http")
async def desktop_bootstrap_middleware(request: Request, call_next):
    secret = os.getenv("ADFIR_INTERNAL_SECRET") or settings.ADFIR_INTERNAL_SECRET
    if secret and secret.strip():
        if request.method != "OPTIONS":
            path = request.url.path.rstrip("/")
            is_health = path in ["/health", "/api/health", "/api/v1/health", "/api/v1/system/health"]
            if not is_health:
                provided_header = request.headers.get("X-ADFIR-Bootstrap-Secret")
                if not provided_header or not hmac.compare_digest(provided_header.encode("utf-8"), secret.encode("utf-8")):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "Forbidden: Invalid or missing desktop bootstrap secret."}
                    )
    response = await call_next(request)
    return response

# Global Security Exception Handler: Never expose raw stack traces to users
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Internal Exception on {request.method} {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred during forensic processing. Please contact your system administrator."}
    )

@app.on_event("startup")
def startup_reconciliation():
    from backend.app.core.database import SessionLocal
    try:
        with SessionLocal() as db:
            investigations.orchestrator_service.reconcile_stale_executions(db)
    except Exception as e:
        logger.warning(f"Startup reconciliation warning: {e}")

# Legacy compatibility router for older investigation endpoints.
app.include_router(investigations.router, prefix="/api/investigations", tags=["Investigations"])
app.include_router(audit.router, prefix="/api", tags=["Audit"])
app.include_router(tools.router, prefix="/api", tags=["Tools"])

from backend.app.api.v1.router import api_router

# Include API v1 and compatibility routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_router, prefix="/api")



@app.get("/")
def root():
    return {
        "status": "ok",
        "application": "ADFIR",
        "version": settings.VERSION,
        "docs_url": "/api/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=get_backend_port(), reload=True)
