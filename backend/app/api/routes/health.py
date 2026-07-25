from fastapi import APIRouter

from app.services.health_service import build_health_payload

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return build_health_payload()
