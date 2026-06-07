"""Training endpoints."""
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/health")
async def health_check():
    """Simple health check — model availability reported via /api/ml/health."""
    return {"status": "ok"}
