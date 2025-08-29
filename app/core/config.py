#!/usr/bin/env python3
"""
Configuration settings for Store Monitoring System
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # Database configuration
    DATABASE_URL: str = (
        "postgresql://neondb_owner:npg_HNBZ6c8dUnuC@"
        "ep-fragrant-snow-a1gvjf6b-pooler.ap-southeast-1.aws.neon.tech/"
        "neondb?sslmode=require"
    )
    
    # Server configuration
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8001
    
    # Application configuration
    APP_TITLE: str = "Store Monitoring System API"
    APP_DESCRIPTION: str = "FastAPI server for store monitoring with proper project structure"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = False
    
    # JSON file settings
    REPORTS_JSON_FILE: str = "reports.json"
    
    # SQLAlchemy settings
    SQLALCHEMY_ECHO: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
