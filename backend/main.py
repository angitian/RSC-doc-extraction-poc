# -*- coding: utf-8 -*-
"""
RSC Administrative Productivity Suite — FastAPI backend.

Endpoints:
  GET  /api/v1/health            -> service status
  POST /api/v1/extract           -> multipart (file, mode, target_url) -> ExtractionResponse

Deploy-agnostic: reads $PORT (Render/Cloud Run) with default 7860 (HF Spaces).
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import (
    ALLOWED_EXTENSIONS,
    ANNEX_FILENAME,
    CORS_ALLOW_HEADERS,
    CORS_ALLOW_METHODS,
    CORS_ALLOW_ORIGINS,
    EXCEL_FILENAME,
    MAX_FILE_SIZE_MB,
)
from app.extraction.classifier import classify_document
from app.extraction.dispatcher import extract_file
from app.generators.excel_generator import generate_excel_bytes, generate_fill_template_bytes
from app.generators.field_mapper import PROFILES, build_field_mappings
from app.generators.pdf_generator import generate_annex_pdf_bytes
from app.models import ExtractionResponse
from app.normalizer.expense_rollup import extract_budget_rollup
from app.normalizer.thai_utils import num_to_thai_baht

app = FastAPI(
    title="RSC Administrative Productivity Suite API",
    version="2.0.0",
    description="Extract structured data from Thai government memos (.docx/.pdf) "
                "and produce dynamic DOM fill instructions, Excel and PDF annex.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_summary(extracted: Dict[str, Any], rollup: Dict[str, Any],
                   doc_type: str, confidence: float) -> Dict[str, Any]:
    date_range = extracted.get("schedule_text", "")
    if not date_range and extracted.get("start_date_iso"):
        date_range = f"{extracted.get('start_date_iso')} ถึง {extracted.get('end_date_iso', '')}"
    items_count = len(rollup.get("rows") or [])
    itinerary_count = sum(len(d.get("items") or []) for d in extracted.get("schedule_activities") or [])

    return {
        "doc_type": doc_type,
        "doc_type_label": {
            "conference_attendance": "ขออนุมัติเข้าร่วมประชุม/อบรม/สัมมนา",
            "travel_request": "คำขออนุมัติเดินทาง",
            "expense_settlement": "รายงาน/ขอเบิกค่าใช้จ่าย",
            "work_report": "รายงานผลการดำเนินงาน",
        }.get(doc_type, doc_type),
        "confidence": confidence,
        "project_name": extracted.get("project_title", ""),
        "traveler": extracted.get("requester_name", ""),
        "date_range": date_range,
        "total_amount": rollup.get("total_amount", 0.0),
        "total_amount_text": num_to_thai_baht(rollup.get("total_amount", 0.0)),
        "expense_items_count": items_count,
        "itinerary_items_count": itinerary_count,
        "categories": rollup.get("expense_summary", {}),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "rsc-extraction-api", "version": "2.0.0"}


def _parse_snapshot(raw_snapshot: str) -> Optional[List[Dict[str, Any]]]:
    """Parse the optional page_snapshot form field (JSON string)."""
    if not raw_snapshot:
        return None
    try:
        data = json.loads(raw_snapshot)
        if isinstance(data, list):
            return data
    except (TypeError, ValueError):
        pass
    return None


@app.post("/api/v1/extract", response_model=ExtractionResponse)
async def extract(
    file: UploadFile = File(...),
    mode: str = Form("full_table"),
    target_url: str = Form(""),
    doc_type: str = Form(""),
    page_snapshot: str = Form(""),
):
    if mode not in ("full_table", "annex_pdf"):
        raise HTTPException(status_code=400, detail=f"mode ไม่ถูกต้อง: {mode} (ต้องเป็น full_table หรือ annex_pdf)")

    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"ไม่รองรับไฟล์ประเภท {ext} — รองรับเฉพาะ .docx .pdf และ .xlsx")

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="ไฟล์ว่างเปล่า")
    if len(raw) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"ไฟล์ใหญ่เกิน {MAX_FILE_SIZE_MB} MB")

    warnings: list[str] = []
    snapshot = _parse_snapshot(page_snapshot)
    try:
        extracted, doc_type, confidence = extract_file(raw, ext, doc_type_override=doc_type or None)
    except Exception as e:  # noqa: BLE001 — surface parse errors to the client
        raise HTTPException(status_code=422, detail=f"ไม่สามารถอ่านไฟล์ได้: {str(e)}")

    rollup = extract_budget_rollup(extracted, extracted.get("breakdown") or [])

    field_mappings, map_warnings, profile_info = build_field_mappings(
        extracted, mode, target_url, page_snapshot=snapshot)
    warnings.extend(map_warnings)

    summary = _build_summary(extracted, rollup, doc_type, confidence)

    # ---- Output assets (base64) ----
    pdf_b64: str | None = None
    excel_b64: str | None = None
    try:
        pdf_bytes = generate_annex_pdf_bytes(extracted, rollup)
        pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
    except Exception as e:  # noqa: BLE001
        warnings.append(f"สร้าง PDF แนบไม่สำเร็จ: {str(e)}")

    try:
        excel_bytes = generate_excel_bytes(extracted, rollup)
        excel_b64 = base64.b64encode(excel_bytes).decode("ascii")
    except Exception as e:  # noqa: BLE001
        warnings.append(f"สร้าง Excel ไม่สำเร็จ: {str(e)}")

    # ---- Raw tables for TSV ----
    raw_tables: Dict[str, list] = {
        "breakdown": [
            [str(r.get("รายการ", "")), str(r.get("รายละเอียด", "")), str(r.get("จำนวนเงิน (บาท)", ""))]
            for r in rollup.get("rows") or []
        ],
        "schedule": [],
    }
    for day in extracted.get("schedule_activities") or []:
        for act in day.get("items") or []:
            raw_tables["schedule"].append(
                [str(day.get("date_title", "")), str(day.get("location", "")),
                 str(act.get("time", "")), str(act.get("activity", ""))]
            )

    return ExtractionResponse(
        doc_type=doc_type,
        confidence=confidence,
        metadata=extracted,
        expense_summary=rollup["expense_summary"],
        total_amount=rollup["total_amount"],
        raw_tables=raw_tables,
        form_type=profile_info.get("form_type"),
        profile_id=profile_info.get("profile_id"),
        profile_name=profile_info.get("profile_name"),
        page_match_confidence=profile_info.get("page_match_confidence", 0.0),
        editable_fields=profile_info.get("editable_fields", []),
        field_mappings=field_mappings,
        pdf_annex_base64=pdf_b64,
        pdf_annex_filename=ANNEX_FILENAME,
        excel_filled_base64=excel_b64,
        excel_filled_filename=EXCEL_FILENAME,
        summary=summary,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Quick Form / Excel template support
# ---------------------------------------------------------------------------
# Derived form fields — the system computes these (Quick Form should hide them)
AUTO_GENS = {
    "conference_select_travel_type",
    "conference_select_region",
    "conference_select_acc",
    "conference_select_participant_role",
    "conference_travelers",
}


@app.get("/api/v1/forms")
def list_forms():
    """List registered form profiles + their field schema (for Quick Form)."""
    out = []
    for p in PROFILES:
        fields = []
        if "fields" in p:
            for f in p["fields"]:
                gen = f.get("gen")
                if gen in AUTO_GENS:
                    continue  # derived — not user-enterable in Quick Form
                if not (f.get("from") or gen) or not f.get("label"):
                    continue  # skip ghost fields (e.g. travelers gen w/o label)
                fields.append({
                    "key": f.get("from") or gen,
                    "label": f.get("label", ""),
                    "type": f.get("type", "text"),
                })
        out.append({
            "profile_id": p.get("profile_id"),
            "name": p.get("name"),
            "form_type": p.get("form_type"),
            "fields": fields,
        })
    return {"forms": out}


@app.post("/api/v1/fill", response_model=ExtractionResponse)
async def fill(values: Dict[str, Any]):
    """Build field_mappings directly from values (no document required).

    Body: {"target_url": "...", "profile_id": "rsc_conference",
           "page_snapshot": [...], "values": {"event_title": "...", "per_diem": 200, ...}}
    """
    target_url = str(values.get("target_url") or "")
    profile_id = str(values.get("profile_id") or "")
    snapshot = values.get("page_snapshot") or None
    vals: Dict[str, Any] = dict(values.get("values") or {})

    profile = next((p for p in PROFILES if p.get("profile_id") == profile_id), None)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"ไม่พบ profile: {profile_id}")

    # Build a minimal extracted dict so the profile builder can run
    extracted: Dict[str, Any] = dict(vals)
    cats = {}
    for k in ("registration", "per_diem", "accommodation", "vehicle", "vehicle_compensation", "other"):
        cats[k] = float(str(vals.get(k) or 0).replace(",", ""))
    extracted["expense_categories"] = cats
    if not extracted.get("project_title"):
        extracted["project_title"] = extracted.get("event_title", "")

    field_mappings, warnings, info = build_field_mappings(extracted, "full_table", target_url, page_snapshot=snapshot)
    rollup = extract_budget_rollup(extracted, extracted.get("breakdown") or [])
    summary = _build_summary(extracted, rollup, info.get("form_type") or "manual", 1.0)

    return ExtractionResponse(
        doc_type=info.get("form_type") or "manual",
        confidence=1.0,
        metadata=extracted,
        expense_summary=rollup["expense_summary"],
        total_amount=rollup["total_amount"],
        form_type=info.get("form_type"),
        profile_id=info.get("profile_id"),
        profile_name=info.get("profile_name"),
        page_match_confidence=info.get("page_match_confidence", 0.0),
        editable_fields=info.get("editable_fields", []),
        field_mappings=field_mappings,
        summary=summary,
        warnings=warnings,
    )


@app.get("/api/v1/templates/{profile_id}")
def get_template(profile_id: str):
    """Download the fill-in Excel template (.xlsx) for a form profile."""
    profile = next((p for p in PROFILES if p.get("profile_id") == profile_id), None)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"ไม่พบ profile: {profile_id}")
    fields = []
    for f in profile.get("fields", []):
        if f.get("from"):
            fields.append({"key": f.get("from"), "label": f.get("label", ""), "type": f.get("type", "text")})
    data = generate_fill_template_bytes(fields)
    import base64 as _b64

    return {"filename": f"template_{profile_id}.xlsx", "base64": _b64.b64encode(data).decode("ascii")}


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))
