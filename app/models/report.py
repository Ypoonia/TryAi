#!/usr/bin/env python3
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, CheckConstraint
from sqlalchemy.sql import func
from app.models.base import Base


class Report(Base):
 
    
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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<Report({self.report_id}, {self.status})>"
    
    def __str__(self):
        created = self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else 'Unknown'
        return f"Report {self.report_id} - {self.status} ({created})"
    
    @property
    def is_pending(self):
        return self.status == 'PENDING'
    
    @property
    def is_running(self):
        return self.status == 'RUNNING'
    
    @property
    def is_complete(self):
        return self.status == 'COMPLETE'
    
    @property
    def is_failed(self):
        return self.status == 'FAILED'
    
    @property
    def is_finished(self):
        return self.status in ('COMPLETE', 'FAILED')
    
    @property
    def has_file(self):
        return self.url is not None and self.url.strip() != ''
    
    @property
    def age_minutes(self):
        if not self.created_at:
            return None
        return (datetime.utcnow() - self.created_at.replace(tzinfo=None)).total_seconds() / 60
    
    def get_status_display(self):
        status_map = {
            'PENDING': 'Waiting to start',
            'RUNNING': 'Processing',
            'COMPLETE': 'Done',
            'FAILED': 'Failed'
        }
        return status_map.get(self.status, self.status)
    
    def to_dict(self):
        return {
            'report_id': self.report_id,
            'status': self.status,
            'status_display': self.get_status_display(),
            'has_file': self.has_file,
            'file_url': self.url if self.has_file else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'age_minutes': self.age_minutes,
        }
    
    class Config:
        from_attributes = True
