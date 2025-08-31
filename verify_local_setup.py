#!/usr/bin/env python3
"""
Verify Local PostgreSQL Setup
Tests all database connections and configurations
"""

import psycopg2
import redis
from app.core.config import settings

def test_postgresql():
    """Test PostgreSQL connection"""
    print("🔍 Testing PostgreSQL connection...")
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor()
        
        # Test basic connectivity
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        print(f"✅ PostgreSQL connected: {version}")
        
        # Test schemas
        cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('public', 'raw')")
        schemas = [row[0] for row in cur.fetchall()]
        print(f"✅ Schemas available: {schemas}")
        
        # Test raw tables
        cur.execute("""
            SELECT table_name, 
                   (SELECT count(*) FROM information_schema.columns WHERE table_schema='raw' AND table_name=t.table_name) as column_count
            FROM information_schema.tables t 
            WHERE table_schema = 'raw'
            ORDER BY table_name
        """)
        tables = cur.fetchall()
        print("✅ Raw tables:")
        for table_name, col_count in tables:
            cur.execute(f"SELECT COUNT(*) FROM raw.{table_name}")
            row_count = cur.fetchone()[0]
            print(f"   - {table_name}: {row_count:,} rows, {col_count} columns")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL error: {e}")
        return False

def test_redis():
    """Test Redis connection"""
    print("\n🔍 Testing Redis connection...")
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        info = r.info()
        print(f"✅ Redis connected: version {info['redis_version']}")
        return True
    except Exception as e:
        print(f"❌ Redis error: {e}")
        return False

def test_config():
    """Test configuration settings"""
    print("\n🔍 Testing configuration...")
    print(f"✅ Database URL: {settings.DATABASE_URL}")
    print(f"✅ Server: {settings.SERVER_HOST}:{settings.SERVER_PORT}")
    print(f"✅ App: {settings.APP_TITLE} v{settings.APP_VERSION}")
    return True

def main():
    """Run all verification tests"""
    print("🚀 Verifying Local Setup for Store Monitoring System")
    print("=" * 50)
    
    tests = [
        ("PostgreSQL Database", test_postgresql),
        ("Redis Message Broker", test_redis),
        ("Configuration", test_config)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 VERIFICATION SUMMARY:")
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Local setup is ready.")
        print("💡 You can now run: python start_system.py")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
    
    return all_passed

if __name__ == "__main__":
    main()
