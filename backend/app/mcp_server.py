"""Optional, private read-only MCP adapter over the authorized application services.

Run with ``uvicorn app.mcp_server:create_app --factory --host 127.0.0.1 --port 8001``.
Requires the ``mcp`` extra and explicit MCP_BEARER_TOKEN, MCP_USER_ID,
MCP_TOKEN_EXPIRES_AT (ISO UTC), MCP_SCOPES (comma-separated tool names).
This single-account private integration is not an OAuth/public MCP deployment.
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.api.analyses import analysis_sources, finding_dict, get_analysis, get_findings
from app.config import settings
from app.db import SessionLocal
from app.models import Analysis, Finding, Section, Source, User, now
from app.security import throttle
from app.services.resources import audit, owned, source_dict

TOOLS = frozenset(
    {
        "list_my_documents",
        "search_document_clauses",
        "get_evidence_passport",
        "get_analysis_report",
        "get_document_sections",
    }
)


def _environment():
    token, user_id = os.getenv("MCP_BEARER_TOKEN", ""), os.getenv("MCP_USER_ID", "")
    scopes = frozenset(s.strip() for s in os.getenv("MCP_SCOPES", "").split(",") if s.strip())
    try:
        expires_at = datetime.fromisoformat(os.environ["MCP_TOKEN_EXPIRES_AT"])
    except (KeyError, ValueError):
        raise RuntimeError("MCP requires an explicit UTC token expiry.") from None
    if expires_at.tzinfo is None or expires_at <= now():
        raise RuntimeError("MCP token must have a future timezone-aware expiry.")
    if len(token) < 32 or not token.isascii() or not user_id or not scopes or not scopes <= TOOLS:
        raise RuntimeError("MCP requires a strong token, fixed account and explicit read-tool scopes.")
    if settings().environment == "production":
        raise RuntimeError(
            "This private MCP adapter is disabled in production; deploy reviewed OAuth separately."
        )
    return token, user_id, scopes, expires_at


def _principal(db, user_id):
    user = db.get(User, user_id)
    if not user or user.is_guest or not user.verified_at:
        raise HTTPException(401, "MCP account unavailable.")
    return user


def _execute(user_id, scopes, tool, action):
    try:
        return _authorized_execute(user_id, scopes, tool, action)
    except ValueError:
        raise
    except Exception:  # noqa: BLE001 -- confidentiality boundary: never serialize internal exception details
        # SDK tool errors must not include DB connection strings or source bodies.
        raise ValueError("Tool operation failed.") from None


def _authorized_execute(user_id, scopes, tool, action):
    """Same ownership/retention guard as REST, with explicit execution scope and audit."""
    with SessionLocal() as db:
        user = _principal(db, user_id)
        if tool not in scopes:
            audit(db, user.id, "mcp.denied", user.id)
            db.commit()
            raise ValueError("Tool permission denied.")
        throttle(db, "mcp:" + user.id, 60, 60)
        try:
            result = action(db, user)
            # JSON serialization validates output before anything private crosses transport.
            if len(json.dumps(result, ensure_ascii=False)) > 1_000_000:
                raise ValueError("Result exceeds MCP output limit; use a smaller page.")
            audit(db, user.id, "mcp." + tool, user.id)
            db.commit()
            return result
        except HTTPException:
            audit(db, user.id, "mcp.unavailable", user.id)
            db.commit()
            raise ValueError("Resource unavailable.") from None


class BearerGuard:
    def __init__(self, app, token, user_id, expires_at):
        self.app, self.token, self.user_id, self.expires_at = app, token, user_id, expires_at

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        values = [value for name, value in scope.get("headers", []) if name.lower() == b"authorization"]
        expected = ("Bearer " + self.token).encode("ascii")
        valid = len(values) == 1 and secrets.compare_digest(values[0], expected) and now() < self.expires_at
        if valid:
            with SessionLocal() as db:
                try:
                    _principal(db, self.user_id)
                except (HTTPException, SQLAlchemyError):
                    valid = False
        if not valid:
            return await JSONResponse(
                {"error": "Unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
            )(scope, receive, send)

        async def secure_send(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).extend(
                    [(b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")]
                )
            await send(message)

        return await self.app(scope, receive, secure_send)


def create_app():
    from mcp.server import MCPServer

    token, user_id, scopes, expires_at = _environment()
    mcp = MCPServer("Veriora private evidence tools")

    @mcp.tool()
    def list_my_documents(offset: int = 0, limit: int = 50) -> dict:
        """List unexpired document metadata for the fixed authorized account."""
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("Invalid pagination.")

        def action(db, user):
            rows = db.scalars(
                select(Source)
                .where(Source.owner_id == user.id, Source.expires_at > now())
                .order_by(Source.captured_at.desc())
                .offset(offset)
                .limit(limit)
            )
            return {"documents": [source_dict(s) for s in rows]}

        return _execute(user_id, scopes, "list_my_documents", action)

    @mcp.tool()
    def get_document_sections(source_id: str, offset: int = 0, limit: int = 20) -> dict:
        """Read preserved extracted sections with exact source locators; no raw file access."""
        if not source_id or len(source_id) > 80 or offset < 0 or not 1 <= limit <= 50:
            raise ValueError("Invalid source or pagination.")

        def action(db, user):
            source = owned(db, Source, source_id, user)
            rows = db.scalars(
                select(Section)
                .where(Section.source_id == source.id)
                .order_by(Section.ordinal)
                .offset(offset)
                .limit(limit)
            )
            return {"source": source_dict(source), "sections": [s.data for s in rows]}

        return _execute(user_id, scopes, "get_document_sections", action)

    @mcp.tool()
    def search_document_clauses(
        analysis_id: str,
        query: str = "",
        category: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        """Search retained findings, preserving unsupported and ambiguous status labels."""
        if (
            len(analysis_id) > 80
            or len(query) > 500
            or (category and len(category) > 50)
            or (status and len(status) > 50)
        ):
            raise ValueError("Input exceeds tool limits.")
        return _execute(
            user_id,
            scopes,
            "search_document_clauses",
            lambda db, user: {
                "findings": get_findings(analysis_id, db, user, category, status, query, offset, limit)
            },
        )

    @mcp.tool()
    def get_evidence_passport(analysis_id: str, finding_id: str) -> dict:
        """Inspect an authorized finding, source metadata and its verification details."""
        if len(analysis_id) > 80 or len(finding_id) > 80:
            raise ValueError("Invalid identifier.")

        def action(db, user):
            analysis = owned(db, Analysis, analysis_id, user)
            finding = db.get(Finding, finding_id)
            if not finding or finding.analysis_id != analysis.id:
                raise HTTPException(404, "Resource unavailable.")
            return {
                "finding": finding_dict(finding),
                "sources": [source_dict(s) for s in analysis_sources(db, analysis)],
                "coverage": analysis.coverage,
                "limitations": analysis.limitations,
            }

        return _execute(user_id, scopes, "get_evidence_passport", action)

    @mcp.tool()
    def get_analysis_report(analysis_id: str) -> dict:
        """Read analysis summary, coverage and limits; does not generate or download an export."""
        if len(analysis_id) > 80:
            raise ValueError("Invalid identifier.")
        return _execute(
            user_id, scopes, "get_analysis_report", lambda db, user: get_analysis(analysis_id, db, user)
        )

    # Default transport security allows localhost only and rejects DNS rebinding.
    # V2's 2026-07-28 transport is inherently stateless. Legacy clients are stateless too.
    return BearerGuard(
        mcp.streamable_http_app(stateless_http=True, json_response=True, max_request_body_size=65536),
        token,
        user_id,
        expires_at,
    )
