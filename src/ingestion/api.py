from fastapi import APIRouter, Depends
from src.security import validate_signed_request
from .worker import ingest_sync

router = APIRouter()


@router.post("/ingest")
def ingest(url: str, _: None = Depends(validate_signed_request)):
    return ingest_sync(url)


@router.get("/ingest/health")
def health():
    return {"status": "ok"}
