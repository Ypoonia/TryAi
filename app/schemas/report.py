#!/usr/bin/env python3
"""
Pydantic schemas for Report operations
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ReportBase(BaseModel):
    """Base report schema"""
    status: str = Field(..., description="Report status")
    url: Optional[str] = Field(None, description="Report URL")


class ReportCreate(BaseModel):
    """Schema for creating a new report"""
    report_id: str = Field(..., description="Unique report identifier")


class ReportUpdate(BaseModel):
    """Schema for updating a report"""
    status: Optional[str] = Field(None, description="New report status")
    url: Optional[str] = Field(None, description="Report URL")


class ReportResponse(BaseModel):
    """Schema for report response"""
    report_id: str = Field(..., description="Unique report identifier")

    class Config:
        from_attributes = True


class ReportStatusResponse(BaseModel):
    """Schema for report status response"""
    status: str = Field(..., description="Current report status")
    report_id: str = Field(..., description="Report identifier")

    class Config:
        from_attributes = True


class ReportDetailResponse(BaseModel):
    """Schema for detailed report response"""
    report_id: str = Field(..., description="Unique report identifier")
    status: str = Field(..., description="Current report status")
    url: Optional[str] = Field(None, description="Report URL")
    created_at: datetime = Field(..., description="Report creation timestamp")
    updated_at: datetime = Field(..., description="Report last update timestamp")

    class Config:
        from_attributes = True


class PendingStatusResponse(BaseModel):
    """Schema for pending status check response"""
    has_pending: bool = Field(..., description="Whether a PENDING report exists")
    report_id: Optional[str] = Field(None, description="Existing PENDING report ID")
    status: Optional[str] = Field(None, description="Existing report status")
    created_at: Optional[datetime] = Field(None, description="Existing report creation time")
    message: str = Field(..., description="Status message")

    class Config:
        from_attributes = True


class CurrentReportResponse(BaseModel):
    """Schema for current report response"""
    current_report_id: Optional[str] = Field(None, description="Current active report ID")
    status: Optional[str] = Field(None, description="Current report status")
    created_at: Optional[datetime] = Field(None, description="Current report creation time")
    last_updated: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        from_attributes = True
