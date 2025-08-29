#!/usr/bin/env python3
"""
Main FastAPI Application - Routes-Controller-Service Architecture
Demonstrates proper layered architecture with clean separation of concerns
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import settings
from app.models import create_tables
from app.routes import reports_rcs
from app.routes import health_rcs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title=f"{settings.APP_TITLE} - RCS Architecture",
    description="FastAPI with Routes-Controller-Service architecture pattern",
    version="4.0.0",
    debug=settings.DEBUG
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with RCS architecture
app.include_router(reports_rcs.router)
app.include_router(health_rcs.router)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("Starting Store Monitoring System API with RCS Architecture...")
    
    # Create database tables
    try:
        create_tables()
        logger.info("Database tables created/verified successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise
    
    logger.info(f"RCS Application started successfully on {settings.SERVER_HOST}:{settings.SERVER_PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("Shutting down Store Monitoring System API...")


@app.get("/", tags=["root"])
def root():
    """
    Root endpoint with RCS architecture information
    """
    return {
        "message": f"{settings.APP_TITLE} - Routes-Controller-Service Architecture",
        "version": "4.0.0",
        "architecture": "Routes-Controller-Service (RCS)",
        "docs": "/docs",
        "health": "/health/",
        "layers": {
            "routes": "HTTP request handling and validation",
            "controllers": "Request/response coordination and formatting", 
            "services": "Business logic and rules implementation",
            "database": "Data access and CRUD operations",
            "models": "Database schema and ORM definitions"
        },
        "endpoints": {
            "POST /reports/trigger": "Trigger new report (RCS pattern)",
            "GET /reports/status?report_id=<id>": "Get report status (RCS pattern)",
            "GET /reports/details?report_id=<id>": "Get detailed report info (NEW)",
            "PUT /reports/status?report_id=<id>&new_status=<status>": "Update report status (NEW)",
            "GET /reports/current": "Get current active report",
            "GET /reports/pending": "Check for pending reports",
            "GET /health/": "System health check"
        },
        "legacy_endpoints": {
            "POST /reports/trigger_report": "Legacy - use /reports/trigger",
            "GET /reports/get_report": "Legacy - use /reports/status",
            "GET /reports/current_report": "Legacy - use /reports/current",
            "GET /reports/pending_status": "Legacy - use /reports/pending",
            "GET /health/healthz": "Legacy - use /health/"
        },
        "architecture_benefits": [
            "Clean separation of concerns",
            "Easy to test individual layers",
            "Maintainable and extensible code",
            "Business logic isolated from HTTP concerns",
            "Consistent error handling patterns"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main_rcs:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG
    )
