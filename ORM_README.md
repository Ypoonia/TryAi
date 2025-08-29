# 🚀 **Store Monitoring System API with SQLAlchemy ORM**

## 📋 **Overview**

This project has been refactored to use **SQLAlchemy ORM** instead of raw SQL queries, providing:

- **Better code organization** with separate models, schemas, and database layers
- **Type safety** with Pydantic validation
- **Easier maintenance** with ORM abstractions
- **Better error handling** with proper transaction management
- **Cleaner API code** with dependency injection

## 🏗️ **Architecture**

### **File Structure**
```
├── models.py          # SQLAlchemy ORM models
├── schemas.py         # Pydantic schemas for API validation
├── database.py        # Database operations and CRUD functions
├── main_orm.py        # FastAPI server using ORM
├── requirements.txt   # Updated dependencies
└── ORM_README.md     # This file
```

### **Layers**
1. **Models Layer** (`models.py`) - Database table definitions
2. **Schemas Layer** (`schemas.py`) - API request/response validation
3. **Database Layer** (`database.py`) - CRUD operations and database logic
4. **API Layer** (`main_orm.py`) - FastAPI endpoints using ORM

## 🗄️ **Database Models**

### **Report Model**
```python
class Report(Base):
    __tablename__ = "reports"
    __table_args__ = {"schema": "raw"}
    
    report_id = Column(String, primary_key=True, index=True)
    status = Column(String, nullable=False)
    url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

**Features:**
- ✅ **Automatic timestamps** with `created_at` and `updated_at`
- ✅ **Status validation** with CHECK constraint
- ✅ **Schema isolation** in `raw` schema
- ✅ **Indexing** on `report_id` for fast lookups

## 🔧 **Database Operations**

### **ReportCRUD Class**
```python
class ReportCRUD:
    @staticmethod
    def create_report(db: Session, report_id: str, status: str = "PENDING") -> Report
    @staticmethod
    def get_report_by_id(db: Session, report_id: str) -> Optional[Report]
    @staticmethod
    def get_latest_pending_report(db: Session) -> Optional[Report]
    @staticmethod
    def update_report_status(db: Session, report_id: str, new_status: str) -> Optional[Report]
    @staticmethod
    def get_all_reports(db: Session, skip: int = 0, limit: int = 100)
    @staticmethod
    def delete_report(db: Session, report_id: str) -> bool
```

**Benefits:**
- 🎯 **Centralized operations** - All database logic in one place
- 🔒 **Transaction safety** - Automatic rollback on errors
- 📝 **Comprehensive logging** - Track all database operations
- 🚀 **Reusable functions** - Easy to extend and maintain

## 📡 **API Endpoints**

### **Core Endpoints**
| Method | Endpoint | Description | Response Model |
|--------|----------|-------------|----------------|
| `POST` | `/trigger_report` | Create new report (if no PENDING exists) | `ReportResponse` |
| `GET` | `/get_report?report_id=<id>` | Get report status | `ReportStatusResponse` |
| `GET` | `/current_report` | Get current active report from JSON | `CurrentReportResponse` |
| `GET` | `/pending_status` | Check if PENDING report exists | `PendingStatusResponse` |
| `GET` | `/healthz` | Health check with DB status | `HealthResponse` |

### **Enhanced Features**
- 🚫 **Single PENDING enforcement** - Prevents multiple pending reports
- 📊 **Detailed status responses** - Rich information about report states
- 🔍 **Comprehensive error handling** - Proper HTTP status codes
- 📝 **Structured logging** - Track all API operations

## 🚀 **Getting Started**

### **1. Install Dependencies**
```bash
pip install -r requirements.txt
```

### **2. Create Database Tables**
```bash
python models.py
```

### **3. Start the Server**
```bash
python main_orm.py
```

### **4. Test the API**
```bash
# Health check
curl "http://localhost:8001/healthz"

# Check pending status
curl "http://localhost:8001/pending_status"

# Trigger new report
curl -X POST "http://localhost:8001/trigger_report"

# Get report status
curl "http://localhost:8001/get_report?report_id=<report_id>"
```

## 🔄 **Migration from Raw SQL**

### **Before (Raw SQL)**
```python
# Old way - Raw SQL with psycopg2
cur.execute(
    "INSERT INTO raw.reports (report_id, status) VALUES (%s, 'PENDING')",
    (rid,),
)
conn.commit()
```

### **After (SQLAlchemy ORM)**
```python
# New way - ORM with dependency injection
@app.post("/trigger_report")
def trigger_report(db: Session = Depends(get_db)):
    db_report = ReportCRUD.create_report(db, rid, "PENDING")
    return ReportResponse(report_id=rid)
```

## 🎯 **Key Benefits of ORM**

### **1. Type Safety**
- ✅ **Pydantic validation** for all API inputs/outputs
- ✅ **SQLAlchemy models** with proper column types
- ✅ **IDE autocomplete** and error detection

### **2. Code Organization**
- ✅ **Separation of concerns** - Models, schemas, operations, API
- ✅ **Reusable components** - CRUD functions, validation schemas
- ✅ **Cleaner main file** - Focus on API logic, not database details

### **3. Error Handling**
- ✅ **Automatic rollbacks** on database errors
- ✅ **Structured logging** for debugging
- ✅ **Proper HTTP status codes** for different error types

### **4. Maintainability**
- ✅ **Easy to modify** database schema
- ✅ **Simple to add** new endpoints
- ✅ **Consistent patterns** across all operations

## 🔧 **Configuration**

### **Database Connection**
```python
DATABASE_URL = (
    "postgresql://neondb_owner:npg_HNBZ6c8dUnuC@"
    "ep-fragrant-snow-a1gvjf6b-pooler.ap-southeast-1.aws.neon.tech/"
    "neondb?sslmode=require"
)
```

### **Session Management**
```python
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## 📊 **Testing the ORM**

### **Test Commands**
```bash
# 1. Start server
python main_orm.py

# 2. Check health
curl "http://localhost:8001/healthz"

# 3. Check pending status
curl "http://localhost:8001/pending_status"

# 4. Try to trigger report (will fail if PENDING exists)
curl -X POST "http://localhost:8001/trigger_report"

# 5. Get current report
curl "http://localhost:8001/current_report"
```

## 🚀 **Next Steps**

### **Potential Enhancements**
1. **Database Migrations** - Use Alembic for schema versioning
2. **Connection Pooling** - Optimize database connections
3. **Caching Layer** - Redis for frequently accessed data
4. **Background Tasks** - Celery for async report processing
5. **API Documentation** - Enhanced OpenAPI/Swagger docs

### **Production Considerations**
- 🔒 **Environment variables** for database credentials
- 📊 **Connection pooling** for high traffic
- 🚨 **Monitoring and alerting** for database health
- 🔄 **Database backups** and recovery procedures

## 📝 **Summary**

The refactoring to SQLAlchemy ORM provides:

- **Better code structure** with clear separation of concerns
- **Enhanced type safety** through Pydantic and SQLAlchemy
- **Improved maintainability** with centralized database operations
- **Professional-grade architecture** suitable for production use
- **Easy extensibility** for future features

Your FastAPI server now follows industry best practices and is ready for production deployment! 🎉
