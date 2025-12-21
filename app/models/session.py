# File: app/models/session.py
# Purpose: SQLAlchemy model for experiment sessions.

from sqlalchemy import Column, Integer, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base

class Session(Base):
    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("participant.id"))
    started_at = Column(DateTime, default=func.now())
    ended_at = Column(DateTime, nullable=True)
    metadata_info = Column(JSON, nullable=True) # Renamed to avoid confusion with sqlalchemy metadata

    participant = relationship("Participant", backref="sessions")
