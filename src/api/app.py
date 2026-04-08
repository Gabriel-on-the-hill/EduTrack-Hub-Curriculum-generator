from __future__ import annotations

from fastapi import FastAPI

from src.api.generation_api import router as generation_router


def create_app() -> FastAPI:
    app = FastAPI(title="EduTrack Generation API")
    app.include_router(generation_router)
    return app


app = create_app()
