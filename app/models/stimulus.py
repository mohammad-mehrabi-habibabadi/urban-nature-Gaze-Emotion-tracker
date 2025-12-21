# File: app/models/stimulus.py
# Purpose: SQLAlchemy model for stimuli with Map Coordinates.

from sqlalchemy import Column, Integer, String, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.models.base import Base

class Stimulus(Base):
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String) # 'neighborhood', 'poi', 'route'
    name = Column(String)
    neighborhood_id = Column(Integer, ForeignKey("stimulus.id"), nullable=True)
    description = Column(Text, nullable=True)
    media_path = Column(String, nullable=True)
    
    # --- New fields for coordinates on the map ---
    # These are percentages (e.g. 50.5 means middle of the page)
    map_x = Column(Float, default=0.0) 
    map_y = Column(Float, default=0.0)

    neighborhood = relationship("Stimulus", remote_side=[id], backref="pois")