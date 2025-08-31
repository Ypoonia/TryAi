#!/usr/bin/env python3
"""
Startup script for the complete Store Monitoring System
Starts Redis, Celery worker, and API server
"""

import subprocess
import time
import sys
import os
from pathlib import Path

def check_redis():
    """Check if Redis is running"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        return True
    except:
        return False

def start_redis():
    """Start Redis server"""
    print("🔴 Starting Redis server...")
    try:
        # Try to start Redis (this might fail if Redis is not installed)
        subprocess.run(["redis-server", "--daemonize", "yes"], check=True)
        time.sleep(2)  # Wait for Redis to start
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Redis not found or failed to start. Please install Redis manually:")
        print("   macOS: brew install redis")
        print("   Ubuntu: sudo apt-get install redis-server")
        return False

def start_celery_worker():
    """Start Celery worker"""
    print("🔄 Starting Celery worker...")
    worker_process = subprocess.Popen([
        sys.executable, "celery_worker.py"
    ])
    return worker_process

def start_api_server():
    """Start the API server"""
    print("🚀 Starting API server...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent)
    api_process = subprocess.Popen([
        sys.executable, "app/main_rcs.py"
    ], env=env)
    return api_process

def main():
    print("🏪 Store Monitoring System - Complete Startup")
    print("=" * 50)
    
    # Check/start Redis
    if not check_redis():
        if not start_redis():
            print("❌ Redis is required but not available. Exiting.")
            sys.exit(1)
    else:
        print("✅ Redis is already running")
    
    # Start Celery worker
    worker_process = start_celery_worker()
    print("✅ Celery worker started (PID: {})".format(worker_process.pid))
    
    # Start API server
    api_process = start_api_server()
    print("✅ API server started (PID: {})".format(api_process.pid))
    
    print("\n🎉 System is running!")
    print("📡 API: http://localhost:8001")
    print("📚 Docs: http://localhost:8001/docs")
    print("🔧 Worker: Celery worker processing reports")
    print("🔴 Redis: Message broker for tasks")
    print("\nPress Ctrl+C to stop all services")
    
    try:
        # Keep the script running
        worker_process.wait()
        api_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down services...")
        worker_process.terminate()
        api_process.terminate()
        print("✅ Services stopped")

if __name__ == "__main__":
    main()
