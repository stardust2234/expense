from collections.abc import AsyncIterator

from sqlalchemy.orm import Session, sessionmaker

from app.database.engine import engine

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


async def get_database_session() -> AsyncIterator[Session]:
    with SessionLocal() as session:
        yield session
