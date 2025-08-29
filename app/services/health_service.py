#!/usr/bin/env python3
"""
Health Service - System Health Business Logic
"""

from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from app.database.crud import check_database_health

logger = logging.getLogger(__name__)


class HealthService:
    """
    Service layer for health check operations
    Contains business logic for system health monitoring
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def check_system_health(self) -> Dict[str, Any]:
        """
        Business operation: Comprehensive system health check
        """
        try:
            # Check database connectivity
            db_health = check_database_health(self.db)
            
            # Additional health checks can be added here
            # - Redis connectivity
            # - External API availability
            # - Disk space
            # - Memory usage
            
            overall_health = db_health.get("ok", False)
            
            health_details = {
                "database": db_health,
                "overall_status": "healthy" if overall_health else "unhealthy"
            }
            
            return {
                "success": True,
                "error_code": None,
                "data": {
                    "ok": overall_health,
                    "database": db_health.get("database", "unknown"),
                    "details": health_details
                }
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "success": False,
                "error_code": "HEALTH_CHECK_FAILED",
                "data": {
                    "ok": False,
                    "database": str(e),
                    "details": {"error": str(e)}
                }
            }
