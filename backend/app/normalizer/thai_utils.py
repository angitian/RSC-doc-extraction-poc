# -*- coding: utf-8 -*-
"""Thai date / baht text helpers (ported & hardened from the original app.py)."""
from __future__ import annotations

import re
from datetime import date, datetime

THAI_MONTHS = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
]
THAI_MONTHS_SHORT = [
    "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
]
THAI_MONTH_SET = set(THAI_MONTHS + THAI_MONTHS_SHORT)


def _month_index(month_str: str) -> int:
    """Return 1-12 for a Thai month name (full or short), else 0."""
    m = month_str.strip()
    for idx, name in enumerate(THAI_MONTHS, start=1):
        if m == name or name in m:
            return idx
    for idx, name in enumerate(THAI_MONTHS_SHORT, start=1):
        if m == name or name in m:
            return idx
    return 0


def to_ad_year(year: int) -> int:
    """Convert a Buddhist-era year to AD when it is clearly over 2400."""
    return year - 543 if year > 2400 else year


def parse_thai_date(date_str) -> date | None:
    """Parse a Thai date string to datetime.date.

    Accepts: '10 สิงหาคม 2569', '10 ส.ค. 69', '10/08/2569', '2026-08-10'.
    Returns None when parsing fails (caller decides fallback).
    """
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()

    # ISO YYYY-MM-DD
    iso = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None

    # DD/MM/YYYY
    slash = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", date_str)
    if slash:
        try:
            y = to_ad_year(int(slash.group(3)))
            return date(y, int(slash.group(2)), int(slash.group(1)))
        except ValueError:
            return None

    # '10 สิงหาคม 2569' | '10 ส.ค. 69' (year may be 2 or 4 digits)
    m = re.fullmatch(r"(\d{1,2})\s+([^\s\d]+)\s+(\d{2,4})", date_str)
    if m:
        month = _month_index(m.group(2))
        year_raw = int(m.group(3))
        if year_raw <= 99:
            # 2-digit year is Buddhist-era shorthand: 69 -> 2569 BE -> 2026 AD
            year = 1957 + year_raw
        else:
            year = to_ad_year(year_raw)
        try:
            return date(year, month, int(m.group(1)))
        except ValueError:
            return None

    # ISO with time component (e.g. 2026-08-10T00:00:00)
    iso_t = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
    if iso_t:
        try:
            return date(int(iso_t.group(1)), int(iso_t.group(2)), int(iso_t.group(3)))
        except ValueError:
            return None

    return None


def format_thai_date(d_obj: date | None, sep: str = "/", with_bauddha: bool = True) -> str:
    """Format date to DD/MM/YYYY (พ.ศ.) — e.g. '10/08/2569'."""
    if d_obj is None:
        d_obj = date.today()
    year = d_obj.year + 543 if with_bauddha else d_obj.year
    return f"{d_obj.day:02d}{sep}{d_obj.month:02d}{sep}{year}"


def iso_to_thai_date(iso_str: str) -> str:
    """'2026-08-10' -> '10/08/2569' (for web date inputs that expect BE)."""
    d = parse_thai_date(iso_str)
    return format_thai_date(d) if d else ""


# ---------------------------------------------------------------------------
# Thai baht text
# ---------------------------------------------------------------------------
_THAI_NUMS = ["ศูนย์", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
_THAI_UNITS = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน", "ล้าน"]


def _convert_group(n: int) -> str:
    if n == 0:
        return ""
    s = str(n)
    length = len(s)
    res: list[str] = []
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
                res.append(_THAI_NUMS[digit] + _THAI_UNITS[pos])
        elif pos == 6:
            res.append("ล้าน")
    return "".join(res)


def num_to_thai_baht(number_val) -> str:
    """Convert a number (str/int/float) to Thai baht text, e.g. 21200 -> 'สองหมื่นเอ็ดพันสองร้อยบาทถ้วน'."""
    try:
        raw = str(number_val).replace(",", "").strip()
        if not raw:
            return ""
        val = float(raw)
        if val == 0:
            return "ศูนย์บาทถ้วน"
    except (TypeError, ValueError):
        return ""

    parts = f"{val:.2f}".split(".")
    baht_part = int(parts[0])
    satang_part = int(parts[1])

    baht_text = ""
    if baht_part == 0:
        baht_text = "ศูนย์บาท"
    else:
        mil = baht_part // 1000000
        rem = baht_part % 1000000
        if mil > 0:
            baht_text += _convert_group(mil) + "ล้าน"
        baht_text += _convert_group(rem) + "บาท"

    satang_text = "ถ้วน" if satang_part == 0 else _convert_group(satang_part) + "สตางค์"
    return baht_text + satang_text


def parse_amount(text: str) -> float:
    """Extract a numeric amount from a Thai currency string, e.g. '12,000.50 บาท' -> 12000.5."""
    if not text:
        return 0.0
    m = re.search(r"[\d,]+(?:\.\d+)?", str(text))
    if not m:
        return 0.0
    return float(m.group(0).replace(",", ""))
