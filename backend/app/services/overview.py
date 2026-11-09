"""Source-linked overview metadata; extraction cues never imply legal identity or enforceability."""

import re
from collections import Counter


def build_overview(sections, findings, coverage, state):
    categories = Counter(f.get("category", "OTHER") for f in findings)
    support = Counter(f.get("support_status", "AMBIGUOUS") for f in findings)
    cues = []
    parties = []
    headings = []
    seen = set()
    patterns = [
        ("Privacy-policy wording", r"\bprivacy\s+policy\b"),
        ("Employment-agreement wording", r"\bemployment\s+(?:agreement|contract)\b"),
        ("Non-disclosure wording", r"\bnon[ -]disclosure\b"),
        ("Terms-and-conditions wording", r"\bterms\s+and\s+conditions\b"),
        ("Agreement/contract wording", r"\b(?:agreement|contract)\b"),
    ]
    for section in sections:
        text = section["text"]

        def reference(match, section=section):
            return {
                "source_id": section["source_id"],
                "section_id": section["id"],
                "page": section.get("page"),
                "quote": match.group(),
                "start": match.start(),
                "end": match.end(),
                "match_status": "EXACT",
            }

        if section["source_id"] not in seen:
            seen.add(section["source_id"])
            for label, pattern in patterns:
                match = re.search(pattern, text[:1000], re.IGNORECASE)
                if match:
                    cues.append(
                        {
                            "label": label,
                            "method": "source text cue, not a legal classification",
                            "citation": reference(match),
                        }
                    )
                    break
        if section.get("heading"):
            headings.append(
                {
                    "heading": section["heading"],
                    "source_id": section["source_id"],
                    "section_id": section["id"],
                    "page": section.get("page"),
                }
            )
        for match in re.finditer(
            r"(?im)^(?:employer|employee|company|customer|client|contractor|party [ab])\s*:\s*[^\n]{1,160}",
            text,
        ):
            parties.append(
                {
                    "text": match.group(),
                    "method": "explicit source label; identity not independently verified",
                    "citation": reference(match),
                }
            )
    if state in ("COMPLETED", "PARTIAL_COMPLETION"):
        summary = f"{len(findings)} findings retained: {support['SUPPORTED']} supported, {support['PARTIALLY_SUPPORTED']} partly supported, {support['AMBIGUOUS']} ambiguous and {support['UNSUPPORTED']} unsupported."
    elif state in ("FAILED", "CANCELLED"):
        summary = "Analysis did not complete. An empty findings list does not establish that the document lacks relevant terms."
    else:
        summary = "Analysis is processing. Coverage and reviewed findings will appear as the server finishes."
    return {
        "summary": summary,
        "category_counts": dict(categories),
        "support_counts": dict(support),
        "document_cues": cues,
        "explicit_party_labels": parties[:50],
        "headings": headings[:100],
        "coverage": coverage,
        "limitations": [
            "Document cues and party labels are source-text extraction, not verified legal status or real-world identity."
        ],
    }
