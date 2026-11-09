from datetime import timedelta

import pytest
from conftest import login_guest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Section, Source, now
from app.services.comparison import ComparisonLimitError, compare_sections


def _sections(texts, source="before"):
    return [
        {
            "id": f"{source}:{index}",
            "source_id": source,
            "text": text,
            "page": None,
            "heading": "Terms",
            "locator": {"kind": "text_range"},
        }
        for index, text in enumerate(texts)
    ]


def test_exact_comparison_preserves_source_passages_and_does_not_infer_contradictions():
    before = _sections(["Consent is required.", "Trial lasts seven days.", "Old refund rule."])
    after = _sections(["Consent is required.", "Trial lasts fourteen days.", "New refund rule."], "after")
    result = compare_sections(before, after)
    assert result["counts"] == {"unchanged": 1, "added": 0, "removed": 0, "changed": 1}
    assert [s["text"] for c in result["changes"] for s in c["before"]] == [s["text"] for s in before]
    assert [s["text"] for c in result["changes"] for s in c["after"]] == [s["text"] for s in after]
    assert "contradictions" in result["limitations"][0]
    assert result["changes"][1]["after"][0]["section_id"] == "after:1"


def test_additions_removals_and_whitespace_changes_are_explicit():
    result = compare_sections(_sections(["A", "removed", "B"]), _sections(["A", "B", "added"], "after"))
    assert result["counts"]["removed"] == 1 and result["counts"]["added"] == 1
    result = compare_sections(_sections(["Consent  required"]), _sections(["Consent required"], "after"))
    assert result["counts"]["changed"] == 1


def test_identical_repeated_clauses_keep_distinct_locations():
    result = compare_sections(_sections(["Repeated"] * 300), _sections(["Repeated"] * 300, "after"))
    assert result["counts"]["unchanged"] == 1
    assert len(result["changes"][0]["before"]) == 300
    assert result["changes"][0]["before"][0]["section_id"] != result["changes"][0]["before"][1]["section_id"]


@pytest.mark.parametrize("texts", [["x" * 100_001], ["x"] * 5001])
def test_comparison_budget_rejects_oversized_inputs(texts):
    with pytest.raises(ComparisonLimitError):
        compare_sections(_sections(texts), _sections(["short"]))


def _upload(client, text):
    from app.worker import run_once

    response = client.post("/api/v1/sources/text", json={"name": "Version.txt", "text": text})
    assert response.status_code == 202
    assert run_once()
    return response.json()["source_id"]


def test_api_compares_captures_and_rejects_unauthorized_expired_or_duplicate_sources(client):
    login_guest(client)
    first = _upload(client, "Consent is required.\n\nFees are 10 units.")
    second = _upload(client, "Consent is required.\n\nFees are 15 units.")
    response = client.post("/api/v1/comparisons", json={"source_ids": [first, second]})
    assert response.status_code == 200, response.text
    assert response.json()["sources"][0]["captured_at"]
    assert response.json()["counts"]["changed"] >= 1
    assert client.post("/api/v1/comparisons", json={"source_ids": [first, first]}).status_code == 422
    with SessionLocal() as db:
        db.get(Source, first).expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert client.post("/api/v1/comparisons", json={"source_ids": [first, second]}).status_code == 404
    client.cookies.clear()
    login_guest(client)
    response = client.post("/api/v1/comparisons", json={"source_ids": [second, first]})
    assert response.status_code == 404 and "Fees" not in response.text


def test_api_rejects_budget_before_diffing(client):
    login_guest(client)
    first = _upload(client, "First version.")
    second = _upload(client, "Second version.")
    with SessionLocal() as db:
        row = db.scalar(select(Section).where(Section.source_id == first))
        row.data = {**row.data, "text": "x" * 100_001}
        db.commit()
    assert client.post("/api/v1/comparisons", json={"source_ids": [first, second]}).status_code == 422
