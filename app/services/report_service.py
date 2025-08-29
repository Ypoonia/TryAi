#!/usr/bin/env python3
"""
Report Service - Business Logic Layer
Handles all business rules and operations for reports
"""

from sqlalchemy.orm import Session
from time import time_ns
from secrets import randbelow
import logging
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

from app.models.report import Report
from app.database.crud import ReportCRUD
from app.core.config import settings

logger = logging.getLogger(__name__)


class ReportService:
    """
    Service layer for report business logic
    Contains all business rules and operations
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.crud = ReportCRUD
    
    def generate_report_id(self) -> str:
        """Generate a unique report ID"""
        return f"{time_ns()}-{randbelow(1_000_000):06d}"
    
    def can_create_new_report(self) -> Dict[str, Any]:
        """
        Business rule: Check if a new report can be created
        Returns validation result with details
        """
        try:
            pending_report = self.crud.get_latest_pending_report(self.db)
            
            if pending_report:
                return {
                    "can_create": False,
                    "reason": "PENDING_EXISTS",
                    "existing_report": {
                        "report_id": pending_report.report_id,
                        "status": pending_report.status,
                        "created_at": pending_report.created_at
                    },
                    "message": f"Cannot create new report. Existing report {pending_report.report_id} is still PENDING."
                }
            
            return {
                "can_create": True,
                "reason": "NO_PENDING",
                "existing_report": None,
                "message": "Ready to create new report"
            }
            
        except Exception as e:
            logger.error(f"Error checking report creation eligibility: {e}")
            return {
                "can_create": False,
                "reason": "ERROR",
                "existing_report": None,
                "message": f"Error validating report creation: {str(e)}"
            }
    
    def create_new_report(self) -> Dict[str, Any]:
        """
        Business operation: Create a new report
        Handles all business logic for report creation
        """
        try:
            # Business rule validation
            validation = self.can_create_new_report()
            if not validation["can_create"]:
                return {
                    "success": False,
                    "error_code": "CREATION_BLOCKED",
                    "data": validation
                }
            
            # Generate unique ID
            report_id = self.generate_report_id()
            logger.info(f"Creating new report with ID: {report_id}")
            
            # Create report in database
            db_report = self.crud.create_report(self.db, report_id, "PENDING")
            
            # Update JSON tracking (business requirement)
            self._update_current_report_json(report_id, "PENDING")
            
            logger.info(f"Report {report_id} created successfully")
            
            return {
                "success": True,
                "error_code": None,
                "data": {
                    "report": db_report,
                    "report_id": report_id,
                    "status": "PENDING",
                    "created_at": db_report.created_at
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating report: {e}")
            return {
                "success": False,
                "error_code": "CREATION_FAILED",
                "data": {"message": str(e)}
            }
    
    def get_report_by_id(self, report_id: str) -> Dict[str, Any]:
        """
        Business operation: Get report details
        """
        try:
            logger.info(f"Fetching report: {report_id}")
            
            db_report = self.crud.get_report_by_id(self.db, report_id)
            
            if not db_report:
                return {
                    "success": False,
                    "error_code": "NOT_FOUND",
                    "data": {"message": f"Report {report_id} not found"}
                }
            
            logger.info(f"Report {report_id} status: {db_report.status}")
            
            return {
                "success": True,
                "error_code": None,
                "data": {
                    "report": db_report,
                    "report_id": report_id,
                    "status": db_report.status,
                    "url": db_report.url,
                    "created_at": db_report.created_at,
                    "updated_at": db_report.updated_at
                }
            }
            
        except Exception as e:
            logger.error(f"Error fetching report {report_id}: {e}")
            return {
                "success": False,
                "error_code": "FETCH_FAILED",
                "data": {"message": str(e)}
            }
    
    def get_pending_report_status(self) -> Dict[str, Any]:
        """
        Business operation: Check for pending reports
        """
        try:
            pending_report = self.crud.get_latest_pending_report(self.db)
            
            if pending_report:
                return {
                    "success": True,
                    "error_code": None,
                    "data": {
                        "has_pending": True,
                        "report_id": pending_report.report_id,
                        "status": pending_report.status,
                        "created_at": pending_report.created_at,
                        "message": "Report is currently PENDING - cannot create new one"
                    }
                }
            else:
                return {
                    "success": True,
                    "error_code": None,
                    "data": {
                        "has_pending": False,
                        "report_id": None,
                        "status": None,
                        "created_at": None,
                        "message": "No PENDING report - can create new report"
                    }
                }
                
        except Exception as e:
            logger.error(f"Error checking pending status: {e}")
            return {
                "success": False,
                "error_code": "STATUS_CHECK_FAILED",
                "data": {"message": str(e)}
            }
    
    def get_current_report_from_json(self) -> Dict[str, Any]:
        """
        Business operation: Get current active report from JSON
        """
        try:
            data = self._load_current_report_json()
            
            return {
                "success": True,
                "error_code": None,
                "data": {
                    "current_report_id": data.get("current_report_id"),
                    "status": data.get("status"),
                    "created_at": data.get("created_at"),
                    "last_updated": data.get("last_updated")
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting current report: {e}")
            return {
                "success": False,
                "error_code": "JSON_READ_FAILED",
                "data": {"message": str(e)}
            }
    
    def update_report_status(self, report_id: str, new_status: str) -> Dict[str, Any]:
        """
        Business operation: Update report status
        """
        try:
            # Business rule: Validate status transition
            valid_statuses = ["PENDING", "RUNNING", "COMPLETE", "FAILED"]
            if new_status not in valid_statuses:
                return {
                    "success": False,
                    "error_code": "INVALID_STATUS",
                    "data": {"message": f"Invalid status: {new_status}. Must be one of {valid_statuses}"}
                }
            
            db_report = self.crud.update_report_status(self.db, report_id, new_status)
            
            if not db_report:
                return {
                    "success": False,
                    "error_code": "NOT_FOUND",
                    "data": {"message": f"Report {report_id} not found"}
                }
            
            # Update JSON if this is the current report
            if new_status in ["COMPLETE", "FAILED"]:
                self._clear_current_report_json()
            
            return {
                "success": True,
                "error_code": None,
                "data": {
                    "report": db_report,
                    "report_id": report_id,
                    "status": new_status,
                    "updated_at": db_report.updated_at
                }
            }
            
        except Exception as e:
            logger.error(f"Error updating report status: {e}")
            return {
                "success": False,
                "error_code": "UPDATE_FAILED",
                "data": {"message": str(e)}
            }
    
    # Private helper methods for JSON operations
    def _load_current_report_json(self) -> Dict[str, Any]:
        """Load current report from JSON file"""
        try:
            if os.path.exists(settings.REPORTS_JSON_FILE):
                with open(settings.REPORTS_JSON_FILE, 'r') as f:
                    return json.load(f)
            else:
                # Return default structure
                default_data = {
                    "current_report_id": None,
                    "status": None,
                    "created_at": None,
                    "last_updated": datetime.now().isoformat()
                }
                self._save_current_report_json(default_data)
                return default_data
        except Exception as e:
            logger.error(f"Error loading reports JSON: {e}")
            return {
                "current_report_id": None,
                "status": None,
                "created_at": None,
                "last_updated": datetime.now().isoformat()
            }
    
    def _save_current_report_json(self, data: Dict[str, Any]) -> None:
        """Save current report data to JSON file"""
        try:
            with open(settings.REPORTS_JSON_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Current report JSON updated: {settings.REPORTS_JSON_FILE}")
        except Exception as e:
            logger.error(f"Error saving reports JSON: {e}")
    
    def _update_current_report_json(self, report_id: str, status: str = "PENDING") -> None:
        """Update JSON file with current active report"""
        try:
            current_report_data = {
                "current_report_id": report_id,
                "status": status,
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
            
            self._save_current_report_json(current_report_data)
            logger.info(f"Current report updated in JSON: {report_id}")
            
        except Exception as e:
            logger.error(f"Error updating current report in JSON: {e}")
    
    def _clear_current_report_json(self) -> None:
        """Clear current report from JSON (when completed/failed)"""
        try:
            empty_data = {
                "current_report_id": None,
                "status": None,
                "created_at": None,
                "last_updated": datetime.now().isoformat()
            }
            self._save_current_report_json(empty_data)
            logger.info("Current report cleared from JSON")
        except Exception as e:
            logger.error(f"Error clearing current report from JSON: {e}")
