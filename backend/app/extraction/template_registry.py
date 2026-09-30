# -*- coding: utf-8 -*-
"""
Template registry — scans backend/templates/*.json manifests and routes a
filled document to the best-matching hardcoded form template.

A manifest declares:
  - template_id / label / docx (canonical blank form file name)
  - required_anchors / optional_anchors + optional_threshold (detection)
  - defaults (fixed field values of the form)
  - fields (rule list consumed by template_engine.extract_rules)

Bad manifests are skipped at load time with a printed warning — they must
never take down /api/v1/extract.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .template_engine import (
    detect,
    doc_paragraphs,
    extract_marker_keys,
    extract_with_template,
    template_paragraphs,
)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


def _load_specs() -> List[Dict[str, Any]]:
    specs: List[Dict[str, Any]] = []
    for manifest in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            spec = json.loads(manifest.read_text(encoding="utf-8"))
            if not spec.get("template_id"):
                raise ValueError("missing template_id")
            spec["_manifest_path"] = str(manifest)
            spec["_docx_path"] = str(TEMPLATES_DIR / spec.get("docx", ""))
            if not spec.get("required_anchors"):
                raise ValueError("missing required_anchors")
            if not spec.get("fields"):
                raise ValueError("missing fields")
            specs.append(spec)
            _validate_markers(spec)
        except Exception as e:  # noqa: BLE001 — registry must never crash startup
            print(f"[template_registry] ข้าม manifest {manifest.name}: {e}")
    return specs


def _validate_markers(spec: Dict[str, Any]) -> None:
    """Soft check: every rule key should exist as {{key}} in the blank template."""
    try:
        paras = template_paragraphs(spec["_docx_path"])
        marker_keys = set(extract_marker_keys(paras))
    except Exception as e:  # noqa: BLE001
        print(f"[template_registry] {spec['template_id']}: อ่าน template docx ไม่ได้ — {e}")
        return
    missing = []
    for rule in spec.get("fields") or []:
        k = rule.get("key")
        if k and k not in marker_keys:
            missing.append(k)
    if missing:
        print(f"[template_registry] {spec['template_id']}: key ที่ไม่มี {{{{key}}}} ใน template: {missing}")


SPECS: List[Dict[str, Any]] = _load_specs()


def get_spec(template_id: str) -> Optional[Dict[str, Any]]:
    return next((s for s in SPECS if s["template_id"] == template_id), None)


def doc_type_labels() -> Dict[str, str]:
    return {s["template_id"]: s.get("label", s["template_id"]) for s in SPECS}


def extract_spec(file_bytes: bytes, spec: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Extract with a specific template spec (used by explicit doc_type override)."""
    return extract_with_template(file_bytes, spec)


def detect_best(paragraphs: List[str]) -> Tuple[Optional[Dict[str, Any]], float]:
    """Best template whose score passes its optional_threshold (0.0 when none)."""
    best, best_score = None, 0.0
    for spec in SPECS:
        score = detect(spec, paragraphs)
        threshold = float(spec.get("optional_threshold", 0.4))
        if score >= threshold and score > best_score:
            best, best_score = spec, score
    return best, best_score


def try_extract(file_bytes: bytes) -> Optional[Tuple[Dict[str, Any], str, float, List[str]]]:
    """Auto-detect + extract with the best-matching template.

    Returns (extracted, doc_type, confidence, warnings) or None when no
    template matches well enough (caller falls back to the generic pipeline).
    """
    paragraphs = doc_paragraphs(file_bytes)
    spec, score = detect_best(paragraphs)
    if spec is None:
        return None

    extracted, warnings = extract_with_template(file_bytes, spec)
    # Post-match sanity: an instance of this form must have at least a title or
    # a date — otherwise treat it as a false positive and fall back.
    if not extracted.get("project_title") and not extracted.get("doc_date"):
        return None
    return extracted, spec["template_id"], round(score, 2), warnings
