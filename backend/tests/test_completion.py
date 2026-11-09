"""Regression checks for the audited integration gaps; synthetic data only."""

import pytest
from conftest import login_guest
from pydantic import ValidationError
from sqlalchemy import select
from test_ai import CHUNKS, SECTIONS
from test_api import upload_text

from app.config import Settings
from app.models import Source, StorageDeletion
from app.services import analysis
from app.services.resources import delete_source, flush_storage_deletions


def test_postgres_driver_normalization_and_no_runtime_sqlite_fallback():
    cfg = Settings(
        _env_file=None, database_url="postgresql://fixture:fixture@localhost/test", environment="development"
    )
    assert cfg.database_url.startswith("postgresql+psycopg://")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="sqlite://", environment="development")
    assert Settings(_env_file=None, database_url="sqlite://", environment="test").database_url == "sqlite://"


def test_isolated_mode_never_inherits_live_provider_credentials():
    cfg = Settings(
        _env_file=None,
        database_url="sqlite://",
        environment="test",
        gemini_api_key="synthetic-secret",
        gemini_model="fixture",
    )
    assert all(not p["key"] and not p["model"] for p in cfg.providers())


def test_source_question_can_use_verified_evidence_without_prior_findings(monkeypatch):
    def generate(configs, system, prompt, schema, role):
        if schema is analysis.SourceAnswerDraft:
            return schema(
                answer="Sharing requires consent except where legally required.",
                abstain=False,
                limitations=[],
                citations=[
                    {
                        "source_id": "src1",
                        "section_id": "sec1",
                        "quote": SECTIONS[0]["text"],
                        "start": None,
                        "end": None,
                        "page": 1,
                    }
                ],
            ), [{"provider": "fixture", "role": role}]
        return schema(
            support_status="SUPPORTED",
            rationale="Complete source supports the qualified answer.",
            missing_qualifiers=[],
            unresolved_references=[],
        ), [{"provider": "fixture", "role": role}]

    monkeypatch.setattr(analysis, "generate_with_fallback", generate)
    result = analysis.ask(
        "Can they share data?", [], SECTIONS, [{"name": "fixture"}], retrieved_chunks=CHUNKS
    )
    assert result["citations"][0]["start"] == 0
    assert result["verification"]["support_status"] == "SUPPORTED"


def test_gemini_wire_schema_preserves_types_but_local_limits_still_apply():
    from app.providers.base import gemini_schema

    schema = gemini_schema(analysis.CandidateBatch.model_json_schema())
    assert "$ref" not in str(schema)
    assert schema["properties"]["findings"]["items"]["properties"]["category"]["enum"]
    with pytest.raises(ValidationError):
        analysis.CandidateBatch.model_validate({"findings": [{}] * 21})


def test_dashboard_pagination_and_display_only_rename(client):
    login_guest(client)
    ids = upload_text(client)
    response = client.get("/api/v1/sources?limit=1")
    assert response.headers["X-Total-Count"] == "1"
    source = response.json()[0]
    assert client.get("/api/v1/dashboard").json()["counts"]["documents"] == 1
    renamed = client.patch("/api/v1/sources/" + ids["source_id"], json={"name": "Review copy"}).json()
    assert renamed["original_name"] == "Review copy"
    assert renamed["sha256"] == source["sha256"]
    assert renamed["original_filename"] == source["original_filename"]
    assert client.get("/api/v1/sources?q=Review").headers["X-Total-Count"] == "1"


def test_deletion_rollback_preserves_original_until_committed(client):
    from app.db import SessionLocal
    from app.services import storage

    login_guest(client)
    ids = upload_text(client)
    with SessionLocal() as db:
        source = db.get(Source, ids["source_id"])
        key = source.object_key
        delete_source(db, source)
        db.rollback()
        assert storage.path(key).exists()
        assert db.get(Source, ids["source_id"])
        assert not db.scalars(select(StorageDeletion)).all()
        delete_source(db, db.get(Source, ids["source_id"]))
        db.commit()
        assert storage.path(key).exists()
        flush_storage_deletions(db)
        assert not storage.path(key).exists()


def test_file_deletion_failure_is_pending_not_false_success(client, monkeypatch):
    from app.db import SessionLocal
    from app.services import storage

    login_guest(client)
    ids = upload_text(client)
    remove = storage.remove
    monkeypatch.setattr(
        storage, "remove", lambda key: (_ for _ in ()).throw(PermissionError("synthetic permission denial"))
    )
    response = client.delete("/api/v1/sources/" + ids["source_id"])
    assert response.status_code == 202 and response.json()["status"] == "DELETION_PENDING"
    assert client.get("/api/v1/sources/" + ids["source_id"]).status_code == 404
    with SessionLocal() as db:
        assert db.scalar(select(StorageDeletion)).attempts == 1
    monkeypatch.setattr(storage, "remove", remove)
    with SessionLocal() as db:
        flush_storage_deletions(db)
        assert not db.scalars(select(StorageDeletion)).all()
