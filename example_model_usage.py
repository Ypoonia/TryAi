#!/usr/bin/env python3
"""
Example Usage of Enhanced Store Monitoring Models

This script demonstrates how to use the improved, human-readable models
in the Store Monitoring System.
"""

import sys
sys.path.append('.')

from app.models import Report, get_database_session, create_all_tables, get_table_info
from datetime import datetime


def demonstrate_model_usage():
    """Demonstrate the enhanced model features."""
    
    print("🏪 Store Monitoring System - Model Demonstration")
    print("=" * 60)
    
    # 1. Show table information
    print("\n📊 Database Table Information:")
    tables = get_table_info()
    for table_name, info in tables.items():
        print(f"  Table: {table_name}")
        print(f"    Columns: {', '.join(info['columns'])}")
        print(f"    Primary Keys: {', '.join(info['primary_keys'])}")
    
    # 2. Create a sample report for demonstration
    print("\n📝 Creating Sample Report...")
    
    # Get a database session
    db_session = next(get_database_session())
    
    try:
        # Create a sample report
        sample_report = Report(
            report_id="demo-report-12345",
            status="PENDING"
        )
        
        # Demonstrate the enhanced properties and methods
        print(f"\n📋 Report Information:")
        print(f"  ID: {sample_report.report_id}")
        print(f"  Status: {sample_report.status}")
        print(f"  Description: {sample_report.get_display_status()}")
        print(f"  Is Pending: {sample_report.is_pending}")
        print(f"  Is Running: {sample_report.is_running}")
        print(f"  Is Complete: {sample_report.is_complete}")
        print(f"  Is Finished: {sample_report.is_finished}")
        print(f"  Has File: {sample_report.has_file}")
        
        # Show string representations
        print(f"\n📄 String Representations:")
        print(f"  repr(): {repr(sample_report)}")
        print(f"  str():  {str(sample_report)}")
        
        # Show summary dictionary
        print(f"\n📊 Summary Dictionary:")
        summary = sample_report.to_summary_dict()
        for key, value in summary.items():
            print(f"    {key}: {value}")
        
        # Simulate status changes
        print(f"\n🔄 Simulating Status Changes:")
        
        # Change to RUNNING
        sample_report.status = "RUNNING"
        print(f"  → Status changed to: {sample_report.get_display_status()}")
        print(f"    Is Running: {sample_report.is_running}")
        
        # Change to COMPLETE with file
        sample_report.status = "COMPLETE"
        sample_report.url = "file://reports/demo-report-12345.csv"
        print(f"  → Status changed to: {sample_report.get_display_status()}")
        print(f"    Is Complete: {sample_report.is_complete}")
        print(f"    Has File: {sample_report.has_file}")
        print(f"    File URL: {sample_report.url}")
        
        print(f"\n✅ Model demonstration completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during demonstration: {e}")
    finally:
        db_session.close()


def show_existing_reports():
    """Show information about existing reports in the database."""
    
    print("\n🗃️  Existing Reports in Database:")
    print("-" * 40)
    
    db_session = next(get_database_session())
    
    try:
        reports = db_session.query(Report).all()
        
        if not reports:
            print("  No reports found in database.")
            return
        
        for i, report in enumerate(reports, 1):
            print(f"\n  Report #{i}:")
            print(f"    {str(report)}")
            print(f"    Description: {report.get_display_status()}")
            if report.has_file:
                print(f"    File: {report.url}")
            if report.age_in_minutes:
                print(f"    Age: {report.age_in_minutes:.1f} minutes")
            if report.processing_time_minutes:
                print(f"    Processing Time: {report.processing_time_minutes:.1f} minutes")
                
    except Exception as e:
        print(f"❌ Error reading reports: {e}")
    finally:
        db_session.close()


if __name__ == "__main__":
    # Ensure tables exist
    create_all_tables()
    
    # Run demonstrations
    demonstrate_model_usage()
    show_existing_reports()
    
    print(f"\n🎉 All demonstrations completed!")
    print(f"\nThe models are now more human-readable with:")
    print(f"  ✅ Better documentation and comments")
    print(f"  ✅ Helpful properties (is_pending, is_complete, etc.)")
    print(f"  ✅ User-friendly string representations")
    print(f"  ✅ Summary dictionaries for API responses")
    print(f"  ✅ Time calculation properties")
    print(f"  ✅ Enhanced error handling and type hints")
