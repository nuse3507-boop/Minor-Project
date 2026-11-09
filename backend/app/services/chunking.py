"""Structure-first token-budgeted chunks, preserving exact section-relative source spans."""

from __future__ import annotations

import re
from functools import lru_cache
from hashlib import sha256


@lru_cache(maxsize=1)
def tokenizer():
    import tiktoken

    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(tokenizer().encode(text, disallowed_special=()))


def _pieces(text: str, budget: int):
    """Prefer complete sentences; an oversized sentence uses measured token-budget bisection."""
    cursor = 0
    for boundary in re.finditer(r"(?<=[.!?;])\s+|\n\s*\n|$", text):
        end = boundary.end()
        if end <= cursor:
            continue
        while count_tokens(text[cursor:end]) > budget:
            low, high = cursor + 1, end
            while low < high:
                mid = (low + high + 1) // 2
                if count_tokens(text[cursor:mid]) <= budget:
                    low = mid
                else:
                    high = mid - 1
            if count_tokens(text[cursor:low]) > budget:
                raise ValueError("Token budget cannot contain a single character.")
            yield cursor, low
            cursor = low
        if end > cursor:
            yield cursor, end
            cursor = end
    if cursor < len(text):
        yield cursor, len(text)


def chunk_sections(sections: list[dict], budget: int = 1800, overlap: int = 150) -> list[dict]:
    if budget < 16 or overlap < 0 or overlap >= budget:
        raise ValueError("Invalid token budget or overlap.")
    chunks: list[dict] = []
    current: list[tuple[dict, int, int]] = []

    def render(pieces):
        return "\n\n".join(s["text"][start:end] for s, start, end in pieces)

    def emit():
        nonlocal current
        if not current:
            return
        text = render(current)
        chunks.append(
            {
                "index": len(chunks),
                "text": text,
                "token_count": count_tokens(text),
                "content_hash": sha256(text.encode()).hexdigest(),
                "spans": [
                    {
                        "section_id": s["id"],
                        "start": start,
                        "end": end,
                        "page": s.get("page"),
                        "heading": s.get("heading", ""),
                    }
                    for s, start, end in current
                ],
            }
        )
        # Overlap consists of complete trailing sentences/sections, bounded by measured tokens.
        context = []
        for piece in reversed(current):
            trial = [piece, *context]
            if count_tokens(render(trial)) > overlap:
                break
            context = trial
        current = context

    for section in sections:
        text = section["text"]
        pieces = [(0, len(text))] if count_tokens(text) <= budget else list(_pieces(text, budget))
        for start, end in pieces:
            piece = (section, start, end)
            if current and count_tokens(render([*current, piece])) > budget:
                emit()
                if current and count_tokens(render([*current, piece])) > budget:
                    current = []
            current.append(piece)
    if current:
        # Identical wording at different source offsets is still distinct source coverage.
        emit()
    return chunks
