from datetime import datetime

from pydantic import BaseModel


class ImportBatchItem(BaseModel):
    id: int
    source_filename: str
    source_type: str
    content_sha256: str | None
    default_currency: str | None
    total_rows: int
    normalised_rows: int
    failed_rows: int
    duplicate_rows: int
    categorised_rows: int
    needs_review_rows: int
    status: str
    processing_error: str | None
    imported_at: datetime
    processing_started_at: datetime | None
    processing_completed_at: datetime | None


class ImportBatchListResponse(BaseModel):
    items: list[ImportBatchItem]
    total: int
    limit: int
    offset: int
