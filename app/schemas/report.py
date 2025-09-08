#!/usr/bin/env python3
"""
Pydantic schemas for Report operations (cleaned & unified)
"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


# Internal, authoritative status enum (use everywhere inside the app)
class ReportStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# --- Input/Update DTOs (internal-ish) ---

class ReportBase(BaseModel):
    """Base report schema"""
    status: ReportStatus = Field(..., description="Report status")
    url: Optional[str] = Field(None, description="Report URL")


class ReportCreate(BaseModel):
    """Schema for creating a new report"""
    report_id: str = Field(..., description="Unique report identifier")


class ReportUpdate(BaseModel):
    """Schema for updating a report"""
    status: Optional[ReportStatus] = Field(None, description="New report status")
    url: Optional[str] = Field(None, description="Report URL")


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


# (Kept for completeness where you may need fuller objects elsewhere)
class ReportDetailResponse(BaseModel):
    report_id: str = Field(..., description="Unique report identifier")
    status: ReportStatus = Field(..., description="Current report status")
    url: Optional[str] = Field(None, description="Report URL")
    created_at: datetime = Field(..., description="Report creation timestamp")
    updated_at: datetime = Field(..., description="Report last update timestamp")

    class Config:
        from_attributes = True
