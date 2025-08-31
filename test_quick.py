#!/usr/bin/env python3
"""
Quick test script to check the algorithm on 5 stores
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


def test_quick():
    """Test the algorithm on 5 stores"""

    print("🧪 Quick Test - 5 Stores")
    print("=" * 30)

    # Create database connection
    database_url = settings.DATABASE_URL
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # Create service
    service = MinuteIndexReportService(db)

    # Get 5 unique store IDs
    query = text("""
        SELECT DISTINCT store_id 
        FROM raw.store_status 
        ORDER BY store_id 
        LIMIT 5
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        store_ids = [row[0] for row in result]

    print(f"📊 Found {len(store_ids)} store IDs: {store_ids}")
    print()

    # Get max UTC timestamp
    max_utc_query = text("SELECT MAX(timestamp_utc) FROM raw.store_status")
    with engine.connect() as conn:
        result = conn.execute(max_utc_query)
        max_utc_str = result.fetchone()[0]
        if isinstance(max_utc_str, str):
            if 'UTC' in max_utc_str:
                max_utc_str = max_utc_str.replace(' UTC', '+00:00')
            max_utc = datetime.fromisoformat(max_utc_str)
        else:
            max_utc = max_utc_str

    print(f"⏰ Max UTC timestamp: {max_utc}")
    print()

    # Test each store
    for i, store_id in enumerate(store_ids):
        try:
            print(f"🔍 Processing store {i+1}/5: {store_id}")

            # Get timezone for this store (fallback if missing)
            tz_query = text("""
                SELECT timezone_str 
                FROM raw.timezones 
                WHERE store_id = :store_id
            """)

            with engine.connect() as conn:
                result = conn.execute(tz_query, {"store_id": store_id})
                tz_row = result.fetchone()
                tz_str = tz_row[0] if tz_row else "America/Chicago"

            print(f"  📍 Timezone: {tz_str}")

            # Process the store
            result = service._process_store_with_minute_index(store_id, tz_str, max_utc)

            if result:
                print(
                    f"  ✅ Success: "
                    f"uptime(day)={result['uptime_last_day']}h, "
                    f"downtime(day)={result['downtime_last_day']}h"
                )
            else:
                print(f"  ❌ Failed: No result returned")

        except Exception as e:
            print(f"  ❌ Error: {str(e)}")

    print("\n✅ Quick test completed!")


if __name__ == "__main__":
    test_quick()
