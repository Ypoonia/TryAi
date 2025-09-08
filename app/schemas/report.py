#!/usr/bin/env python3
"""
Pydantic schemas for Report operations (cleaned & minimal)
"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Literal


# Internal, authoritative status enum (use everywhere inside the app)
class ReportStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# --- Output DTOs (HTTP responses) ---

class ReportResponse(BaseModel):
    """
    Trigger response. Return current status with report_id and message.
    """
    report_id: str = Field(..., description="Unique report identifier")
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"] = Field(..., description="Report status")
    message: str = Field(..., description="Human-readable message")

    class Config:
        from_attributes = True


class ReportStatusResponse(BaseModel):
    """
    Status response for GET /get_report.
    Status values match ReportStatus enum for consistency.
    """
    report_id: str = Field(..., description="Report identifier")
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"] = Field(..., description="Current report status")
    url: Optional[str] = Field(None, description="Report URL (only when COMPLETED)")

    class Config:
        from_attributes = True
