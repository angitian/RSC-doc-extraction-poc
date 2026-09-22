# -*- coding: utf-8 -*-
"""
Government expense categorization & totals.

Categorizes extracted breakdown rows into standard Thai government budget
categories so the review card and Excel/PDF outputs are meaningful even when
the source document uses free-form item names.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .thai_utils import parse_amount

# Ordered rules: (category_key, category_label, [keywords])
# The first matching rule wins; keywords are matched as substrings (lowercased).
CATEGORY_RULES: List[tuple] = [
    ("per_diem", "ค่าเบี้ยเลี้ยง", ["เบี้ยเลี้ยง", "เบี้ยประชุม", "ค่าเบี้ย"]),
    ("accommodation", "ค่าที่พัก", ["ที่พัก", "โรงแรม", "ค่าห้อง", "ห้องพัก"]),
    ("fuel", "ค่าน้ำมันเชื้อเพลิง", ["น้ำมัน", "เชื้อเพลิง", "แก๊ส", "ก๊าซ", "น้ำมันดีเซล", "น้ำมันเบนซิน", "gasoline", "diesel"]),
    ("vehicle", "ค่าเช่ายานพาหนะ", ["ค่าเช่ารถ", "เช่ารถ", "พาหนะ", "รถตู้", "รถบัส", "รถยนต์", "รถโดยสาร", "ค่าจ้างเหมารถ", "เหมารถ", "ค่าโดยสาร", "ค่ารถไฟ", "เครื่องบิน", "ค่าตั๋ว", "ค่าเดินทาง", "ค่าระวาง"]),
    ("transport_allowance", "ค่าเดินทาง (เหมาจ่าย)", ["ค่าเดินทาง"]),
    ("materials", "ค่าวัสดุ/อุปกรณ์", ["วัสดุ", "อุปกรณ์", "เอกสาร", "เครื่องเขียน", "กระดาษ", "หมึก", "ซอง", "ครุภัณฑ์", "สื่อ", "ป้าย", "ของรางวัล", "ของที่ระลึก"]),
    ("labor", "ค่าจ้าง/ค่าตอบแทน", ["ค่าจ้าง", "ค่าตอบแทน", "วิทยากร", "ค่าสอน", "ค่าแรง", "เหมาประกอบ", "จ้างเหมา", "ค่าบริการ"]),
    ("food", "ค่าอาหาร/เครื่องดื่ม", ["อาหาร", "เครื่องดื่ม", "อาหารว่าง", "อาหารกลางวัน", "อาหารเช้า", "อาหารเย็น", "กาแฟ", "น้ำดื่ม"]),
    ("venue", "ค่าเช่าสถานที่", ["ค่าเช่าห้อง", "เช่าห้อง", "สถานที่", "ห้องประชุม", "สถานที่จัด", "ค่าเช่าสถานที่"]),
    ("communication", "ค่าโทรศัพท์/สื่อสาร", ["โทรศัพท์", "อินเทอร์เน็ต", "สื่อสาร", "ไปรษณีย์", "ค่าส่ง"]),
    ("fees", "ค่าธรรมเนียม/อื่นๆ", ["ค่าธรรมเนียม", "ค่าแรกเข้า", "ค่าสมัคร", "ภาษี", "ค่าประกัน", "ค่าปรับ"]),
]

FALLBACK_LABEL = "อื่นๆ"


def categorize_item(item_name: str) -> tuple:
    """Return (category_key, category_label) for a free-form expense item."""
    text = (item_name or "").lower()
    if not text:
        return ("other", FALLBACK_LABEL)
    for key, label, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw in text:
                return (key, label)
    return ("other", FALLBACK_LABEL)


def rollup_expenses(breakdown: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate breakdown rows into categories and compute the total.

    Args:
        breakdown: list of {"รายการ", "รายละเอียด", "จำนวนเงิน (บาท)"}

    Returns:
        {"expense_summary": {label: float}, "total_amount": float, "rows": [...]}
    """
    summary: Dict[str, float] = {}
    categorized: List[Dict[str, Any]] = []
    total = 0.0

    for row in breakdown or []:
        item_name = str(row.get("รายการ", "")).strip()
        amount = parse_amount(row.get("จำนวนเงิน (บาท)", 0))
        key, label = categorize_item(item_name)

        summary[label] = summary.get(label, 0.0) + amount
        total += amount
        categorized.append({
            "รายการ": item_name,
            "รายละเอียด": str(row.get("รายละเอียด", "")).strip(),
            "จำนวนเงิน (บาท)": amount,
            "หมวดหมู่": label,
        })

    # Round to 2 decimals to avoid float drift
    summary = {k: round(v, 2) for k, v in sorted(summary.items(), key=lambda kv: -kv[1])}
    return {
        "expense_summary": summary,
        "total_amount": round(total, 2),
        "rows": categorized,
    }


def extract_budget_rollup(metadata: Dict[str, Any], breakdown: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Best-effort total: prefer the explicit budget_amount line, else sum rows."""
    result = rollup_expenses(breakdown)
    explicit = parse_amount(metadata.get("budget_amount"))
    if explicit > 0 and (result["total_amount"] == 0 or abs(explicit - result["total_amount"]) > explicit * 0.01):
        # Keep both signals; use explicit as the authoritative total but keep the
        # categorized detail for the review card.
        result["total_amount"] = explicit
    return result


def strip_amount(text: str) -> str:
    """Remove the 'บาท' suffix / parentheses from an amount cell like '12,000.00'."""
    return re.sub(r"[\sบาท฿( )]", "", str(text or "")).strip()
