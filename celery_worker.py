#!/usr/bin/env python3
"""
Celery worker for async report generation
"""

import os
import sys

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.celery_app import celery_app

if __name__ == "__main__":
    print("🚀 Starting Celery Worker for Store Monitoring System")
    print("📊 Queue: reports")
    print("🔧 Broker: Redis")
    print("=" * 50)
    
    # Start the worker
    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        "--queues=reports",
        "--concurrency=1",
        "--hostname=store-monitoring-worker@%h"
    ])
