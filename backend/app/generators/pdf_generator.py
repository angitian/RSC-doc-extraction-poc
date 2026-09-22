# -*- coding: utf-8 -*-
"""Annex PDF generation (fpdf2 + Thai font) — 'ประมาณการค่าใช้จ่ายและกำหนดการ'."""
from __future__ import annotations

import io
from typing import Any, Dict, List

from fpdf import FPDF
from fpdf.fonts import FontFace

from ..config import FONT_THAI_PATH
from ..normalizer.thai_utils import num_to_thai_baht


def _load_font(pdf: FPDF) -> str:
    """Register the Thai font if present; fall back to Helvetica."""
    if FONT_THAI_PATH.exists():
        pdf.add_font("Sarabun", "", str(FONT_THAI_PATH))
        # No Sarabun-Bold file bundled — reuse the regular file so the table
        # API's BOLD style resolves instead of raising "Undefined font".
        pdf.add_font("Sarabun", "B", str(FONT_THAI_PATH))
        return "Sarabun"
    return "Helvetica"


def _money(v) -> str:
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v or "")


def _clean(text) -> str:
    """Sanitize text for PDF rendering (tabs are not covered by Thai glyphs)."""
    return str(text or "").replace("\t", " ").replace("\r", " ")


def _draw_table(pdf: FPDF, font: str, headers: List[str], rows: List[List[str]],
                widths: List[float], header_fill=(0, 50, 98)):
    """Bordered table via fpdf2's table API (handles wrapping + page breaks)."""
    pdf.set_font(font, size=9.5)
    header_face = FontFace(emphasis="BOLD", fill_color=header_fill, color=(255, 255, 255))
    with pdf.table(
        borders_layout="ALL",
        col_widths=widths,
        line_height=5.6,
        padding=1,
        text_align="LEFT",
        first_row_as_headings=False,
    ) as table:
        head = table.row()
        for h in headers:
            head.cell(_clean(h), style=header_face, align="C")
        for row in rows:
            body = table.row()
            for cell in row:
                body.cell(_clean(cell))
    pdf.ln(3)


def generate_annex_pdf_bytes(extracted: Dict[str, Any], rollup: Dict[str, Any]) -> bytes:
    """Build the consolidated annex PDF (expense + schedule)."""
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    font = _load_font(pdf)

    # ---- Header ----
    pdf.set_font(font, size=15)
    pdf.cell(0, 9, "ประมาณการค่าใช้จ่ายและกำหนดการ", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font(font, size=11)
    title = extracted.get("project_title", "")
    if title:
        pdf.multi_cell(0, 6.2, _clean(f"โครงการ: {title}"), new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(0, 6.2, _clean(f"ส่วนงาน: {extracted.get('agency_name', '')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(0, 6.2, _clean(f"เลขที่หนังสือ: {extracted.get('doc_number', '')}   วันที่: {extracted.get('doc_date', '')}"),
                   new_x="LMARGIN", new_y="NEXT")
    if extracted.get("requester_name"):
        pdf.multi_cell(0, 6.2, _clean(f"ผู้ขอ: {extracted.get('requester_name', '')}  {extracted.get('requester_position', '')}"),
                       new_x="LMARGIN", new_y="NEXT")
    if extracted.get("schedule_text"):
        pdf.multi_cell(0, 6.2, _clean(f"ช่วงเวลา: {extracted.get('schedule_text', '')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # ---- Expense table ----
    rows = rollup.get("rows") or []
    pdf.set_font(font, size=12)
    pdf.cell(0, 7, "1. ประมาณการค่าใช้จ่าย", new_x="LMARGIN", new_y="NEXT")
    expense_rows = [
        [str(i + 1), r.get("รายการ", ""), r.get("รายละเอียด", ""), _money(r.get("จำนวนเงิน (บาท)", 0))]
        for i, r in enumerate(rows)
    ]
    if expense_rows:
        _draw_table(pdf, font, ["ลำดับ", "รายการ", "รายละเอียด", "จำนวนเงิน (บาท)"],
                    expense_rows, [12, 55, 75, 42])
    pdf.set_font(font, size=10.5)
    pdf.multi_cell(0, 6.2, _clean(f"รวมเป็นเงินทั้งสิ้น {_money(rollup.get('total_amount', 0))} บาท "
                                  f"({num_to_thai_baht(rollup.get('total_amount', 0))})"),
                   new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ---- Schedule table ----
    schedule = extracted.get("schedule_activities") or []
    if schedule:
        pdf.set_font(font, size=12)
        pdf.cell(0, 7, "2. กำหนดการ", new_x="LMARGIN", new_y="NEXT")
        sched_rows: List[List[str]] = []
        for day in schedule:
            items = day.get("items") or []
            if not items:
                sched_rows.append([day.get("date_title", ""), day.get("location", ""), "-", "-"])
                continue
            for act in items:
                sched_rows.append([day.get("date_title", ""), day.get("location", ""),
                                   act.get("time", ""), act.get("activity", "")])
        _draw_table(pdf, font, ["วันที่", "สถานที่", "เวลา", "กิจกรรม"],
                    sched_rows, [38, 44, 26, 78])

    # ---- Signature block ----
    pdf.ln(8)
    pdf.set_font(font, size=11)
    pdf.cell(0, 6.2, "ลงชื่อ ...................................................... ผู้ขออนุมัติ",
             align="R", new_x="LMARGIN", new_y="NEXT")
    if extracted.get("requester_name"):
        pdf.cell(0, 6.2, f"({extracted.get('requester_name', '')})", align="R",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6.2, extracted.get("requester_position", ""), align="R",
                 new_x="LMARGIN", new_y="NEXT")

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
