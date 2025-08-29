#!/usr/bin/env python3
"""
FastAPI Server for Store Monitoring System
TryLoop Repository - Minimal APIs for Report Management
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import psycopg2
import asyncio
import time
import random
import logging
from datetime import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Store Monitoring System API",
    description="Minimal APIs for report management in TryLoop repository",
    version="1.0.0"
)

# Database connection string
DATABASE_URL = "postgresql://neondb_owner:npg_HNBZ6c8dUnuC@ep-fragrant-snow-a1gvjf6b-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# Pydantic models
class ReportResponse(BaseModel):
    report_id: str

class ReportStatusResponse(BaseModel):
    status: str
    report_id: str

class ErrorResponse(BaseModel):
    status: str
    error: str
    report_id: str

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

def generate_report_id() -> str:
    """Generate unique report_id: timestamp_ns + - + 6-digit random"""
    timestamp_ns = int(time.time() * 1_000_000_000)  # nanoseconds
    random_6digit = random.randint(100000, 999999)
    return f"{timestamp_ns}-{random_6digit}"

async def process_report_background(report_id: str):
    """Background task to process report status changes"""
    try:
        # Wait a bit before starting
        await asyncio.sleep(0.1)
        
        # Update status to RUNNING
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE raw.reports 
            SET status = 'RUNNING' 
            WHERE report_id = %s
        """, (report_id,))
        conn.commit()
        logger.info(f"Report {report_id} status updated to RUNNING")
        
        # Simulate processing time
        await asyncio.sleep(1.5)
        
        # Update status to COMPLETE
        cur.execute("""
            UPDATE raw.reports 
            SET status = 'COMPLETE' 
            WHERE report_id = %s
        """, (report_id,))
        conn.commit()
        logger.info(f"Report {report_id} status updated to COMPLETE")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Background processing failed for {report_id}: {e}")
        # Update status to FAILED
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE raw.reports 
                SET status = 'FAILED' 
                WHERE report_id = %s
            """, (report_id,))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as update_error:
            logger.error(f"Failed to update status to FAILED: {update_error}")

@app.post("/trigger_report", response_model=ReportResponse)
async def trigger_report(background_tasks: BackgroundTasks):
    """
    Trigger a new report generation
    
    Returns:
        ReportResponse: Contains the generated report_id
    """
    try:
        # Generate unique report_id
        report_id = generate_report_id()
        
        # Insert into raw.reports with status='PENDING'
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO raw.reports (report_id, status) 
            VALUES (%s, 'PENDING')
        """, (report_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Report {report_id} created with PENDING status")
        
        # Spawn background task to process the report
        background_tasks.add_task(process_report_background, report_id)
        
        return ReportResponse(report_id=report_id)
        
    except Exception as e:
        logger.error(f"Failed to trigger report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger report: {str(e)}")

@app.get("/get_report", response_model=ReportStatusResponse)
async def get_report(report_id: str):
    """
    Get the status of a report
    
    Args:
        report_id: The unique identifier of the report
        
    Returns:
        ReportStatusResponse: Contains the current status and report_id
    """
    try:
        # Query the report status from database
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT status FROM raw.reports 
            WHERE report_id = %s
        """, (report_id,))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail="Report not found")
        
        status = result[0]
        
        # Return appropriate response based on status
        if status in ['PENDING', 'RUNNING']:
            return ReportStatusResponse(status="Running", report_id=report_id)
        elif status == 'FAILED':
            return ReportStatusResponse(status="Failed", report_id=report_id)
        elif status == 'COMPLETE':
            return ReportStatusResponse(status="Complete", report_id=report_id)
        else:
            # Unknown status
            return ReportStatusResponse(status=status, report_id=report_id)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get report {report_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get report: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Store Monitoring System API",
        "version": "1.0.0",
        "endpoints": {
            "POST /trigger_report": "Trigger a new report generation",
            "GET /get_report?report_id=<id>": "Get report status"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        conn.close()
        
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
