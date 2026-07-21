from psycopg import connect
from psycopg.rows import dict_row

from app.config import get_settings


def check_database_connection() -> bool:
    settings = get_settings()
    with connect(settings.database_url, connect_timeout=2, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ready")
            row = cur.fetchone()
    return bool(row and row["ready"] == 1)
