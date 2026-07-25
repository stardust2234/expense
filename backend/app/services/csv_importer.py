import csv
from collections.abc import Sequence
from typing import TextIO

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import ImportBatch, RawTransaction


class CsvImportError(ValueError):
    """Raised when a CSV cannot be safely stored as raw transactions."""


def _validate_headers(fieldnames: Sequence[str | None] | None) -> list[str]:
    if fieldnames is None:
        raise CsvImportError("CSV must include a header row")
    if any(header is None or not header.strip() for header in fieldnames):
        raise CsvImportError("CSV headers must not be empty")

    headers = [header.strip() for header in fieldnames if header is not None]
    if len(headers) != len(set(headers)):
        raise CsvImportError("CSV headers must be unique")
    return headers


def import_csv(
    session: Session,
    *,
    source_filename: str,
    stream: TextIO,
    source_type: str = "csv",
    content_sha256: str | None = None,
    default_currency: str | None = None,
) -> ImportBatch:
    """Atomically persist a CSV import and its unmodified row values."""
    if not source_filename.strip():
        raise CsvImportError("source_filename must not be empty")

    try:
        reader = csv.DictReader(stream, strict=True)
        headers = _validate_headers(reader.fieldnames)
        batch = ImportBatch(
            source_filename=source_filename.strip(),
            source_type=source_type,
            content_sha256=content_sha256,
            default_currency=default_currency,
        )
        session.add(batch)

        row_count = 0
        for source_row_number, row in enumerate(reader, start=2):
            if None in row:
                raise CsvImportError(
                    f"CSV row {source_row_number} contains more values than the header"
                )

            raw_data = {header: row.get(header) for header in headers}
            if not any(value not in (None, "") for value in raw_data.values()):
                continue

            batch.raw_transactions.append(
                RawTransaction(
                    source_row_number=source_row_number,
                    raw_data=raw_data,
                )
            )
            row_count += 1

        batch.total_rows = row_count
        session.commit()
        session.refresh(batch)
        return batch
    except (csv.Error, SQLAlchemyError, CsvImportError) as error:
        session.rollback()
        if isinstance(error, CsvImportError):
            raise
        raise CsvImportError(f"CSV import failed: {error}") from error
