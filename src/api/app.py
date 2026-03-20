from fastapi import FastAPI

from src.api.admin_api import router as admin_router
from src.api.generator_api import router as generator_router
from src.ingestion.api import router as ingestion_router
from src.ingestion.search_api import router as search_router

app = FastAPI(title="EduTrack Hub API")
app.include_router(ingestion_router)
app.include_router(search_router)
app.include_router(admin_router)
app.include_router(generator_router)
