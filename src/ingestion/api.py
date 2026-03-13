from fastapi import APIRouter
from .worker import ingest_sync

router = APIRouter()


@router.post("")
def ingest(url: str):
    return ingest_sync(url)
