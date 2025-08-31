#!/usr/bin/env python3
"""
Quick test script to verify the updated endpoints
"""

import requests
import time
import json

BASE_URL = "http://127.0.0.1:8001"

def test_trigger_report():
    """Test the trigger_report endpoint"""
    print("🚀 Testing POST /reports/trigger_report")
    
    try:
        response = requests.post(f"{BASE_URL}/reports/trigger_report")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 202:
            return response.json().get('report_id')
        else:
            print("❌ Trigger report failed")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_get_report(report_id):
    """Test the get_report endpoint"""
    print(f"\n📊 Testing GET /reports/get_report?report_id={report_id}")
    
    try:
        response = requests.get(f"{BASE_URL}/reports/get_report?report_id={report_id}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("✅ Get report successful")
        else:
            print("❌ Get report failed")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    print("🔧 Testing Updated Endpoints")
    print("="*50)
    
    # Test trigger report
    report_id = test_trigger_report()
    
    if report_id:
        # Test get report
        test_get_report(report_id)
        
        # Test with non-existent report ID
        print(f"\n🧪 Testing with fake report ID")
        test_get_report("fake-report-id-12345")
    
    print("\n✅ Testing completed!")

if __name__ == "__main__":
    main()
