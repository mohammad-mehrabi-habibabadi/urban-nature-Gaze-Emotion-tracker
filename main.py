# File: main.py
# Purpose: Entry point for the application.

import uvicorn
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.factory.app_factory import create_app
from app.db.init_db import init_db

app = create_app()

# Initialize DB on start
@app.on_event("startup")
def on_startup():
    init_db()

# Handler for accurate display of database/validation errors (fix issue 422)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"Validation Error: {exc.errors()}")  # Print error to console
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

if __name__ == "__main__":
    # workers=1 is important for singleton logic
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, workers=1)