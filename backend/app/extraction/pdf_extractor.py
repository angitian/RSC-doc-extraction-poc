# -*- coding: utf-8 -*-
"""PDF ingestion via PyMuPDF (fitz).

Extracts text lines (and, when possible, native tables) so the shared
text_pipeline heuristics can run on PDF scans / exports as well.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24 (preferred)
except ImportError:  # pragma: no cover
    import fitz  # older alias

from .text_pipeline import extract_from_text


def _extract_text_and_tables(doc: "fitz.Document") -> tuple:
    paragraphs: List[str] = []
    full_text: List[str] = []
    tables: List[List[List[str]]] = []

    for page in doc:
        text = page.get_text("text")
        for line in text.splitlines():
            line = line.strip()
            if line:
                paragraphs.append(line)
                full_text.append(line)

        # Best-effort native table detection (PyMuPDF >= 1.23)
        try:
            finder = page.find_tables()
            for tab in finder.tables:
                rows = [[str(c).strip() for c in row] for row in tab.extract()]
                if rows and any(any(cell for cell in row) for row in rows):
                    tables.append(rows)
        except Exception:
            pass

    return paragraphs, full_text, tables


def extract_pdf(file_bytes: bytes) -> Dict[str, Any]:
    """Parse a .pdf document and return the extracted field dictionary."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        paragraphs, full_text, tables = _extract_text_and_tables(doc)
        return extract_from_text(paragraphs, full_text, tables)
    finally:
        doc.close()
