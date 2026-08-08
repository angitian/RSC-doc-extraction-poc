# -*- coding: utf-8 -*-
import streamlit as st
import docx
import re
import pandas as pd
import io
import json
import os
import base64
from datetime import datetime, date
import textwrap
import streamlit.components.v1 as components

# Set page config
st.set_page_config(
    page_title="RSC-doc-extraction-poc",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# Data Constants & Heuristics
# -----------------------------------------------------------------------------
ACC_MAPPING = {
    "ACC-2026-RD68": {
        "budget_year": "2569",
        "budget_source": "กองทุนส่งเสริมวิทยาศาสตร์ วิจัยและนวัตกรรม (สวพ.)"
    },
    "ACC-2026-SF01": {
        "budget_year": "2569",
        "budget_source": "งบประมาณแผ่นดิน / สถาบันพัฒนาและฝึกอบรมโรงงานต้นแบบ"
    },
    "ACC-2025-IEC01": {
        "budget_year": "2568",
        "budget_source": "โครงการวิจัยและประกอบเครื่องต้นแบบ IEC"
    }
}

DEFAULT_BREAKDOWN = pd.DataFrame([
    {"รายการ": "ค่าเช่าพาหนะ", "รายละเอียด": "จำนวน 6 วัน x 1,500 บาท", "จำนวนเงิน (บาท)": "9,000"},
    {"รายการ": "ค่าน้ำมันเชื้อเพลิง", "รายละเอียด": "จำนวน 6 วัน x 1,000 บาท", "จำนวนเงิน (บาท)": "6,000"},
    {"รายการ": "ค่าทางด่วน / ผ่านทาง", "รายละเอียด": "จำนวน 1 เหมา", "จำนวนเงิน (บาท)": "1,200"},
    {"รายการ": "ค่าเบี้ยเลี้ยงและที่พัก", "รายละเอียด": "เหมาจ่าย", "จำนวนเงิน (บาท)": "5,000"},
])

THAI_MONTHS = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
]
THAI_MONTHS_SHORT = [
    "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."
]

def parse_thai_date(date_str):
    """Parses Thai date string or DD/MM/YYYY to datetime.date object. Defaults to today's date if parsing fails."""
    if not date_str or not isinstance(date_str, str):
        return datetime.now().date()
        
    date_str = date_str.strip()
    
    # Match DD/MM/YYYY
    slash_match = re.search(r'(\d{1,2})\/(\d{1,2})\/(\d{4})', date_str)
    if slash_match:
        day = int(slash_match.group(1))
        month = int(slash_match.group(2))
        year_be = int(slash_match.group(3))
        year_ad = year_be - 543 if year_be > 2400 else year_be
        try:
            return datetime(year_ad, month, day).date()
        except:
            pass

    match = re.search(r'(\d{1,2})\s+([^\s\d]+)\s+(\d{4})', date_str)
    if match:
        day = int(match.group(1))
        m_str = match.group(2).strip()
        year_be = int(match.group(3))
        year_ad = year_be - 543 if year_be > 2400 else year_be
        
        month = 1
        for idx, m_name in enumerate(THAI_MONTHS, start=1):
            if m_name in m_str:
                month = idx
                break
        else:
            for idx, m_short in enumerate(THAI_MONTHS_SHORT, start=1):
                if m_short in m_str:
                    month = idx
                    break
        try:
            return datetime(year_ad, month, day).date()
        except:
            pass
            
    return datetime.now().date()

def format_thai_date(d_obj):
    """Formats datetime.date to DD/MM/YYYY (พ.ศ.) string (e.g. 10/08/2569)."""
    if not d_obj:
        d_obj = datetime.now().date()
    y_be = d_obj.year + 543
    return f"{d_obj.day:02d}/{d_obj.month:02d}/{y_be}"

