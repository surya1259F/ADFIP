import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.core.database import engine, Base
from backend.app.api.endpoints import health, system, investigations

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ADFIR_API")

# Initialize database schema
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-Assisted Digital Forensic Investigation Platform (ADFIR) Desktop Backend",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs"
)

# Secure Cross-Origin Resource Sharing for Desktop/Tauri
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Security Exception Handler: Never expose raw stack traces to users
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Internal Exception on {request.method} {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred during forensic processing. Check system audit logs for details."}
    )

# Include Routers with exact required /api prefix
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(system.router, prefix="/api", tags=["System"])
app.include_router(investigations.router, prefix="/api/investigations", tags=["Investigations"])

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
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
