"""V1 API router — aggregates all v1 route modules."""
from fastapi import APIRouter
from app.api.v1 import health, scheduling, training

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(scheduling.router, tags=["scheduling"])
router.include_router(training.router, tags=["training"])
