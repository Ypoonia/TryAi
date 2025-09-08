#!/usr/bin/env python3
"""
Routes package for Store Monitoring System
"""

from app.routes.reports_rcs import router as reports_router

__all__ = [
    "reports_router"
]
