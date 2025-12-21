# File: app/models/event.py
# Purpose: SQLAlchemy model for logging experiment events (clicks, gaze, emotion, etc).

from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base

class Event(Base):
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("session.id"))
    timestamp = Column(DateTime, default=func.now())
    event_type = Column(String) # 'click', 'gaze', 'emotion', 'route_choice', 'page_view'
    payload = Column(JSON) # Flexible payload

    session = relationship("Session", backref="events")
