import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models import ImportBatch
from app.services import import_job_service


def test_import_executor_can_restart_after_shutdown(monkeypatch) -> None:
    created = []

    class FakeExecutor:
        def __init__(self, **_kwargs):
            self.shutdown_calls = []
            created.append(self)

        def shutdown(self, **kwargs):
            self.shutdown_calls.append(kwargs)

    monkeypatch.setattr(import_job_service, "ThreadPoolExecutor", FakeExecutor)
    monkeypatch.setattr(import_job_service, "_executor", None)

    first = import_job_service._get_executor()
    import_job_service.shutdown_import_jobs()
    second = import_job_service._get_executor()

    assert second is not first
    assert len(created) == 2
    assert first.shutdown_calls == [{"wait": True, "cancel_futures": False}]


def test_import_queue_rejects_work_when_capacity_is_exhausted(monkeypatch) -> None:
    class UnavailableSlot:
        def acquire(self, **_kwargs):
            return False

    monkeypatch.setattr(import_job_service, "_queue_slots", UnavailableSlot())

    with pytest.raises(import_job_service.ImportQueueFullError):
        import_job_service.enqueue_import_job(1)


def test_only_one_worker_can_claim_a_queued_batch(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as session:
        batch = ImportBatch(
            source_filename="statement.csv",
            source_type="csv",
            processing_status="queued",
        )
        session.add(batch)
        session.commit()
        batch_id = batch.id

    calls = 0

    def normalise(*_args, **_kwargs):
        nonlocal calls
        calls += 1

    monkeypatch.setattr(import_job_service, "normalise_pending_transactions", normalise)
    monkeypatch.setattr(
        import_job_service, "categorise_normalised_transactions", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        import_job_service,
        "reconcile_pending_commitments",
        lambda *_args, **_kwargs: None,
    )

    import_job_service.process_import_batch(batch_id, session_factory=session_factory)
    import_job_service.process_import_batch(batch_id, session_factory=session_factory)

    with Session(engine) as session:
        completed = session.get(ImportBatch, batch_id)
        assert completed is not None
        assert completed.processing_status == "completed"
        assert completed.processing_claim_token is None
    assert calls == 1


def test_recovery_does_not_steal_an_active_processing_lease(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(UTC)
    with Session(engine) as session:
        queued = ImportBatch(
            source_filename="queued.csv", source_type="csv", processing_status="queued"
        )
        expired = ImportBatch(
            source_filename="expired.csv",
            source_type="csv",
            processing_status="processing",
            processing_claim_token="expired",
            processing_lease_expires_at=now - timedelta(minutes=1),
        )
        active = ImportBatch(
            source_filename="active.csv",
            source_type="csv",
            processing_status="processing",
            processing_claim_token="active",
            processing_lease_expires_at=now + timedelta(minutes=5),
        )
        session.add_all([queued, expired, active])
        session.commit()
        queued_id, expired_id, active_id = queued.id, expired.id, active.id

    enqueued: list[int] = []
    monkeypatch.setattr(import_job_service, "SessionLocal", session_factory)
    monkeypatch.setattr(
        import_job_service,
        "enqueue_import_job",
        lambda batch_id, **_kwargs: enqueued.append(batch_id),
    )

    assert import_job_service.resume_incomplete_import_jobs() == 2
    assert enqueued == [queued_id, expired_id]
    with Session(engine) as session:
        active = session.get(ImportBatch, active_id)
        assert active is not None
        assert active.processing_status == "processing"
        assert active.processing_claim_token == "active"


from datetime import UTC, datetime, timedelta
