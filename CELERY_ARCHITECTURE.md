# Store Monitoring System - Redis + Celery Architecture

## 🏗️ Architecture Overview

The system now uses **Redis + Celery** for asynchronous report generation, providing better scalability and reliability.

## 🔄 Flow Diagram

```
API Trigger (POST /reports/trigger)
    ↓
Creates report row in DB → status = PENDING
    ↓
Calls Celery task → generate_report.delay(report_id)
    ↓
Celery Worker (backed by Redis broker)
    ↓
Picks up generate_report(report_id)
    ↓
Marks report = RUNNING
    ↓
Runs MinuteIndexReportService to compute results (JSON + CSV)
    ↓
Saves output file path in DB
    ↓
Marks report = COMPLETE
    ↓
API Fetch (GET /reports/status?report_id=...)
    ↓
Returns status, url (to CSV file)
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Install Redis
```bash
# macOS
brew install redis

# Ubuntu
sudo apt-get install redis-server
```

### 3. Start the Complete System
```bash
python start_system.py
```

This will start:
- 🔴 **Redis** (message broker)
- 🔄 **Celery Worker** (background processing)
- 🚀 **API Server** (FastAPI)

## 📁 File Structure

```
├── app/
│   ├── celery_app.py          # Celery configuration
│   ├── tasks/
│   │   ├── __init__.py
│   │   └── report_tasks.py    # Celery tasks
│   └── services/
│       └── report_service.py  # Updated to use Celery
├── celery_worker.py           # Worker startup script
├── start_system.py           # Complete system startup
└── main_rcs.py              # API server
```

## 🔧 Components

### **Redis**
- **Role**: Message broker for Celery
- **Port**: 6379
- **Purpose**: Queues tasks, handles retries, stores results

### **Celery Worker**
- **Role**: Background task processor
- **Queue**: `reports`
- **Tasks**: `generate_report`
- **Concurrency**: 1 worker (can be scaled)

### **API Server**
- **Role**: HTTP interface
- **Port**: 8001
- **Endpoints**: 
  - `POST /reports/trigger` - Create and enqueue report
  - `GET /reports/status` - Check report status
  - `GET /files/reports/{filename}` - Download CSV

## 📊 Report Generation Flow

### 1. **API Trigger**
```bash
curl -X POST "http://localhost:8001/reports/trigger"
```

**Response:**
```json
{
  "report_id": "1756601234567890-123456",
  "status": "PENDING",
  "task_id": "abc123-def456"
}
```

### 2. **Background Processing**
- Celery worker picks up the task
- Processes 100 stores using MinuteIndexReportService
- Generates both JSON (metadata) and CSV (report)
- Updates database with results

### 3. **Status Check**
```bash
curl "http://localhost:8001/reports/status?report_id=1756601234567890-123456"
```

**Response:**
```json
{
  "report_id": "1756601234567890-123456",
  "status": "COMPLETED",
  "url": "/files/reports/1756601234567890-123456.csv"
}
```

## 📈 Benefits

### **Scalability**
- Multiple workers can process reports in parallel
- Redis handles task distribution and load balancing
- API server remains responsive during processing

### **Reliability**
- Tasks are persisted in Redis
- Automatic retries on failure
- Graceful error handling and status updates

### **Monitoring**
- Task status tracking
- Worker health monitoring
- Detailed logging at each step

## 🔍 Monitoring

### **Celery Monitoring**
```bash
# Check worker status
celery -A app.celery_app inspect active

# Check queue status
celery -A app.celery_app inspect stats
```

### **Redis Monitoring**
```bash
# Check Redis info
redis-cli info

# Monitor Redis commands
redis-cli monitor
```

## 🛠️ Troubleshooting

### **Redis Connection Issues**
```bash
# Check if Redis is running
redis-cli ping

# Start Redis manually
redis-server
```

### **Celery Worker Issues**
```bash
# Start worker manually
python celery_worker.py

# Check worker logs
celery -A app.celery_app worker --loglevel=debug
```

### **Task Failures**
- Check worker logs for error details
- Tasks automatically retry on failure
- Failed tasks are marked as "FAILED" in database

## 📝 Output Files

### **JSON File** (`{report_id}.json`)
- Rich metadata and algorithm details
- Used for debugging and analysis
- Contains full algorithm information

### **CSV File** (`{report_id}.csv`)
- Flat report format as required by assignment
- Contains store uptime/downtime data
- Ready for business users

## 🎯 Next Steps

1. **Scale Workers**: Add more Celery workers for higher throughput
2. **Add Monitoring**: Implement Celery Flower for web-based monitoring
3. **Add Caching**: Use Redis for caching frequently accessed data
4. **Add Alerts**: Implement notifications for failed reports
