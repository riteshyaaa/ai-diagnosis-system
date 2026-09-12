"""
MedFusion AI — API v1 Router Aggregator.
"""

from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.patients import router as patients_router
from app.api.v1.cases import router as cases_router
from app.api.v1.images import router as images_router
from app.api.v1.clinical_records import router as clinical_records_router
from app.api.v1.predictions import router as predictions_router
from app.api.v1.explanations import router as explanations_router
from app.api.v1.reviews import router as reviews_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(patients_router)
api_v1_router.include_router(cases_router)
api_v1_router.include_router(images_router)
api_v1_router.include_router(clinical_records_router)
api_v1_router.include_router(predictions_router)
api_v1_router.include_router(explanations_router)
api_v1_router.include_router(reviews_router)

__all__ = ["api_v1_router"]
