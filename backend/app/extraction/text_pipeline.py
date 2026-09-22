# -*- coding: utf-8 -*-
"""
Shared text-based extraction pipeline (ported & hardened from app.py).

Works on any source that produces:
  - paragraphs: list[str]   (non-empty text lines in order)
  - full_text:  list[str]   (same lines, used for joined regex scanning)
  - tables:     list[list[list[str]]]  (optional; e.g. python-docx tables / PDF tables)

Kept deliberately dependency-free (no pandas / no streamlit).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional

from ..config import DEFAULT_LOCATION, DEFAULT_PROVINCE, USE_DEFAULT_LOCATION
from ..normalizer.thai_utils import (
    THAI_MONTH_SET,
    num_to_thai_baht,
    parse_thai_date,
)

# Clean default values -------------------------------------------------------
DEFAULT_FIELDS: Dict[str, Any] = {
    "agency_name": "",
    "contact_phone": "",
    "doc_number": "",
    "doc_seq_num": "",
    "doc_number_tail": "",
    "doc_date": "",
    "doc_date_iso": "",
    "budget_year": "",            # BE 2-digit, e.g. "68" (from doc_date)
    "recipient_title": "",        # เรียน: ... (last occurrence = approval chain)
    "closing_text": "",           # จึงเรียนมา...
    "requester_name": "",
    "requester_position": "",
    "approver_left_name": "",
    "approver_left_pos": "",
    "approver_right_name": "",
    "approver_right_pos": "",
    "project_title": "",
    "project_context": "",
    "project_objective": "",
    "action_verb": "ดำเนินงาน",
    "action_details": "",
    "target_group_name": "ผู้เข้าร่วม",
    "target_group_quantity": "1",
    "target_group_unit": "งาน",
    "location_name": "",
    "province_name": "",
    "location_province": "",
    "schedule_text": "",
    "start_date_iso": "",
    "end_date_iso": "",
    "budget_amount": "",
    "budget_text": "",
    "breakdown": [],
    "schedule_activities": [],
}


def _today_iso() -> str:
    return date.today().strftime("%Y-%m-%d")


def extract_from_text(
    paragraphs: List[str],
    full_text: List[str],
    tables: Optional[List[List[List[str]]]] = None,
) -> Dict[str, Any]:
    """Run the full regex/heuristic extraction over document text lines."""
    extracted = dict(DEFAULT_FIELDS)
    full_text_str = "\n".join(full_text)
    tables = tables or []

    # 0. ส่วนงาน & เบอร์โทรศัพท์
    agency_match = re.search(r"ส่วนงาน\s*([^\n\r]+)", full_text_str)
    if agency_match:
        raw_agency = agency_match.group(1).strip()
        # Keep the agency name clean — strip trailing "\t โทร ..." / phone digits
        agency_name = re.split(r"\s*(?:โทร\.?|โทรศัพท์)\s*[0-9\-\s]*$", raw_agency)[0].strip()
        extracted["agency_name"] = agency_name

    phone_match = re.search(r"(?:โทร\.?|โทรศัพท์)\s*([0-9\-\s]{3,15})", full_text_str)
    if phone_match:
        extracted["contact_phone"] = phone_match.group(1).strip()

    # 2. วันที่หนังสือ (parsed first so the doc-number tail can reuse its year)
    date_match = re.search(r"วันที่\s*(\d{1,2}\s+[^\s\d]+\s+\d{4})", full_text_str)
    if date_match:
        extracted["doc_date"] = date_match.group(1).strip()
        d_obj = parse_thai_date(extracted["doc_date"])
        if d_obj:
            extracted["doc_date_iso"] = d_obj.strftime("%Y-%m-%d")
            extracted["budget_year"] = str((d_obj.year + 543) % 100)  # BE 2-digit, e.g. 68

    # เรียน: ... (use the LAST occurrence = the approval chain addressee)
    learn_lines = [p for p in paragraphs if p.startswith("เรียน") and len(p.strip()) > 6]
    if learn_lines:
        extracted["recipient_title"] = learn_lines[-1].replace("เรียน", "", 1).strip()

    # จึงเรียนมา ... (closing text)
    close_match = re.search(r"(จึงเรียนมา[^\n\r]*)", full_text_str)
    if close_match:
        extracted["closing_text"] = close_match.group(1).strip()

    # 1. เลขที่หนังสือ
    num_match = re.search(r"(?:ที่|อว\.?)\s*([อว\s\.\d\/\-]+)", full_text_str)
    if num_match:
        val = num_match.group(1).strip()
        # Messy layouts may put 'วันที่ ...' on the same line as the doc number.
        # The char class includes 'ว' so it can swallow the first letter of
        # 'วันที่' — handle both the full word and the truncated 'ว'.
        val = re.split(r"\s*วันที่", val)[0]
        val = re.sub(r"\s*ว\s*$", "", val)
        val = re.sub(r"\s+", " ", val).strip()
        if not val.startswith("อว"):
            val = f"อว {val}"
        extracted["doc_number"] = val

        # Tail = the numeric run like '7608.8.1/1234/69' or '7608.8/'
        # (must start with a digit so 'อว.' does not confuse the match)
        num_run = re.search(r"\d[\d\.]*(?:\/[0-9\.\/]*)?", val)
        if num_run:
            tail = num_run.group(0).strip(" .")
            # Incomplete tail (ends with '/') -> complete with budget year
            # from the document date (e.g. '7608.8/' + เอกสารปี 2568 -> '7608.8/68')
            if tail.endswith("/"):
                d_obj = parse_thai_date(extracted.get("doc_date") or "")
                yr = str((d_obj.year + 543) % 100) if d_obj else str((date.today().year + 543) % 100)
                tail = f"{tail}{yr}"
            extracted["doc_number_tail"] = tail
        else:
            extracted["doc_number_tail"] = val.replace("อว", "").strip()

        seq_match = re.search(r"7608\.8(?:\.1)?\/([^\/\s]+)", val)
        if seq_match:
            extracted["doc_seq_num"] = seq_match.group(1).strip()
        else:
            seq2 = re.search(r"\/([^\/\s]+)(?:\/\d{2})?", val)
            if seq2:
                extracted["doc_seq_num"] = seq2.group(1).strip()

    # 3. เรื่อง / ชื่อโครงการ
    title_match = re.search(r"เรื่อง\s*([^\n\r]+)", full_text_str)
    if title_match:
        raw_title = title_match.group(1).strip()
        cleaned = re.sub(
            r"^(?:ขออนุมัติ|ขออนุมัติดำเนินงาน|ขออนุมัติเบิกจ่าย|ดำเนินงาน)\s*", "", raw_title
        ).strip()
        extracted["project_title"] = cleaned or raw_title

    # Paragraph segmentation: ที่มา (ตามที่...) / วัตถุประสงค์ (ในการนี้...)
    p_context: List[str] = []
    p_objective: List[str] = []
    skip_prefixes = ("ที่ ", "วันที่ ", "เรื่อง ", "อ้างถึง ", "----------------", "บันทึกข้อความ",
                     "ส่วนงาน", "เรียน", "จึงเรียนมา", "ลงชื่อ", "รายละเอียดค่าจ้างเหมา", "ประมาณการค่าใช้จ่าย")
    for p in paragraphs:
        if p.startswith(skip_prefixes):
            continue
        if "ตามที่" in p:
            p_context.append(p)
        elif "ในการนี้" in p:
            p_objective.append(p)

    if p_context:
        extracted["project_context"] = "\n".join(p_context)
    if p_objective:
        extracted["project_objective"] = "\n".join(p_objective)

    # Action verb
    verb_match = re.search(
        r"(จัดอบรม|จัดประชุม|จัดสัมมนา|เดินทางไปติดตามงาน|เดินทางไปปฏิบัติงาน|เดินทางไปตรวจราชการ|"
        r"ขออนุมัติจ้างเหมา|ขออนุมัติดำเนินงาน|ขออนุมัติเบิกจ่าย)",
        full_text_str,
    )
    if verb_match:
        extracted["action_verb"] = verb_match.group(1).strip()

    # Action details
    act_match = re.search(
        r"(?:จะได้ดำเนินการ|จะดำเนินการ|ขออนุมัติ|ดำเนินงาน)\s*([^\n\r]+?)(?=\s*มีรายละเอียด|\s*ณ|\s*ในวันที่|\s*โดยมี|\s*$)",
        extracted.get("project_objective", "") or full_text_str,
    )
    if act_match:
        extracted["action_details"] = act_match.group(1).strip()

    # Target group
    tgt_m = re.search(r"(?:ผู้เข้าร่วม|กลุ่มเป้าหมาย|จำนวน|เกษตรกร|บุคลากร)\s*([^\d\s\n]+)?\s*(\d+)\s*(คน|แห่ง|ราย|หมู่บ้าน|ชุมชน)", full_text_str)
    if tgt_m:
        extracted["target_group_name"] = tgt_m.group(1) or "ผู้เข้าร่วมโครงการ"
        extracted["target_group_quantity"] = tgt_m.group(2)
        extracted["target_group_unit"] = tgt_m.group(3)

    # 4. สถานที่ & จังหวัด
    loc_match = re.search(r"ณ\s+([^\n\r,]+?)(?=\s+(?:มีผู้เดินทาง|มีกำหนดการ|และมีประมาณการ|ประจำปี|\n|\r|$))", full_text_str)
    if not loc_match:
        loc_match = re.search(r"(?:สถานที่|จัดขึ้นที่)\s+([^\n\r,]+?)(?=\s+(?:ในวันที่|ระหว่างวันที่|โดย|\n|\r|$))", full_text_str)

    if loc_match:
        raw_loc_full = loc_match.group(1).strip()
        prov_m = re.search(r"(?:จ\.|จังหวัด)\s*([^\s,]+)", raw_loc_full)
        prov_n = prov_m.group(1).strip() if prov_m else ""
        loc_n = re.sub(r"\s*(?:ต\.|ตำบล|อ\.|อำเภอ|จ\.|จังหวัด).*$", "", raw_loc_full).strip()
        if loc_n and not loc_n.isdigit() and len(loc_n) > 1:
            extracted["location_name"] = loc_n
            extracted["province_name"] = prov_n or "กรุงเทพมหานคร"
            if loc_n and prov_n:
                extracted["location_province"] = f"ณ {loc_n} จ.{prov_n}"
            elif loc_n:
                extracted["location_province"] = f"ณ {loc_n}"
    elif USE_DEFAULT_LOCATION:
        # No explicit location clause — use the unit's standard default
        extracted["location_name"] = DEFAULT_LOCATION
        extracted["province_name"] = DEFAULT_PROVINCE
        extracted["location_province"] = f"ณ {DEFAULT_LOCATION} จ.{DEFAULT_PROVINCE}"

    # 5. กำหนดการ (ช่วงวันที่)
    sched_kw = r"(?:ในระหว่างวันที่|ระหว่างวันที่|ในวันที่|เดินทางวันที่|กำหนดการเดินทางวันที่|กำหนดการเดินทาง|ช่วงวันที่)"
    sched_dt = r"(\d{1,2}\s*(?:,\s*\d{1,2})*\s*(?:และ\s*\d{1,2})*\s+[^\s\d]+\s+\d{4}|\d{1,2}\s+[^\s\d]+\s+\d{4}\s*(?:ถึงวันที่|ถึง)\s*\d{1,2}\s+[^\s\d]+\s+\d{4}|\d{1,2}\s+[^\s\d]+\s+\d{4})"
    sched_match = re.search(f"{sched_kw}\\s*{sched_dt}", full_text_str)
    if sched_match:
        s_text = sched_match.group(1).strip()
        extracted["schedule_text"] = s_text
        dates = re.findall(r"(\d{1,2})\s*([^\s\d]+)?\s*(\d{4})?", s_text)
        parsed_dates: List[Any] = []
        for d, m, y in dates:
            if d:
                parsed_dates.append(parse_thai_date(f"{d} {m} {y}".strip()))
        parsed_dates = [d for d in parsed_dates if d]
        if parsed_dates:
            extracted["start_date_iso"] = parsed_dates[0].strftime("%Y-%m-%d")
            extracted["end_date_iso"] = parsed_dates[-1].strftime("%Y-%m-%d")

    # 6. วงเงินรวม & ตัวอักษร
    budget_match = re.search(r"(?:รวม|รวมเป็นเงินทั้งสิ้น|มีค่าใช้จ่าย|เป็นเงิน)\s*([\d\,]+(?:\.\d+)?)\s*บาท\s*(?:\((.*?)\))?", full_text_str)
    if budget_match:
        extracted["budget_amount"] = budget_match.group(1).replace(",", "").strip()
        if budget_match.group(2):
            extracted["budget_text"] = f"({budget_match.group(2).strip()})"
        else:
            auto_b = num_to_thai_baht(extracted["budget_amount"])
            if auto_b:
                extracted["budget_text"] = f"({auto_b})"
    else:
        amt_search = re.search(r"([\d\,]+(?:\.\d+)?)\s*บาท\s*(?:\((.*?)\))?", full_text_str)
        if amt_search:
            extracted["budget_amount"] = amt_search.group(1).replace(",", "").strip()
            if amt_search.group(2):
                extracted["budget_text"] = f"({amt_search.group(2).strip()})"
            else:
                auto_b = num_to_thai_baht(extracted["budget_amount"])
                if auto_b:
                    extracted["budget_text"] = f"({auto_b})"

    # 7. ผู้ขอ (จากแถบลงนามท้ายเอกสาร)
    for i, p in enumerate(paragraphs):
        if "จึงเรียนมา" in p or p.startswith("ลงชื่อ"):
            for j in range(i, min(i + 4, len(paragraphs))):
                nm = re.search(r"\(?\s*(นาย|นาง|นางสาว|ดร\.|ผศ\.|รศ\.|ศ\.)\s*([^\)]+)\)?", paragraphs[j])
                if nm:
                    extracted["requester_name"] = f"{nm.group(1)}{nm.group(2).strip()}".strip("() ")
                    if j + 1 < len(paragraphs):
                        pos_cand = paragraphs[j + 1].strip()
                        if pos_cand and not pos_cand.startswith("ลงชื่อ") and not pos_cand.startswith("เรียน") and len(pos_cand) < 40:
                            extracted["requester_position"] = pos_cand
                    break
            if extracted["requester_name"]:
                break
    if not extracted["requester_name"]:
        name_match = re.search(r"\(?\s*(นาย|นาง|นางสาว|ดร\.|ผศ\.|รศ\.|ศ\.)\s*([^\)]+)\)?", full_text_str)
        if name_match:
            extracted["requester_name"] = f"{name_match.group(1)}{name_match.group(2).strip()}".strip("() ")

    # 7b. ผู้อนุมัติ (block 'เห็นควรอนุมัติ ... อนุมัติ' — two signatories side by side)
    for i, p in enumerate(paragraphs):
        if "เห็นควรอนุมัติ" in p:
            for j in range(i, min(i + 6, len(paragraphs))):
                names = re.findall(r"\(?\s*(นาย|นาง|นางสาว|ดร\.|ผศ\.|รศ\.|ศ\.)\s*([^\)]+)\)?", paragraphs[j])
                if len(names) >= 2:
                    extracted["approver_left_name"] = f"{names[0][0]}{names[0][1].strip()}".strip("() ")
                    extracted["approver_right_name"] = f"{names[1][0]}{names[1][1].strip()}".strip("() ")
                    # Positions: next line, tab-separated; may wrap to the line after
                    if j + 1 < len(paragraphs):
                        pos_parts = [pt.strip() for pt in paragraphs[j + 1].split("\t") if pt.strip()]
                        if len(pos_parts) >= 2:
                            extracted["approver_left_pos"] = pos_parts[0]
                            extracted["approver_right_pos"] = pos_parts[1]
                            if j + 2 < len(paragraphs) and len(pos_parts[0]) < 12:
                                nxt = paragraphs[j + 2].strip()
                                if nxt and not any(nxt.startswith(k) for k in ("ลงชื่อ", "เรียน", "(", "เห็นควร")):
                                    extracted["approver_left_pos"] += f" {nxt}"
                    break
            if extracted["approver_left_name"]:
                break

    # 8. Breakdown (ตารางค่าใช้จ่าย)
    table_rows: List[Dict[str, str]] = []
    table_rows = _parse_attachment_breakdown(full_text) or _parse_doc_tables(tables) or _parse_plaintext_breakdown(full_text)
    if table_rows:
        extracted["breakdown"] = table_rows

    # 9. Schedule activities (จากหัวข้อ "กำหนดการ")
    extracted["schedule_activities"] = _parse_schedule_activities(full_text, extracted)

    return extracted


# ---------------------------------------------------------------------------
# Breakdown parsers (3 strategies, first non-empty wins)
# ---------------------------------------------------------------------------
def _parse_attachment_breakdown(full_text: List[str]) -> List[Dict[str, str]]:
    """Strategy 1: explicit 'ประมาณการค่าใช้จ่าย' attachment section."""
    rows: List[Dict[str, str]] = []
    in_attach = False
    seen: set = set()
    for p in full_text:
        p_clean = p.strip()
        if "ประมาณการค่าใช้จ่าย" in p_clean and len(p_clean) < 30:
            in_attach = True
            continue
        if in_attach:
            if p_clean.startswith("รวม") or "จึงเรียนมา" in p_clean or "เห็นควรอนุมัติ" in p_clean:
                break
            parts = [pt.strip() for pt in p_clean.split("\t") if pt.strip()]
            if len(parts) >= 2:
                if parts[-1] == "บาท" and len(parts) >= 3:
                    amt_str, rest = parts[-2], parts[:-2]
                else:
                    amt_str, rest = parts[-1].replace("บาท", "").strip(), parts[:-1]
                if amt_str.replace(",", "").replace(".", "").isdigit():
                    item_name, detail_text = _split_item_detail(" ".join(rest))
                    if item_name and item_name not in seen:
                        seen.add(item_name)
                        rows.append({"รายการ": item_name, "รายละเอียด": detail_text, "จำนวนเงิน (บาท)": amt_str})
    return rows


def _parse_doc_tables(tables) -> List[Dict[str, str]]:
    """Strategy 2: native document tables (docx tables / pdf tables)."""
    rows: List[Dict[str, str]] = []
    for table in tables:
        for row in table:
            cells = [str(c).strip() for c in row]
            if len(cells) >= 3:
                if "รายการ" in cells[0] and "จำนวนเงิน" in cells[2]:
                    continue
                if any(cells):
                    rows.append({"รายการ": cells[0], "รายละเอียด": cells[1], "จำนวนเงิน (บาท)": cells[2]})
    return rows


def _parse_plaintext_breakdown(full_text: List[str]) -> List[Dict[str, str]]:
    """Strategy 3: lines ending with '<amount> บาท' in the body text."""
    rows: List[Dict[str, str]] = []
    seen: set = set()
    for p in full_text:
        if p.startswith("จึงเรียนมา") or p.startswith("ลงชื่อ") or "เห็นควรอนุมัติ" in p:
            continue
        if p.startswith("ในการนี้") or p.startswith("พร้อมทั้ง") or p.startswith("ตามที่"):
            continue
        m = re.search(r"^(.*?)\s+([\d\,]+(?:\.\d+)?)\s*บาท(?:\s*\(.*?\))?(?:\s*ขอถัวเฉลี่ย.*)?\s*$", p)
        if not m:
            continue
        full_item = m.group(1).strip()
        amt_str = m.group(2).strip()
        if any(hdr in full_item for hdr in ["เรื่อง", "อ้างถึง", "เรียน", "วันที่", "บันทึกข้อความ", "รวม"]):
            continue
        item_name, detail_text = _split_item_detail(full_item)
        if item_name and item_name not in seen:
            seen.add(item_name)
            rows.append({"รายการ": item_name, "รายละเอียด": detail_text, "จำนวนเงิน (บาท)": amt_str})
    return rows


def _split_item_detail(full_item: str):
    """Split 'ค่าจ้างเหมาพาหนะ จำนวน 6 วัน x 1,500 บาท' into item + detail."""
    detail_m = re.search(r"^(.*?)\s+((?:จำนวน|เหมา|เหมาจ่าย|\d+\s*(?:วัน|คน|ครั้ง|ชุด|กล่อง)).*)$", full_item)
    if detail_m:
        return detail_m.group(1).strip(), detail_m.group(2).strip()
    return full_item, "-"


# ---------------------------------------------------------------------------
# Schedule activities parser
# ---------------------------------------------------------------------------
def _parse_schedule_activities(full_text: List[str], extracted: Dict[str, Any]) -> List[Dict[str, Any]]:
    schedule_activities: List[Dict[str, Any]] = []
    in_schedule = False
    current_day = None

    day_re = re.compile(r"^(?:วันที่\s*)?(\d{1,2}(?:\s*[-–]\s*\d{1,2})?)\s+([^\s\d]+)\s+(\d{2,4})")
    time_re = re.compile(r"^(\d{1,2}[\.\:]\d{2}\s*[\–\-]\s*\d{1,2}[\.\:]\d{2}\s*น\.)\s*(.*)$")
    loc_re = re.compile(r"^(?:ณ|สถานที่\s*[:：])\s*(.+)$")

    for p in full_text:
        if p.startswith("กำหนดการเดินทาง") or p.startswith("กำหนดการ"):
            in_schedule = True
            continue
        if in_schedule:
            if "ประมาณการค่าใช้จ่าย" in p or "เห็นควรอนุมัติ" in p or p.startswith("ลงชื่อ"):
                if schedule_activities:
                    break

            date_m = day_re.match(p)
            if date_m and date_m.group(2).strip() in THAI_MONTH_SET:
                day_part = date_m.group(1).strip()
                month_part = date_m.group(2).strip()
                year_part = date_m.group(3).strip()
                if len(year_part) == 2:
                    year_part = f"25{year_part}"
                date_title = f"วันที่ {day_part} {month_part} {year_part}"
                current_day = {"date_title": date_title, "location": extracted.get("location_name", ""), "items": []}
                schedule_activities.append(current_day)
                continue

            loc_m = loc_re.match(p)
            if loc_m and current_day is not None:
                current_day["location"] = loc_m.group(1).strip()
                continue

            time_m = time_re.match(p)
            if time_m and current_day is not None:
                current_day["items"].append({"time": time_m.group(1).strip(), "activity": time_m.group(2).strip()})

    return schedule_activities
