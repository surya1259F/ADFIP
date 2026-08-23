from fastapi import APIRouter
from backend.app.api.v1.endpoints import system, cases, evidence, investigation, reports

api_router = APIRouter()
api_router.include_router(system.router, prefix="/system", tags=["System"])
api_router.include_router(cases.router, prefix="/cases", tags=["Cases"])
api_router.include_router(evidence.router, prefix="/evidence", tags=["Evidence"])
api_router.include_router(investigation.router, prefix="/investigation", tags=["Investigation"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
