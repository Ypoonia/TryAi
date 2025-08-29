#!/usr/bin/env python3
"""
Report model for the Store Monitoring System
"""

from sqlalchemy import Column, String, DateTime, Text, CheckConstraint
from sqlalchemy.sql import func
from app.models.base import Base


class Report(Base):
    """Report model for the raw.reports table"""
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETE', 'FAILED')",
            name='reports_status_check'
        ),
        {"schema": "raw"}
    )
    
    report_id = Column(String, primary_key=True, index=True)
    status = Column(String, nullable=False)
    url = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )
    
    def __repr__(self):
        return f"<Report(report_id='{self.report_id}', status='{self.status}')>"
    
    class Config:
        """Pydantic model configuration"""
        from_attributes = True
