# File: app/api/routes/sessions.py
# Purpose: API endpoints for managing experiment sessions.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.session import get_db
from app.models.participant import Participant
from app.models.session import Session as SessionModel
from app.services.experiment_logic import experiment_logic

router = APIRouter()

class SessionStartRequest(BaseModel):
    participant_code: str
    record_video: bool = False 
    monitor_inches: float = 17.3  
    camera_pos: str = "top"  

class SessionResponse(BaseModel):
    session_id: int
    participant_code: str

class ScreenConfig(BaseModel):
    screen_w: int
    screen_h: int
    window_w: int
    window_h: int
    window_x: int
    window_y: int

@router.post("/{session_id}/screen_config")
def update_screen_config(session_id: int, config: ScreenConfig, db: Session = Depends(get_db)):
    """Get screen dimensions from frontend and send to GazeTracker"""
  
    config_dict = config.dict()
   
    from app.services.gaze_tracker import gaze_tracker
    gaze_tracker.update_screen_config(config_dict)
    
    return {"status": "updated"}

@router.post("/start", response_model=SessionResponse)
def start_session(req: SessionStartRequest, db: Session = Depends(get_db)):
    # Find or create participant
    participant = db.query(Participant).filter(Participant.code == req.participant_code).first()
    if not participant:
        participant = Participant(code=req.participant_code)
        db.add(participant)
        db.commit()
        db.refresh(participant)
    
    # Create session
    new_session = SessionModel(participant_id=participant.id)
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    # Adjusting monitor size and camera position
    from app.services.gaze_tracker import gaze_tracker
    gaze_tracker.set_monitor_size(req.monitor_inches)
    gaze_tracker.set_camera_pos(req.camera_pos) 

    # Sending recording settings to Logic
    experiment_logic.start_session(new_session.id, record_video=req.record_video)
    
    return {"session_id": new_session.id, "participant_code": participant.code}


class ContextUpdate(BaseModel):
    context: str
    stimulus_id: int | None = None

@router.post("/{session_id}/context")
def update_context(session_id: int, data: ContextUpdate, db: Session = Depends(get_db)):
    """
    Update the current tracking context (e.g., 'map', 'landing', 'route_choice').
    """
   
    experiment_logic.set_context(data.context, data.stimulus_id)
    return {"status": "context_updated", "current": data.context}



@router.post("/{session_id}/stop")
def stop_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Stop experiment logic
    experiment_logic.stop_session()
    
    # Update end time
    from sqlalchemy.sql import func
    session.ended_at = func.now()
    db.commit()
    
    return {"message": "Session stopped"}

# --- Calibration ---
class CalibrationPoint(BaseModel):
    x: float
    y: float

@router.post("/{session_id}/calibration/point")
def record_calibration_point(session_id: int, point: CalibrationPoint):
    """The frontend calls this when the user looks at the red dot"""
    from app.services.gaze_tracker import gaze_tracker
    success = gaze_tracker.store_calibration_point(point.x, point.y)
    return {"status": "recorded" if success else "failed"}

@router.post("/{session_id}/calibration/train")
def train_calibration(session_id: int):
    """End of calibration and model training"""
    from app.services.gaze_tracker import gaze_tracker
    success = gaze_tracker.train_calibration()
    return {"status": "calibrated" if success else "failed"}

@router.post("/{session_id}/calibration/reset")
def reset_calibration(session_id: int):
    from app.services.gaze_tracker import gaze_tracker
    gaze_tracker.reset_calibration()
    return {"status": "reset"}

