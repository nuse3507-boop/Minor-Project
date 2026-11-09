"""Deterministic comparison of immutable captures, without semantic/legal conclusions."""

from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher

MAX_CHARACTERS = 100_000
MAX_SECTIONS = 5_000
LIMITATIONS = [
    "This compares exact extracted text from two retained captures; it does not detect legal contradictions or establish semantic equivalence.",
    "Capture timestamps are observation dates, not policy effective dates. Independent uploads may be unrelated documents.",
    "Changes may reflect extraction, formatting, reading order or incomplete source coverage. Inspect the original evidence.",
    "No monitoring or historical archive is implied. Only the two selected immutable source versions were compared.",
]


class ComparisonLimitError(ValueError):
    pass


def _passage(section: dict) -> dict:
    return {
        "section_id": section["id"],
        "source_id": section.get("source_id"),
        "text": section["text"],
        "page": section.get("page"),
        "heading": section.get("heading", ""),
        "locator": section.get("locator", {}),
    }


def compare_sections(before: list[dict], after: list[dict]) -> dict:
    for sections in (before, after):
        if len(sections) > MAX_SECTIONS or sum(len(section["text"]) for section in sections) > MAX_CHARACTERS:
            raise ComparisonLimitError(
                "Comparison supports at most 100,000 extracted characters and 5,000 sections per source."
            )
    # autojunk bounds pathological repeated-section matching; all unmatched text remains visible.
    matcher = SequenceMatcher(a=[s["text"] for s in before], b=[s["text"] for s in after], autojunk=True)
    kinds = {"equal": "unchanged", "insert": "added", "delete": "removed", "replace": "changed"}
    changes = [
        {
            "kind": kinds[tag],
            "before": [_passage(s) for s in before[a_start:a_end]],
            "after": [_passage(s) for s in after[b_start:b_end]],
            "alignment": "exact_text_sequence",
        }
        for tag, a_start, a_end, b_start, b_end in matcher.get_opcodes()
    ]
    counts = Counter(change["kind"] for change in changes)
    return {
        "changes": changes,
        "counts": {kind: counts[kind] for kind in kinds.values()},
        "method": "exact preserved-section sequence diff",
        "limitations": LIMITATIONS,
        "coverage": {
            "before_sections": len(before),
            "after_sections": len(after),
            "before_characters": sum(len(s["text"]) for s in before),
            "after_characters": sum(len(s["text"]) for s in after),
        },
    }
