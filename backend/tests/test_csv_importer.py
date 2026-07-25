from collections.abc import Iterator
from io import StringIO

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models import ImportBatch, RawTransaction
from app.services.csv_importer import CsvImportError, import_csv


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session


def test_import_csv_stores_batch_and_raw_rows(session: Session) -> None:
    batch = import_csv(
        session,
        source_filename="current-account.csv",
        stream=StringIO(
            "Date,Description,Amount,Currency\n"
            "2026-07-01,TESCO STORES,25.99,GBP\n"
            "2026-07-02,TRAINLINE,48.50,GBP\n"
        ),
    )

    rows = session.scalars(select(RawTransaction).order_by(RawTransaction.source_row_number)).all()

    assert batch.source_type == "csv"
    assert batch.total_rows == 2
    assert [row.source_row_number for row in rows] == [2, 3]
    assert rows[0].raw_data == {
        "Date": "2026-07-01",
        "Description": "TESCO STORES",
        "Amount": "25.99",
        "Currency": "GBP",
    }


def test_import_csv_skips_blank_rows(session: Session) -> None:
    batch = import_csv(
        session,
        source_filename="transactions.csv",
        stream=StringIO("Date,Description\n,\n2026-07-01,Coffee\n"),
    )

    assert batch.total_rows == 1
    assert batch.raw_transactions[0].source_row_number == 3


def test_malformed_csv_is_rolled_back(session: Session) -> None:
    with pytest.raises(CsvImportError, match="more values than the header"):
        import_csv(
            session,
            source_filename="invalid.csv",
            stream=StringIO("Date,Description\n2026-07-01,Coffee,unexpected\n"),
        )

    assert session.scalar(select(ImportBatch)) is None
