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
from .minute_index_report_service import MinuteIndexReportService
from .comprehensive_store_report_service import ComprehensiveStoreReportService

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
        self.minute_index_service = MinuteIndexReportService(db)
        self.comprehensive_service = ComprehensiveStoreReportService(db)
    
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
                    "message": f"Cannot create new report. Existing report {pending_report.report_id} is still {pending_report.status}."
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
                        "message": f"Report is currently {pending_report.status} - cannot create new one"
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
                        "message": "No PENDING/RUNNING report - can create new report"
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
    
    def set_report_status_and_url(self, report_id: str, status: str, url: Optional[str] = None) -> Dict[str, Any]:
        """
        Business operation: Update report status and URL (for compute workers)
        """
        try:
            # Business rule: Validate status transition
            valid_statuses = ["PENDING", "RUNNING", "COMPLETE", "FAILED"]
            if status not in valid_statuses:
                return {
                    "success": False,
                    "error_code": "INVALID_STATUS",
                    "data": {"message": f"Invalid status: {status}. Must be one of {valid_statuses}"}
                }
            
            # Business rule: URL should only be set for COMPLETE status
            if status == "COMPLETE" and not url:
                logger.warning(f"Report {report_id} marked COMPLETE but no URL provided")
            elif status != "COMPLETE" and url:
                logger.warning(f"Report {report_id} status {status} has URL - URLs typically only for COMPLETE")
            
            db_report = self.crud.set_report_status_and_url(self.db, report_id, status, url)
            
            if not db_report:
                return {
                    "success": False,
                    "error_code": "NOT_FOUND",
                    "data": {"message": f"Report {report_id} not found"}
                }
            
            # Business rule: Clear JSON tracking when job completes or fails
            if status in ["COMPLETE", "FAILED"]:
                self._clear_current_report_json()
            
            logger.info(f"Business logic: Report {report_id} status updated to {status} with URL: {url}")
            
            return {
                "success": True,
                "error_code": None,
                "data": {
                    "report": db_report,
                    "report_id": report_id,
                    "status": status,
                    "url": url,
                    "updated_at": db_report.updated_at
                }
            }
            
        except Exception as e:
            logger.error(f"Error setting report status and URL: {e}")
            return {
                "success": False,
                "error_code": "UPDATE_FAILED",
                "data": {"message": str(e)}
            }
    
    def get_report_with_url_logic(self, report_id: str) -> Dict[str, Any]:
        """
        Business operation: Get report with URL visibility rules
        """
        try:
            logger.info(f"Fetching report with URL logic: {report_id}")
            
            db_report = self.crud.get_report_by_id(self.db, report_id)
            
            if not db_report:
                return {
                    "success": False,
                    "error_code": "NOT_FOUND",
                    "data": {"message": f"Report {report_id} not found"}
                }
            
            # Business rule: Only expose URL when status is COMPLETE
            exposed_url = None
            display_status = db_report.status
            
            if db_report.status in ("PENDING", "RUNNING"):
                display_status = "RUNNING"
                exposed_url = None
            elif db_report.status == "FAILED":
                display_status = "FAILED"
                exposed_url = None
            elif db_report.status == "COMPLETE":
                display_status = "COMPLETED"
                # Convert file:// URL to /files/ format
                if db_report.url and db_report.url.startswith("file://"):
                    file_path = db_report.url.replace("file://", "")
                    if "reports/" in file_path:
                        filename = file_path.split("reports/")[-1]
                        # Convert to CSV format as required
                        if filename.endswith(".json"):
                            filename = filename.replace(".json", ".csv")
                        exposed_url = f"/files/reports/{filename}"
                    else:
                        exposed_url = db_report.url
                else:
                    exposed_url = db_report.url
            
            logger.info(f"Report {report_id} business logic: status={display_status}, URL exposed={exposed_url is not None}")
            
            return {
                "success": True,
                "error_code": None,
                "data": {
                    "report": db_report,
                    "report_id": report_id,
                    "status": display_status,
                    "url": exposed_url,
                    "raw_status": db_report.status,
                    "created_at": db_report.created_at,
                    "updated_at": db_report.updated_at
                }
            }
            
        except Exception as e:
            logger.error(f"Error fetching report with URL logic {report_id}: {e}")
            return {
                "success": False,
                "error_code": "FETCH_FAILED",
                "data": {"message": str(e)}
            }
    
    def generate_actual_store_report(self, report_id: str, comprehensive: bool = True) -> Dict[str, Any]:
        """
        Generate the actual store monitoring report
        
        Args:
            report_id: Unique report identifier
            comprehensive: If True, process ALL stores with data normalization
        """
        try:
            logger.info(f"Starting actual report generation for {report_id} (comprehensive={comprehensive})")
            
            if comprehensive:
                # Use comprehensive service for ALL stores with normalization
                result = self.comprehensive_service.generate_comprehensive_report(report_id)
            else:
                # Use limited service for testing
                result = self.minute_index_service.generate_store_report(report_id, 100)
            
            if result["success"]:
                if comprehensive:
                    logger.info(f"Comprehensive report {report_id}: {result['successfully_processed']}/{result['total_unique_stores']} stores")
                else:
                    logger.info(f"Report {report_id} generated: {result['total_stores']} stores")
                
                # The file path is the URL we want to store
                file_url = f"file://{result['file_path']}"
                
                # Update the database with COMPLETE status and URL
                self.set_report_status_and_url(report_id, "COMPLETE", file_url)
                
                return {
                    "success": True,
                    "report_id": report_id,
                    "url": file_url,
                    "total_stores": result.get("total_unique_stores", result.get("total_stores", 0)),
                    "successfully_processed": result.get("successfully_processed", result.get("total_stores", 0)),
                    "summary": result["summary"],
                    "algorithm": result.get("algorithm", "Comprehensive Minute-Index")
                }
            else:
                logger.error(f"Report generation failed for {report_id}: {result.get('error')}")
                
                # Mark as failed
                self.set_report_status_and_url(report_id, "FAILED")
                
                return {
                    "success": False,
                    "report_id": report_id,
                    "error": result.get("error", "Unknown error")
                }
                
        except Exception as e:
            logger.error(f"Error in actual report generation for {report_id}: {e}")
            
            # Mark as failed
            try:
                self.set_report_status_and_url(report_id, "FAILED")
            except:
                pass  # Don't fail on cleanup
            
            return {
                "success": False,
                "report_id": report_id,
                "error": str(e)
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
