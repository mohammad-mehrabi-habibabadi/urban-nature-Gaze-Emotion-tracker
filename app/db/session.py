# File: app/db/session.py
# Purpose: Database session management.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# SQLite requires connect_args={"check_same_thread": False} for multithreading
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency for FastAPI to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
