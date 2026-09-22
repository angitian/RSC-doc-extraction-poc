# -*- coding: utf-8 -*-
"""
Dynamic DOM Field Mapper.

Profiles are keyed by target_url patterns. When the target web portal changes
its DOM or a new portal is added, update a profile here — no extension update
is needed (the extension only executes whatever field_mappings it receives).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..models import DOMAction

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def _act(selector: str, action: str = "set_value", value: str | None = None,
         repeat: int = 1, delay_ms: int = 150, index: int | None = None,
         meta: Dict[str, Any] | None = None, label: str | None = None,
         key: str | None = None, skip_if_value_present: bool = False) -> DOMAction:
    return DOMAction(selector=selector, action=action, value=value, label=label,
                     key=key, skip_if_value_present=skip_if_value_present,
                     repeat=repeat, delay_ms=delay_ms, index=index, meta=meta or {})


def _budget_year(extracted: Dict[str, Any]) -> str:
    """2-digit budget year — prefer the extracted one, fall back to the doc-number tail."""
    year = str(extracted.get("budget_year") or "").strip()
    if year:
        return year
    tail = str(extracted.get("doc_number_tail", ""))
    m = __import__("re").search(r"/(\d{2})$", tail.strip())
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# RSC Smart Approval profile
# ---------------------------------------------------------------------------
def _build_rsc_mappings(extracted: Dict[str, Any], mode: str) -> List[DOMAction]:
    actions: List[DOMAction] = []
    breakdown = extracted.get("breakdown") or []
    schedule = extracted.get("schedule_activities") or []

    # ---- Section 1: ข้อมูลหนังสือ ----
    # ACC select: match option containing budget year suffix, e.g. "RSC-68_..._สกสว"
    yr = _budget_year(extracted)
    if yr:
        actions.append(_act("#acc-field", "set_select", yr, delay_ms=200, label="รหัสงบประมาณ (ACC)"))
    actions.append(_act("#project-document-number", "set_value", extracted.get("doc_number_tail", ""),
                         label="เลขที่หนังสือ", key="doc_number_tail"))
    actions.append(_act("#project-document-date", "set_value", extracted.get("doc_date_iso", ""),
                         label="วันที่หนังสือ", key="doc_date_iso"))
    if extracted.get("contact_phone"):
        actions.append(_act("#project-document-contact-phone", "set_value", extracted.get("contact_phone", ""),
                             label="โทรศัพท์สำหรับติดต่อในหนังสือ", key="contact_phone"))

    # ---- Section 2: เนื้อหาบันทึกข้อความ ----
    if extracted.get("project_context"):
        actions.append(_act("#backgroundContext-field", "set_value", extracted.get("project_context", ""),
                             label="ที่มาและบริบทของโครงการ", key="project_context"))
    if extracted.get("project_objective"):
        # วัตถุประสงค์: React auto-ID (textarea-19 -> textarea-63) เปลี่ยนทุก build
        # -> ใช้ label ภาษาไทยเป็นตัวชี้หลัก (selector ว่าง)
        actions.append(_act("", "set_value", extracted.get("project_objective", ""),
                             label="วัตถุประสงค์", key="project_objective"))
    if extracted.get("requester_name"):
        actions.append(_act("#project-applicant-name", "set_value", extracted.get("requester_name", ""),
                             label="ชื่อ-นามสกุล", key="requester_name", skip_if_value_present=True))
    if extracted.get("requester_position"):
        actions.append(_act("#project-applicant-position", "set_value", extracted.get("requester_position", ""),
                             label="ตำแหน่ง", key="requester_position", skip_if_value_present=True))
    actions.append(_act("", "set_value", extracted.get("action_verb", "ดำเนินงาน"),
                         label="คำกริยาดำเนินการ", key="action_verb"))
    if extracted.get("project_title"):
        actions.append(_act("", "set_value", extracted.get("project_title", ""),
                             label="ชื่อโครงการ/โครงการย่อย", key="project_title"))
    if extracted.get("start_date_iso"):
        actions.append(_act("#project-location-shared-start-date", "set_value", extracted.get("start_date_iso", ""),
                             label="วันที่เริ่มต้นของทุกสถานที่", key="start_date_iso"))
    if extracted.get("end_date_iso"):
        actions.append(_act("#project-location-shared-end-date", "set_value", extracted.get("end_date_iso", ""),
                             label="วันที่สิ้นสุดของทุกสถานที่", key="end_date_iso"))
    if extracted.get("location_name"):
        actions.append(_act("#project-location-0-location", "set_value", extracted.get("location_name", ""),
                             label="สถานที่ดำเนินโครงการ", key="location_name"))
    if extracted.get("province_name"):
        actions.append(_act("#project-location-0-province", "set_value", extracted.get("province_name", ""),
                             label="จังหวัด", key="province_name"))
    if extracted.get("target_group_name"):
        actions.append(_act("#target-group-name-project-target-group-2", "set_value",
                             extracted.get("target_group_name", ""), label="ชื่อกลุ่มเป้าหมาย", key="target_group_name"))
    if extracted.get("target_group_quantity"):
        actions.append(_act("#target-group-quantity-project-target-group-2", "set_value",
                             extracted.get("target_group_quantity", ""), label="จำนวน", key="target_group_quantity"))
    if extracted.get("target_group_unit"):
        actions.append(_act("#target-group-unit-project-target-group-2", "set_value",
                             extracted.get("target_group_unit", ""), label="หน่วย", key="target_group_unit"))
    if extracted.get("action_details"):
        actions.append(_act("#project-additional-details", "set_value", extracted.get("action_details", ""),
                             label="ข้อความชี้แจงเพิ่มเติมหลังกลุ่มเป้าหมาย", key="action_details"))

    # ---- Section 4: วงเงินรวม ----
    if extracted.get("budget_amount"):
        # วงเงินรวม: React auto-ID (input-95 -> input-315) -> label-based
        actions.append(_act("", "set_value", str(extracted.get("budget_amount", "")).replace(",", ""),
                             label="วงเงินรวม (บาท)", key="budget_amount"))

    # ---- Section 5: เอกสารประกอบ ----
    if mode == "annex_pdf":
        # โครงสร้างจริงของฟอร์ม: radios "แนบไฟล์ PDF" (ค่า default อยู่แล้ว) ของ
        # 1. ประมาณการค่าใช้จ่าย และ 2. กำหนดการ ไม่มี file input แยก —
        # ไฟล์จะไปที่ช่องกลางเดียว "3. เอกสารเพิ่มเติม" (input[type=file] ตัวเดียว
        # ทั้งหน้า, accept=application/pdf, multiple) แล้วระบบรวมเป็น "เอกสารแนบ"
        # ต่อท้ายชุดเอกสาร → ฉีด PDF 1 ไฟล์ (มีทั้งประมาณการ+กำหนดการ) ครั้งเดียว
        # Radio scope ตาม name เพื่อไม่สลับกันระหว่าง expense/schedule
        actions.append(_act("", "click", delay_ms=300, label="แนบไฟล์ PDF",
                             meta={"scope_name": "expense-document-source"}))
        actions.append(_act("", "click", delay_ms=300, label="แนบไฟล์ PDF",
                             meta={"scope_name": "schedule-document-source"}))
        # selector ใช้แบบ generic (ไม่ hard-code React ID) — content script จะ
        # fallback ไป input[type=file] / input[accept*=pdf] และ label ให้อัตโนมัติ
        actions.append(_act('input[type="file"]', "file_attach", label="เอกสารเพิ่มเติม", meta={
            "filename": "ประมาณการค่าใช้จ่ายและกำหนดการ.pdf",
            "mime": "application/pdf",
            "note": "value จะถูกแทนด้วย base64 ของ pdf_annex จาก backend โดย sidepanel ก่อนส่งให้ content script",
        }))
        return actions

    # ---- Mode full_table: expense + schedule ถูกกรอกในระบบ ----
    # Radio → สร้างในระบบ (label + scope name กัน React ID เปลี่ยน)
    actions.append(_act("", "click", delay_ms=250, label="สร้างในระบบ",
                         meta={"scope_name": "expense-document-source"}))
    actions.append(_act("", "click", delay_ms=250, label="สร้างในระบบ",
                         meta={"scope_name": "schedule-document-source"}))

    # ข้อมูลหัวเอกสารแนบ
    if extracted.get("project_title"):
        actions.append(_act("#generated-expense-project-name", "set_value", extracted.get("project_title", ""),
                             label="ชื่อโครงการในเอกสาร"))
    if extracted.get("agency_name"):
        actions.append(_act("#generated-expense-department", "set_value", extracted.get("agency_name", ""),
                             label="หน่วยงาน"))

    # ตารางค่าใช้จ่าย (เริ่มต้นมี 1 แถว -> คลิกเพิ่มถ้าจำเป็น)
    # หมายเหตุ: expense-*/schedule-* เป็น ID ที่ app ตั้งชื่อเอง (เสถียร) —
    # ไม่ต้องใช้ label (label fallback จะชี้ผิดแถวถ้า selector พัง)
    for i, row in enumerate(breakdown):
        if i > 0:
            actions.append(_act("button", "click_button", "เพิ่มรายการ", delay_ms=350))
        actions.append(_act(f"#expense-row-type-{i}", "set_select", "item"))
        actions.append(_act(f"#expense-number-{i}", "set_value", str(i + 1)))
        actions.append(_act(f"#expense-description-{i}", "set_value", row.get("รายการ", "")))
        actions.append(_act(f"#expense-calculation-{i}", "set_value", row.get("รายละเอียด", "")))
        amt = str(row.get("จำนวนเงิน (บาท)", "")).replace(",", "")
        if amt:
            actions.append(_act(f"#expense-loan-{i}", "set_value", amt))
    if breakdown:
        actions.append(_act("#generated-expense-notes", "set_value", "ขอถัวเฉลี่ยทุกรายการ", label="หมายเหตุ"))

    # ตารางกำหนดการ (เริ่มต้นมี 1 วัน/1 กิจกรรม -> คลิกเพิ่มถ้าจำเป็น)
    if extracted.get("project_title"):
        actions.append(_act("#generated-schedule-title", "set_value",
                             f"กำหนดการ{extracted.get('project_title', '')}", label="ชื่อกำหนดการ"))
    if extracted.get("schedule_text"):
        actions.append(_act("#generated-schedule-subtitle", "set_value",
                             extracted.get("schedule_text", ""), label="รายละเอียดใต้ชื่อเรื่อง"))

    for di, day in enumerate(schedule):
        if di > 0:
            actions.append(_act("button", "click_button", "เพิ่มวันหรือช่วงกิจกรรม", delay_ms=350))
        actions.append(_act(f"#schedule-date-{di}", "set_value", day.get("date_title", "")))
        if day.get("location"):
            actions.append(_act(f"#schedule-location-{di}", "set_value", day.get("location", "")))
        for ai, act in enumerate(day.get("items") or []):
            if ai > 0:
                # เพิ่มกิจกรรมภายในวันปัจจุบัน: scope ในการ์ดของวันนี้
                actions.append(_act(
                    f"article:has(#schedule-date-{di})", "click_button", "เพิ่มกิจกรรมในช่วงนี้", delay_ms=300))
            actions.append(_act(f"#schedule-time-{di}-{ai}", "set_value", act.get("time", "")))
            actions.append(_act(f"#schedule-activity-{di}-{ai}", "set_value", act.get("activity", "")))
    if schedule:
        actions.append(_act("#generated-schedule-notes", "set_value", "หมายเหตุ: กำหนดการอาจปรับตามความเหมาะสม"))

    return actions


# ---------------------------------------------------------------------------
# Profile registry (JSON-driven)
# ---------------------------------------------------------------------------
def _load_profiles() -> List[Dict[str, Any]]:
    profiles = []
    for f in sorted(PROFILES_DIR.glob("*.json")):
        try:
            profiles.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:  # noqa: BLE001
            print(f"[field_mapper] skip profile {f.name}: {e}")
    return profiles


PROFILES = _load_profiles()

# Python builders referenced by profiles (profiles with complex dynamic logic)
BUILDERS = {"rsc_main": _build_rsc_mappings}


def resolve_profile(target_url: str, page_snapshot: Optional[list] = None) -> Tuple[Optional[Dict], float]:
    """Resolve a form profile from URL patterns + optional DOM signature.

    Returns (profile, confidence 0..1). When a page_snapshot is provided and a
    signature match is strong (>0.6), it wins over the URL; otherwise the URL
    match is authoritative.
    """
    url = (target_url or "").lower()
    url_matches = [p for p in PROFILES if any(pat in url for pat in p.get("url_patterns", []))]

    if page_snapshot:
        ids = set()
        for ctrl in page_snapshot:
            for k in ("id", "name"):
                v = ctrl.get(k)
                if v:
                    ids.add(str(v).lower())
        scored = []
        for p in PROFILES:
            sig = [s.lower() for s in p.get("dom_signature", [])]
            if not sig:
                continue
            hits = sum(1 for s in sig if any(s in i for i in ids))
            scored.append((p, hits / len(sig)))
        scored.sort(key=lambda x: -x[1])
        if scored and scored[0][1] >= 0.6:
            return scored[0][0], scored[0][1]

    if url_matches:
        return url_matches[0], 1.0
    return None, 0.0


# ---------------------------------------------------------------------------
# JSON (declarative) profile builder
# ---------------------------------------------------------------------------
def _apply_transform(value, transform: Optional[str]):
    if value is None:
        return None
    if transform == "strip_commas":
        return str(value).replace(",", "")
    if transform == "number":
        s = str(value).replace(",", "")
        return s if s else None
    return value


def _build_json_mappings(profile: Dict[str, Any], extracted: Dict[str, Any], mode: str) -> Tuple[List[DOMAction], List[Dict]]:
    actions: List[DOMAction] = []
    editable: List[Dict] = []
    categories = extracted.get("expense_categories") or {}

    for f in profile.get("fields", []):
        gen = f.get("gen")
        key = f.get("from")

        if gen == "conference_select_travel_type":
            v = extracted.get("event_type")
            if v:
                actions.append(_act("", "set_select", v, label=f["label"], key=key, delay_ms=150))
                editable.append({"key": key, "label": f["label"], "type": "select", "value": v})

        elif gen == "conference_select_region":
            actions.append(_act("", "set_select", "domestic", label=f["label"]))
            editable.append({"key": key or "region", "label": f["label"], "type": "select", "value": "domestic"})

        elif gen == "conference_select_acc":
            yr = _budget_year(extracted)
            if yr:
                actions.append(_act("", "set_select", yr, label=f["label"], key=key, delay_ms=200))
            editable.append({"key": key or "acc", "label": f["label"], "type": "select", "value": yr or ""})

        elif gen == "conference_select_participant_role":
            title = str(extracted.get("project_title") or "")
            v = "presenter" if "นำเสนอ" in title else "attendee"
            actions.append(_act("", "set_select", v, label=f["label"]))
            editable.append({"key": "participant_role", "label": f["label"], "type": "select", "value": v})

        elif gen == "conference_expense_number":
            amt = float(categories.get(key, 0) or 0)
            v = int(amt) if amt == int(amt) else amt
            if v > 0:
                actions.append(_act("", "set_value", str(v), label=f["label"], key=key,
                                     meta={"type": "number"}, delay_ms=120))
            editable.append({"key": key, "label": f["label"], "type": "number", "value": v if v > 0 else 0})

        elif gen == "conference_travelers":
            n = int(extracted.get("traveler_count") or 1)
            travelers = extracted.get("travelers") or []
            if n > 1:
                actions.append(_act("", "click_button", "เพิ่มผู้ร่วมเดินทาง", repeat=n - 1, delay_ms=300))
                actions.append(_act("", "wait", delay_ms=250))
                if not travelers:
                    pass  # row field IDs are captured live via the 'จับฟอร์ม' tool

        else:
            # Static field: value from metadata[key] or a constant `value`
            val = extracted.get(key) if key else f.get("value")
            if val is None or str(val) == "":
                continue
            val = _apply_transform(val, f.get("transform"))
            act = _act(f.get("target", ""), "set_value", str(val), label=f.get("label"), key=key,
                       meta={"type": f.get("type", "text")})
            act.skip_if_value_present = bool(f.get("skip_if_value_present"))
            actions.append(act)
            editable.append({"key": key, "label": f.get("label"), "type": f.get("type", "text"), "value": str(val)})

    return actions, editable


def build_field_mappings(extracted: Dict[str, Any], mode: str, target_url: str,
                         page_snapshot: Optional[list] = None) -> Tuple[List[DOMAction], List[str], Dict[str, Any]]:
    """Build DOMAction list for the target page.

    Returns (mappings, warnings, info) where info carries profile_id,
    form_type, page_match_confidence and editable_fields (for the review card).
    """
    profile, confidence = resolve_profile(target_url, page_snapshot)
    info: Dict[str, Any] = {
        "profile_id": None,
        "profile_name": None,
        "form_type": None,
        "page_match_confidence": 0.0,
        "editable_fields": [],
    }
    if profile is None:
        return [], [f"ไม่พบ profile สำหรับหน้าเว็บนี้ ({target_url}) — ยังยิงข้อมูลอัตโนมัติไม่ได้"], info

    info.update({
        "profile_id": profile.get("profile_id"),
        "profile_name": profile.get("name"),
        "form_type": profile.get("form_type"),
        "page_match_confidence": round(confidence, 2),
    })

    builder_name = profile.get("builder")
    if builder_name:
        mappings = BUILDERS[builder_name](extracted, mode)
        editable = _collect_editable_from_built(mappings)
    else:
        mappings, editable = _build_json_mappings(profile, extracted, mode)
    info["editable_fields"] = editable

    warnings = []
    if not (extracted.get("breakdown") or []) and mode == "full_table" and profile.get("builder") == "rsc_main":
        warnings.append("ไม่พบตารางค่าใช้จ่ายในเอกสาร — ตารางค่าใช้จ่ายจะว่าง")
    if not (extracted.get("schedule_activities") or []) and mode == "full_table" and profile.get("builder") == "rsc_main":
        warnings.append("ไม่พบตารางกำหนดการในเอกสาร — ตารางกำหนดการจะว่าง")
    if profile.get("profile_id") == "rsc_conference" and int(extracted.get("traveler_count") or 1) > 1:
        warnings.append("มีผู้ร่วมเดินทาง >1 คน — ระบบเพิ่มแถวให้แล้ว แต่ช่องกรอกชื่อต้องยืนยันด้วยปุ่ม 'จับฟอร์ม' ครั้งแรก")

    return mappings, warnings, info


def _collect_editable_from_built(mappings: List[DOMAction]) -> List[Dict]:
    """Best-effort editable fields for python-built profiles (rsc_main)."""
    seen = set()
    out = []
    for m in mappings:
        if m.key and m.key not in seen and m.action in ("set_value", "set_select"):
            seen.add(m.key)
            out.append({"key": m.key, "label": m.label or m.key, "type": "text", "value": m.value or ""})
    return out
