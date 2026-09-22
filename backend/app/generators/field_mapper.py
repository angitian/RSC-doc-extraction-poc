# -*- coding: utf-8 -*-
"""
Dynamic DOM Field Mapper.

Profiles are keyed by target_url patterns. When the target web portal changes
its DOM or a new portal is added, update a profile here — no extension update
is needed (the extension only executes whatever field_mappings it receives).
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..models import DOMAction


def _act(selector: str, action: str = "set_value", value: str | None = None,
         repeat: int = 1, delay_ms: int = 150, index: int | None = None,
         meta: Dict[str, Any] | None = None, label: str | None = None) -> DOMAction:
    return DOMAction(selector=selector, action=action, value=value, label=label,
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
    actions.append(_act("#project-document-number", "set_value", extracted.get("doc_number_tail", ""), label="เลขที่หนังสือ"))
    actions.append(_act("#project-document-date", "set_value", extracted.get("doc_date_iso", ""), label="วันที่หนังสือ"))
    if extracted.get("contact_phone"):
        actions.append(_act("#project-document-contact-phone", "set_value", extracted.get("contact_phone", ""),
                             label="โทรศัพท์สำหรับติดต่อในหนังสือ"))

    # ---- Section 2: เนื้อหาบันทึกข้อความ ----
    if extracted.get("project_context"):
        actions.append(_act("#backgroundContext-field", "set_value", extracted.get("project_context", ""),
                             label="ที่มาและบริบทของโครงการ"))
    if extracted.get("project_objective"):
        # วัตถุประสงค์: React auto-ID (textarea-19 -> textarea-63) เปลี่ยนทุก build
        # -> ใช้ label ภาษาไทยเป็นตัวชี้หลัก (selector ว่าง)
        actions.append(_act("", "set_value", extracted.get("project_objective", ""), label="วัตถุประสงค์"))
    if extracted.get("requester_name"):
        actions.append(_act("#project-applicant-name", "set_value", extracted.get("requester_name", ""),
                             label="ชื่อ-นามสกุล"))
    if extracted.get("requester_position"):
        actions.append(_act("#project-applicant-position", "set_value", extracted.get("requester_position", ""),
                             label="ตำแหน่ง"))
    actions.append(_act("", "set_value", extracted.get("action_verb", "ดำเนินงาน"), label="คำกริยาดำเนินการ"))
    if extracted.get("project_title"):
        actions.append(_act("", "set_value", extracted.get("project_title", ""), label="ชื่อโครงการ/โครงการย่อย"))
    if extracted.get("start_date_iso"):
        actions.append(_act("#project-location-shared-start-date", "set_value", extracted.get("start_date_iso", ""),
                             label="วันที่เริ่มต้นของทุกสถานที่"))
    if extracted.get("end_date_iso"):
        actions.append(_act("#project-location-shared-end-date", "set_value", extracted.get("end_date_iso", ""),
                             label="วันที่สิ้นสุดของทุกสถานที่"))
    if extracted.get("location_name"):
        actions.append(_act("#project-location-0-location", "set_value", extracted.get("location_name", ""),
                             label="สถานที่ดำเนินโครงการ"))
    if extracted.get("province_name"):
        actions.append(_act("#project-location-0-province", "set_value", extracted.get("province_name", ""),
                             label="จังหวัด"))
    if extracted.get("target_group_name"):
        actions.append(_act("#target-group-name-project-target-group-2", "set_value",
                             extracted.get("target_group_name", ""), label="ชื่อกลุ่มเป้าหมาย"))
    if extracted.get("target_group_quantity"):
        actions.append(_act("#target-group-quantity-project-target-group-2", "set_value",
                             extracted.get("target_group_quantity", ""), label="จำนวน"))
    if extracted.get("target_group_unit"):
        actions.append(_act("#target-group-unit-project-target-group-2", "set_value",
                             extracted.get("target_group_unit", ""), label="หน่วย"))
    if extracted.get("action_details"):
        actions.append(_act("#project-additional-details", "set_value", extracted.get("action_details", ""),
                             label="ข้อความชี้แจงเพิ่มเติมหลังกลุ่มเป้าหมาย"))

    # ---- Section 4: วงเงินรวม ----
    if extracted.get("budget_amount"):
        # วงเงินรวม: React auto-ID (input-95 -> input-315) -> label-based
        actions.append(_act("", "set_value", str(extracted.get("budget_amount", "")).replace(",", ""),
                             label="วงเงินรวม (บาท)"))

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
# Profile registry
# ---------------------------------------------------------------------------
PROFILES = [
    {
        "name": "RSC Smart Approval",
        "url_patterns": ["smart-approval", "smart_approval", "rsc", "approval"],
        "demo": True,
        "build": _build_rsc_mappings,
    },
]


def resolve_profile(target_url: str):
    """Return the profile dict matching target_url, or None."""
    url = (target_url or "").lower()
    for profile in PROFILES:
        for pattern in profile["url_patterns"]:
            if pattern in url:
                return profile
    return None


def build_field_mappings(extracted: Dict[str, Any], mode: str, target_url: str) -> tuple:
    """Build DOMAction list for the target page.

    Returns (mappings, warnings).
    """
    profile = resolve_profile(target_url)
    if profile is None:
        return [], [f"ไม่พบ profile สำหรับหน้าเว็บนี้ ({target_url}) — ยังยิงข้อมูลอัตโนมัติไม่ได้"]

    mappings = profile["build"](extracted, mode)
    warnings = []
    if not (extracted.get("breakdown") or []) and mode == "full_table":
        warnings.append("ไม่พบตารางค่าใช้จ่ายในเอกสาร — ตารางค่าใช้จ่ายจะว่าง")
    if not (extracted.get("schedule_activities") or []) and mode == "full_table":
        warnings.append("ไม่พบตารางกำหนดการในเอกสาร — ตารางกำหนดการจะว่าง")
    return mappings, warnings
