# File: app/models/participant.py
# Purpose: SQLAlchemy model for participants.

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.models.base import Base

class Participant(Base):
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=func.now())
