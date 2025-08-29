#!/usr/bin/env python3
"""
Pydantic schemas for health check operations
"""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema for health check response"""
    ok: bool = Field(..., description="Health status")
    database: str = Field(..., description="Database connection status")

    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    """Schema for error responses"""
    detail: str = Field(..., description="Error message")

    class Config:
        from_attributes = True
