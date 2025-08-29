#!/usr/bin/env python3
"""
Health Controller - Health Check Request Handling
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session
import logging

from app.services.health_service import HealthService
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)


class HealthController:
    """
    Controller layer for health check operations
    Handles health check requests and responses
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.service = HealthService(db)
    
    def check_health(self) -> HealthResponse:
        """
        Controller: Handle health check request
        """
        try:
            # Call service layer
            result = self.service.check_system_health()
            
            if not result["success"]:
                # Health check failed
                error_data = result["data"]
                logger.warning(f"Health check failed: {error_data}")
                
                return HealthResponse(
                    ok=False,
                    database=error_data.get("database", "error")
                )
            
            # Success case
            health_data = result["data"]
            
            return HealthResponse(
                ok=health_data["ok"],
                database=health_data["database"]
            )
            
        except Exception as e:
            logger.error(f"Unexpected error in health check controller: {e}")
            return HealthResponse(
                ok=False,
                database=f"controller_error: {str(e)}"
            )
