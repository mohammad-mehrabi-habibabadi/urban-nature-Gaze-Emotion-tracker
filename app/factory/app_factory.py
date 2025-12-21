# File: app/factory/app_factory.py
# Purpose: Application Factory for FastAPI.

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
# Adding websockets to imports
from app.api.routes import sessions, stimuli, events, websockets 
from app.core.config import settings

def create_app() -> FastAPI:
    app = FastAPI(title=settings.PROJECT_NAME)
    
    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], 
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # API Routes
    app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(stimuli.router, prefix="/api/stimuli", tags=["stimuli"])
    app.include_router(events.router, prefix="/api/events", tags=["events"])
    
    # WebSocket Route 
    # The final address will be: /ws/dashboard
    app.include_router(websockets.router, prefix="/ws", tags=["websockets"])
    
    # Static Files (Frontend)
    # This line will send all remaining requests to the static folder.
    app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
    
    return app