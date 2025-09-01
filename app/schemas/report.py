#!/usr/bin/env python3
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Literal


# Internal, authoritative status enum (use everywhere inside the app)
class ReportStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"




class ReportResponse(BaseModel):
  
    report_id: str = Field(..., description="Unique report identifier")
    status: Literal["PENDING", "RUNNING", "COMPLETE", "FAILED"] = Field(..., description="Report status")
    message: str = Field(..., description="Human-readable message")

    class Config:
        from_attributes = True


class ReportStatusResponse(BaseModel):
  
    report_id: str = Field(..., description="Report identifier")
    status: Literal["PENDING", "RUNNING", "COMPLETE", "FAILED"] = Field(..., description="Current report status")
    url: Optional[str] = Field(None, description="Report URL (only when COMPLETE)")

    class Config:
        from_attributes = True
