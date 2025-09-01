#!/usr/bin/env python3
"""Database setup and configuration"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

# Database connection
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.SQLALCHEMY_ECHO,
    pool_pre_ping=True,
    pool_recycle=3600
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base model class
Base = declarative_base()


def get_database_session():
    """Get database session for FastAPI"""
    session = SessionLocal()
    try:
        yield session
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def create_all_tables():
    """Create database tables"""
    Base.metadata.create_all(bind=engine)


def drop_all_tables():
    """Drop all database tables - USE CAREFULLY!"""
    Base.metadata.drop_all(bind=engine)


# Legacy aliases
get_db = get_database_session
create_tables = create_all_tables

