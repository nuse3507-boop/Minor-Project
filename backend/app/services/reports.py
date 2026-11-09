"""Printable evidence report; all document and model text is escaped before rendering."""

from html import escape


def report_html(manifest):
    def safe(value):
        return escape(str(value if value is not None else "Not available"))

    parts = [
        "<h1>VERIORA</h1><p class='eyebrow'>DOCUMENT ANALYSIS / EVIDENCE REPORT</p>",
        f"<p>Analysis {safe(manifest['analysis_id'])}<br>Captured report scope: {safe(manifest['created_at'])}<br>",
        f"Analysis state: {safe(manifest['status'])}</p>",
        "<h2>Scope and limitations</h2><ul>",
    ]
    parts += [f"<li>{safe(item)}</li>" for item in manifest["limitations"]]
    parts += ["</ul><h2>Captured sources</h2>"]
    for source in manifest["sources"]:
        parts += [
            f"<h3>{safe(source['original_name'])}</h3>",
            f"<p>Version: {safe(source['id'])}<br>Acquired: {safe(source['captured_at'])}<br>",
            f"Origin: {safe(source.get('source_url') or source['kind'])}<br>",
            f"SHA-256:<br><span class='hash'>{safe(source['sha256'][:32])}<br>{safe(source['sha256'][32:])}</span></p>",
        ]
    parts += ["<h2>Processing coverage</h2><ul>"]
    for key, value in manifest["coverage"].items():
        parts.append(f"<li>{safe(key.replace('_', ' '))}: {safe(value)}</li>")
    parts += ["</ul><h2>Findings and Evidence Passports</h2>"]
    if not manifest["findings"]:
        parts.append(
            "<p>No findings were generated. This does not establish that the source has no relevant provisions.</p>"
        )
    for index, finding in enumerate(manifest["findings"], 1):
        verified = (
            finding.get("support_status") == "SUPPORTED"
            and all(c.get("match_status") in ("EXACT", "NORMALIZED") for c in finding.get("citations", []))
            and bool(finding.get("citations"))
        )
        status = "Verified against source" if verified else finding.get("support_status", "AMBIGUOUS")
        parts += [
            f"<h3>{index}. {safe(finding['statement'])}</h3>",
            f"<p><b>{safe(status)}</b> / {safe(finding['category'])}<br>Finding: {safe(finding.get('finding_id'))}</p>",
            f"<p>{safe(finding.get('rationale'))}</p>",
        ]
        for citation in finding.get("citations", []):
            parts += [
                f"<blockquote>{safe(citation['quote'])}</blockquote>",
                f"<p>Source: {safe(citation['source_id'])}<br>Section: {safe(citation['section_id'])}<br>",
                f"Page: {safe(citation.get('page'))}; Unicode offsets: {safe(citation['start'])}–{safe(citation['end'])}; ",
                f"Citation validity: {safe(citation.get('match_status'))}</p>",
            ]
        parts += [
            f"<p>Qualifications: {safe('; '.join(finding.get('qualifications', [])) or 'None recorded')}</p>",
            f"<p>Verifier: {safe(finding.get('verification', {}).get('method'))}<br>",
            f"Review rationale: {safe(finding.get('verification', {}).get('rationale'))}<br>",
            f"Model: {safe(finding.get('provider'))} / {safe(finding.get('model'))}<br>",
            f"Prompt version: {safe(finding.get('prompt_version'))}</p>",
        ]
    parts += [
        "<h2>Integrity notice</h2><p>A document digest identifies captured bytes. It does not prove origin authenticity, real-world conduct, enforceability or court admissibility. Keep the JSON manifest alongside this report for machine-readable metadata.</p>"
    ]
    return "".join(parts)
