# Store Monitoring System API

FastAPI server for the TryLoop repository providing minimal APIs for report management.

## 🚀 Quick Start

### Installation
```bash
pip install -r requirements.txt
```

### Run the Server
```bash
python main.py
```

The server will start on `http://localhost:8000`

## 📚 API Endpoints

### 1. POST /trigger_report

Triggers a new report generation.

**Request:**
```bash
POST /trigger_report
```

**Response:**
```json
{
  "report_id": "1735481234567890-123456"
}
```

**What happens:**
1. Generates unique `report_id` (timestamp_ns + 6-digit random)
2. Inserts row into `raw.reports` with `status='PENDING'`
3. Spawns background task placeholder (status updates will be handled manually in next step)
4. Returns the `report_id` immediately

### 2. GET /get_report

Gets the current status of a report.

**Request:**
```bash
GET /get_report?report_id=1735481234567890-123456
```

**Response Examples:**

**PENDING/RUNNING Status:**
```json
{
  "status": "Running",
  "report_id": "1735481234567890-123456"
}
```

**COMPLETE Status:**
```json
{
  "status": "Complete",
  "report_id": "1735481234567890-123456"
}
```

**FAILED Status:**
```json
{
  "status": "Failed",
  "report_id": "1735481234567890-123456"
}
```

**Report Not Found:**
```json
{
  "detail": "Report not found"
}
```

### 3. GET /

Root endpoint with API information.

**Response:**
```json
{
  "message": "Store Monitoring System API",
  "version": "1.0.0",
  "endpoints": {
    "POST /trigger_report": "Trigger a new report generation",
    "GET /get_report?report_id=<id>": "Get report status"
  }
}
```

### 4. GET /health

Health check endpoint to verify database connectivity.

**Response:**
```json
{
  "status": "healthy",
  "database": "connected"
}
```

## 🗄️ Database Schema

The API uses the `raw.reports` table:

```sql
CREATE TABLE raw.reports (
  report_id TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('PENDING','RUNNING','COMPLETE','FAILED')),
  url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 🔄 Report Lifecycle

1. **PENDING** → Report created, background task placeholder started
2. **Status updates will be handled manually in the next step**
3. **No automatic progression** - all status changes will be manual

## 🧪 Testing the API

### Using curl

**Trigger a report:**
```bash
curl -X POST "http://localhost:8000/trigger_report"
```

**Check report status:**
```bash
curl "http://localhost:8000/get_report?report_id=YOUR_REPORT_ID"
```

### Using Python requests

```python
import requests

# Trigger report
response = requests.post("http://localhost:8000/trigger_report")
report_id = response.json()["report_id"]
print(f"Report ID: {report_id}")

# Check status
status_response = requests.get(f"http://localhost:8000/get_report?report_id={report_id}")
print(f"Status: {status_response.json()}")
```

## 📝 Logs

The API provides detailed logging for:
- Report creation and status changes
- Background task processing
- Database connection status
- Error handling

## 🔧 Configuration

- **Database**: Neon PostgreSQL (configured in `DATABASE_URL`)
- **Port**: 8000 (configurable in `main.py`)
- **Host**: 0.0.0.0 (accessible from any IP)

## 🚨 Error Handling

- **400**: Bad request
- **404**: Report not found
- **500**: Internal server error (database connection, processing failures)

## 📊 Background Tasks

The API uses FastAPI's `BackgroundTasks` to:
- Create reports asynchronously
- Provide a placeholder for future manual status updates
- Maintain responsive API endpoints
- **Note**: Status updates will be handled manually in the next step
