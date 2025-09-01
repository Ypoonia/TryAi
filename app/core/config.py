from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    
    DATABASE_URL: str = "postgresql://localhost/store_monitoring"
    
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8001
    
    APP_TITLE: str = "Store Monitoring System API"
    APP_DESCRIPTION: str = "FastAPI server for store monitoring with proper project structure"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = False
    
    REPORTS_JSON_FILE: str = "reports.json"
    
    SQLALCHEMY_ECHO: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
