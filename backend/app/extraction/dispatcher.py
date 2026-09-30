# -*- coding: utf-8 -*-
"""
Extraction dispatcher — routes a file to the extractor for its doc_type.

Registry is keyed by doc_type; 'auto' uses the classifier, or the caller can
pass an explicit doc_type override (e.g. from the side panel).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .classifier import classify_document
from .conference_extractor import extract_conference
from .docx_extractor import extract_docx
from .excel_extractor import extract_excel
from .pdf_extractor import extract_pdf
from . import template_registry

ExtractorFn = Callable[[bytes], Dict[str, Any]]

# doc_type -> (extensions, extractor)
# conference_attendance: the fixed HR-SD-S-F13 form (.docx)
# memo (default): free-form บันทึกข้อความ (.docx / .pdf / .xlsx)
REGISTRY: Dict[str, Dict[str, Any]] = {
    "conference_attendance": {
        "extensions": {".docx"},
        "extractor": extract_conference,
    },
}


def _memo_extractor_for(ext: str) -> ExtractorFn:
    if ext == ".pdf":
        return extract_pdf
    if ext == ".xlsx":
        return extract_excel
    return extract_docx


def pick_extractor(doc_type: Optional[str], ext: str):
    """Return the extractor for a doc_type, defaulting to the memo extractor."""
    entry = REGISTRY.get(doc_type or "")
    if entry and ext in entry["extensions"]:
        return entry["extractor"]
    return _memo_extractor_for(ext)


def extract_file(file_bytes: bytes, ext: str, doc_type_override: Optional[str] = None) -> Dict[str, Any]:
    """Extract using auto-classification (or an explicit override).

    Returns (extracted_dict, resolved_doc_type, confidence).

    Precedence:
      1. explicit doc_type_override (REGISTRY extractor or template by id)
      2. hardcoded-form template registry (auto-detect, .docx only)
      3. generic memo pipeline + keyword classifier (fallback)
    """
    ext = ext.lower()
    if doc_type_override:
        if doc_type_override in REGISTRY and ext in REGISTRY[doc_type_override]["extensions"]:
            extracted = REGISTRY[doc_type_override]["extractor"](file_bytes)
            return extracted, doc_type_override, 1.0
        spec = template_registry.get_spec(doc_type_override)
        if spec is not None and ext == ".docx":
            extracted, warnings = template_registry.extract_spec(file_bytes, spec)
            extracted["_warnings"] = warnings
            return extracted, doc_type_override, 1.0
        # unknown override -> fall through to auto-detection

    # Auto: template registry first (fixed forms win over generic heuristics)
    if ext == ".docx":
        result = template_registry.try_extract(file_bytes)
        if result is not None:
            extracted, doc_type, confidence, warnings = result
            extracted["_warnings"] = warnings
            return extracted, doc_type, confidence

    # Fallback: generic pipeline + classifier
    candidate = _memo_extractor_for(ext)(file_bytes)
    doc_type, confidence = classify_document(candidate)
    if doc_type in REGISTRY and ext in REGISTRY[doc_type]["extensions"]:
        # re-run with the specialized extractor for better precision
        extracted = REGISTRY[doc_type]["extractor"](file_bytes)
        return extracted, doc_type, confidence
    return candidate, doc_type, confidence
