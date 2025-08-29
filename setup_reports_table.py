#!/usr/bin/env python3
"""
Setup Reports Table in Neon Database
Creates reports table in raw schema with triggers and indexes
"""

import psycopg2
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection string
DB_URL = "postgresql://neondb_owner:npg_HNBZ6c8dUnuC@ep-fragrant-snow-a1gvjf6b-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def setup_reports_table(cursor):
    """Setup the raw.reports table with all features"""
    
    # Create reports table in raw schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw.reports (
          report_id TEXT PRIMARY KEY,
          status    TEXT NOT NULL CHECK (status IN ('PENDING','RUNNING','COMPLETE','FAILED')),
          url       TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    logger.info("Created raw.reports table")
    
    # Create function for auto-updating updated_at
    cursor.execute("""
        CREATE OR REPLACE FUNCTION raw_set_updated_at() RETURNS trigger AS $$
        BEGIN
          NEW.updated_at := now();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    logger.info("Created raw_set_updated_at function")
    
    # Create trigger for auto-updating updated_at
    cursor.execute("""
        DROP TRIGGER IF EXISTS trg_reports_updated_at ON raw.reports
    """)
    cursor.execute("""
        CREATE TRIGGER trg_reports_updated_at
        BEFORE UPDATE ON raw.reports
        FOR EACH ROW EXECUTE FUNCTION raw_set_updated_at()
    """)
    logger.info("Created trigger for auto-updating updated_at")
    
    # Create index on status
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reports_status ON raw.reports(status)
    """)
    logger.info("Created index on status column")

def test_reports_table(cursor, conn):
    """Test the reports table functionality"""
    
    # Insert test data
    cursor.execute("""
        INSERT INTO raw.reports (report_id, status) 
        VALUES ('test-123', 'PENDING')
    """)
    logger.info("Inserted test record")
    
    # Query test data
    cursor.execute("""
        SELECT * FROM raw.reports WHERE report_id='test-123'
    """)
    test_row = cursor.fetchone()
    logger.info(f"Test record: {test_row}")
    
    # Test status constraint with proper transaction handling
    try:
        cursor.execute("""
            INSERT INTO raw.reports (report_id, status) 
            VALUES ('test-invalid', 'INVALID_STATUS')
        """)
        logger.error("Status constraint failed - should have rejected invalid status")
    except Exception as e:
        logger.info(f"Status constraint working correctly: {str(e)}")
        # Rollback to clear the failed transaction state
        conn.rollback()
        # Reconnect cursor for next operations
        cursor = conn.cursor()
    
    # Test updated_at trigger
    cursor.execute("""
        UPDATE raw.reports 
        SET status = 'RUNNING' 
        WHERE report_id = 'test-123'
    """)
    
    cursor.execute("""
        SELECT report_id, status, created_at, updated_at 
        FROM raw.reports 
        WHERE report_id = 'test-123'
    """)
    updated_row = cursor.fetchone()
    logger.info(f"Updated record: {updated_row}")
    
    # Clean up test data
    cursor.execute("DELETE FROM raw.reports WHERE report_id = 'test-123'")
    logger.info("Cleaned up test data")

def main():
    """Main function to setup reports table"""
    
    try:
        # Connect to database
        logger.info("Connecting to Neon database...")
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = False
        cursor = conn.cursor()
        
        # Setup reports table
        logger.info("Setting up raw.reports table...")
        setup_reports_table(cursor)
        
        # Commit the table creation
        conn.commit()
        logger.info("Table structure committed")
        
        # Test the functionality
        logger.info("Testing reports table functionality...")
        test_reports_table(cursor, conn)
        
        # Commit all changes
        conn.commit()
        logger.info("✅ Reports table setup completed successfully!")
        
        # Show final table structure
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_schema = 'raw' AND table_name = 'reports'
            ORDER BY ordinal_position
        """)
        
        logger.info("\n=== Final Table Structure ===")
        for row in cursor.fetchall():
            logger.info(f"{row[0]}: {row[1]} {'NULL' if row[2] == 'YES' else 'NOT NULL'} {row[3] or ''}")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        raise
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        logger.info("Database connection closed")

if __name__ == "__main__":
    main()
