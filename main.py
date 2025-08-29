#!/usr/bin/env python3
"""
FastAPI Server for Store Monitoring System
TryLoop Repository - Minimal APIs for Report Management
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
from time import time_ns
from secrets import randbelow
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Store Monitoring System API (skeleton)")

DATABASE_URL = (
    "postgresql://neondb_owner:npg_HNBZ6c8dUnuC@"
    "ep-fragrant-snow-a1gvjf6b-pooler.ap-southeast-1.aws.neon.tech/"
    "neondb?sslmode=require"
)

def db():
    """Get database connection"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

def new_report_id() -> str:
    """Generate unique report ID"""
    return f"{time_ns()}-{randbelow(1_000_000):06d}"

class ReportResponse(BaseModel):
    report_id: str

class ReportStatusResponse(BaseModel):
    status: str
    report_id: str

@app.post("/trigger_report", response_model=ReportResponse)
def trigger_report():
    """Trigger a new report generation"""
    try:
        rid = new_report_id()
        logger.info(f"Creating report with ID: {rid}")
        
        conn = db()
        cur = conn.cursor()
        
        cur.execute(
            "INSERT INTO raw.reports (report_id, status) VALUES (%s, 'PENDING')",
            (rid,),
        )
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Report {rid} created successfully")
        return ReportResponse(report_id=rid)
        
    except Exception as e:
        logger.error(f"Failed to trigger report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger report: {str(e)}")

@app.get("/get_report", response_model=ReportStatusResponse)
def get_report(report_id: str):
    """Get report status by ID"""
    try:
        logger.info(f"Fetching status for report: {report_id}")
        
        conn = db()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT status FROM raw.reports WHERE report_id=%s",
            (report_id,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            logger.warning(f"Report {report_id} not found")
            raise HTTPException(status_code=404, detail="report_id not found")

        logger.info(f"Report {report_id} status: {row[0]}")
        return ReportStatusResponse(status=row[0], report_id=report_id)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get report {report_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get report: {str(e)}")

@app.get("/healthz")
def healthz():
    """Health check endpoint"""
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result and result[0] == 1:
            return {"ok": True, "database": "connected"}
        else:
            return {"ok": False, "database": "query_failed"}
            
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"ok": False, "database": str(e)}

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "Store Monitoring System API",
        "endpoints": {
            "POST /trigger_report": "Trigger a new report",
            "GET /get_report?report_id=<id>": "Get report status",
            "GET /healthz": "Health check"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)  # Changed port to 8001
