#!/bin/bash

# 🚀 Quick API Test Script
# Run this to test your enhanced Store Monitoring API

echo "🔥 STORE MONITORING API - QUICK TEST"
echo "===================================="

BASE_URL="http://localhost:8001"

echo ""
echo "1️⃣ Testing Health Check..."
curl -s -X GET "$BASE_URL/health/" | jq '.' || echo "❌ Health check failed"

echo ""
echo "2️⃣ Triggering New Report..."
TRIGGER_RESPONSE=$(curl -s -X POST "$BASE_URL/reports/trigger_report" \
  -H "Content-Type: application/json" \
  -d '{}')

echo "$TRIGGER_RESPONSE" | jq '.'

# Extract report ID
REPORT_ID=$(echo "$TRIGGER_RESPONSE" | jq -r '.report_id // empty')

if [ -n "$REPORT_ID" ]; then
    echo ""
    echo "3️⃣ Checking Report Status..."
    echo "Report ID: $REPORT_ID"
    
    curl -s -X GET "$BASE_URL/reports/get_report/$REPORT_ID" | jq '.'
    
    echo ""
    echo "4️⃣ Testing Idempotent Behavior..."
    echo "Triggering report again (should return existing)..."
    curl -s -X POST "$BASE_URL/reports/trigger_report" \
      -H "Content-Type: application/json" \
      -d '{}' | jq '.'
    
    echo ""
    echo "5️⃣ Testing Error Handling..."
    echo "Checking invalid report ID..."
    curl -s -X GET "$BASE_URL/reports/get_report/invalid-id-12345" | jq '.'
    
else
    echo "❌ Failed to get report ID from trigger response"
fi

echo ""
echo "✅ API Test Complete!"
echo ""
echo "🔍 To monitor your report:"
echo "curl -X GET \"$BASE_URL/reports/get_report/$REPORT_ID\""
echo ""
echo "📋 Your Report ID: $REPORT_ID"
