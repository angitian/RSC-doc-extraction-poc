# -*- coding: utf-8 -*-
"""
Smoke test — exercises the whole pipeline without starting the HTTP server.

Usage:
    python tests/smoke_test.py <path-to-docx-or-pdf> [mode]

Runs: extract -> classify -> rollup -> field_mappings -> excel -> pdf annex
and prints a compact report. Exit code 0 on success.
"""
from __future__ import annotations

import base64
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.extraction.classifier import classify_document
from app.extraction.docx_extractor import extract_docx
from app.extraction.pdf_extractor import extract_pdf
from app.generators.excel_generator import generate_excel_bytes
from app.generators.field_mapper import build_field_mappings
from app.generators.pdf_generator import generate_annex_pdf_bytes
from app.normalizer.expense_rollup import extract_budget_rollup


def run(path: str, mode: str = "full_table") -> int:
    raw = open(path, "rb").read()
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        extracted = extract_docx(raw)
    elif ext == ".pdf":
        extracted = extract_pdf(raw)
    else:
        print(f"unsupported: {ext}")
        return 2

    doc_type, confidence = classify_document(extracted)
    rollup = extract_budget_rollup(extracted, extracted.get("breakdown") or [])
    mappings, warnings = build_field_mappings(extracted, mode, "http://localhost/rsc-approval")

    excel_bytes = generate_excel_bytes(extracted, rollup)
    pdf_bytes = generate_annex_pdf_bytes(extracted, rollup)

    print(f"file       : {os.path.basename(path)}")
    print(f"doc_type   : {doc_type} (conf {confidence})")
    print(f"project    : {extracted.get('project_title', '')[:80]}")
    print(f"total      : {rollup['total_amount']}  categories: {rollup['expense_summary']}")
    print(f"mappings   : {len(mappings)}  (mode={mode})")
    print(f"excel      : {len(excel_bytes)} bytes   pdf: {len(pdf_bytes)} bytes")
    print(f"extra      : location={extracted.get('location_province', '')[:40]}  "
          f"year={extracted.get('budget_year', '')}  recipient={extracted.get('recipient_title', '')[:30]}  "
          f"closing={extracted.get('closing_text', '')[:20]}")
    if warnings:
        print("warnings   :")
        for w in warnings:
            print(f"             - {w}")

    assert excel_bytes[:2] == b"PK", "Excel is not a valid zip/xlsx"
    assert pdf_bytes[:4] == b"%PDF", "Annex is not a valid PDF"

    # New fields (per plan): location fallback + budget_year must be present
    # when the doc has a date; recipient/closing when a memo has them.
    if extracted.get("doc_date"):
        assert extracted.get("budget_year"), "budget_year missing despite doc_date"
    assert extracted.get("location_name"), "location_name empty (fallback not applied)"
    assert extracted.get("province_name"), "province_name empty (fallback not applied)"
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    mode = sys.argv[2] if len(sys.argv) > 2 else "full_table"
    sys.exit(run(sys.argv[1], mode))
