from fastapi import APIRouter

from services import stats_service

router = APIRouter()


@router.get("/health")
def health():
    return stats_service.health()
