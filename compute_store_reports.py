#!/usr/bin/env python3
"""
Store Reports Compute Worker
Demonstrates the minute-index algorithm for generating store monitoring reports

This script simulates a compute worker that:
1. Marks report as RUNNING
2. Generates the actual store report using the minute-index algorithm
3. Marks report as COMPLETE with file URL
"""

import sys
import requests
import time
import logging
from pathlib import Path

# Add the app directory to the path for imports
sys.path.append(str(Path(__file__).parent))

from app.models import SessionLocal
from app.services.report_service import ReportService

# Configuration
API_BASE_URL = "http://localhost:8001"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_latest_pending_report():
    """Get the latest pending report from the API"""
    try:
        response = requests.get(f"{API_BASE_URL}/reports/pending")
        if response.status_code == 200:
            data = response.json()
            if data["has_pending"]:
                return data["report_id"]
        return None
    except Exception as e:
        logger.error(f"Failed to get pending report: {e}")
        return None

def mark_report_running(report_id: str):
    """Mark report as RUNNING"""
    try:
        response = requests.put(f"{API_BASE_URL}/reports/complete", params={
            "report_id": report_id,
            "status": "RUNNING"
        })
        if response.status_code == 200:
            logger.info(f"✅ Report {report_id} marked as RUNNING")
            return True
        else:
            logger.error(f"❌ Failed to mark report as RUNNING: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error marking report as RUNNING: {e}")
        return False

def mark_report_complete(report_id: str, url: str):
    """Mark report as COMPLETE with URL"""
    try:
        response = requests.put(f"{API_BASE_URL}/reports/complete", params={
            "report_id": report_id,
            "status": "COMPLETE",
            "url": url
        })
        if response.status_code == 200:
            logger.info(f"✅ Report {report_id} marked as COMPLETE with URL: {url}")
            return True
        else:
            logger.error(f"❌ Failed to mark report as COMPLETE: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error marking report as COMPLETE: {e}")
        return False

def mark_report_failed(report_id: str):
    """Mark report as FAILED"""
    try:
        response = requests.put(f"{API_BASE_URL}/reports/complete", params={
            "report_id": report_id,
            "status": "FAILED"
        })
        if response.status_code == 200:
            logger.info(f"❌ Report {report_id} marked as FAILED")
            return True
        else:
            logger.error(f"❌ Failed to mark report as FAILED: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error marking report as FAILED: {e}")
        return False

def generate_store_report(report_id: str, comprehensive: bool = True):
    """
    Generate the actual store report using comprehensive algorithm
    
    Args:
        report_id: Report identifier
        comprehensive: If True, process ALL stores with data normalization
    """
    logger.info(f"🚀 Starting store report generation for {report_id}")
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Create report service
        report_service = ReportService(db)
        
        if comprehensive:
            logger.info(f"⚙️ Running comprehensive algorithm for ALL unique stores...")
            logger.info(f"🔧 Data normalization: Missing timezone → America/Chicago, Missing hours → 24/7")
        else:
            logger.info(f"⚙️ Running limited algorithm for testing...")
        
        start_time = time.time()
        result = report_service.generate_actual_store_report(report_id, comprehensive)
        end_time = time.time()
        
        processing_time = end_time - start_time
        logger.info(f"⏱️ Algorithm completed in {processing_time:.2f} seconds")
        
        if result["success"]:
            file_url = result["url"]
            
            logger.info(f"📊 Report Summary:")
            if comprehensive:
                logger.info(f"   - Total Unique Stores: {result['total_stores']}")
                logger.info(f"   - Successfully Processed: {result['successfully_processed']}")
                logger.info(f"   - Processing Rate: {100 * result['successfully_processed'] / result['total_stores']:.1f}%")
            else:
                logger.info(f"   - Total Stores: {result['total_stores']}")
            
            logger.info(f"   - Algorithm: {result.get('algorithm', 'Comprehensive')}")
            logger.info(f"   - File: {file_url.replace('file://', '')}")
            
            # Print summary statistics
            summary = result.get("summary", {})
            if "averages" in summary:
                avg = summary["averages"]
                logger.info(f"   - Avg Uptime (hour): {avg.get('uptime_last_hour_minutes', 0):.1f} min")
                logger.info(f"   - Avg Uptime (day): {avg.get('uptime_last_day_hours', 0):.1f} hrs")
                logger.info(f"   - Avg Uptime (week): {avg.get('uptime_last_week_hours', 0):.1f} hrs")
            
            if comprehensive and "data_normalization" in summary:
                norm = summary["data_normalization"]
                logger.info(f"   - Default Timezone Applied: {norm.get('stores_with_default_timezone', 'N/A')}")
                logger.info(f"   - Default Hours Applied: {norm.get('stores_with_default_business_hours', 'N/A')}")
            
            return {
                "success": True,
                "url": file_url,
                "result": result
            }
        else:
            logger.error(f"❌ Report generation failed: {result.get('error')}")
            return {
                "success": False,
                "error": result.get("error")
            }
            
    except Exception as e:
        logger.error(f"❌ Exception during report generation: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        db.close()

def process_pending_report():
    """
    Complete workflow: find pending report and process it
    """
    logger.info("🔍 Looking for pending reports...")
    
    # Get pending report
    report_id = get_latest_pending_report()
    if not report_id:
        logger.info("ℹ️ No pending reports found")
        return False
    
    logger.info(f"📝 Found pending report: {report_id}")
    
    # Mark as running
    if not mark_report_running(report_id):
        return False
    
    # Generate the report (always comprehensive)
    result = generate_store_report(report_id, True)
    
    if result["success"]:
        # Mark as complete with URL
        return mark_report_complete(report_id, result["url"])
    else:
        # Mark as failed
        return mark_report_failed(report_id)

def main():
    """Main compute worker function"""
    
    print("🎯 Comprehensive Store Reports Compute Worker")
    print("=" * 55)
    print("Using Carry-Forward (Seed-Before) Interval Sweep Algorithm")
    print("📊 Processing ALL unique store IDs with data normalization")
    print()
    
    print("🔧 Data Normalization Rules:")
    print("   - Missing timezone → America/Chicago")
    print("   - Missing business hours → 24/7 operation")
    print("   - Processing every unique store ID found")
    print()
    
    # Process pending report
    success = process_pending_report()
    
    if success:
        print()
        print("✅ Store report generation completed successfully!")
        print("📁 Check the reports/ directory for the JSON output file")
        print("🔗 Use GET /reports/status?report_id=... to see the URL")
        print("📊 Comprehensive report includes ALL unique store IDs")
    else:
        print()
        print("❌ Store report generation failed or no pending reports")
    
    return success

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
