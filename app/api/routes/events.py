# File: app/api/routes/events.py
# Purpose: API endpoints for logging frontend events (clicks, choices).

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Json
from typing import Any, Dict
from app.db.session import get_db
from app.models.event import Event

router = APIRouter()

class EventCreate(BaseModel):
    session_id: int
    event_type: str
    payload: Dict[str, Any]

@router.post("/")
def log_event(event_data: EventCreate, db: Session = Depends(get_db)):
    new_event = Event(
        session_id=event_data.session_id,
        event_type=event_data.event_type,
        payload=event_data.payload
    )
    db.add(new_event)
    db.commit()
    return {"status": "ok"}
