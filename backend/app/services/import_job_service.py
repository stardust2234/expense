import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from threading import BoundedSemaphore, Event, Lock, Thread
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models import ImportBatch
from app.services.commitment_reconciliation import reconcile_pending_commitments
from app.services.import_batch_service import (
    batch_counts,
    get_import_batch,
)
from app.services.transaction_processor import (
    categorise_normalised_transactions,
    normalise_pending_transactions,
)

logger = logging.getLogger(__name__)
SessionFactory = Callable[[], Session]
IMPORT_JOB_LEASE = timedelta(minutes=15)
MAX_QUEUED_IMPORT_JOBS = 32
PUBLIC_IMPORT_ERROR = "The import could not be processed. You can safely retry it."
_executor: ThreadPoolExecutor | None = None
_executor_lock = Lock()
_queue_slots = BoundedSemaphore(MAX_QUEUED_IMPORT_JOBS)


class ImportQueueFullError(RuntimeError):
    pass


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="import-worker")
        return _executor


def shutdown_import_jobs(*, wait: bool = True) -> None:
    """Stop accepting work and cleanly release the import worker thread."""
    global _executor
    with _executor_lock:
        executor, _executor = _executor, None
    if executor is not None:
        executor.shutdown(wait=wait, cancel_futures=False)


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
    if not _queue_slots.acquire(blocking=False):
        raise ImportQueueFullError("The import queue is full; try again later")
    try:
        future = _get_executor().submit(
            process_import_batch,
            batch_id,
            retry_failed=retry_failed,
            session_factory=session_factory,
        )
    except Exception:
        _queue_slots.release()
        raise
    future.add_done_callback(lambda _future: _queue_slots.release())
    return future


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

    scheduled = 0
    for batch_id in batch_ids:
        try:
            enqueue_import_job(batch_id, retry_failed=True)
            scheduled += 1
        except ImportQueueFullError:
            logger.warning("Import queue reached capacity while recovering queued jobs")
            break
    return scheduled


def process_import_batch(
    batch_id: int,
    *,
    retry_failed: bool = False,
    session_factory: SessionFactory = SessionLocal,
) -> None:
    """Run a tracked import job using a session independent from the request."""
    with session_factory() as session:
        claim_token = str(uuid4())
        claimed_row = session.execute(
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
            .returning(ImportBatch.id, ImportBatch.workspace_id)
        ).one_or_none()
        session.commit()
        if claimed_row is None:
            logger.info("Import batch %s was already claimed or is not queued", batch_id)
            return
        if claimed_row.workspace_id is not None:
            session.info["workspace_id"] = claimed_row.workspace_id
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
            with _claim_heartbeat(session_factory, batch_id=batch.id, claim_token=claim_token):
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
        except Exception:
            session.rollback()
            failed_batch = session.scalar(
                select(ImportBatch).where(
                    ImportBatch.id == batch_id,
                    ImportBatch.processing_claim_token == claim_token,
                )
            )
            if failed_batch is not None:
                failed_batch.processing_status = "failed"
                failed_batch.processing_error = PUBLIC_IMPORT_ERROR
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


@contextmanager
def _claim_heartbeat(
    session_factory: SessionFactory,
    *,
    batch_id: int,
    claim_token: str,
):
    """Renew a lease independently while a potentially long processing stage runs."""
    stopped = Event()
    interval_seconds = max(1.0, IMPORT_JOB_LEASE.total_seconds() / 3)

    def heartbeat() -> None:
        while not stopped.wait(interval_seconds):
            try:
                with session_factory() as heartbeat_session:
                    _renew_claim(
                        heartbeat_session,
                        batch_id=batch_id,
                        claim_token=claim_token,
                    )
            except Exception:
                logger.exception("Could not renew lease for import batch %s", batch_id)

    thread = Thread(target=heartbeat, name=f"import-heartbeat-{batch_id}", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=min(interval_seconds, 5.0))
