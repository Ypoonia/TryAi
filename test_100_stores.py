#!/usr/bin/env python3
"""
Test script to check the algorithm on 100 stores
"""

import sys
import os
import logging
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.minute_index_report_service import MinuteIndexReportService
from app.core.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_100_stores():
    """Test the algorithm on 100 stores"""

    print("🧪 Testing Algorithm on 100 Stores")
    print("=" * 50)

    # Create database connection
    database_url = settings.DATABASE_URL
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # Create service
    service = MinuteIndexReportService(db)

    # Generate a proper report with ID
    import time
    report_id = f"test_{int(time.time() * 1000)}"
    print(f"📝 Creating test report: {report_id}")
    print()

    # Use the proper report generation method
    result = service.generate_store_report(report_id, max_stores=100)

    if result["success"]:
        print("✅ Report generated successfully!")
        print(f"📊 Total stores processed: {result['total_stores']}")
        print(f"📁 Report file: {result['file_path']}")
        print(f"⏰ Generated at: {result['generated_at']}")
        print(f"🔧 Algorithm: {result['algorithm']}")
        
        # Show summary
        summary = result.get('summary', {})
        if summary:
            print("\n📈 Summary Statistics:")
            print(f"  • Total stores: {summary.get('total_stores', 'N/A')}")
            print(f"  • Successfully processed: {summary.get('successful_stores', 'N/A')}")
            print(f"  • Failed stores: {summary.get('failed_stores', 'N/A')}")
            print(f"  • Success rate: {summary.get('success_rate', 'N/A')}%")
    else:
        print("❌ Report generation failed!")
        print(f"Error: {result.get('error', 'Unknown error')}")

    return result


if __name__ == "__main__":
    test_100_stores()
