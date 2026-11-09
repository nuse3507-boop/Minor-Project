"""Opt-in checks use uncommitted synthetic rows; existing PostgreSQL data is never deleted."""

import os
from datetime import timedelta

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Chunk, Source, User, now, uid
from app.services.retrieval import retrieve_chunks


@pytest.mark.skipif(
    os.getenv("VERIORA_POSTGRES_TEST") != "1", reason="Explicit PostgreSQL integration opt-in required"
)
def test_postgres_foreign_keys_and_native_retrieval_rollback():
    assert engine.dialect.name == "postgresql"
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            assert len(inspect(connection).get_foreign_keys("evidence_spans")) == 3
            with Session(bind=connection) as db:
                user = User(id=uid(), email=None, is_guest=True)
                db.add(user)
                db.flush()
                source = Source(
                    id=uid(),
                    owner_id=user.id,
                    original_name="Uncommitted fixture.txt",
                    kind="text",
                    object_key="never-written.enc",
                    sha256="0" * 64,
                    expires_at=now() + timedelta(minutes=5),
                    status="READY",
                )
                db.add(source)
                db.flush()
                db.add(
                    Chunk(
                        source_id=source.id,
                        ordinal=0,
                        data={"text": "Cancellation is permitted with notice.", "spans": []},
                    )
                )
                db.flush()
                chunks = retrieve_chunks(db, [source.id], "Can I cancel?", owner_id=user.id)
                assert chunks and chunks[0]["retrieval"]["method"] == "postgresql_fts"
                assert retrieve_chunks(db, [source.id], "cancellation", owner_id=uid()) == []
        finally:
            if transaction.is_active:
                transaction.rollback()
