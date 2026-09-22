# -*- coding: utf-8 -*-
"""Document type classification with a heuristic confidence score."""
from __future__ import annotations

from typing import Any, Dict, Tuple

# Keyword buckets per document type
TYPE_RULES: Dict[str, Dict[str, Any]] = {
    "conference_attendance": {
        "keywords": [
            "แบบขออนุมัติเข้าร่วมประชุม", "hr-sd-s-f13", "เข้าร่วมประชุม/อบรม/สัมมนา",
            "เข้าร่วมประชุม", "เข้าร่วมสัมมนา", "เข้าร่วมฝึกอบรม", "จัดโดย",
            "ประมาณการค่าใช้จ่ายประกอบด้วย", "ค่าลงทะเบียน", "เงินชดเชยพาหนะส่วนตัว",
        ],
        "label": "ขออนุมัติเข้าร่วมประชุม/อบรม/สัมมนา",
    },
    "travel_request": {
        "keywords": [
            "เดินทาง", "ติดตามงาน", "ไปราชการ", "เบี้ยเลี้ยง", "ค่าเช่าที่พัก", "ค่าเบี้ยเลี้ยง",
            "ผู้เดินทาง", "กำหนดการเดินทาง", "ค่าพาหนะ", "ค่าโดยสาร", "เดินทางไป",
        ],
        "label": "คำขออนุมัติเดินทาง",
    },
    "expense_settlement": {
        "keywords": [
            "เบิกจ่าย", "รายงานผลการใช้จ่าย", "ค่าใช้จ่าย", "ใบเสร็จ", "บิล", "ขอยืมเงิน",
            "รายงานการเงิน", "เคลียร์ริ่ง", "ค่าจัดซื้อ", "จ่ายแล้ว",
        ],
        "label": "รายงาน/ขอเบิกค่าใช้จ่าย",
    },
    "work_report": {
        "keywords": [
            "รายงานผลการดำเนินงาน", "รายงานความก้าวหน้า", "ผลการปฏิบัติงาน", "สรุปผลโครงการ",
            "รายงานสรุป", "รายงานการจัด", "เสร็จสิ้น",
        ],
        "label": "รายงานผลการดำเนินงาน",
    },
}


def classify_document(extracted: Dict[str, Any]) -> Tuple[str, float]:
    """Classify doc_type and estimate confidence from keyword hits.

    Returns (doc_type, confidence) — confidence 0.0..1.0.
    """
    text = " ".join(
        str(extracted.get(k, ""))
        for k in ("project_title", "project_context", "project_objective", "action_details", "schedule_text")
    ).lower()

    scores: Dict[str, int] = {}
    for doc_type, rule in TYPE_RULES.items():
        hits = sum(1 for kw in rule["keywords"] if kw in text)
        scores[doc_type] = hits

    best = max(scores, key=scores.get)
    best_hits = scores[best]
    total_hits = sum(scores.values())

    if best_hits == 0:
        return "travel_request", 0.35  # most common memo type; low confidence

    # Confidence: share of hits + base
    confidence = min(0.95, 0.5 + (best_hits / max(total_hits, 1)) * 0.45)
    return best, round(confidence, 2)