def num_to_thai_baht(number_val):
    """Converts number string/float to Thai Baht text (e.g., 21200 -> สองหมื่นเอ็ดพันสองร้อยบาทถ้วน)."""
    try:
        raw = str(number_val).replace(",", "").strip()
        if not raw:
            return ""
        val = float(raw)
        if val == 0:
            return "ศูนย์บาทถ้วน"
    except:
        return ""
        
    THAI_NUMS = ["ศูนย์", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
    THAI_UNITS = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน", "ล้าน"]
    
    parts = f"{val:.2f}".split(".")
    baht_part = int(parts[0])
    satang_part = int(parts[1])
    
    def convert_group(n):
        if n == 0:
            return ""
        s = str(n)
        length = len(s)
        res = []
        for i, ch in enumerate(s):
            digit = int(ch)
            pos = length - i - 1
            if digit != 0:
                if pos == 1 and digit == 1:
                    res.append("สิบ")
                elif pos == 1 and digit == 2:
                    res.append("ยี่สิบ")
                elif pos == 0 and digit == 1 and length > 1:
                    res.append("เอ็ด")
                else:
                    res.append(THAI_NUMS[digit] + THAI_UNITS[pos])
            elif pos == 6:
                res.append("ล้าน")
        return "".join(res)
        
    baht_text = ""
    if baht_part == 0:
        baht_text = "ศูนย์บาท"
    else:
        mil = baht_part // 1000000
        rem = baht_part % 1000000
        if mil > 0:
            baht_text += convert_group(mil) + "ล้าน"
        baht_text += convert_group(rem) + "บาท"
        
    if satang_part == 0:
        satang_text = "ถ้วน"
    else:
        satang_text = convert_group(satang_part) + "สตางค์"
        
    return baht_text + satang_text


# -----------------------------------------------------------------------------
# DOCX Extraction Logic (Enhanced & Robust)
# -----------------------------------------------------------------------------
def extract_memo_data(file_source):
    """Parses a .docx file and extracts fields using regex & heuristics."""
    extracted = {
        "doc_number": "",
        "doc_seq_num": "",
        "doc_number_tail": "",
        "doc_date": "",
        "doc_date_iso": datetime.now().date().strftime("%Y-%m-%d"),
        "doc_date_obj": datetime.now().date(),
        "requester_name": "",
        "requester_position": "",
        "project_title": "",
        "project_context": "",
        "project_objective": "",
        "project_group_text": "",
        "action_details": "",
        "action_verb": "ดำเนินงาน",
        "target_group_name": "ผู้เข้าร่วม",
        "target_group_quantity": "1",
        "target_group_unit": "งาน",
        "location_name": "",
        "province_name": "",
        "location_province": "",
        "schedule_text": "",
        "start_date_iso": datetime.now().date().strftime("%Y-%m-%d"),
        "end_date_iso": datetime.now().date().strftime("%Y-%m-%d"),
        "has_time_loc_phrase": True,
        "show_p3_paragraph": True,
        "budget_amount": "",
        "budget_text": "",
        "breakdown_df": pd.DataFrame(columns=["รายการ", "รายละเอียด", "จำนวนเงิน (บาท)"]),
        "schedule_activities": [],
        "agency_name": "",
        "contact_phone": ""
    }
    
    try:
        if isinstance(file_source, (bytes, bytearray)):
            doc = docx.Document(io.BytesIO(file_source))
        elif hasattr(file_source, "read"):
            doc = docx.Document(file_source)
        else:
            doc = docx.Document(str(file_source))
            
        full_text = []
        paragraphs = []
        for p in doc.paragraphs:
            txt = p.text.strip()
            if txt:
                paragraphs.append(txt)
                full_text.append(txt)
                
        full_text_str = "\n".join(full_text)

        # 0. ส่วนงาน & เบอร์โทรศัพท์สำหรับติดต่อในหนังสือ (agency_name & contact_phone)
        agency_match = re.search(r'ส่วนงาน\s*([^\n\r]+)', full_text_str)
        if agency_match:
            extracted["agency_name"] = agency_match.group(1).strip()
            
        phone_match = re.search(r'(?:โทร\.?|โทรศัพท์)\s*([0-9\-\s]{3,15})', full_text_str)
        if phone_match:
            extracted["contact_phone"] = phone_match.group(1).strip()
        else:
            extracted["contact_phone"] = "053-218618"
        
        # 1. เลขที่หนังสือ (doc_number & doc_seq_num & doc_number_tail)
        num_match = re.search(r'(?:ที่|อว\.?)\s*([อว\s\.\d\/\-]+)', full_text_str)
        if num_match:
            val = num_match.group(1).strip()
            if not val.startswith("อว"):
                val = f"อว {val}"
            extracted["doc_number"] = val
            
            # Tail document number (e.g. "7608.8.1/0012/69" without "อว")
            tail_m = re.search(r'([0-9\.]+\/[0-9\.\/]+)', val)
            if tail_m:
                extracted["doc_number_tail"] = tail_m.group(1).strip()
            else:
                extracted["doc_number_tail"] = val.replace("อว", "").strip()

            seq_match = re.search(r'7608\.8(?:\.1)?\/([^\/\s]+)', val)
            if seq_match:
                extracted["doc_seq_num"] = seq_match.group(1).strip()
            else:
                seq_match2 = re.search(r'\/([^\/\s]+)(?:\/\d{2})?', val)
                if seq_match2:
                    extracted["doc_seq_num"] = seq_match2.group(1).strip()
                
        # 2. วันที่หนังสือ (doc_date & doc_date_iso YYYY-MM-DD)
        date_match = re.search(r'วันที่\s*(\d{1,2}\s+[^\s\d]+\s+\d{4})', full_text_str)
        if date_match:
            extracted["doc_date"] = date_match.group(1).strip()
            d_obj = parse_thai_date(extracted["doc_date"])
            extracted["doc_date_obj"] = d_obj
            extracted["doc_date_iso"] = d_obj.strftime("%Y-%m-%d")


        # 3. เรื่อง / ชื่อโครงการ (project_title)
        title_match = re.search(r'เรื่อง\s*([^\n\r]+)', full_text_str)
        if title_match:
            raw_title = title_match.group(1).strip()
            # Clean up title if it contains leading verb phrases
            cleaned_title = re.sub(r'^(?:ขออนุมัติ|ขออนุมัติดำเนินงาน|ขออนุมัติเบิกจ่าย|ดำเนินงาน)\s*', '', raw_title).strip()
            extracted["project_title"] = cleaned_title or raw_title

        # Paragraph segmentation
        p_context = []
        p_objective = []
        for p in paragraphs:
            if p.startswith("ที่ ") or p.startswith("วันที่ ") or p.startswith("เรื่อง ") or p.startswith("อ้างถึง ") or p.startswith("----------------"):
                continue
            if any(p.startswith(k) for k in ["บันทึกข้อความ", "ส่วนงาน", "เรียน", "จึงเรียนมา", "ลงชื่อ", "รายละเอียดค่าจ้างเหมา", "ประมาณการค่าใช้จ่าย"]):
                continue
            if "ตามที่" in p:
                p_context.append(p)
            elif "ในการนี้" in p:
                p_objective.append(p)

        if p_context:
            extracted["project_context"] = "\n".join(p_context)
        if p_objective:
            extracted["project_objective"] = "\n".join(p_objective)

        # Action Details & Verb heuristic
        verb_match = re.search(r'(จัดอบรม|จัดประชุม|จัดสัมมนา|เดินทางไปติดตามงาน|เดินทางไปปฏิบัติงาน|เดินทางไปตรวจราชการ|ขออนุมัติจ้างเหมา|ขออนุมัติดำเนินงาน|ขออนุมัติเบิกจ่าย)', full_text_str)
        if verb_match:
            extracted["action_verb"] = verb_match.group(1).strip()
        else:
            extracted["action_verb"] = "ดำเนินงาน"

        act_match = re.search(r'(?:จะได้ดำเนินการ|จะดำเนินการ|ขออนุมัติ|ดำเนินงาน)\s*([^\n\r]+?)(?=\s*มีรายละเอียด|\s*ณ|\s*ในวันที่|\s*โดยมี|\s*$)', extracted.get("project_objective", "") or full_text_str)
        if act_match:
            extracted["action_details"] = act_match.group(1).strip()

        # Target Group heuristics
        tgt_m = re.search(r'(?:ผู้เข้าร่วม|กลุ่มเป้าหมาย|จำนวน|เกษตรกร|บุคลากร)\s*([^\d\s\n]+)?\s*(\d+)\s*(คน|แห่ง|ราย|หมู่บ้าน|ชุมชน)', full_text_str)
        if tgt_m:
            extracted["target_group_name"] = tgt_m.group(1) or "ผู้เข้าร่วมโครงการ"
            extracted["target_group_quantity"] = tgt_m.group(2)
            extracted["target_group_unit"] = tgt_m.group(3)
        else:
            extracted["target_group_name"] = "ผู้เข้าร่วม"
            extracted["target_group_quantity"] = "1"
            extracted["target_group_unit"] = "งาน"

        # 4. สถานที่ & จังหวัด (Enhanced heuristic supporting ตำบล/อำเภอ/จังหวัด formats)
        loc_match = re.search(r'ณ\s+([^\n\r,]+?)(?=\s+(?:มีผู้เดินทาง|มีกำหนดการ|และมีประมาณการ|ประจำปี|\n|\r|$))', full_text_str)
        if not loc_match:
            loc_match = re.search(r'(?:สถานที่|จัดขึ้นที่)\s+([^\n\r,]+?)(?=\s+(?:ในวันที่|ระหว่างวันที่|โดย|\n|\r|$))', full_text_str)
            
        if loc_match:
            raw_loc_full = loc_match.group(1).strip()
            
            # Extract province
            prov_m = re.search(r'(?:จ\.|จังหวัด)\s*([^\s,]+)', raw_loc_full)
            prov_n = prov_m.group(1).strip() if prov_m else ""
            
            # Clean location name by stripping Tambon, Amphoe, Province clauses
            loc_n = re.sub(r'\s*(?:ต\.|ตำบล|อ\.|อำเภอ|จ\.|จังหวัด).*$', '', raw_loc_full).strip()
            
            if loc_n and not loc_n.isdigit() and len(loc_n) > 1:
                extracted["location_name"] = loc_n
                extracted["province_name"] = prov_n or "กรุงเทพมหานคร"
                if loc_n and prov_n:
                    extracted["location_province"] = f"ณ {loc_n} จ.{prov_n}"
                elif loc_n:
                    extracted["location_province"] = f"ณ {loc_n}"
        else:
            # Default fallback when doc text does not specify explicit location keyword
            extracted["location_name"] = "มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี"
            extracted["province_name"] = "กรุงเทพมหานคร"
            extracted["location_province"] = "ณ มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี จ.กรุงเทพมหานคร"

        # 5. กำหนดการ (schedule_text, start_date_iso, end_date_iso)
        sched_kw = r'(?:ในระหว่างวันที่|ระหว่างวันที่|ในวันที่|เดินทางวันที่|กำหนดการเดินทางวันที่|กำหนดการเดินทาง|ช่วงวันที่)'
        sched_dt = r'(\d{1,2}\s*(?:,\s*\d{1,2})*\s*(?:และ\s*\d{1,2})*\s+[^\s\d]+\s+\d{4}|\d{1,2}\s+[^\s\d]+\s+\d{4}\s*(?:ถึงวันที่|ถึง)\s*\d{1,2}\s+[^\s\d]+\s+\d{4}|\d{1,2}\s+[^\s\d]+\s+\d{4})'
        sched_match = re.search(f'{sched_kw}\\s*{sched_dt}', full_text_str)
        if sched_match:
            s_text = sched_match.group(1).strip()
            extracted["schedule_text"] = s_text
            
            # Parse start and end date ISO YYYY-MM-DD
            dates = re.findall(r'(\d{1,2})\s*([^\s\d]+)?\s*(\d{4})?', s_text)
            parsed_dates = []
            for d, m, y in dates:
                if d:
                    dt_str = f"{d} {m} {y}".strip()
                    parsed_dates.append(parse_thai_date(dt_str))
            if parsed_dates:
                extracted["start_date_iso"] = parsed_dates[0].strftime("%Y-%m-%d")
                extracted["end_date_iso"] = parsed_dates[-1].strftime("%Y-%m-%d")
            else:
                today_iso = datetime.now().date().strftime("%Y-%m-%d")
                extracted["start_date_iso"] = today_iso
                extracted["end_date_iso"] = today_iso
        else:
            today_iso = datetime.now().date().strftime("%Y-%m-%d")
            extracted["start_date_iso"] = today_iso
            extracted["end_date_iso"] = today_iso


        # 6. วงเงินรวม & วงเงินตัวอักษร (Prioritize 'รวม' lines first)
        budget_match = re.search(r'(?:รวม|รวมเป็นเงินทั้งสิ้น|มีค่าใช้จ่าย|เป็นเงิน)\s*([\d\,]+(?:\.\d+)?)\s*บาท\s*(?:\((.*?)\))?', full_text_str)
        if budget_match:
            extracted["budget_amount"] = budget_match.group(1).replace(",", "").strip()
            if budget_match.group(2):
                extracted["budget_text"] = f"({budget_match.group(2).strip()})"
            else:
                auto_b = num_to_thai_baht(extracted["budget_amount"])
                if auto_b:
                    extracted["budget_text"] = f"({auto_b})"
        else:
            amt_search = re.search(r'([\d\,]+(?:\.\d+)?)\s*บาท\s*(?:\((.*?)\))?', full_text_str)
            if amt_search:
                extracted["budget_amount"] = amt_search.group(1).replace(",", "").strip()
                if amt_search.group(2):
                    extracted["budget_text"] = f"({amt_search.group(2).strip()})"
                else:
                    auto_b = num_to_thai_baht(extracted["budget_amount"])
                    if auto_b:
                        extracted["budget_text"] = f"({auto_b})"

        # 7. ชื่อ-นามสกุล และ ตำแหน่งผู้ขอ (ดึงเฉพาะแถบลงนามท้ายเอกสาร)
        for i, p in enumerate(paragraphs):
            if "จึงเรียนมา" in p or p.startswith("ลงชื่อ"):
                for j in range(i, min(i+4, len(paragraphs))):
                    nm = re.search(r'\(?\s*(นาย|นาง|นางสาว|ดร\.|ผศ\.|รศ\.|ศ\.)\s*([^\)]+)\)?', paragraphs[j])
                    if nm:
                        extracted["requester_name"] = f"{nm.group(1)}{nm.group(2).strip()}".strip("() ")
                        if j + 1 < len(paragraphs):
                            pos_cand = paragraphs[j+1].strip()
                            if pos_cand and not pos_cand.startswith("ลงชื่อ") and not pos_cand.startswith("เรียน") and len(pos_cand) < 40:
                                extracted["requester_position"] = pos_cand
                        break
                if extracted["requester_name"]:
                    break

        # Fallback for requester name if signature section not found
        if not extracted["requester_name"]:
            name_match = re.search(r'\(?\s*(นาย|นาง|นางสาว|ดร\.|ผศ\.|รศ\.|ศ\.)\s*([^\)]+)\)?', full_text_str)
            if name_match:
                extracted["requester_name"] = f"{name_match.group(1)}{name_match.group(2).strip()}".strip("() ")

        # 8. Tables extraction & Plaintext Breakdown parsing
        table_rows = []

        # 8.1 First check if there is an explicit Attachment Breakdown (เอกสารแนบประมาณการค่าใช้จ่าย)
        in_attach_breakdown = False
        seen_items = set()
        for p in full_text:
            p_clean = p.strip()
            if "ประมาณการค่าใช้จ่าย" in p_clean and len(p_clean) < 30:
                in_attach_breakdown = True
                continue
            if in_attach_breakdown:
                if p_clean.startswith("รวม") or "จึงเรียนมา" in p_clean or "เห็นควรอนุมัติ" in p_clean:
                    break
                parts = [pt.strip() for pt in p_clean.split('\t') if pt.strip()]
                if len(parts) >= 2:
                    if parts[-1] == "บาท" and len(parts) >= 3:
                        amt_str = parts[-2]
                        rest = parts[:-2]
                    else:
                        amt_str = parts[-1].replace("บาท", "").strip()
                        rest = parts[:-1]
                    
                    if amt_str.replace(",", "").replace(".", "").isdigit():
                        combined = " ".join(rest)
                        detail_m = re.search(r'^(.*?)\s+((?:จำนวน|เหมา|เหมาจ่าย|\d+\s*(?:วัน|คน|ครั้ง|ชุด|กล่อง)).*)$', combined)
                        if detail_m:
                            item_name = detail_m.group(1).strip()
                            detail_text = detail_m.group(2).strip()
                        else:
                            item_name = combined
                            detail_text = "-"
                        
                        if item_name not in seen_items:
                            seen_items.add(item_name)
                            table_rows.append({
                                "รายการ": item_name,
                                "รายละเอียด": detail_text,
                                "จำนวนเงิน (บาท)": amt_str
                            })

        # 8.2 Tables extraction fallback
        if not table_rows:
            for table in doc.tables:
                for row in table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    if len(cells) >= 3 and not ("รายการ" in cells[0] and "จำนวนเงิน" in cells[2]):
                        if any(cells):
                            table_rows.append({
                                "รายการ": cells[0],
                                "รายละเอียด": cells[1],
                                "จำนวนเงิน (บาท)": cells[2]
                            })

        # 8.3 Body Plaintext Breakdown fallback
        if not table_rows:
            seen_items = set()
            for p in full_text:
                if p.startswith("จึงเรียนมา") or p.startswith("ลงชื่อ") or "เห็นควรอนุมัติ" in p:
                    if table_rows:
                        break
                    continue
                if p.startswith("ในการนี้") or p.startswith("พร้อมทั้ง") or p.startswith("ตามที่"):
                    continue
                
                # Match line ending with number and บาท (allowing tab or multiple spaces before amount)
                m = re.search(r'^(.*?)\s+([\d\,]+(?:\.\d+)?)\s*บาท(?:\s*\(.*?\))?(?:\s*ขอถัวเฉลี่ย.*)?\s*$', p)
                if m:
                    full_item_str = m.group(1).strip()
                    amt_str = m.group(2).strip()

                    if any(hdr in full_item_str for hdr in ["เรื่อง", "อ้างถึง", "เรียน", "วันที่", "บันทึกข้อความ", "รวม"]):
                        continue

                    # Smart split item name and details (e.g. 'ค่าจ้างเหมาพาหนะ จำนวน 6 วัน x 1,500 บาท' -> item & detail)
                    detail_m = re.search(r'^(.*?)\s+((?:จำนวน|เหมา|เหมาจ่าย|\d+\s*(?:วัน|คน|ครั้ง|ชุด|กล่อง)).*)$', full_item_str)
                    if detail_m:
                        item_name = detail_m.group(1).strip()
                        detail_text = detail_m.group(2).strip()
                    else:
                        item_name = full_item_str
                        detail_text = "-"

                    if item_name not in seen_items:
                        seen_items.add(item_name)
                        table_rows.append({
                            "รายการ": item_name,
                            "รายละเอียด": detail_text,
                            "จำนวนเงิน (บาท)": amt_str
                        })

        if table_rows:
            extracted["breakdown_df"] = pd.DataFrame(table_rows)

        # 9. Extract Dynamic Schedule Activities (ถ้ามีในเอกสารแนบ)
        # Phase 4.1: Enhanced regex for diverse date formats and location per day
        schedule_activities = []
        in_schedule = False
        current_day = None

        # Valid Thai month names (full + abbreviated) for validation
        THAI_MONTHS = {
            'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
            'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม',
            'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
            'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'
        }

        # Expanded date patterns with month validation:
        #   วันที่ 10 สิงหาคม 2569
        #   วันที่ 10-12 ส.ค. 69
        #   10 ส.ค. 69
        #   วันที่ 10 ก.ย. 2569
        day_re = re.compile(
            r'^(?:วันที่\s*)?(\d{1,2}(?:\s*[-–]\s*\d{1,2})?)\s+([^\s\d]+)\s+(\d{2,4})'
        )
        # Time patterns: 08.00-12.00 น. / 08:00-12:00 น. / 08.00 – 12.00 น.
        time_re = re.compile(
            r'^(\d{1,2}[\.\:]\d{2}\s*[\–\-]\s*\d{1,2}[\.\:]\d{2}\s*น\.)\s*(.*)$'
        )
        # Location pattern: ณ จ.เชียงใหม่ / สถานที่: ...
        loc_re = re.compile(r'^(?:ณ|สถานที่\s*[:：])\s*(.+)$')

        for p in full_text:
            # Only trigger in_schedule for section headers that START with "กำหนดการ"
            # This prevents false trigger from body text containing "กำหนดการ" mid-sentence
            if p.startswith("กำหนดการเดินทาง") or p.startswith("กำหนดการ"):
                in_schedule = True
                continue
            if in_schedule:
                if "ประมาณการค่าใช้จ่าย" in p or "เห็นควรอนุมัติ" in p or p.startswith("ลงชื่อ"):
                    if schedule_activities:
                        break

                date_m = day_re.match(p)
                # Validate month name to prevent false day blocks from non-date lines
                if date_m and date_m.group(2).strip() in THAI_MONTHS:
                    day_part = date_m.group(1).strip()
                    month_part = date_m.group(2).strip()
                    year_part = date_m.group(3).strip()
                    # Normalize year to 4-digit Buddhist era
                    if len(year_part) == 2:
                        year_part = f"25{year_part}"
                    date_title = f"วันที่ {day_part} {month_part} {year_part}"

                    current_day = {
                        "date_title": date_title,
                        "location": extracted.get("location_name", ""),
                        "items": []
                    }
                    schedule_activities.append(current_day)
                    continue

                # Check for per-day location line
                loc_m = loc_re.match(p)
                if loc_m and current_day is not None:
                    current_day["location"] = loc_m.group(1).strip()
                    continue

                time_m = time_re.match(p)
                if time_m and current_day is not None:
                    current_day["items"].append({
                        "time": time_m.group(1).strip(),
                        "activity": time_m.group(2).strip()
                    })

        if schedule_activities:
            extracted["schedule_activities"] = schedule_activities

    except Exception as e:
        st.warning(f"เกิดข้อผิดพลาดในการสกัดข้อมูลจาก DOCX: {str(e)}")

    return extracted


# -----------------------------------------------------------------------------
# Session State Helper
# -----------------------------------------------------------------------------
def populate_session_state(data, force=False):
    for key, value in data.items():
        if force or key not in st.session_state:
            st.session_state[key] = value

    if "acc_code" not in st.session_state or force:
        st.session_state["acc_code"] = "ACC-2026-RD68"
        st.session_state["budget_year"] = ACC_MAPPING["ACC-2026-RD68"]["budget_year"]
        st.session_state["budget_source"] = ACC_MAPPING["ACC-2026-RD68"]["budget_source"]

    # Explicitly sync widget-bound keys when force=True to prevent widget value resets
    if force:
        if "doc_seq_num" in data:
            st.session_state["seq_input"] = data["doc_seq_num"]
        if "doc_number" in data:
            st.session_state["custom_doc_num_input"] = data["doc_number"]
        if "doc_date_obj" in data:
            st.session_state["doc_date_picker"] = data["doc_date_obj"]
        if "schedule_text" in data:
            st.session_state["schedule_text_raw_input"] = data["schedule_text"]
        if "budget_amount" in data:
            st.session_state["b_amt_input"] = data["budget_amount"]
        if "budget_text" in data:
            st.session_state["b_text_input"] = data["budget_text"]
        if "has_time_loc_phrase" in data:
            st.session_state["time_loc_toggle"] = data["has_time_loc_phrase"]


# -----------------------------------------------------------------------------
# Initialize Session State (Clean Default, No Hardcoded Sample Leak)
# -----------------------------------------------------------------------------
default_init = {
    "doc_number": "",
    "doc_seq_num": "",
    "doc_date": "",
    "agency_name": "ศูนย์สนับสนุนโครงการหลวงและโครงการพระราชดำริ โทร. 053-218618",
    "recipient_title": "ผู้อำนวยการสถาบันพัฒนาและฝึกอบรมโรงงานต้นแบบ",
    "closing_text": "จึงเรียนมาเพื่อโปรดพิจารณาอนุมัติ",
    "requester_name": "",
    "requester_position": "",
    "approver_left_name": "(นายศเรนทร์ ฐปนางกูร)",
    "approver_left_pos": "ผู้อำนวยการศูนย์ส่งเสริมและสนับสนุน มูลนิธิโครงการหลวงและโครงการตามพระราชดำริ",
    "approver_right_name": "(ผศ.ดร.บุณยพัด สุภานิช)",
    "approver_right_pos": "ผู้อำนวยการสถาบันพัฒนาและฝึกอบรมโรงงานต้นแบบ",
    "project_title": "",
    "project_context": "",
    "project_objective": "",
    "action_details": "",
    "location_name": "",
    "province_name": "",
    "location_province": "",
    "schedule_text": "",
    "has_time_loc_phrase": False,
    "show_p3_paragraph": True,
    "budget_amount": "",
    "budget_text": "",
    "breakdown_df": pd.DataFrame(columns=["รายการ", "รายละเอียด", "จำนวนเงิน (บาท)"])
}

populate_session_state(default_init)


# Load KMUTT emblem logo base64 if available
KMUTT_LOGO_PATH = os.path.join(os.path.dirname(__file__), "kmutt_logo.png")
KMUTT_LOGO_B64 = ""
if os.path.exists(KMUTT_LOGO_PATH):
    with open(KMUTT_LOGO_PATH, "rb") as logo_file:
        KMUTT_LOGO_B64 = f"data:image/png;base64,{base64.b64encode(logo_file.read()).decode('utf-8')}"


# -----------------------------------------------------------------------------
# Document Generators (DOCX & PDF Exports)
# -----------------------------------------------------------------------------
def generate_docx_bytes(payload):
    doc = docx.Document()
    
    # 3-Column Header Table for Left Logo + Centered Title
    if os.path.exists(KMUTT_LOGO_PATH):
        tbl = doc.add_table(rows=1, cols=3)
        tbl.autofit = False
        tbl.columns[0].width = docx.shared.Inches(1.5)
        tbl.columns[1].width = docx.shared.Inches(4.0)
        tbl.columns[2].width = docx.shared.Inches(1.5)
        
        row = tbl.rows[0].cells
        p_logo = row[0].paragraphs[0]
        p_logo.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.LEFT
        run_logo = p_logo.add_run()
        run_logo.add_picture(KMUTT_LOGO_PATH, width=docx.shared.Inches(0.7))

        p_title = row[1].paragraphs[0]
        p_title.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER
        run = p_title.add_run("บันทึกข้อความ")
        run.bold = True
        run.font.size = docx.shared.Pt(18)
    else:
        p_title = doc.add_paragraph()
        p_title.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER
        run = p_title.add_run("บันทึกข้อความ")
        run.bold = True
        run.font.size = docx.shared.Pt(18)

    doc.add_paragraph(f"ส่วนงาน: {payload.get('agency_name', '')}")
    doc.add_paragraph(f"ที่: {payload.get('doc_number', '')}\t\tวันที่: {payload.get('doc_date', '')}")
    doc.add_paragraph(f"เรื่อง: {payload.get('project_title', '')}")
    doc.add_paragraph(f"เรียน: {payload.get('recipient_title', '')}")

    if payload.get("project_context"):
        doc.add_paragraph(payload.get("project_context"))
    if payload.get("project_objective"):
        doc.add_paragraph(payload.get("project_objective"))
    if payload.get("show_p3_paragraph") and payload.get("p3_full_text"):
        doc.add_paragraph(payload.get("p3_full_text"))

    breakdown = payload.get("breakdown", [])
    if breakdown:
        t = doc.add_table(rows=1, cols=3)
        hdr = t.rows[0].cells
        hdr[0].text = "รายการ"
        hdr[1].text = "รายละเอียด"
        hdr[2].text = "จำนวนเงิน (บาท)"
        for r in breakdown:
            row = t.add_row().cells
            row[0].text = str(r.get("รายการ", ""))
            row[1].text = str(r.get("รายละเอียด", ""))
            row[2].text = str(r.get("จำนวนเงิน (บาท)", ""))

    time_loc = "ตามวัน เวลา และสถานที่ดังกล่าว " if payload.get("has_time_loc_phrase") else ""
    doc.add_paragraph(f"ในการนี้ข้าพเจ้าจึงใคร่ขออนุมัติดำเนินงาน {time_loc}พร้อมทั้งขออนุมัติค่าใช้จ่าย จำนวน {payload.get('budget_amount', '')} บาท {payload.get('budget_text', '')} (เบิกจ่ายจากรหัสงบประมาณ {payload.get('acc_code', '')} {payload.get('budget_source', '')})")
    doc.add_paragraph(payload.get("closing_text", "จึงเรียนมาเพื่อโปรดพิจารณาอนุมัติ"))
    doc.add_paragraph(f"ลงชื่อ {payload.get('requester_name', '')}\n{payload.get('requester_position', '')}")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def generate_pdf_bytes(payload):
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    
    if os.path.exists(KMUTT_LOGO_PATH):
        pdf.image(KMUTT_LOGO_PATH, x=15, y=10, w=18)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    ttf_candidates = [
        os.path.join(base_dir, "THSarabunNew.ttf"),
        os.path.join(base_dir, "Sarabun-Regular.ttf"),
        "/usr/share/fonts/truetype/thaifonts/THSarabunNew.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    ttf_path = next((p for p in ttf_candidates if os.path.exists(p)), None)
    pdf_font = "Helvetica"
    if ttf_path:
        pdf_font = "thai_font"
        pdf.add_font(pdf_font, "", ttf_path, uni=True)
        pdf.set_font(pdf_font, size=13)
    else:
        pdf.set_font("Helvetica", size=12)

    pdf.set_y(14)
    pdf.cell(w=0, text="บันทึกข้อความ", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font(pdf_font, size=10)
    pdf.multi_cell(w=0, text=f"ส่วนงาน: {payload.get('agency_name', '')}", new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(w=0, text=f"ที่: {payload.get('doc_number', '')}   วันที่: {payload.get('doc_date', '')}", new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(w=0, text=f"เรื่อง: {payload.get('project_title', '')}", new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(w=0, text=f"เรียน: {payload.get('recipient_title', '')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    if payload.get("project_context"):
        pdf.multi_cell(w=0, text=payload.get("project_context"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
    if payload.get("project_objective"):
        pdf.multi_cell(w=0, text=payload.get("project_objective"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
    if payload.get("show_p3_paragraph") and payload.get("p3_full_text"):
        pdf.multi_cell(w=0, text=payload.get("p3_full_text"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    time_loc = "ตามวัน เวลา และสถานที่ดังกล่าว " if payload.get("has_time_loc_phrase") else ""
    pdf.multi_cell(w=0, text=f"ในการนี้ข้าพเจ้าจึงใคร่ขออนุมัติดำเนินงาน {time_loc}พร้อมทั้งขออนุมัติค่าใช้จ่าย จำนวน {payload.get('budget_amount', '')} บาท {payload.get('budget_text', '')} (เบิกจ่ายจากรหัสงบประมาณ {payload.get('acc_code', '')} {payload.get('budget_source', '')})", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.multi_cell(w=0, text=payload.get("closing_text", "จึงเรียนมาเพื่อโปรดพิจารณาอนุมัติ"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.multi_cell(w=0, text=f"ลงชื่อ {payload.get('requester_name', '')}\n{payload.get('requester_position', '')}", new_x="LMARGIN", new_y="NEXT")

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


# -----------------------------------------------------------------------------
# Sidebar Configuration
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Sidebar Configuration
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 📄 Smart Data Control")
    st.caption("ระบบ PoC สกัดคำจาก DOCX บันทึกข้อความ")
    
    st.markdown("<hr style='margin: 6px 0; border: none; border-top: 1px solid #e2e8f0;'/>", unsafe_allow_html=True)
    st.markdown("**📁 อัปโหลดเอกสาร (.docx)**")
    uploaded_file = st.file_uploader("เลือกไฟล์ .docx เพื่อสกัดข้อมูล", type=["docx"], label_visibility="collapsed")
    
    if uploaded_file is not None:
        if st.session_state.get("last_uploaded_name") != uploaded_file.name:
            with st.spinner("กำลังอ่านและสกัดข้อมูล..."):
                extracted_data = extract_memo_data(uploaded_file)
                st.session_state["last_uploaded_name"] = uploaded_file.name
                populate_session_state(extracted_data, force=True)
                st.success("สกัดข้อมูลเรียบร้อยแล้ว!")
                st.rerun()
                
        btn_clicked = st.button("📥 ประมวลผลและสกัดข้อมูลอีกครั้ง", use_container_width=True, key="process_docx_btn")
        if btn_clicked:
            with st.spinner("กำลังอ่านและสกัดข้อมูล..."):
                extracted_data = extract_memo_data(uploaded_file)
                populate_session_state(extracted_data, force=True)
                st.success("สกัดข้อมูลเรียบร้อยแล้ว!")
                st.rerun()

    st.markdown("<hr style='margin: 6px 0; border: none; border-top: 1px solid #e2e8f0;'/>", unsafe_allow_html=True)
    if st.button("🔄 รีเซ็ตข้อมูลทั้งหมด", use_container_width=True, key="reset_all_btn"):
        st.session_state.clear()
        populate_session_state(default_init, force=True)
        st.rerun()

    st.markdown("<hr style='margin: 6px 0; border: none; border-top: 1px solid #e2e8f0;'/>", unsafe_allow_html=True)
    
    # Export Section inside Collapsible Expander (Default expanded for quick access)
    with st.expander("📤 ส่งออกเอกสาร & คัดลอก JSON (Export / Copy JSON)", expanded=True):
        # Clean and format doc_number_tail dynamically
        raw_doc_num = str(st.session_state.get("doc_number", "")).strip()
        seq_num = str(st.session_state.get("doc_seq_num", st.session_state.get("seq_input", ""))).strip()
        b_year = str(st.session_state.get("budget_year", "")).strip()
        y_sfx = b_year[-2:] if len(b_year) >= 2 else str((datetime.now().year + 543) % 100)
        
        if seq_num and seq_num != "____":
            clean_tail = f"7608.8.1/{seq_num}/{y_sfx}"
        else:
            # Fallback: extract full pattern or strip leading อว.
            clean_tail = re.sub(r'^(?:อว\.?|\.)\s*', '', raw_doc_num).strip()
            clean_tail = clean_tail.replace("____", "").replace("___", "").strip()
            clean_tail = re.sub(r'\s+', ' ', clean_tail)
            # If tail ends with a trailing slash (e.g. "7608.8.1/"), complete with default suffix if empty
            if clean_tail.endswith('/'):
                clean_tail = f"{clean_tail}{y_sfx}"

        # Phase 4.3: Payload validation before export
        breakdown_df = st.session_state.get("breakdown_df", DEFAULT_BREAKDOWN)
        if breakdown_df is None or breakdown_df.empty:
            breakdown_df = DEFAULT_BREAKDOWN
            st.warning("⚠️ ตารางค่าใช้จ่ายว่าง — ใช้ข้อมูล Default Breakdown แทน")
        breakdown_records = breakdown_df.to_dict(orient="records")

        sched_acts_export = st.session_state.get("schedule_activities", [])
        if (not sched_acts_export or (isinstance(sched_acts_export, list) and len(sched_acts_export) == 0)):
            sched_text = st.session_state.get("schedule_text", "")
            if sched_text:
                sched_acts_export = [{
                    "date_title": sched_text,
                    "location": st.session_state.get("location_name", ""),
                    "items": []
                }]
                st.info("ℹ️ ไม่พบตารางกำหนดการ — สร้างโครงสร้าง 1 วันจาก schedule_text")

        export_payload = {
            "agency_name": st.session_state.get("agency_name", ""),
            "doc_number": raw_doc_num,
            "doc_number_tail": clean_tail or raw_doc_num,
            "doc_date": st.session_state.get("doc_date", ""),
            "doc_date_iso": st.session_state.get("doc_date_iso", datetime.now().date().strftime("%Y-%m-%d")),
            "contact_phone": st.session_state.get("contact_phone", "053-218618"),
            "recipient_title": st.session_state.get("recipient_title", ""),
            "closing_text": st.session_state.get("closing_text", ""),
            "requester_name": str(st.session_state.get("requester_name", "")).strip("() "),
            "requester_position": st.session_state.get("requester_position", ""),
            "approver_left_name": str(st.session_state.get("approver_left_name", "")).strip("() "),
            "approver_left_pos": st.session_state.get("approver_left_pos", ""),
            "approver_right_name": str(st.session_state.get("approver_right_name", "")).strip("() "),
            "approver_right_pos": st.session_state.get("approver_right_pos", ""),
            "project_title": st.session_state.get("project_title", ""),
            "project_context": st.session_state.get("project_context", ""),
            "project_objective": st.session_state.get("project_objective", ""),
            "action_verb": st.session_state.get("action_verb", "ดำเนินงาน"),
            "action_details": st.session_state.get("action_details", ""),
            "target_group_name": st.session_state.get("target_group_name", "ผู้เข้าร่วม"),
            "target_group_quantity": st.session_state.get("target_group_quantity", "1"),
            "target_group_unit": st.session_state.get("target_group_unit", "งาน"),
            "location_name": st.session_state.get("location_name", ""),
            "province_name": st.session_state.get("province_name", ""),
            "location_province": st.session_state.get("location_province", ""),
            "schedule_mode": st.session_state.get("schedule_mode", ""),
            "schedule_text": st.session_state.get("schedule_text", ""),
            "start_date_iso": st.session_state.get("start_date_iso", datetime.now().date().strftime("%Y-%m-%d")),
            "end_date_iso": st.session_state.get("end_date_iso", datetime.now().date().strftime("%Y-%m-%d")),
            "schedule_iso_dates": st.session_state.get("schedule_iso_dates", []),
            "has_time_loc_phrase": st.session_state.get("has_time_loc_phrase", True),
            "show_p3_paragraph": st.session_state.get("show_p3_paragraph", True),
            "acc_code": st.session_state.get("acc_code", ""),
            "budget_year": st.session_state.get("budget_year", ""),
            "budget_source": st.session_state.get("budget_source", ""),
            "budget_amount": st.session_state.get("budget_amount", ""),
            "budget_text": st.session_state.get("budget_text", ""),
            "breakdown": breakdown_records,
            "schedule_document_title": f"กำหนดการ{st.session_state.get('project_title', '')}" if st.session_state.get('project_title') else "",
            "schedule_activities": sched_acts_export
        }

        st.markdown("**⚡ ส่งออกสำหรับ Extension / การอนุมัติ:**")
        json_str_payload = json.dumps(export_payload, ensure_ascii=False, indent=2)
        
        # HTML/JS Custom Button for Direct 1-Click Clipboard Copy
        copy_button_html = f"""
        <script>
        function copyRSCPayload() {{
            const jsonText = {json.dumps(json_str_payload)};
            navigator.clipboard.writeText(jsonText).then(() => {{
                const msgElem = document.getElementById('rsc-copy-status');
                msgElem.style.display = 'block';
                setTimeout(() => {{ msgElem.style.display = 'none'; }}, 3000);
            }}).catch(err => {{
                console.error('Copy failed', err);
            }});
        }}
        </script>
        <button onclick="copyRSCPayload()" style="
            width: 100%;
            background-color: #2563eb;
            color: white;
            padding: 10px 14px;
            font-size: 14px;
            font-weight: bold;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: background-color 0.2s;
            margin-bottom: 6px;
        " onmouseover="this.style.backgroundColor='#1d4ed8'" onmouseout="this.style.backgroundColor='#2563eb'">
            📋 คัดลอกไป RSC_Approval
        </button>
        <div id="rsc-copy-status" style="display: none; font-size: 12px; color: #16a34a; font-weight: bold; text-align: center; margin-bottom: 10px;">
            ✅ คัดลอกข้อมูลเรียบร้อย! นำไปกด Auto-Fill ใน Extension ได้เลย
        </div>
        """
        components.html(copy_button_html, height=75)

        st.markdown("---")
        st.markdown("**📁 ส่งออกไฟล์อื่นๆ:**")
        col_ex_a, col_ex_b = st.columns(2)
        with col_ex_a:
            if st.button("📄 สร้าง Word (.docx)", use_container_width=True, key="btn_prep_docx"):
                st.session_state["active_export"] = "docx"
            if st.button("📥 ดู JSON Raw Data", use_container_width=True, key="btn_prep_json"):
                st.session_state["active_export"] = "json"
        with col_ex_b:
            if st.button("📕 สร้าง PDF (.pdf)", use_container_width=True, key="btn_prep_pdf"):
                st.session_state["active_export"] = "pdf"
            if st.button("📊 สร้าง Excel (.xlsx)", use_container_width=True, key="btn_prep_excel"):
                st.session_state["active_export"] = "excel"

        active_exp = st.session_state.get("active_export")
        if active_exp == "docx":
            docx_data = generate_docx_bytes(export_payload)
            st.download_button(
                label="⬇️ คลิกเพื่อดาวน์โหลด Word (.docx)",
                data=docx_data,
                file_name="บันทึกข้อความ_สมาร์ทฟอร์ม.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key="dl_docx_ready"
            )
        elif active_exp == "pdf":
            pdf_data = generate_pdf_bytes(export_payload)
            st.download_button(
                label="⬇️ คลิกเพื่อดาวน์โหลด PDF (.pdf)",
                data=pdf_data,
                file_name="บันทึกข้อความ_สมาร์ทฟอร์ม.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="dl_pdf_ready"
            )
        elif active_exp == "json":
            json_str = json.dumps(export_payload, ensure_ascii=False, indent=2)
            st.code(json_str, language="json")
            st.download_button(
                label="⬇️ คลิกเพื่อดาวน์โหลด JSON",
                data=json_str,
                file_name="smart_memo_data.json",
                mime="application/json",
                use_container_width=True,
                key="dl_json_ready"
            )
            st.info("💡 สามารถคัดลอก JSON ด้านบนเพื่อนำไปกรอกฟอร์มปลายทางผ่าน Chrome Extension (v.1) ได้ทันที")

        elif active_exp == "excel":
            excel_io = io.BytesIO()
            with pd.ExcelWriter(excel_io, engine="openpyxl") as writer:
                meta_df = pd.DataFrame([{k: str(v) for k, v in export_payload.items() if k != "breakdown"}])
                meta_df.to_excel(writer, sheet_name="Metadata", index=False)
                st.session_state.get("breakdown_df", DEFAULT_BREAKDOWN).to_excel(writer, sheet_name="Breakdown", index=False)
            excel_io.seek(0)

            st.download_button(
                label="⬇️ คลิกเพื่อดาวน์โหลด Excel (.xlsx)",
                data=excel_io.getvalue(),
                file_name="smart_memo_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dl_excel_ready"
            )


# -----------------------------------------------------------------------------
# CSS Styling for Independent Form Column Scrolling & Sticky Preview Pinned
# -----------------------------------------------------------------------------
st.markdown("""
<style>
/* Reclaim top space while preserving clean view */
header[data-testid="stHeader"] {
    display: none !important;
}
.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 0.5rem !important;
}
section[data-testid="stSidebar"] {
    padding-top: 0 !important;
}
section[data-testid="stSidebar"] .block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 0.5rem !important;
}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {
    gap: 0.3rem !important;
}
section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p {
    margin-bottom: 0.2rem !important;
}

/* Make left column (Form Editor) extend naturally down the page without fixed bottom crop */
div[data-testid="stColumn"]:nth-of-type(1) {
    padding-right: 12px;
    border-right: 1px solid #eee;
}

/* Make right column (Live A4 Preview) sticky pinned to top while scrolling */
div[data-testid="stColumn"]:nth-of-type(2) {
    position: sticky !important;
    top: 0.5rem !important;
    align-self: flex-start !important;
}

/* Color-Coded Expander Headers for Left Column (Single Clean Border, No Double Box) */
/* Section 1: Sky Blue */
.st-key-sec1_exp div[data-testid="stExpander"] {
    border: 2px solid #0284c7 !important;
    border-radius: 8px !important;
    background-color: #f0f9ff !important;
    margin-bottom: 12px !important;
    overflow: hidden !important;
}
.st-key-sec1_exp details {
    border: none !important;
    outline: none !important;
}
.st-key-sec1_exp summary {
    background-color: #e0f2fe !important;
    color: #0369a1 !important;
}
.st-key-sec1_exp summary * {
    color: #0369a1 !important;
    font-weight: bold !important;
}

/* Section 2: Soft Pink */
.st-key-sec2_exp div[data-testid="stExpander"] {
    border: 2px solid #db2777 !important;
    border-radius: 8px !important;
    background-color: #fdf2f8 !important;
    margin-bottom: 12px !important;
    overflow: hidden !important;
}
.st-key-sec2_exp details {
    border: none !important;
    outline: none !important;
}
.st-key-sec2_exp summary {
    background-color: #fce7f3 !important;
    color: #be185d !important;
}
.st-key-sec2_exp summary * {
    color: #be185d !important;
    font-weight: bold !important;
}

/* Section 3: Amber Gold */
.st-key-sec3_exp div[data-testid="stExpander"] {
    border: 2px solid #d97706 !important;
    border-radius: 8px !important;
    background-color: #fffbe6 !important;
    margin-bottom: 12px !important;
    overflow: hidden !important;
}
.st-key-sec3_exp details {
    border: none !important;
    outline: none !important;
}
.st-key-sec3_exp summary {
    background-color: #fef3c7 !important;
    color: #b45309 !important;
}
.st-key-sec3_exp summary * {
    color: #b45309 !important;
    font-weight: bold !important;
}

/* Section 4: Fresh Green */
.st-key-sec4_exp div[data-testid="stExpander"] {
    border: 2px solid #16a34a !important;
    border-radius: 8px !important;
    background-color: #f0fdf4 !important;
    margin-bottom: 12px !important;
    overflow: hidden !important;
}
.st-key-sec4_exp details {
    border: none !important;
    outline: none !important;
}
.st-key-sec4_exp summary {
    background-color: #dcfce7 !important;
    color: #15803d !important;
}
.st-key-sec4_exp summary * {
    color: #15803d !important;
    font-weight: bold !important;
}

/* Section 5: Bright Orange */
.st-key-sec5_exp div[data-testid="stExpander"] {
    border: 2px solid #ea580c !important;
    border-radius: 8px !important;
    background-color: #fff7ed !important;
    margin-bottom: 12px !important;
    overflow: hidden !important;
}
.st-key-sec5_exp details {
    border: none !important;
    outline: none !important;
}
.st-key-sec5_exp summary {
    background-color: #ffedd5 !important;
    color: #c2410c !important;
}
.st-key-sec5_exp summary * {
    color: #c2410c !important;
    font-weight: bold !important;
}
.st-key-sec5_exp summary * {
    color: #c2410c !important;
    font-weight: bold !important;
}
</style>
""", unsafe_allow_html=True)

col_edit, col_preview = st.columns([1, 1], gap="medium")

# =============================================================================
# LEFT COLUMN: 5-Part Form / Block Editor
# =============================================================================
with col_edit:
    st.subheader("✏️ ฟอร์มแก้ไขข้อมูล (5 Sections)")

    # Section 1: ข้อมูลทั่วไป
    with st.expander("📌 Section 1: ข้อมูลทั่วไป & ระบบงบประมาณ", expanded=True, key="sec1_exp"):
        st.markdown("**เลขที่หนังสือ \***")
        st.caption("กรอกเฉพาะส่วนต่อจาก อว. ระบบจะคงคำนำหน้าและจัดรูปแบบให้อัตโนมัติ")
        
        doc_mode = st.radio(
            "รูปแบบการกรอกเลขที่หนังสือ",
            options=["รูปแบบมาตรฐาน (อว. 7608.8.1/____/YY)", "กำหนดเองทั้งหมด"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        b_year = str(st.session_state.get("budget_year", "")).strip()
        year_suffix = b_year[-2:] if len(b_year) >= 2 else str((datetime.now().year + 543) % 100)
            
        if doc_mode == "รูปแบบมาตรฐาน (อว. 7608.8.1/____/YY)":
            col_pfx, col_seq, col_sfx = st.columns([2.5, 3.5, 1.5])
            with col_pfx:
                st.text_input("คำนำหน้า", value="อว. 7608.8.1/", disabled=True, key="pfx_input")
            with col_seq:
                seq_val = st.text_input("เลขลำดับ", placeholder="เช่น 1234", key="doc_seq_num")
            with col_sfx:
                st.text_input("ปี (2 หลัก)", value=f"/{year_suffix}", disabled=True, key="sfx_input")
                
            formatted_doc_num = f"อว 7608.8.1/{seq_val}/{year_suffix}" if seq_val else f"อว 7608.8.1/____/{year_suffix}"
            st.session_state["doc_number"] = formatted_doc_num
        else:
            custom_doc_num = st.text_input("เลขที่หนังสือ (กำหนดเอง)", value=st.session_state.get("doc_number", ""), key="custom_doc_num_input")
            st.session_state["doc_number"] = custom_doc_num

        cur_d_obj = st.session_state.get("doc_date_obj")
        if not cur_d_obj or not isinstance(cur_d_obj, (datetime, date, type(datetime.now().date()))):
            cur_d_obj = parse_thai_date(st.session_state.get("doc_date", ""))

        picked_date = st.date_input(
            "วันที่หนังสือ (เลือกจากปฏิทิน)",
            value=cur_d_obj,
            format="DD/MM/YYYY",
            key="doc_date_picker"
        )
        st.session_state["doc_date_obj"] = picked_date
        st.session_state["doc_date"] = format_thai_date(picked_date)
        
        st.session_state["contact_phone"] = st.text_input(
            "โทรศัพท์สำหรับติดต่อในหนังสือ (contact_phone)",
            value=st.session_state.get("contact_phone", "053-218618"),
            placeholder="เช่น 9682 หรือ 053-218618",
            help="แสดงในหัวหนังสือส่วนงาน หรือเว้นว่างได้"
        )
        
        # ACC Code Selector & Auto-fill budget year/source
        acc_options = list(ACC_MAPPING.keys())
        current_acc = st.session_state.get("acc_code", acc_options[0])
        idx = acc_options.index(current_acc) if current_acc in acc_options else 0
        
        selected_acc = st.selectbox("รหัสงบประมาณ (acc_code)", options=acc_options, index=idx)
        if selected_acc != st.session_state.get("acc_code"):
            st.session_state["acc_code"] = selected_acc
            st.session_state["budget_year"] = ACC_MAPPING[selected_acc]["budget_year"]
            st.session_state["budget_source"] = ACC_MAPPING[selected_acc]["budget_source"]
            st.rerun()

        year_options = ["2566", "2567", "2568", "2569", "2570", "2571", "2572"]
        current_year = str(st.session_state.get("budget_year", "2569")).strip()
        year_idx = year_options.index(current_year) if current_year in year_options else 3

        c1, c2 = st.columns(2)
        with c1:
            selected_b_year = st.selectbox("ปีงบประมาณ (budget_year)", options=year_options, index=year_idx, key="budget_year_selectbox")
            st.session_state["budget_year"] = selected_b_year
        with c2:
            st.session_state["budget_source"] = st.text_input("แหล่งงบประมาณ (budget_source)", value=st.session_state.get("budget_source", ""))
            
        st.file_uploader("แนบไฟล์ PDF เอกสารแนบเพิ่มเติม (attachment_pdf)", type=["pdf"])

    # Section 2: ข้อมูลผู้ขอ
    with st.expander("👤 Section 2: ข้อมูลผู้ขออนุมัติ", expanded=True, key="sec2_exp"):
        st.session_state["requester_name"] = st.text_input("ชื่อ-นามสกุล ผู้ขอ (requester_name)", value=st.session_state.get("requester_name", ""))
        st.session_state["requester_position"] = st.text_input("ตำแหน่ง ผู้ขอ (requester_position)", value=st.session_state.get("requester_position", ""))

    # Section 3: รายละเอียดโครงการ
    with st.expander("📝 Section 3: รายละเอียดโครงการ & วัตถุประสงค์", expanded=True, key="sec3_exp"):
        st.session_state["project_title"] = st.text_input("เรื่อง / ชื่อโครงการ (project_title)", value=st.session_state.get("project_title", ""))
        st.session_state["project_context"] = st.text_area("บริบทโครงการ / ย่อหน้าแรก (project_context)", value=st.session_state.get("project_context", ""), height=90)
        st.session_state["project_objective"] = st.text_area("วัตถุประสงค์ (project_objective)", value=st.session_state.get("project_objective", ""), height=90)
        
        col_v1, col_v2 = st.columns([2, 4])
        with col_v1:
            st.session_state["action_verb"] = st.text_input("คำกริยาดำเนินการ (action_verb)", value=st.session_state.get("action_verb", "ดำเนินงาน"), placeholder="เช่น จัดอบรม / เดินทางไป")
        with col_v2:
            st.session_state["action_details"] = st.text_input("รายละเอียดการดำเนินงาน (action_details)", value=st.session_state.get("action_details", ""), placeholder="เช่น ติดตามงานและทดสอบระบบ")
            
        col_tg_hdr, col_tg_tgl = st.columns([4, 2])
        with col_tg_hdr:
            st.markdown("**👥 ข้อมูลกลุ่มเป้าหมาย**")
        with col_tg_tgl:
            enable_target_group = st.checkbox("ระบุกลุ่มเป้าหมาย", value=st.session_state.get("enable_target_group", True), key="chk_enable_target_group")
            st.session_state["enable_target_group"] = enable_target_group

        if enable_target_group:
            col_tg1, col_tg2, col_tg3 = st.columns([3, 2, 2])
            with col_tg1:
                st.session_state["target_group_name"] = st.text_input("ชื่อกลุ่มเป้าหมาย", value=st.session_state.get("target_group_name", "ผู้เข้าร่วม"))
            with col_tg2:
                st.session_state["target_group_quantity"] = st.text_input("จำนวน", value=st.session_state.get("target_group_quantity", "1"))
            with col_tg3:
                st.session_state["target_group_unit"] = st.text_input("หน่วย", value=st.session_state.get("target_group_unit", "งาน"))
        else:
            st.session_state["target_group_name"] = ""
            st.session_state["target_group_quantity"] = ""
            st.session_state["target_group_unit"] = ""
            st.caption("🚫 ปิดใช้งานกลุ่มเป้าหมาย (ระบบจะไม่ส่งข้อมูลและจะไม่ลบกลุ่มเป้าหมายบนหน้าเว็บ)")

        st.markdown("---")

        st.markdown("**✍️ ข้อความย่อหน้า 3 (ย่อหน้าขออนุมัติดำเนินงาน - พิมพ์แก้ไขได้ทั้งประโยค):**")
        
        req_name_raw = str(st.session_state.get("requester_name", "")).strip()
        req_name_clean = req_name_raw.replace("(", "").replace(")", "").strip()
        req_pos = str(st.session_state.get("requester_position", "")).strip()
        act_part = str(st.session_state.get('action_details', '')).strip()
        sched_part = str(st.session_state.get('schedule_text', '')).strip()
        loc_part = str(st.session_state.get('location_province', '')).strip()

        act_str = f" {act_part}" if act_part else ""
        sched_str = f" ในวันที่ {sched_part}" if sched_part else ""
        loc_str = f" {loc_part}" if loc_part else ""

        auto_composed_p3 = f"ดังนั้น ข้าพเจ้า {req_name_clean} ตำแหน่ง {req_pos} ขออนุมัติดำเนินงาน{act_str}{sched_str}{loc_str}".strip()

        if "p3_full_text" not in st.session_state or not st.session_state["p3_full_text"]:
            st.session_state["p3_full_text"] = auto_composed_p3

        def reset_p3():
            st.session_state["p3_full_text"] = auto_composed_p3

        p3_input_val = st.text_area(
            "ข้อความย่อหน้า 3 (สามารถพิมพ์แก้ไขคำได้อย่างอิสระ)",
            value=st.session_state.get("p3_full_text", auto_composed_p3),
            height=90,
            help="สามารถแก้ไข ลบ หรือพิมพ์ประโยคใหม่ในย่อหน้านี้ได้อย่างอิสระ"
        )
        st.session_state["p3_full_text"] = p3_input_val

        st.button(
            "⚡ ประกอบประโยคย่อหน้า 3 ให้อัตโนมัติ",
            use_container_width=True,
            on_click=reset_p3,
            help="ดึงข้อมูลจากชื่อ ตำแหน่ง กิจกรรม วันที่ และสถานที่มารวมเป็นประโยคใหม่"
        )

        st.markdown("---")
        show_p3_toggle = st.toggle("👁️ แสดงย่อหน้า 'ดังนั้น ข้าพเจ้า...' ในเอกสาร", value=st.session_state.get("show_p3_paragraph", True))
        st.session_state["show_p3_paragraph"] = show_p3_toggle

    # Section 4: สถานที่ & กำหนดการ
    with st.expander("📍 Section 4: สถานที่ & กำหนดการ", expanded=True, key="sec4_exp"):
        col_loc_hdr, col_loc_tgl = st.columns([4, 2])
        with col_loc_hdr:
            st.markdown("**📍 สถานที่ดำเนินโครงการ**")
        with col_loc_tgl:
            enable_location = st.checkbox("ระบุสถานที่ดำเนินโครงการ", value=st.session_state.get("enable_location", True), key="chk_enable_location")
            st.session_state["enable_location"] = enable_location

        if enable_location:
            col_l1, col_l2 = st.columns(2)
            with col_l1:
                st.session_state["location_name"] = st.text_input("สถานที่ (location_name)", value=st.session_state.get("location_name", ""))
            with col_l2:
                st.session_state["province_name"] = st.text_input("จังหวัด (province_name)", value=st.session_state.get("province_name", ""))

            loc_str = str(st.session_state.get("location_name", "")).strip()
            prov_str = str(st.session_state.get("province_name", "")).strip()
            if loc_str and prov_str:
                st.session_state["location_province"] = f"ณ {loc_str} จ.{prov_str}"
            elif loc_str:
                st.session_state["location_province"] = f"ณ {loc_str}"
            else:
                st.session_state["location_province"] = ""
        else:
            st.session_state["location_name"] = ""
            st.session_state["province_name"] = ""
            st.session_state["location_province"] = ""
            st.caption("🚫 ปิดใช้งานสถานที่ดำเนินโครงการ (ระบบจะไม่ส่งสถานที่และจะลบสถานที่บนหน้าเว็บให้อัตโนมัติ)")

        st.markdown("---")
        st.markdown("**📅 ระบบเลือกวันที่ดำเนินงาน (schedule_text)**")
        sched_mode = st.radio(
            "เลือกรูปแบบวันที่ดำเนินงาน",
            options=["ใช้วันที่จากข้อความเดิมที่สกัดได้", "เลือกจากปฏิทิน (บังคับเก็บเป็น Date Object)"],
            horizontal=True,
            key="sched_mode_radio"
        )
        st.session_state["schedule_mode"] = sched_mode

        if sched_mode == "ใช้วันที่จากข้อความเดิมที่สกัดได้":
            st.session_state["schedule_text"] = st.text_input(
                "วันที่ดำเนินงาน / ช่วงเวลา (ข้อความเดิม)",
                value=st.session_state.get("schedule_text", ""),
                key="schedule_text_raw_input",
                help="ข้อความดั้งเดิมจากเอกสาร หรือระบุหลายวัน/หลายช่วงเพิ่มเติมได้"
            )
        else:
            st.caption("📅 บังคับเก็บข้อมูลเป็น Date Object (รองรับการเลือกหลายวัน หรือหลายช่วงวันที่จากปฏิทิน)")
            
            if "schedule_date_items" not in st.session_state or not isinstance(st.session_state["schedule_date_items"], list):
                st.session_state["schedule_date_items"] = [
                    {"type": "range", "start_date": datetime.now().date(), "end_date": datetime.now().date()}
                ]
                
            items = list(st.session_state["schedule_date_items"])
            updated_items = []
            formatted_date_parts = []
            iso_dates_list = []
            items_to_remove = []

            for idx, item in enumerate(items):
                st.markdown(f"**รายการวันที่ #{idx+1}**")
                col_type, col_picker, col_del = st.columns([2.5, 4.5, 1])
                with col_type:
                    i_type = st.selectbox(
                        f"ประเภท #{idx+1}",
                        options=["วันเดียว (Single Date)", "ช่วงวันที่ (Date Range)"],
                        index=0 if item.get("type") == "single" else 1,
                        key=f"item_type_sel_{idx}"
                    )
                
                with col_picker:
                    if "Single" in i_type:
                        val_d = item.get("date", datetime.now().date())
                        if not isinstance(val_d, (datetime, date)):
                            val_d = datetime.now().date()
                        picked = st.date_input(f"เลือกวัน #{idx+1}", value=val_d, format="DD/MM/YYYY", key=f"item_date_pick_{idx}")
                        updated_items.append({"type": "single", "date": picked})
                        formatted_date_parts.append(format_thai_date(picked))
                        iso_dates_list.append({"type": "single", "date": picked.isoformat()})
                    else:
                        start_d = item.get("start_date", datetime.now().date())
                        end_d = item.get("end_date", datetime.now().date())
                        if not isinstance(start_d, (datetime, date)): start_d = datetime.now().date()
                        if not isinstance(end_d, (datetime, date)): end_d = datetime.now().date()
                        
                        picked_range = st.date_input(f"เลือกช่วงวัน #{idx+1}", value=(start_d, end_d), format="DD/MM/YYYY", key=f"item_range_pick_{idx}")

                        if isinstance(picked_range, (list, tuple)) and len(picked_range) == 2:
                            s_d, e_d = picked_range[0], picked_range[1]
                        elif isinstance(picked_range, (list, tuple)) and len(picked_range) == 1:
                            s_d, e_d = picked_range[0], picked_range[0]
                        else:
                            s_d, e_d = datetime.now().date(), datetime.now().date()
                            
                        updated_items.append({"type": "range", "start_date": s_d, "end_date": e_d})
                        if s_d == e_d:
                            formatted_date_parts.append(format_thai_date(s_d))
                        else:
                            formatted_date_parts.append(f"{format_thai_date(s_d)} ถึงวันที่ {format_thai_date(e_d)}")
                        iso_dates_list.append({"type": "range", "start_date": s_d.isoformat(), "end_date": e_d.isoformat()})
                
                with col_del:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ ลบ", key=f"del_item_btn_{idx}"):
                        items_to_remove.append(idx)

            if items_to_remove:
                for r_idx in sorted(items_to_remove, reverse=True):
                    items.pop(r_idx)
                st.session_state["schedule_date_items"] = items
                st.rerun()

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("➕ เพิ่มวันที่ (Single Date)", use_container_width=True):
                    items.append({"type": "single", "date": datetime.now().date()})
                    st.session_state["schedule_date_items"] = items
                    st.rerun()
            with col_btn2:
                if st.button("➕ เพิ่มช่วงวันที่ (Date Range)", use_container_width=True):
                    items.append({"type": "range", "start_date": datetime.now().date(), "end_date": datetime.now().date()})
                    st.session_state["schedule_date_items"] = items
                    st.rerun()

            st.session_state["schedule_date_items"] = updated_items
            st.session_state["schedule_iso_dates"] = iso_dates_list
            combined_sched = ", ".join(formatted_date_parts) if formatted_date_parts else ""
            st.session_state["schedule_text"] = combined_sched
            st.info(f"📌 ข้อความวันที่สรุปจากปฏิทิน: **{combined_sched}**")

        st.markdown("---")
        show_time_loc = st.toggle(
            "👁️ แสดงข้อความ 'ตามวัน เวลา และสถานที่ดังกล่าว' ในประโยคขออนุมัติค่าใช้จ่าย",
            value=st.session_state.get("has_time_loc_phrase", True),
            key="time_loc_toggle"
        )
        st.session_state["has_time_loc_phrase"] = show_time_loc

        # Phase 4.2: Manual Schedule Activities Editor
        st.markdown("---")
        st.markdown("**📅 ตารางกำหนดการเดินทาง (Schedule Activities Editor):**")
        st.caption("แก้ไขหรือเพิ่มกิจกรรมในแต่ละวันได้โดยตรง — ข้อมูลนี้จะถูกส่งไปยัง Chrome Extension")

        sched_acts = st.session_state.get("schedule_activities", [])
        if not isinstance(sched_acts, list):
            sched_acts = []

        # Flatten schedule_activities into a flat DataFrame for editing
        flat_rows = []
        for d_idx, day in enumerate(sched_acts):
            if not isinstance(day, dict):
                continue
            items = day.get("items", [])
            if not items:
                flat_rows.append({
                    "day": d_idx + 1,
                    "date_title": day.get("date_title", ""),
                    "location": day.get("location", ""),
                    "time": "",
                    "activity": ""
                })
            else:
                for item in items:
                    flat_rows.append({
                        "day": d_idx + 1,
                        "date_title": day.get("date_title", ""),
                        "location": day.get("location", ""),
                        "time": item.get("time", ""),
                        "activity": item.get("activity", "")
                    })

        sched_edit_df = pd.DataFrame(
            flat_rows,
            columns=["day", "date_title", "location", "time", "activity"]
        )
        if sched_edit_df.empty:
            sched_edit_df = pd.DataFrame(
                [{"day": 1, "date_title": "", "location": "", "time": "", "activity": ""}],
                columns=["day", "date_title", "location", "time", "activity"]
            )

        edited_sched = st.data_editor(
            sched_edit_df,
            num_rows="dynamic",
            use_container_width=True,
            key="sched_activities_editor"
        )

        # Rebuild schedule_activities from flat DataFrame
        rebuilt = []
        for _, row in edited_sched.iterrows():
            day_num = int(row["day"]) if pd.notna(row["day"]) else 1
            date_title = str(row["date_title"]) if pd.notna(row["date_title"]) else ""
            location = str(row["location"]) if pd.notna(row["location"]) else ""
            time_val = str(row["time"]) if pd.notna(row["time"]) else ""
            activity_val = str(row["activity"]) if pd.notna(row["activity"]) else ""

            # Find or create day entry
            day_entry = None
            for d in rebuilt:
                if d["_day_num"] == day_num:
                    day_entry = d
                    break
            if not day_entry:
                day_entry = {
                    "_day_num": day_num,
                    "date_title": date_title,
                    "location": location,
                    "items": []
                }
                rebuilt.append(day_entry)
            else:
                if date_title:
                    day_entry["date_title"] = date_title
                if location:
                    day_entry["location"] = location

            if time_val or activity_val:
                day_entry["items"].append({
                    "time": time_val,
                    "activity": activity_val
                })

        # Clean up temporary key
        cleaned = []
        for d in rebuilt:
            cleaned.append({
                "date_title": d.get("date_title", ""),
                "location": d.get("location", ""),
                "items": d.get("items", [])
            })
        st.session_state["schedule_activities"] = cleaned

    # Section 5: วงเงินงบประมาณ & ตาราง
    with st.expander("💰 Section 5: วงเงิน & ตารางค่าใช้จ่าย", expanded=True, key="sec5_exp"):
        def on_budget_amt_change():
            new_amt = st.session_state.get("b_amt_input", "")
            st.session_state["budget_amount"] = new_amt
            auto_t = num_to_thai_baht(new_amt)
            if auto_t:
                st.session_state["budget_text"] = f"({auto_t})"
                st.session_state["b_text_input"] = f"({auto_t})"

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            raw_amt_val = st.text_input(
                "วงเงินรวม (บาท)",
                value=st.session_state.get("budget_amount", ""),
                key="b_amt_input",
                on_change=on_budget_amt_change
            )
            st.session_state["budget_amount"] = raw_amt_val

        with col_b2:
            cur_amt = st.session_state.get("budget_amount", "")
            if st.session_state.get("last_converted_amt") != cur_amt:
                auto_t = num_to_thai_baht(cur_amt)
                if auto_t:
                    st.session_state["budget_text"] = f"({auto_t})"
                    st.session_state["b_text_input"] = f"({auto_t})"
                st.session_state["last_converted_amt"] = cur_amt

            budget_txt_val = st.text_input(
                "วงเงินรวม (ตัวอักษร - แปลงอัตโนมัติ)",
                value=st.session_state.get("budget_text", ""),
                key="b_text_input"
            )
            st.session_state["budget_text"] = budget_txt_val

        st.markdown("---")
        st.markdown("**รูปแบบการแสดงผลรายการค่าใช้จ่ายในเอกสาร:**")
        b_disp_mode = st.radio(
            "เลือกรูปแบบการแสดงผลค่าใช้จ่าย",
            options=[
                "1. ไม่แสดงในเอกสาร",
                "2. แสดงเป็นข้อๆ (1. [รายการ] [รายละเอียด] .......... [จำนวนเงิน] บาท)",
                "3. แสดงเป็นตาราง (Table Grid)"
            ],
            index=1,
            key="breakdown_mode_radio"
        )
        st.session_state["breakdown_display_mode"] = b_disp_mode
        
        st.markdown("**ตารางแสดงรายละเอียดงบประมาณ (Editable Breakdown Table):**")
        edited_df = st.data_editor(
            st.session_state.get("breakdown_df", DEFAULT_BREAKDOWN),
            num_rows="dynamic",
            use_container_width=True
        )
        st.session_state["breakdown_df"] = edited_df

        # Auto calculate total budget_amount from breakdown table if present
        if not edited_df.empty and "จำนวนเงิน (บาท)" in edited_df.columns:
            tot = 0.0
            for val in edited_df["จำนวนเงิน (บาท)"]:
                v_clean = str(val).replace(",", "").strip()
                try:
                    tot += float(v_clean)
                except:
                    pass
            if tot > 0:
                tot_str = str(int(tot)) if tot.is_integer() else f"{tot:.2f}"
                if st.session_state.get("budget_amount") != tot_str:
                    st.session_state["budget_amount"] = tot_str
                    st.session_state["b_amt_input"] = tot_str
                    auto_t = num_to_thai_baht(tot_str)
                    if auto_t:
                        st.session_state["budget_text"] = f"({auto_t})"
                        st.session_state["b_text_input"] = f"({auto_t})"


# =============================================================================
# RIGHT COLUMN: Live A4 Document Preview (Interactive WYSIWYG & Section Mapping)
# =============================================================================
with col_preview:
    st.subheader("👁️ Live A4 Document Preview & Direct Edit")
    st.caption("✨ **ระบบ Interactive Document**: ข้อความใน A4 เชื่อมโยงกับ Section 1 - 5 ฝั่งซ้าย สามารถพิมพ์แก้ไขใน A4 ได้โดยตรง!")

    # Section Mapping Helper Info
    st.markdown("""
    <div style="font-size: 11px; margin-bottom: 8px; display: flex; gap: 6px; flex-wrap: wrap;">
        <span style="background-color: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 3px; font-weight: bold;">📌 Section 1: ข้อมูลทั่วไป</span>
        <span style="background-color: #fce7f3; color: #be185d; padding: 2px 6px; border-radius: 3px; font-weight: bold;">👤 Section 2: ผู้ขอ</span>
        <span style="background-color: #fef3c7; color: #b45309; padding: 2px 6px; border-radius: 3px; font-weight: bold;">📝 Section 3: โครงการ</span>
        <span style="background-color: #dcfce7; color: #15803d; padding: 2px 6px; border-radius: 3px; font-weight: bold;">📍 Section 4: กำหนดการ/สถานที่</span>
        <span style="background-color: #fff7ed; color: #c2410c; padding: 2px 6px; border-radius: 3px; font-weight: bold;">💰 Section 5: งบประมาณ</span>
    </div>
    """, unsafe_allow_html=True)

    # Render breakdown items into HTML based on selected display mode
    b_mode = st.session_state.get("breakdown_display_mode", "2. แสดงเป็นข้อๆ (1. [รายการ] [รายละเอียด] .......... [จำนวนเงิน] บาท)")
    df_current = st.session_state.get("breakdown_df", DEFAULT_BREAKDOWN)
    table_block_html = ""

    if "ไม่แสดง" not in b_mode and not df_current.empty:
        if "ข้อๆ" in b_mode or "1." in b_mode:
            list_items_html = ""
            row_count = 1
            for idx, row in df_current.iterrows():
                item = str(row.get("รายการ", "")).strip()
                detail = str(row.get("รายละเอียด", "")).strip()
                amt = str(row.get("จำนวนเงิน (บาท)", "")).strip()
                if item or detail or amt:
                    detail_part = f" {detail}" if detail != "-" and detail else ""
                    amt_str = f"{amt} บาท" if amt else ""
                    list_items_html += f"""
                    <div style="display: flex; justify-content: space-between; margin-left: 40px; margin-right: 20px; margin-bottom: 5px; font-size: 14px;">
                        <div>{row_count}. {item}{detail_part}</div>
                        <div style="text-align: right; min-width: 140px; white-space: nowrap;">{amt_str}</div>
                    </div>
                    """
                    row_count += 1
            if list_items_html:
                table_block_html = f"""
                <div class="editable-box sec-5-box" contenteditable="true" title="💰 Section 5: คลิกเพื่อแก้ไขรายละเอียดค่าใช้จ่าย" style="margin: 12px 0;">
                    {list_items_html}
                </div>
                """
        else: # "ตาราง"
            table_html_rows = ""
            for idx, row in df_current.iterrows():
                item = row.get("รายการ", "")
                detail = row.get("รายละเอียด", "")
                amt = row.get("จำนวนเงิน (บาท)", "")
                table_html_rows += f"""
                <tr>
                    <td style="border: 1px solid #aaa; padding: 5px 8px;">{item}</td>
                    <td style="border: 1px solid #aaa; padding: 5px 8px;">{detail}</td>
                    <td style="border: 1px solid #aaa; padding: 5px 8px; text-align: right;">{amt}</td>
                </tr>
                """
            if len(table_html_rows.strip()) > 0:
                table_block_html = f"""
                <div class="editable-box sec-5-box" contenteditable="true" title="💰 Section 5: คลิกเพื่อแก้ไขตารางงบประมาณ" style="margin: 15px 0;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 13.5px;">
                        <thead>
                            <tr style="background-color: #f2f2f2;">
                                <th style="border: 1px solid #aaa; padding: 6px; text-align: left; width: 35%;">รายการ</th>
                                <th style="border: 1px solid #aaa; padding: 6px; text-align: left; width: 45%;">รายละเอียด</th>
                                <th style="border: 1px solid #aaa; padding: 6px; text-align: right; width: 20%;">จำนวนเงิน (บาท)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_html_rows}
                        </tbody>
                    </table>
                </div>
                """

    # Dynamic Expense Attachment Block (แสดงแบบฟอร์มประมาณการค่าใช้จ่ายแนบท้ายเอกสารในพรีวิว A4)
    expense_attachment_html = ""
    if not df_current.empty:
        att_rows_html = ""
        total_amt = 0.0
        row_idx = 1
        for _, row in df_current.iterrows():
            item = str(row.get("รายการ", "")).strip()
            detail = str(row.get("รายละเอียด", "")).strip()
            amt_s = str(row.get("จำนวนเงิน (บาท)", "")).replace(",", "").strip()
            
            detail_str = f"<br/><span style='font-size:12px; color:#555;'>{detail}</span>" if detail != "-" and detail else ""
            try:
                amt_val = float(amt_s)
                total_amt += amt_val
                amt_fmt = f"{amt_val:,.2f}"
            except:
                amt_fmt = amt_s
            
            att_rows_html += f"""
            <tr>
                <td style="border: 1px solid #333; padding: 6px; text-align: center; vertical-align: top;">{row_idx}</td>
                <td style="border: 1px solid #333; padding: 6px; text-align: left; vertical-align: top;">{item}{detail_str}</td>
                <td style="border: 1px solid #333; padding: 6px; text-align: right; vertical-align: top;">{amt_fmt}</td>
            </tr>
            """
            row_idx += 1
        
        b_txt = st.session_state.get("budget_text", "")
        expense_attachment_html = f"""
        <div style="page-break-before: always; margin-top: 30px; padding-top: 20px; border-top: 2px dashed #94a3b8;">
            <div style="text-align: center; font-weight: bold; font-size: 16px; margin-bottom: 4px;">แบบฟอร์มประมาณการค่าใช้จ่าย</div>
            <div style="text-align: center; font-size: 13px; color: #555; margin-bottom: 12px;">(ใช้ประกอบกับสัญญาการยืมเงิน)</div>
            <div style="margin-bottom: 8px; font-weight: bold;">หน่วยงาน {st.session_state.get('agency_name', '')}</div>
            
            <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 10px;">
                <thead>
                    <tr style="background-color: #f8fafc;">
                        <th style="border: 1px solid #333; padding: 6px; width: 10%;">ลำดับ</th>
                        <th style="border: 1px solid #333; padding: 6px; width: 65%;">รายการ</th>
                        <th style="border: 1px solid #333; padding: 6px; width: 25%;">จำนวนเงิน (บาท)</th>
                    </tr>
                </thead>
                <tbody>
                    {att_rows_html}
                    <tr>
                        <td colspan="2" style="border: 1px solid #333; padding: 6px; text-align: center; font-weight: bold;">รวม</td>
                        <td style="border: 1px solid #333; padding: 6px; text-align: right; font-weight: bold;">{total_amt:,.2f}</td>
                    </tr>
                    <tr>
                        <td colspan="3" style="border: 1px solid #333; padding: 6px; text-align: center; font-weight: bold; background-color: #f8fafc;">{b_txt}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """

    # Dynamic Schedule Attachment Block (แสดงรายละเอียดกำหนดการแนบท้ายเอกสารในพรีวิว A4)
    schedule_preview_html = ""
    sched_acts = st.session_state.get("schedule_activities", [])
    if sched_acts and isinstance(sched_acts, list) and len(sched_acts) > 0:
        sched_days_html = ""
        for day in sched_acts:
            d_title = day.get("date_title", "")
            d_loc = day.get("location", "")
            loc_str = f" ({d_loc})" if d_loc else ""
            
            acts_html = ""
            for item in day.get("items", []):
                t_str = item.get("time", "")
                a_str = item.get("activity", "")
                acts_html += f"""
                <div style="display: flex; gap: 15px; margin-left: 20px; font-size: 13px; line-height: 1.4;">
                    <div style="font-weight: bold; min-width: 130px;">{t_str}</div>
                    <div>{a_str}</div>
                </div>
                """
            
            sched_days_html += f"""
            <div style="margin-bottom: 10px;">
                <div style="font-weight: bold; font-size: 13.5px; color: #1e3a8a; margin-bottom: 4px;">📅 {d_title}{loc_str}</div>
                {acts_html}
            </div>
            """
        
        if sched_days_html:
            schedule_preview_html = f"""
            <div style="page-break-before: always; margin-top: 30px; padding-top: 20px; border-top: 2px dashed #94a3b8;">
                <div style="text-align: center; font-weight: bold; font-size: 16px; margin-bottom: 12px;">เอกสารแนบ 2: รายละเอียดกำหนดการเดินทาง</div>
                <div class="editable-box sec-4-box" contenteditable="true" title="📍 Section 4: คลิกเพื่อแก้ไขรายละเอียดกำหนดการ" style="padding: 10px; background-color: #f8fafc; border-radius: 6px;">
                    {sched_days_html}
                </div>
            </div>
            """

    # Format numeric total with commas if applicable
    raw_amt = str(st.session_state.get("budget_amount", "0")).replace(",", "").strip()
    try:
        val_num = float(raw_amt)
        formatted_amt = f"{int(val_num):,}" if val_num.is_integer() else f"{val_num:,.2f}"
    except:
        formatted_amt = raw_amt

    # Dynamic Sentence Construction / Custom Editable Text for Paragraph 3 (ดังนั้น...)
    p3_html_block = ""
    if st.session_state.get("show_p3_paragraph", True):
        req_name_raw = str(st.session_state.get("requester_name", "")).strip()
        req_name_clean = req_name_raw.replace("(", "").replace(")", "").strip()
        
        act_part = st.session_state.get('action_details', '').strip()
        sched_part = st.session_state.get('schedule_text', '').strip()
        loc_part = st.session_state.get('location_province', '').strip()

        act_str = f" {act_part}" if act_part else ""
        sched_str = f" ในวันที่ {sched_part}" if sched_part else ""
        loc_str = f" {loc_part}" if loc_part else ""

        fallback_p3 = f"ดังนั้น ข้าพเจ้า {req_name_clean} ตำแหน่ง {st.session_state.get('requester_position', '')} ขออนุมัติดำเนินงาน{act_str}{sched_str}{loc_str}".strip()
        current_p3_text = st.session_state.get("p3_full_text", "") or fallback_p3

        p3_html_block = f"""
        <div class="editable-box sec-4-box" contenteditable="true" title="📍 Section 4: คลิกเพื่อแก้ไขย่อหน้าสรุปการดำเนินงาน" style="text-indent: 40px; text-align: justify; margin-bottom: 10px;">
            {current_p3_text}
        </div>
        """

    time_loc_phrase = "ตามวัน เวลา และสถานที่ดังกล่าว " if st.session_state.get("has_time_loc_phrase", True) else ""

    # Standard Thai Official Memo HTML Template (Squeezed for 1-Page A4 Fit)
    a4_html = textwrap.dedent(f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8" />
    <style>
        body {{
            margin: 0;
            padding: 0;
            background-color: transparent;
            font-family: 'Sarabun', 'TH Sarabun PSK', 'Segoe UI', Tahoma, sans-serif;
        }}
        .editable-box {{
            border-radius: 4px;
            padding: 2px 4px;
            transition: all 0.2s ease-in-out;
        }}
        .editable-box:hover {{
            background-color: #f0f9ff;
            outline: 1.5px dashed #0284c7;
            cursor: text;
        }}
        .editable-box:focus {{
            background-color: #ffffff;
            outline: 2px solid #2563eb;
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2);
        }}
        .sec-1-box:hover {{ background-color: #e0f2fe; outline-color: #0284c7; }}
        .sec-2-box:hover {{ background-color: #fce7f3; outline-color: #db2777; }}
        .sec-3-box:hover {{ background-color: #fef3c7; outline-color: #d97706; }}
        .sec-4-box:hover {{ background-color: #dcfce7; outline-color: #16a34a; }}
        .sec-5-box:hover {{ background-color: #fff7ed; outline-color: #ea580c; }}
        
        .tag-badge {{
            font-size: 10px;
            font-weight: bold;
            padding: 1px 5px;
            border-radius: 3px;
            margin-right: 4px;
            vertical-align: middle;
            user-select: none;
        }}
    </style>
    </head>
    <body>
    <div style="
        background-color: #ffffff;
        color: #111111;
        width: 100%;
        min-height: 750px;
        padding: 30px 40px;
        border: 1px solid #d3d3d3;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        font-size: 14px;
        line-height: 1.45;
        border-radius: 4px;
        box-sizing: border-box;
    ">
        <!-- Official Header with Emblem on Left, Title Centered -->
        <div style="position: relative; min-height: 60px; margin-bottom: 15px; display: flex; align-items: center;">
            {f'<img src="{KMUTT_LOGO_B64}" style="width: 62px; height: auto; position: absolute; left: 0; top: 0;" />' if KMUTT_LOGO_B64 else ''}
            <div style="width: 100%; text-align: center; font-size: 26px; font-weight: bold; letter-spacing: 1px; color: #000; line-height: 60px;">บันทึกข้อความ</div>
        </div>
        
        <!-- Document Metadata -->
        <div class="editable-box sec-1-box" contenteditable="true" title="📌 Section 1: คลิกแก้ไขส่วนงาน/โทรศัพท์" style="margin-bottom: 8px;">
            <span class="tag-badge" style="background:#e0f2fe; color:#0369a1;">📌 S1</span><span style="font-weight: bold;">ส่วนงาน:</span> {st.session_state.get('agency_name', 'ศูนย์สนับสนุนโครงการหลวงและโครงการพระราชดำริ โทร. 053-218618')}
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <div class="editable-box sec-1-box" contenteditable="true" title="📌 Section 1: คลิกแก้ไขเลขที่หนังสือ"><span class="tag-badge" style="background:#e0f2fe; color:#0369a1;">📌 S1</span><span style="font-weight: bold;">ที่:</span> {st.session_state.get('doc_number', '')}</div>
            <div class="editable-box sec-1-box" contenteditable="true" title="📌 Section 1: คลิกแก้ไขวันที่หนังสือ"><span class="tag-badge" style="background:#e0f2fe; color:#0369a1;">📌 S1</span><span style="font-weight: bold;">วันที่:</span> {st.session_state.get('doc_date', '')}</div>
        </div>
        <div class="editable-box sec-3-box" contenteditable="true" title="📝 Section 3: คลิกแก้ไขชื่อเรื่องโครงการ" style="margin-bottom: 8px;">
            <span class="tag-badge" style="background:#fef3c7; color:#b45309;">📝 S3</span><span style="font-weight: bold;">เรื่อง:</span> {st.session_state.get('project_title', '')}
        </div>
        <div class="editable-box sec-1-box" contenteditable="true" title="📌 Section 1: คลิกแก้ไขผู้รับหนังสือ (เรียน...)" style="margin-bottom: 12px;">
            <span class="tag-badge" style="background:#e0f2fe; color:#0369a1;">📌 S1</span><span style="font-weight: bold;">เรียน:</span> {st.session_state.get('recipient_title', 'ผู้อำนวยการสถาบันพัฒนาและฝึกอบรมโรงงานต้นแบบ')}
        </div>
        
        <hr style="border: none; border-top: 1.5px solid #333; margin: 10px 0 15px 0;" />
        
        <!-- Content Body -->
        <div class="editable-box sec-3-box" contenteditable="true" title="📝 Section 3: คลิกแก้ไขบริบทโครงการ (ย่อหน้าแรก)" style="text-indent: 40px; text-align: justify; margin-bottom: 10px;">
            <span class="tag-badge" style="background:#fef3c7; color:#b45309;">📝 S3</span>{st.session_state.get('project_context', '')}
        </div>
        <div class="editable-box sec-3-box" contenteditable="true" title="📝 Section 3: คลิกแก้ไขวัตถุประสงค์ (ย่อหน้าที่สอง)" style="text-indent: 40px; text-align: justify; margin-bottom: 10px;">
            <span class="tag-badge" style="background:#fef3c7; color:#b45309;">📝 S3</span>{st.session_state.get('project_objective', '')}
        </div>
        {p3_html_block}


        <!-- Budget Breakdown Table -->
        {table_block_html}

        <!-- Total Budget line -->
        <div class="editable-box sec-5-box" contenteditable="true" title="💰 Section 5: คลิกแก้ไขข้อความงบประมาณรวม" style="text-indent: 40px; margin-bottom: 10px; text-align: justify;">
            <span class="tag-badge" style="background:#fff7ed; color:#c2410c;">💰 S5</span>ในการนี้ข้าพเจ้าจึงใคร่ขออนุมัติดำเนินงาน{time_loc_phrase}พร้อมทั้งขออนุมัติค่าใช้จ่าย จำนวน <b>{formatted_amt}</b> บาท <b>{st.session_state.get('budget_text', '')}</b> (เบิกจ่ายจากรหัสงบประมาณ <b>{st.session_state.get('acc_code', '')}</b> {st.session_state.get('budget_source', '')})
        </div>


        <div class="editable-box sec-1-box" contenteditable="true" title="📌 Section 1: คลิกแก้ไขประโยคลงท้าย" style="text-indent: 40px; margin-top: 10px; margin-bottom: 15px;">
            <span class="tag-badge" style="background:#e0f2fe; color:#0369a1;">📌 S1</span>{st.session_state.get('closing_text', 'จึงเรียนมาเพื่อโปรดพิจารณาอนุมัติ')}
        </div>

        <!-- Requester Signature Area -->
        <div style="display: flex; justify-content: flex-end; margin-bottom: 20px;">
            <div class="editable-box sec-2-box" contenteditable="true" title="👤 Section 2: คลิกแก้ไขชื่อและตำแหน่งผู้ขออนุมัติ" style="text-align: center; width: 230px;">
                <div style="margin-bottom: 6px;">ลงชื่อ...................................................</div>
                <div style="font-weight: 500;"><span class="tag-badge" style="background:#fce7f3; color:#be185d;">👤 S2</span>{st.session_state.get('requester_name', '')}</div>
                <div style="color: #333; font-size: 13px;">{st.session_state.get('requester_position', '')}</div>
            </div>
        </div>

        <!-- Official Approval Signature Blocks (เห็นควรอนุมัติ vs อนุมัติ) -->
        <div style="display: flex; justify-content: space-between; margin-top: 15px; padding: 0 5px;">
            <!-- Left: เห็นควรอนุมัติ -->
            <div class="editable-box sec-2-box" contenteditable="true" title="👤 Section 2: คลิกแก้ไขผู้เห็นควรอนุมัติ" style="text-align: center; width: 45%;">
                <div style="font-weight: bold; margin-bottom: 10px;">เห็นควรอนุมัติ</div>
                <div style="margin-bottom: 6px;">ลงชื่อ...................................................</div>
                <div style="font-weight: 500;"><span class="tag-badge" style="background:#fce7f3; color:#be185d;">👤 S2</span>{st.session_state.get('approver_left_name', '(นายศเรนทร์ ฐปนางกูร)')}</div>
                <div style="font-size: 12px; color: #222; line-height: 1.3;">
                    {st.session_state.get('approver_left_pos', 'ผู้อำนวยการศูนย์ส่งเสริมและสนับสนุน มูลนิธิโครงการหลวงและโครงการตามพระราชดำริ')}
                </div>
            </div>

            <!-- Right: อนุมัติ -->
            <div class="editable-box sec-2-box" contenteditable="true" title="👤 Section 2: คลิกแก้ไขผู้อนุมัติ" style="text-align: center; width: 45%;">
                <div style="font-weight: bold; margin-bottom: 10px;">อนุมัติ</div>
                <div style="margin-bottom: 6px;">ลงชื่อ...................................................</div>
                <div style="font-weight: 500;"><span class="tag-badge" style="background:#fce7f3; color:#be185d;">👤 S2</span>{st.session_state.get('approver_right_name', '(ผศ.ดร.บุณยพัด สุภานิช)')}</div>
                <div style="font-size: 12px; color: #222; line-height: 1.3;">
                    {st.session_state.get('approver_right_pos', 'ผู้อำนวยการสถาบันพัฒนาและฝึกอบรมโรงงานต้นแบบ')}
                </div>
            </div>
        </div>

        <!-- Attachment 1: Dynamic Expense Breakdown Form Preview -->
        {expense_attachment_html}

        <!-- Attachment 2: Dynamic Schedule Block Preview -->
        {schedule_preview_html}
    </div>
    </body>
    </html>
    """).strip()

    components.html(a4_html, height=850, scrolling=True)



