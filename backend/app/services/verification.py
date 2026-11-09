"""Deterministic provenance validation is deliberately separate from semantic support."""

from __future__ import annotations

import re


def _normalized(text: str) -> tuple[str, list[int]]:
    output, positions = [], []
    for match in re.finditer(r"\s+|\S", text):
        output.append(" " if match.group().isspace() else match.group())
        positions.append(match.start())
    return "".join(output), positions


def verify_quote(candidate: dict, sections: list[dict]) -> dict:
    result = {
        "section_id": candidate.get("section_id"),
        "quote": candidate.get("quote", ""),
        "page": candidate.get("page"),
        "start": None,
        "end": None,
        "match_status": "INVALID",
        "support_status": "AMBIGUOUS",
        "reason": "The quoted text or supplied source coordinates could not be validated.",
    }
    section = next((s for s in sections if s["id"] == candidate.get("section_id")), None)
    if not section or not isinstance(candidate.get("quote"), str) or not candidate["quote"].strip():
        return result
    if candidate.get("page") is not None and candidate["page"] != section.get("page"):
        return result
    if (
        candidate.get("source_id")
        and section.get("source_id")
        and candidate["source_id"] != section["source_id"]
    ):
        return result
    text, quote = section["text"], candidate["quote"]
    provided_start, provided_end = candidate.get("start"), candidate.get("end")
    if provided_start is not None or provided_end is not None:
        if (
            type(provided_start) is not int
            or type(provided_end) is not int
            or not 0 <= provided_start < provided_end <= len(text)
        ):
            return result
        if text[provided_start:provided_end] != quote:
            return result
        start, end, match_status = provided_start, provided_end, "EXACT"
    else:
        start = text.find(quote)
        if start >= 0:
            # Repeated passages without an explicit location are ambiguous rather than guessed.
            if text.find(quote, start + 1) >= 0:
                return {
                    **result,
                    "reason": "Quote occurs more than once; explicit source offsets are required.",
                }
            end, match_status = start + len(quote), "EXACT"
        else:
            normalized_text, positions = _normalized(text)
            normalized_quote, _ = _normalized(quote)
            match = normalized_text.find(normalized_quote)
            if match < 0 or normalized_text.find(normalized_quote, match + 1) >= 0:
                return result
            start = positions[match]
            final_index = match + len(normalized_quote)
            end = positions[final_index] if final_index < len(positions) else len(text)
            quote, match_status = text[start:end], "NORMALIZED"
    return {
        **result,
        "page": section.get("page"),
        "start": start,
        "end": end,
        "quote": quote,
        "match_status": match_status,
        "reason": "Source span validated; semantic interpretation still requires a separate verifier.",
    }
