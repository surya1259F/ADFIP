import logging
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.core.database import engine, Base
from backend.app.api.endpoints import health, system, investigations, audit, tools

# Configure logging cleanly without adding duplicate handlers on reload/tests
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ADFIR_API")

import os
import hmac
from backend.app.core.config import settings, get_backend_port


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan: runs startup logic (directory creation, DB migrations,
    RevokedToken table bootstrap) only when the server actually starts,
    not at import time.
    """
    # Ensure required workspace data directories exist
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    settings.CASES_DIR.mkdir(parents=True, exist_ok=True)
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (settings.DATA_DIR / "avatars").mkdir(parents=True, exist_ok=True)

    # Run Alembic migrations
    from backend.app.core.migrations import run_db_migrations
    run_db_migrations(engine)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    # Ensure RevokedToken, OAuth tables, and required user columns exist
    try:
        from backend.app.models.models import RevokedToken, UserExternalIdentity, OAuthState, OAuthExchangeCode
        RevokedToken.__table__.create(bind=engine, checkfirst=True)
        UserExternalIdentity.__table__.create(bind=engine, checkfirst=True)
        OAuthState.__table__.create(bind=engine, checkfirst=True)
        OAuthExchangeCode.__table__.create(bind=engine, checkfirst=True)

        from sqlalchemy import text
        with engine.connect() as conn:
            user_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)"))]
            if "avatar_url" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR"))
                conn.commit()
    except Exception as exc:
        logger.warning(f"Could not ensure auth tables/columns: {exc}")


    yield
    # (shutdown logic goes here if needed in the future)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-Assisted Digital Forensic Investigation Platform (ADFIR) Desktop Backend",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    lifespan=lifespan,
)


def get_allowed_origins() -> list:
    custom_origins = os.getenv("ADFIR_ALLOWED_ORIGINS")
    if custom_origins:
        return [o.strip() for o in custom_origins.split(",") if o.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
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
    allow_headers=["Authorization", "Content-Type", "X-ADFIR-Bootstrap-Secret", "Accept", "X-Request-ID", "X-Correlation-ID"],
    expose_headers=["X-Request-ID", "X-Correlation-ID"],
)

# Request Correlation ID Middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Correlation-ID"] = req_id
    return response

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

# Global Security Exception Handler: Never expose raw stack traces to users, ensure CORS headers on errors
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    logger.warning(f"[Request-ID: {req_id}] Validation error on {request.method} {request.url.path}: {str(exc)}")
    origin = request.headers.get("origin")
    resp_headers = {
        "X-Request-ID": req_id,
        "X-Correlation-ID": req_id,
    }
    if origin and (origin in get_allowed_origins()):
        resp_headers["Access-Control-Allow-Origin"] = origin
        resp_headers["Access-Control-Allow-Credentials"] = "true"
        resp_headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        resp_headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-ADFIR-Bootstrap-Secret, Accept, X-Request-ID, X-Correlation-ID"
        resp_headers["Access-Control-Expose-Headers"] = "X-Request-ID, X-Correlation-ID"
    safe_errors = []
    for err in exc.errors():
        safe_err = dict(err)
        if "input" in safe_err and isinstance(safe_err["input"], (bytes, bytearray)):
            safe_err["input"] = f"<binary data: {len(safe_err['input'])} bytes>"
        safe_errors.append(safe_err)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": safe_errors, "request_id": req_id},
        headers=resp_headers
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    logger.error(f"[Request-ID: {req_id}] Internal Exception on {request.method} {request.url.path}: {str(exc)}", exc_info=True)
    origin = request.headers.get("origin")
    resp_headers = {
        "X-Request-ID": req_id,
        "X-Correlation-ID": req_id,
    }
    if origin and (origin in get_allowed_origins()):
        resp_headers["Access-Control-Allow-Origin"] = origin
        resp_headers["Access-Control-Allow-Credentials"] = "true"
        resp_headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        resp_headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-ADFIR-Bootstrap-Secret, Accept, X-Request-ID, X-Correlation-ID"
        resp_headers["Access-Control-Expose-Headers"] = "X-Request-ID, X-Correlation-ID"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal error occurred during forensic processing. Please contact your system administrator.",
            "request_id": req_id,
            "path": request.url.path,
        },
        headers=resp_headers
    )


# Legacy Compatibility Routers for /api prefix (pure compatibility shims for legacy clients and root test suites)
app.include_router(health.router, prefix="/api", tags=["Health"], include_in_schema=False)
app.include_router(investigations.router, prefix="/api/cases", tags=["Legacy Cases"], include_in_schema=False)
app.include_router(investigations.router, prefix="/api/investigations", tags=["Legacy Investigations"], include_in_schema=False)
app.include_router(system.router, prefix="/api", tags=["System"], include_in_schema=False)
app.include_router(audit.router, prefix="/api", tags=["Audit"], include_in_schema=False)
app.include_router(tools.router, prefix="/api", tags=["Tools"], include_in_schema=False)

# Canonical API Router: authoritative /api/v1 prefix and compatibility /api alias (excluded from schema to avoid duplicate operation IDs)
from backend.app.api.v1.router import api_router
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_router, prefix="/api", include_in_schema=False)

# Root level health routes for direct health verification
app.include_router(health.router, tags=["Health"], include_in_schema=False)


@app.get("/")
def root():
    return {
        "status": "ok",
        "application": "ADFIR",
        "version": settings.VERSION,
        "docs_url": "/api/docs"
    }


from fastapi.openapi.docs import get_swagger_ui_html

@app.get("/docs", include_in_schema=False)
async def swagger_docs_alias():
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title=f"{settings.PROJECT_NAME} - Swagger UI",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=get_backend_port(), reload=True)
