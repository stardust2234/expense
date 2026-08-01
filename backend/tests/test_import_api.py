import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.session import get_database_session
from app.main import app
from app.models import (
    CategorisationRule,
    Category,
    Expense,
    ImportBatch,
    Merchant,
    MerchantAlias,
    RawTransaction,
    TransactionStatus,
)

CSV_CONTENT = """Date,Description,Amount,Currency
2026-07-24,TESCO STORES 0123,25.99,GBP
2026-07-25,UNKNOWN PAYMENT,10.00,GBP
"""


async def wait_for_import(client: AsyncClient, batch_id: int) -> dict:
    for _ in range(100):
        response = await client.get(f"/api/imports/{batch_id}")
        payload = response.json()
        if payload["status"] in {"completed", "completed_with_errors", "failed"}:
            return payload
        await asyncio.sleep(0.02)
    raise AssertionError(f"Import batch {batch_id} did not finish")


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'imports.db'}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as database_session:
        yield database_session


@pytest.mark.anyio
async def test_csv_upload_runs_the_complete_pipeline(session: Session) -> None:
    category = Category(name="Groceries")
    merchant = Merchant(
        name="Tesco",
        aliases=[MerchantAlias(pattern="TESCO STORES")],
    )
    rule = CategorisationRule(
        match_pattern="TESCO",
        category=category,
        priority=100,
    )
    session.add_all([merchant, rule])
    session.commit()

    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/imports/file",
                files={
                    "file": (
                        "transactions.csv",
                        CSV_CONTENT,
                        "text/csv",
                    )
                },
            )
            completed = await wait_for_import(client, response.json()["id"])
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert completed["status"] == "completed"
    assert completed["normalised_rows"] == 2
    assert completed["categorised_rows"] == 1
    assert completed["needs_review_rows"] == 1
    session.expire_all()
    expenses = session.scalars(select(Expense).order_by(Expense.id)).all()
    assert expenses[0].merchant is merchant
    assert expenses[0].status is TransactionStatus.CATEGORISED
    assert expenses[1].status is TransactionStatus.NEEDS_REVIEW


@pytest.mark.anyio
async def test_csv_upload_rejects_non_utf8(session: Session) -> None:
    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/imports/file",
                files={"file": ("bad.csv", b"\xff\xfe", "text/csv")},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.anyio
async def test_import_preserves_raw_timestamp_and_stores_normalised_date(
    session: Session,
) -> None:
    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/imports/file",
                files={
                    "file": (
                        "revolut.csv",
                        (
                            "Completed Date,Description,Amount,Currency\n"
                            "4/15/26 15:50,Coffee,-3.50,GBP\n"
                        ),
                        "text/csv",
                    )
                },
            )
            completed = await wait_for_import(client, response.json()["id"])
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert completed["status"] == "completed"
    session.expire_all()
    raw = session.scalar(select(RawTransaction))
    expense = session.scalar(select(Expense))
    assert raw is not None
    assert expense is not None
    assert raw.raw_data["Completed Date"] == "4/15/26 15:50"
    assert expense.transaction_date.isoformat() == "2026-04-15"


@pytest.mark.anyio
async def test_duplicate_history_and_failed_batch_retry(session: Session) -> None:
    content = "Date,Description,Amount,Currency\nnot-a-date,Coffee,-3.50,GBP\n"

    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            uploaded = await client.post(
                "/api/imports/file",
                files={"file": ("failed.csv", content, "text/csv")},
            )
            failed = await wait_for_import(client, uploaded.json()["id"])
            history = await client.get("/api/imports")
            duplicate = await client.post(
                "/api/imports/file",
                files={"file": ("renamed.csv", content, "text/csv")},
            )

            raw = session.scalar(select(RawTransaction))
            assert raw is not None
            raw.raw_data = {
                **raw.raw_data,
                "Date": "2026-07-24",
            }
            session.commit()

            retried = await client.post(f"/api/imports/{uploaded.json()['id']}/retry")
            detail = await wait_for_import(client, uploaded.json()["id"])
            retry_again = await client.post(f"/api/imports/{uploaded.json()['id']}/retry")
    finally:
        app.dependency_overrides.clear()

    assert uploaded.status_code == 202
    assert failed["failed_rows"] == 1
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["status"] == "completed_with_errors"
    assert duplicate.status_code == 409
    assert "batch 1" in duplicate.json()["detail"]
    assert retried.status_code == 202
    assert retried.json()["status"] == "queued"
    assert detail["status"] == "completed"
    assert detail["normalised_rows"] == 1
    assert detail["needs_review_rows"] == 1
    assert detail["failed_rows"] == 0
    assert retry_again.status_code == 409


@pytest.mark.anyio
async def test_completed_import_can_be_deleted_with_its_transactions(
    session: Session,
) -> None:
    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            uploaded = await client.post(
                "/api/imports/file",
                files={"file": ("delete-me.csv", CSV_CONTENT, "text/csv")},
            )
            batch_id = uploaded.json()["id"]
            await wait_for_import(client, batch_id)
            raw_id = session.scalar(select(RawTransaction.id))
            expense_ids = list(session.scalars(select(Expense.id)))

            deleted = await client.delete(f"/api/imports/{batch_id}")
            missing = await client.get(f"/api/imports/{batch_id}")
    finally:
        app.dependency_overrides.clear()

    assert deleted.status_code == 204
    assert missing.status_code == 404
    session.expire_all()
    assert session.get(ImportBatch, batch_id) is None
    assert raw_id is not None and session.get(RawTransaction, raw_id) is None
    assert expense_ids
    assert all(session.get(Expense, expense_id) is None for expense_id in expense_ids)


@pytest.mark.anyio
async def test_active_import_cannot_be_deleted(session: Session) -> None:
    batch = ImportBatch(
        source_filename="running.csv",
        source_type="csv",
        processing_status="processing",
    )
    session.add(batch)
    session.commit()

    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.delete(f"/api/imports/{batch.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert session.get(ImportBatch, batch.id) is batch


@pytest.mark.anyio
async def test_overlapping_statement_skips_existing_transactions(
    session: Session,
) -> None:
    first_content = (
        "Date,Description,Amount,Currency\n"
        "2026-07-24,Coffee,-3.50,GBP\n"
        "2026-07-25,Groceries,-12.00,GBP\n"
    )
    overlapping_content = (
        "Date,Description,Amount,Currency\n2026-07-24,Coffee,-3.50,GBP\n2026-07-26,Bus,-2.00,GBP\n"
    )

    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            first = await client.post(
                "/api/imports/file",
                files={"file": ("history.csv", first_content, "text/csv")},
            )
            await wait_for_import(client, first.json()["id"])
            second = await client.post(
                "/api/imports/file",
                files={"file": ("july.csv", overlapping_content, "text/csv")},
            )
            completed = await wait_for_import(client, second.json()["id"])
    finally:
        app.dependency_overrides.clear()

    assert completed["normalised_rows"] == 1
    assert completed["duplicate_rows"] == 1
    assert completed["failed_rows"] == 0
    assert session.query(Expense).count() == 3
