# File: app/core/config.py
# Purpose: Configuration settings for the application.

import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Urban Experiment Platform"
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///./experiment.db"
    
    # Offline settings
    OFFLINE_MODE: bool = True

    class Config:
        case_sensitive = True

settings = Settings()
