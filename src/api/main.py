from fastapi import FastAPI

from src.api.admin_api import router as admin_router
from src.ingestion.api import router as ingestion_router
from src.ingestion.search_api import router as search_router

app = FastAPI(title="EduTrack Curriculum Generator API")

app.include_router(ingestion_router, prefix="/v1/ingest", tags=["ingestion"])
app.include_router(search_router, prefix="/v1/ingest", tags=["search"])
app.include_router(admin_router, prefix="/v1/admin", tags=["admin"])


@app.get("/v1/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
