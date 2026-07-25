import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models import ImportBatch
from app.services.commitment_reconciliation import reconcile_pending_commitments
from app.services.import_batch_service import batch_counts, get_import_batch
from app.services.transaction_processor import (
    categorise_normalised_transactions,
    normalise_pending_transactions,
)

logger = logging.getLogger(__name__)
SessionFactory = Callable[[], Session]
TERMINAL_IMPORT_STATUSES = {"completed", "completed_with_errors", "failed"}
ACTIVE_IMPORT_STATUSES = {"queued", "processing"}
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="import-worker")


def queue_import_batch(session: Session, batch: ImportBatch) -> None:
    batch.processing_status = "queued"
    batch.processing_error = None
    batch.processing_started_at = None
    batch.processing_completed_at = None
    session.commit()


def enqueue_import_job(
    batch_id: int,
    *,
    retry_failed: bool = False,
    session_factory: SessionFactory = SessionLocal,
) -> Future[None]:
    return _executor.submit(
        process_import_batch,
        batch_id,
        retry_failed=retry_failed,
        session_factory=session_factory,
    )


def resume_incomplete_import_jobs() -> int:
    """Requeue work left queued or processing by a previous process."""
    with SessionLocal() as session:
        batches = session.scalars(
            select(ImportBatch)
            .where(ImportBatch.processing_status.in_(ACTIVE_IMPORT_STATUSES))
            .order_by(ImportBatch.id)
        ).all()
        batch_ids = [batch.id for batch in batches]
        for batch in batches:
            batch.processing_status = "queued"
            batch.processing_error = None
        session.commit()

    for batch_id in batch_ids:
        enqueue_import_job(batch_id, retry_failed=True)
    return len(batch_ids)


def process_import_batch(
    batch_id: int,
    *,
    retry_failed: bool = False,
    session_factory: SessionFactory = SessionLocal,
) -> None:
    """Run a tracked import job using a session independent from the request."""
    with session_factory() as session:
        batch = session.get(ImportBatch, batch_id)
        if batch is None:
            logger.error("Import batch %s disappeared before processing", batch_id)
            return

        batch.processing_status = "processing"
        batch.processing_started_at = datetime.now(UTC)
        batch.processing_completed_at = None
        batch.processing_error = None
        session.commit()

        try:
            normalise_pending_transactions(
                session,
                default_currency=batch.default_currency,
                import_batch_id=batch.id,
                retry_failed=retry_failed,
            )
            categorise_normalised_transactions(
                session,
                import_batch_id=batch.id,
            )
            reconcile_pending_commitments(session, import_batch_id=batch.id)
            session.expire_all()
            refreshed = get_import_batch(session, batch_id=batch.id)
            _, failed, _, _ = batch_counts(refreshed)
            refreshed.processing_status = "completed_with_errors" if failed else "completed"
            refreshed.processing_completed_at = datetime.now(UTC)
            session.commit()
        except Exception as error:
            session.rollback()
            failed_batch = session.get(ImportBatch, batch_id)
            if failed_batch is not None:
                failed_batch.processing_status = "failed"
                failed_batch.processing_error = str(error)[:1000]
                failed_batch.processing_completed_at = datetime.now(UTC)
                session.commit()
            logger.exception("Import batch %s failed", batch_id)
