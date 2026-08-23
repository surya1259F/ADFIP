from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    PROJECT_NAME: str = "ADFIR - Autonomous DFIR Platform"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Base directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    EVIDENCE_DIR: Path = DATA_DIR / "evidence"
    CASES_DIR: Path = DATA_DIR / "cases"
    REPORTS_DIR: Path = DATA_DIR / "reports"
    
    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/adfir.db"
    
    # Forensic tool paths
    VOLATILITY_PYTHON: Path = BASE_DIR / "volatility-env" / "bin" / "python"
    VOLATILITY_CLI: Path = BASE_DIR / "volatility-env" / "bin" / "vol"
    
    # LLM Settings (Provider Abstraction)
    DEFAULT_LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    LOCAL_LLM_ENDPOINT: str = "http://localhost:11434/v1"
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()

# Ensure required workspace data directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
settings.CASES_DIR.mkdir(parents=True, exist_ok=True)
settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
