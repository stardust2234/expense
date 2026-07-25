from app.config import get_settings
from app.database.engine import check_database_connection


def build_health_payload() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "database": "ok" if check_database_connection() else "unreachable",
    }
