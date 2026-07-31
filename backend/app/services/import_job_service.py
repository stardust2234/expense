import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update
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
ACTIVE_IMPORT_STATUSES = {"queued", "processing"}
IMPORT_JOB_LEASE = timedelta(minutes=15)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="import-worker")


def queue_import_batch(session: Session, batch: ImportBatch) -> None:
    batch.processing_status = "queued"
    batch.processing_error = None
    batch.processing_started_at = None
    batch.processing_completed_at = None
    batch.processing_claim_token = None
    batch.processing_lease_expires_at = None
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
    """Enqueue queued work and reclaim only processing jobs with expired leases."""
    now = datetime.now(UTC)
    with SessionLocal() as session:
        batches = session.scalars(
            select(ImportBatch)
            .where(
                (ImportBatch.processing_status == "queued")
                | (
                    (ImportBatch.processing_status == "processing")
                    & (
                        ImportBatch.processing_lease_expires_at.is_(None)
                        | (ImportBatch.processing_lease_expires_at <= now)
                    )
                )
            )
            .order_by(ImportBatch.id)
        ).all()
        batch_ids = [batch.id for batch in batches]
        for batch in batches:
            batch.processing_status = "queued"
            batch.processing_error = None
            batch.processing_claim_token = None
            batch.processing_lease_expires_at = None
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
        claim_token = str(uuid4())
        claimed = session.execute(
            update(ImportBatch)
            .where(
                ImportBatch.id == batch_id,
                ImportBatch.processing_status == "queued",
                ImportBatch.processing_claim_token.is_(None),
            )
            .values(
                processing_status="processing",
                processing_started_at=datetime.now(UTC),
                processing_completed_at=None,
                processing_error=None,
                processing_claim_token=claim_token,
                processing_lease_expires_at=datetime.now(UTC) + IMPORT_JOB_LEASE,
            )
        ).rowcount
        session.commit()
        if claimed != 1:
            logger.info("Import batch %s was already claimed or is not queued", batch_id)
            return
        batch = session.scalar(
            select(ImportBatch).where(
                ImportBatch.id == batch_id,
                ImportBatch.processing_claim_token == claim_token,
            )
        )
        if batch is None:
            logger.error("Import batch %s claim disappeared", batch_id)
            return

        try:
            _renew_claim(session, batch_id=batch.id, claim_token=claim_token)
            normalise_pending_transactions(
                session,
                default_currency=batch.default_currency,
                import_batch_id=batch.id,
                retry_failed=retry_failed,
            )
            _renew_claim(session, batch_id=batch.id, claim_token=claim_token)
            categorise_normalised_transactions(
                session,
                import_batch_id=batch.id,
            )
            reconcile_pending_commitments(session, import_batch_id=batch.id)
            session.commit()
            session.expire_all()
            refreshed = get_import_batch(session, batch_id=batch.id)
            _, failed, _, _, _ = batch_counts(refreshed)
            refreshed.processing_status = "completed_with_errors" if failed else "completed"
            refreshed.processing_completed_at = datetime.now(UTC)
            refreshed.processing_claim_token = None
            refreshed.processing_lease_expires_at = None
            session.commit()
        except Exception as error:
            session.rollback()
            failed_batch = session.scalar(
                select(ImportBatch).where(
                    ImportBatch.id == batch_id,
                    ImportBatch.processing_claim_token == claim_token,
                )
            )
            if failed_batch is not None:
                failed_batch.processing_status = "failed"
                failed_batch.processing_error = str(error)[:1000]
                failed_batch.processing_completed_at = datetime.now(UTC)
                failed_batch.processing_claim_token = None
                failed_batch.processing_lease_expires_at = None
                session.commit()
            logger.exception("Import batch %s failed", batch_id)


def _renew_claim(session: Session, *, batch_id: int, claim_token: str) -> None:
    renewed = session.execute(
        update(ImportBatch)
        .where(
            ImportBatch.id == batch_id,
            ImportBatch.processing_status == "processing",
            ImportBatch.processing_claim_token == claim_token,
        )
        .values(processing_lease_expires_at=datetime.now(UTC) + IMPORT_JOB_LEASE)
    ).rowcount
    if renewed != 1:
        raise RuntimeError(f"Import batch {batch_id} processing lease was lost")
    session.commit()
