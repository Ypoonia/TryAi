# 🚀 Store Monitoring API - Postman Collection

## Base Configuration
- **Base URL**: `http://localhost:8001`
- **Content-Type**: `application/json`

---

## 📋 API Endpoints for Testing

### 1. 🏥 Health Check (Verify Server is Running)

**GET** `/health/`

```
Method: GET
URL: http://localhost:8001/health/
Headers: None required
Body: None
```

**Expected Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2025-09-01T01:52:00.000Z",
  "database": "connected",
  "message": "Store Monitoring System is operational"
}
```

---

### 2. 🔥 Trigger New Report

**POST** `/reports/trigger_report`

```
Method: POST
URL: http://localhost:8001/reports/trigger_report
Headers: 
  Content-Type: application/json
Body: {} (empty JSON object)
```

**Expected Responses:**

**New Report (202 Accepted):**
```json
{
  "report_id": "12345678-1234-1234-1234-123456789012",
  "status": "PENDING",
  "message": "Report generation started"
}
```

**Headers:**
```
Retry-After: 60
```

**Existing Active Report (200 OK):**
```json
{
  "report_id": "existing-report-id",
  "status": "RUNNING",
  "message": "Report generation already in progress"
}
```

**Headers:**
```
Retry-After: 30
```

---

### 3. 📊 Get Report Status

**GET** `/reports/get_report/{report_id}`

Replace `{report_id}` with actual report ID from trigger response.

```
Method: GET
URL: http://localhost:8001/reports/get_report/12345678-1234-1234-1234-123456789012
Headers: None required
Body: None
```

**Expected Responses:**

**Pending/Running Report (200 OK):**
```json
{
  "report_id": "12345678-1234-1234-1234-123456789012",
  "status": "RUNNING"
}
```

**Headers:**
```
Retry-After: 15
```

**Completed Report (200 OK):**
```json
{
  "report_id": "12345678-1234-1234-1234-123456789012",
  "status": "COMPLETED",
  "url": "/files/reports/12345678-1234-1234-1234-123456789012.csv"
}
```

**Failed Report (200 OK):**
```json
{
  "report_id": "12345678-1234-1234-1234-123456789012",
  "status": "FAILED"
}
```

**Report Not Found (404 Not Found):**
```json
{
  "detail": "Report invalid-id not found"
}
```

---

## 🧪 Test Scenarios

### Scenario 1: Complete Flow Test
1. **Health Check** → Verify server is running
2. **Trigger Report** → Get report_id 
3. **Check Status** → Poll until COMPLETED or FAILED
4. **Download** → Use URL from completed response

### Scenario 2: Idempotent Behavior Test
1. **Trigger Report** → Get first report_id
2. **Trigger Report Again** → Should return same report_id with "already in progress"
3. **Wait for completion**
4. **Trigger Report** → Should create new report

### Scenario 3: Error Handling Test
1. **Get Invalid Report** → Use non-existent report_id
2. **Malformed Request** → Test with invalid data

---

## 📝 Postman Collection JSON

Copy this into Postman to import the complete collection:

```json
{
  "info": {
    "name": "Store Monitoring API",
    "description": "Enhanced Store Monitoring System with idempotent report generation",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {
      "key": "baseUrl",
      "value": "http://localhost:8001",
      "type": "string"
    },
    {
      "key": "reportId",
      "value": "",
      "type": "string"
    }
  ],
  "item": [
    {
      "name": "Health Check",
      "request": {
        "method": "GET",
        "header": [],
        "url": {
          "raw": "{{baseUrl}}/health/",
          "host": ["{{baseUrl}}"],
          "path": ["health", ""]
        }
      },
      "response": []
    },
    {
      "name": "Trigger Report",
      "event": [
        {
          "listen": "test",
          "script": {
            "exec": [
              "if (pm.response.code === 202 || pm.response.code === 200) {",
              "    const response = pm.response.json();",
              "    pm.collectionVariables.set('reportId', response.report_id);",
              "    console.log('Report ID saved:', response.report_id);",
              "}"
            ]
          }
        }
      ],
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{}"
        },
        "url": {
          "raw": "{{baseUrl}}/reports/trigger_report",
          "host": ["{{baseUrl}}"],
          "path": ["reports", "trigger_report"]
        }
      },
      "response": []
    },
    {
      "name": "Get Report Status",
      "request": {
        "method": "GET",
        "header": [],
        "url": {
          "raw": "{{baseUrl}}/reports/get_report/{{reportId}}",
          "host": ["{{baseUrl}}"],
          "path": ["reports", "get_report", "{{reportId}}"]
        }
      },
      "response": []
    },
    {
      "name": "Get Report Status (Manual ID)",
      "request": {
        "method": "GET",
        "header": [],
        "url": {
          "raw": "{{baseUrl}}/reports/get_report/test-report-id",
          "host": ["{{baseUrl}}"],
          "path": ["reports", "get_report", "test-report-id"]
        }
      },
      "response": []
    }
  ]
}
```

---

## ⚡ Quick Start Commands

### Start the Server:
```bash
cd /Users/ayushmac/Desktop/FinalLoop
python -m uvicorn app.main_rcs:app --host 127.0.0.1 --port 8001 --reload
```

### Test with cURL:
```bash
# Health check
curl -X GET http://localhost:8001/health/

# Trigger report
curl -X POST http://localhost:8001/reports/trigger_report \
  -H "Content-Type: application/json" \
  -d '{}'

# Check status (replace with actual report_id)
curl -X GET http://localhost:8001/reports/get_report/YOUR_REPORT_ID
```

---

## 🎯 Expected Behavior

### HTTP Status Codes:
- **200**: Success (health, existing report, status found)
- **202**: Accepted (new report triggered)
- **404**: Report not found
- **500**: Server error

### HTTP Headers:
- **Retry-After**: Polling guidance in seconds
  - `60`: New report processing time estimate
  - `30`: Existing report check interval
  - `15`: Active report polling interval

### Status Values:
- **PENDING**: Report created, not yet started
- **RUNNING**: Report generation in progress
- **COMPLETED**: Report ready with download URL
- **FAILED**: Report generation failed

---

## 🔍 Monitoring Tips

1. **Watch Headers**: Use Retry-After for intelligent polling
2. **Save Report IDs**: Store from trigger response for status checks
3. **Check Logs**: Server logs show detailed processing info
4. **Test Idempotent**: Trigger multiple times to verify behavior
5. **Validate URLs**: Completed reports include download URLs

---

## 🚀 Ready to Test!

Your enhanced Store Monitoring API is ready for comprehensive testing with proper idempotent behavior, enhanced error handling, and clean HTTP responses!
