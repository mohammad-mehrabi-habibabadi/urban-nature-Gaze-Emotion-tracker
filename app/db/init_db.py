# File: app/db/init_db.py
# Purpose: Initialize DB and Ensure Map Coordinates are always correct (Self-Healing).

from app.db.session import engine, SessionLocal
from app.models.base import Base
from app.models.stimulus import Stimulus

def init_db():
    # Creating tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Always check and update data (Upsert Logic)
        sync_stimuli_data(db)
    finally:
        db.close()

def sync_stimuli_data(db):
    """
    This function ensures that the coordinates and names of the images are always consistent with the code.
    It will correct the database even if it is old.
    """
    
    # --- 1. Definition of Reference Data (Source of Truth) ---
    neighborhoods_data = [
        {"name": "Luxury", "desc": "North-West District", "img": "img/map_luxury.jpg", "x": 20.0, "y": 25.0},
        {"name": "Traditional", "desc": "Old Town Center", "img": "img/map_traditional.jpg", "x": 75.0, "y": 30.0},
        {"name": "Modern", "desc": "Business District", "img": "img/map_modern.jpg", "x": 25.0, "y": 70.0},
        {"name": "Mixed", "desc": "Suburban Area", "img": "img/map_mixed.jpg", "x": 80.0, "y": 65.0},
    ]

    # Dictionary to store neighborhood objects for use in POIs
    n_objs = {}

    print("Checking & Updating Neighborhoods...")
    for n_data in neighborhoods_data:
        # Database search
        stim = db.query(Stimulus).filter(Stimulus.type == "neighborhood", Stimulus.name == n_data["name"]).first()
        
        if not stim:
            # If it doesn't exist, create it.
            stim = Stimulus(type="neighborhood", name=n_data["name"])
            db.add(stim)
            print(f" + Created Neighborhood: {n_data['name']}")
        
        # Always update these values ​​(Force Update)
        stim.description = n_data["desc"]
        stim.media_path = n_data["img"]
        stim.map_x = n_data["x"]
        stim.map_y = n_data["y"]
        
        n_objs[n_data["name"]] = stim
    
    db.commit() # Save locations to get IDs

    # --- 2. Definition of POIs ---
    pois_data = [
        # Luxury
        {"name": "Luxury Park", "p_name": "Luxury", "img": "img/luxury_park.jpg", "x": 30.0, "y": 40.0},
        {"name": "Luxury Square", "p_name": "Luxury", "img": "img/luxury_square.jpg", "x": 60.0, "y": 20.0},
        {"name": "Tree-lined Avenue", "p_name": "Luxury", "img": "img/luxury_street.jpg", "x": 45.0, "y": 70.0},
        {"name": "Modern Plaza", "p_name": "Luxury", "img": "img/luxury_concrete.jpg", "x": 80.0, "y": 50.0},
        
        # Traditional
        {"name": "Historic Garden", "p_name": "Traditional", "img": "img/traditional_park.jpg", "x": 25.0, "y": 30.0},
        {"name": "Old Bazaar", "p_name": "Traditional", "img": "img/traditional_square.jpg", "x": 50.0, "y": 50.0},
        {"name": "Cobblestone Alley", "p_name": "Traditional", "img": "img/traditional_street.jpg", "x": 70.0, "y": 20.0},
        {"name": "Stone Courtyard", "p_name": "Traditional", "img": "img/traditional_concrete.jpg", "x": 60.0, "y": 80.0},

        # Modern
        {"name": "Vertical Garden", "p_name": "Modern", "img": "img/modern_park.jpg", "x": 40.0, "y": 30.0},
        {"name": "Times Square", "p_name": "Modern", "img": "img/modern_square.jpg", "x": 50.0, "y": 50.0},
        {"name": "Glass Street", "p_name": "Modern", "img": "img/modern_street.jpg", "x": 20.0, "y": 60.0},
        {"name": "Skate Park", "p_name": "Modern", "img": "img/modern_concrete.jpg", "x": 70.0, "y": 70.0},

        # Mixed
        {"name": "Community Park", "p_name": "Mixed", "img": "img/mixed_park.jpg", "x": 30.0, "y": 30.0},
        {"name": "Roundabout", "p_name": "Mixed", "img": "img/mixed_square.jpg", "x": 60.0, "y": 60.0},
        {"name": "Main Street", "p_name": "Mixed", "img": "img/mixed_street.jpg", "x": 40.0, "y": 80.0},
        {"name": "Sidewalk", "p_name": "Mixed", "img": "img/mixed_concrete.jpg", "x": 80.0, "y": 40.0},
    ]

    print("Checking & Updating POIs...")
    for p_data in pois_data:
        parent = n_objs.get(p_data["p_name"])
        if not parent: continue

        stim = db.query(Stimulus).filter(Stimulus.type == "poi", Stimulus.name == p_data["name"]).first()
        
        if not stim:
            stim = Stimulus(type="poi", name=p_data["name"])
            db.add(stim)
        
        # Force Update
        stim.neighborhood_id = parent.id
        stim.media_path = p_data["img"]
        stim.map_x = p_data["x"]
        stim.map_y = p_data["y"]
        stim.description = f"Located in {p_data['p_name']}"

    # --- 3. Routes (without coordinates) ---
    routes_data = [
        {"name": "Green & Quiet", "img": "img/route_green.jpg", "desc": "Nature path"},
        {"name": "Mixed Use", "img": "img/route_mixed.jpg", "desc": "Balanced path"},
        {"name": "Busy Urban", "img": "img/route_busy.jpg", "desc": "City path"},
        {"name": "Crowded Market", "img": "img/route_crowded.jpg", "desc": "Social path"},
    ]

    for r_data in routes_data:
        stim = db.query(Stimulus).filter(Stimulus.type == "route", Stimulus.name == r_data["name"]).first()
        if not stim:
            stim = Stimulus(type="route", name=r_data["name"])
            db.add(stim)
        
        stim.media_path = r_data["img"]
        stim.description = r_data["desc"]

    db.commit()
    print("Database Synced Successfully (Coordinates Updated).")

if __name__ == "__main__":
    init_db()