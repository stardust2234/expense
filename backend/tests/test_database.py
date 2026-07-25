import sqlite3
from pathlib import Path

from app.database.engine import SQLITE_BUSY_TIMEOUT_MS, configure_sqlite_connection


def test_sqlite_connections_enable_concurrency_and_integrity_pragmas(
    tmp_path: Path,
) -> None:
    connection = sqlite3.connect(tmp_path / "hardened.db")
    try:
        configure_sqlite_connection(connection)

        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == SQLITE_BUSY_TIMEOUT_MS
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 1
    finally:
        connection.close()
