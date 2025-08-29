#!/usr/bin/env python3
"""
Main Entry Point - Clean Routes-Controller-Service Architecture
FastAPI application with proper layered architecture
"""

import uvicorn
from app.main_rcs import app
from app.core.config import settings

if __name__ == "__main__":
    print("🚀 Starting Store Monitoring API with Routes-Controller-Service Architecture")
    print(f"📡 Server: http://{settings.SERVER_HOST}:{settings.SERVER_PORT}")
    print(f"📚 Docs: http://{settings.SERVER_HOST}:{settings.SERVER_PORT}/docs")
    
    uvicorn.run(
        "app.main_rcs:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG
    )
