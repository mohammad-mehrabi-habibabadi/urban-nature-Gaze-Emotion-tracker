# File: app/api/routes/stimuli.py
# Purpose: API endpoints for fetching stimuli with MAP COORDINATES.

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.db.session import get_db
from app.models.stimulus import Stimulus
from app.services.experiment_logic import experiment_logic

router = APIRouter()


class StimulusSchema(BaseModel):
    id: int
    type: str
    name: str
    description: Optional[str] = None
    media_path: Optional[str] = None
    neighborhood_id: Optional[int] = None
    

    map_x: float = 0.0
    map_y: float = 0.0
    
    class Config:
        orm_mode = True
        extra = "ignore"



@router.get("/neighborhoods", response_model=List[StimulusSchema])
def get_neighborhoods(db: Session = Depends(get_db)):
    return db.query(Stimulus).filter(Stimulus.type == "neighborhood").all()

@router.get("/neighborhoods/{neighborhood_id}/pois", response_model=List[StimulusSchema])
def get_pois(neighborhood_id: int, db: Session = Depends(get_db)):
    return db.query(Stimulus).filter(Stimulus.type == "poi", Stimulus.neighborhood_id == neighborhood_id).all()

@router.get("/routes", response_model=List[StimulusSchema])
def get_routes(db: Session = Depends(get_db)):
    return db.query(Stimulus).filter(Stimulus.type == "route").all()

@router.post("/stop_viewing")
def stop_viewing_stimulus():
    """
    Notify the backend that the user has stopped viewing a specific stimulus.
    """
    experiment_logic.clear_stimulus()
    return {"message": "Stopped viewing stimulus"}

@router.get("/{stimulus_id}", response_model=StimulusSchema)
def get_stimulus(stimulus_id: int, db: Session = Depends(get_db)):
    # Also notify experiment logic that we are viewing this stimulus
    experiment_logic.set_context("stimulus_view", stimulus_id)
    return db.query(Stimulus).filter(Stimulus.id == stimulus_id).first()