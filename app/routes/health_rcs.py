#!/usr/bin/env python3
"""
Health Routes - Using Routes-Controller-Service Architecture
Clean separation of concerns for health check operations
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models import get_db
from app.controllers import HealthController
from app.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


def get_health_controller(db: Session = Depends(get_db)) -> HealthController:
    """Dependency to get Health Controller with database session"""
    return HealthController(db)


@router.get("/", response_model=HealthResponse, summary="System health check")
def health_check(controller: HealthController = Depends(get_health_controller)):
    """
    Comprehensive system health check
    
    **Checks:**
    - Database connectivity
    - Query execution capability
    - Overall system status
    
    **Returns:**
    - ok: Boolean indicating overall system health
    - database: Database connection status details
    
    **Note:**
    This endpoint always returns HTTP 200, but the 'ok' field
    indicates the actual health status.
    """
    return controller.check_health()

