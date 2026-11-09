"""Persistence lifecycle regression tests; no provider or external URL is contacted."""

from datetime import timedelta
from hashlib import sha256

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    from app import worker
    from app.config import settings
    from app.db import Base
    from app.models import User
    from app.services import storage

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    cfg = settings().model_copy(
        update={"storage_path": tmp_path / "originals", "storage_key": Fernet.generate_key().decode()}
    )
    monkeypatch.setattr(worker, "SessionLocal", factory)
    monkeypatch.setattr(worker, "settings", lambda: cfg)
    monkeypatch.setattr(storage, "settings", lambda: cfg)
    with factory() as db:
        user = User(is_guest=True, retention_days=1)
        db.add(user)
        db.commit()
        user_id = user.id
    yield factory, user_id, cfg.storage_path
    engine.dispose()


def _create_text(factory, user_id):
    from app.models import User
    from app.services.resources import create_source

    with factory() as db:
        source, job = create_source(
            db, db.get(User, user_id), b"Consent is required, except by law.", "Policy.txt"
        )
        db.commit()
        return source.id, job.id


def test_worker_ingestion_persists_real_source_anchors_and_encrypted_bytes(lifecycle):
    from app import worker
    from app.models import Chunk, Job, Section, Source
    from app.services import storage

    factory, user_id, root = lifecycle
    source_id, job_id = _create_text(factory, user_id)
    assert worker.run_once()
    with factory() as db:
        source, job = db.get(Source, source_id), db.get(Job, job_id)
        assert source.status == "READY" and job.state == "COMPLETED"
        raw = storage.read(source.object_key, source.sha256)
        assert source.sha256 == sha256(raw).hexdigest()
        assert raw not in (root / source.object_key).read_bytes()
        section = db.scalar(select(Section).where(Section.source_id == source_id))
        assert section.data["source_id"] == source_id
        assert section.data["locator"]["identity_map"] is True
        chunk = db.scalar(select(Chunk).where(Chunk.source_id == source_id))
        assert chunk.data["spans"][0]["section_id"] == section.id


def test_cancellation_between_chunking_and_persistence_cannot_resurrect_results(lifecycle, monkeypatch):
    from app import worker
    from app.models import Job, Section
    from app.services import chunking

    factory, user_id, _ = lifecycle
    source_id, job_id = _create_text(factory, user_id)
    real_chunk = chunking.chunk_sections

    def cancel_during_chunking(sections):
        result = real_chunk(sections)
        with factory() as db:
            job = db.get(Job, job_id)
            job.state, job.lease_token = "CANCELLED", None
            db.commit()
        return result

    monkeypatch.setattr(chunking, "chunk_sections", cancel_during_chunking)
    assert worker.run_once()
    with factory() as db:
        assert db.get(Job, job_id).state == "CANCELLED"
        assert db.scalar(select(func.count()).select_from(Section).where(Section.source_id == source_id)) == 0


def test_delete_source_removes_derived_analysis_findings_and_original(lifecycle):
    from app import worker
    from app.models import Analysis, AnalysisSource, Finding, Job, Section, Source
    from app.services.resources import delete_source, flush_storage_deletions

    factory, user_id, root = lifecycle
    source_id, _ = _create_text(factory, user_id)
    assert worker.run_once()
    with factory() as db:
        job = Job(owner_id=user_id, kind="analysis", state="COMPLETED")
        db.add(job)
        db.flush()
        analysis = Analysis(owner_id=user_id, job_id=job.id)
        db.add(analysis)
        db.flush()
        db.add(AnalysisSource(analysis_id=analysis.id, source_id=source_id))
        db.add(Finding(analysis_id=analysis.id, data={"statement": "document-specific secret"}))
        db.commit()
        analysis_id = analysis.id
    with factory() as db:
        source = db.get(Source, source_id)
        path = root / source.object_key
        assert path.exists()
        delete_source(db, source)
        db.commit()
        flush_storage_deletions(db)
        assert not path.exists()
    with factory() as db:
        assert db.get(Source, source_id) is None
        assert db.get(Analysis, analysis_id) is None
        assert db.scalar(select(func.count()).select_from(Finding)) == 0
        assert db.scalar(select(func.count()).select_from(Section)) == 0


