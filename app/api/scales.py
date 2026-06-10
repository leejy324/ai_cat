from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import auth_required
from app.database import get_db
from app.schemas.scale import (
    ScaleFeedbackResponse,
    ScaleStatsResponse,
    ScaleSubmitRequest,
    ScaleSubmitResponse,
)
from app.services import scale_service

router = APIRouter()


@router.post("/submit", response_model=ScaleSubmitResponse, status_code=201)
async def submit_scale(
    body: ScaleSubmitRequest,
    student_id: str = Depends(auth_required),
    db: AsyncSession = Depends(get_db),
):
    return await scale_service.submit_scale(db, student_id, body)


@router.get("/{record_id}/feedback", response_model=ScaleFeedbackResponse)
async def get_feedback(
    record_id: str,
    student_id: str = Depends(auth_required),
    db: AsyncSession = Depends(get_db),
):
    return await scale_service.get_feedback(db, record_id, student_id)


@router.get("/stats", response_model=ScaleStatsResponse)
async def get_stats(
    student_id: str = Depends(auth_required),
    db: AsyncSession = Depends(get_db),
):
    return await scale_service.get_stats(db, student_id)
