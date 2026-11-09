"""Bounded passive extraction; offsets always reference unmodified extracted Unicode text."""

from __future__ import annotations

import re
import zipfile
from hashlib import sha256
from io import BytesIO
from pathlib import Path


class ExtractionError(ValueError):
    """Safe, user-facing input validation error."""


def extract(data: bytes, name: str, max_bytes: int = 20 * 1024 * 1024, max_pages: int = 150) -> dict:
    if not data or len(data) > max_bytes:
        raise ExtractionError("Document is empty or exceeds the upload size limit.")
    suffix = Path(name).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".html", ".htm"}:
        raise ExtractionError("Supported formats are PDF, DOCX, TXT and HTML.")
    sections: list[dict] = []
    warnings: list[str] = []
    pages_total = pages_extracted = 0
    source_digest = sha256(data).hexdigest()

    def add(text: str, locator: dict, page: int | None = None, heading: str = ""):
        if not text.strip():
            return
        ordinal = len(sections)
        sections.append(
            {
                "id": f"sec_{source_digest[:12]}_{ordinal}",
                "ordinal": ordinal,
                "page": page,
                "heading": heading,
                "text": text,
                "locator": {**locator, "offset_unit": "unicode_codepoint", "identity_map": True},
            }
        )

    try:
        if suffix == ".pdf":
            if not data.startswith(b"%PDF-"):
                raise ExtractionError("The uploaded file is not a PDF.")
            import pymupdf

            with pymupdf.open(stream=data, filetype="pdf") as document:
                if document.needs_pass:
                    raise ExtractionError("Password-protected PDF: upload an unlocked copy.")
                pages_total = document.page_count
                if not 0 < pages_total <= max_pages:
                    raise ExtractionError(f"PDF must contain between 1 and {max_pages} pages.")
                warnings.append(
                    "PDF reading order and hidden text cannot be guaranteed; inspect original pages."
                )
                for index in range(pages_total):
                    page = document[index]
                    try:
                        blocks = page.get_text("blocks", sort=True)
                        text_blocks = [b for b in blocks if len(b) > 6 and b[6] == 0 and b[4].strip()]
                        if not text_blocks:
                            warnings.append(f"Page {index + 1} has no extractable text; OCR is required.")
                            continue
                        pages_extracted += 1
                        for block in text_blocks:
                            add(
                                block[4],
                                {"kind": "pdf_block", "bbox": list(block[:4]), "block": block[5]},
                                index + 1,
                            )
                    except Exception:  # noqa: BLE001 - isolate parser failures and disclose every failed page.
                        warnings.append(f"Page {index + 1} could not be extracted.")
            mime = "application/pdf"
        elif suffix == ".docx":
            if not zipfile.is_zipfile(BytesIO(data)):
                raise ExtractionError("The uploaded file is not a DOCX archive.")
            with zipfile.ZipFile(BytesIO(data)) as archive:
                infos = archive.infolist()
                if len(infos) > 5000 or sum(i.file_size for i in infos) > 80 * 1024 * 1024:
                    raise ExtractionError("DOCX decompression limit exceeded.")
                if "word/document.xml" not in archive.namelist() or any(
                    "vbaProject" in i.filename for i in infos
                ):
                    raise ExtractionError("Invalid or macro-enabled DOCX is unsupported.")
            from docx import Document
            from docx.oxml.ns import qn
            from docx.table import Table
            from docx.text.paragraph import Paragraph

            document = Document(BytesIO(data))
            heading = ""
            for index, child in enumerate(document.element.body.iterchildren()):
                if child.tag == qn("w:p"):
                    paragraph = Paragraph(child, document)
                    if paragraph.style and paragraph.style.name.startswith("Heading"):
                        heading = paragraph.text
                    add(paragraph.text, {"kind": "docx_paragraph", "paragraph": index + 1}, heading=heading)
                elif child.tag == qn("w:tbl"):
                    table = Table(child, document)
                    for row_index, row in enumerate(table.rows):
                        add(
                            " | ".join(cell.text for cell in row.cells),
                            {"kind": "docx_table_row", "block": index + 1, "row": row_index + 1},
                            heading=heading,
                        )
            warnings.append(
                "DOCX pagination is unavailable. Headers, footers, text boxes and embedded attachments require original-file review."
            )
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ExtractionError("Text must use UTF-8 encoding; convert and upload again.") from exc
            if "\x00" in text or sum(ord(c) < 32 and c not in "\n\r\t" for c in text) > 3:
                raise ExtractionError("Binary or suspicious text input is unsupported.")
            if suffix in {".html", ".htm"}:
                from bs4 import BeautifulSoup

                if not re.search(
                    r"<\s*(?:!doctype\s+html|html|body|head|p|div|section|article|h[1-6])\b",
                    text,
                    re.IGNORECASE,
                ):
                    raise ExtractionError("The uploaded file does not contain recognized HTML.")
                soup = BeautifulSoup(text, "html.parser")
                for node in soup(["script", "style", "iframe", "object", "embed", "noscript", "template"]):
                    node.decompose()
                heading = ""
                blocks = soup.find_all(
                    ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "tr", "pre", "blockquote"]
                )
                for index, node in enumerate(blocks):
                    # Leaf legal blocks avoid double-counting nested list/table text.
                    if node.find(["p", "li", "tr", "pre", "blockquote"]):
                        continue
                    if node.name.startswith("h"):
                        heading = node.get_text(" ", strip=True)
                    add(
                        node.get_text(" ", strip=True),
                        {"kind": "html_block", "tag": node.name, "anchor": node.get("id"), "block": index},
                        heading=heading,
                    )
                if not sections:
                    add(soup.get_text("\n", strip=True), {"kind": "html_document"})
                warnings.append(
                    "HTML capture excludes scripts, dynamic content and linked attachments; discovery is not exhaustive."
                )
                mime = "text/html"
            else:
                if text.startswith(("%PDF-", "PK\x03\x04", "MZ")) or re.search(
                    r"<\s*(?:!doctype|html|script)\b", text[:4096], re.IGNORECASE
                ):
                    raise ExtractionError("File contents do not match the TXT extension.")
                # Retain blank separators in each section, producing a complete original offset map.
                for match in re.finditer(r"(?:[^\n]|\n(?!\s*\n))+(?:\n\s*\n|$)", text):
                    add(match.group(), {"kind": "text_range", "start": match.start(), "end": match.end()})
                mime = "text/plain"
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError("Document is malformed or could not be safely extracted.") from exc
    if not sections:
        raise ExtractionError(
            "No readable text found. Scanned PDFs require OCR, which is not supported in this release."
        )
    if sum(len(s["text"]) for s in sections) > 2_000_000:
        raise ExtractionError("Extracted text exceeds the processing limit.")
    return {
        "sections": sections,
        "coverage": {
            "pages_total": pages_total,
            "pages_extracted": pages_extracted,
            "sections_total": len(sections),
            "warnings": warnings,
        },
        "mime": mime,
    }