def test_expired_lease_fails_without_repeating_provider_work(lifecycle):
    from app import worker
    from app.models import Job, now

    factory, user_id, _ = lifecycle
    with factory() as db:
        job = Job(
            owner_id=user_id,
            kind="analysis",
            state="PROCESSING",
            lease_token="stale",
            lease_until=now() - timedelta(minutes=1),
        )
        db.add(job)
        db.commit()
        job_id = job.id
    assert worker.claim() is None
    with factory() as db:
        job = db.get(Job, job_id)
        assert job.state == "FAILED" and job.lease_token is None
        assert "interrupted" in job.error
    with pytest.raises(worker.LeaseLost):
        worker.progress(job_id, "stale", "VERIFYING")


def test_capture_retry_reuses_saved_original_after_extraction_failure(lifecycle, monkeypatch):
    from app import worker
    from app.models import Job, Source, uid
    from app.services import discovery, ingest

    factory, user_id, root = lifecycle
    data = b"<html><p>Consent is required except by law.</p></html>"
    monkeypatch.setattr(
        discovery,
        "safe_fetch",
        lambda url: {"data": data, "url": url, "mime": "text/html", "sha256": sha256(data).hexdigest()},
    )
    real_extract = ingest.extract

    def fail_extraction(*args, **kwargs):
        raise ingest.ExtractionError("Temporary extraction failure.")

    monkeypatch.setattr(ingest, "extract", fail_extraction)
    source_id = uid()
    with factory() as db:
        job = Job(
            owner_id=user_id,
            kind="capture",
            payload={
                "source_id": source_id,
                "url": "https://official.example/privacy",
                "discovered_from": "https://official.example/",
            },
        )
        db.add(job)
        db.commit()
        job_id = job.id
    assert worker.run_once()
    with factory() as db:
        job = db.get(Job, job_id)
        assert job.state == "FAILED"
        assert db.get(Source, source_id) is not None
        job.state, job.lease_until = "QUEUED", None
        db.commit()
    monkeypatch.setattr(ingest, "extract", real_extract)
    assert worker.run_once()
    with factory() as db:
        assert db.get(Job, job_id).state == "COMPLETED"
        assert db.get(Source, source_id).status == "READY"
        assert len(list(root.rglob("*.enc"))) == 1


def test_transaction_rollback_removes_uncommitted_private_original(lifecycle):
    from app.models import Source, User
    from app.services.resources import create_source

    factory, user_id, root = lifecycle
    with factory() as db:
        source, _ = create_source(db, db.get(User, user_id), b"Uncommitted private content.", "private.txt")
        source_id = source.id
        db.rollback()
    with factory() as db:
        assert db.get(Source, source_id) is None
    assert list(root.rglob("*.enc")) == []


def test_expired_source_scope_denies_analysis_derivatives_before_cleanup(client):
    from conftest import login_guest

    from app.db import SessionLocal
    from app.models import Analysis, AnalysisSource, Finding, Job, Source, now
    from app.worker import run_once

    user = login_guest(client)
    response = client.post("/api/v1/sources/text", json={"text": "A private source-specific obligation."})
    assert response.status_code == 202
    source_id = response.json()["source_id"]
    assert run_once()
    with SessionLocal() as db:
        job = Job(owner_id=user["id"], kind="analysis", state="COMPLETED")
        db.add(job)
        db.flush()
        analysis = Analysis(owner_id=user["id"], job_id=job.id)
        db.add(analysis)
        db.flush()
        db.add(AnalysisSource(analysis_id=analysis.id, source_id=source_id))
        db.add(Finding(analysis_id=analysis.id, data={"statement": "private source-specific obligation"}))
        db.commit()
        analysis_id = analysis.id
        db.get(Source, source_id).expires_at = now() - timedelta(seconds=1)
        db.commit()
    for suffix in ("", "/findings", "/questions"):
        response = client.get(f"/api/v1/analyses/{analysis_id}{suffix}")
        assert response.status_code == 404
        assert "private source-specific" not in response.text
