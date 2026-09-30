# -*- coding: utf-8 -*-
"""
Tests for per-section skip (เปิด/ปิดการกรอก ประมาณการค่าใช้จ่าย/กำหนดการ).

Usage:
    python tests/test_skip_sections.py

Covers:
  - skip_sections=["expense"] -> no expense mappings, schedule still filled
  - skip_sections=["schedule"] -> no schedule mappings, expense still filled
  - skip both -> no Section-5 actions at all
  - warnings: skip+data -> "ข้ามการกรอก..."; skip+no-data -> no "จะว่าง" warning
  - annex_pdf mode + skip -> no file_attach for the skipped section
  - skip wins over attach_sections
Exit code 0 on success.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from app.extraction.dispatcher import extract_file
from app.generators.field_mapper import build_field_mappings

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEMO_ANALYZE = os.path.join(ROOT, "2026-10 บันทึกข้อความขออนุมัติ วิเคราะห์สาร.docx")   # breakdown 7 rows, no schedule
MEMO_TRIP = os.path.join(ROOT, "2026-08 บันทึกข้อความขออนุมัติเดินทางติดตามงาน สค.69.docx")  # breakdown 4 + schedule 6 days

URL = "https://rsc-approval.kmutt.ac.th/approval"

_failures: list = []


def _check(name: str, cond: bool, detail: str = ""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        _failures.append(f"{name}: {detail}")


def _extract(path: str):
    return extract_file(open(path, "rb").read(), ".docx")[0]


def _expense_related(a) -> bool:
    s = a.selector or ""
    return "expense" in s or (a.meta or {}).get("scope_name") == "expense-document-source"


def _schedule_related(a) -> bool:
    s = a.selector or ""
    return "schedule" in s or (a.meta or {}).get("scope_name") == "schedule-document-source"


def _act_map(a):
    return (a.action, a.selector or "", a.label or "", (a.meta or {}).get("scope_name", ""))


def test_skip_expense():
    print("skip expense (memo วิเคราะห์สาร: มีค่าใช้จ่าย, ไม่มีกำหนดการ)")
    ext = _extract(MEMO_ANALYZE)
    mappings, warnings, info = build_field_mappings(ext, "full_table", URL, skip_sections=["expense"])
    exp = [a for a in mappings if _expense_related(a)]
    sched = [a for a in mappings if _schedule_related(a)]
    _check("ไม่มี action ของ expense เลย", not exp, str([_act_map(a) for a in exp[:4]]))
    _check("ไม่มี radio สร้างในระบบ/แนบ PDF ของ expense",
           not any((a.meta or {}).get("scope_name") == "expense-document-source" for a in mappings))
    _check("ยังมี schedule mapping (ปิดเฉพาะ expense)",
           len(sched) > 0 or any(a.selector and "generated-schedule" in a.selector for a in mappings),
           str(len(sched)))
    _check("warning ข้ามการกรอกตารางค่าใช้จ่าย", any("ข้ามการกรอกตารางค่าใช้จ่าย" in w for w in warnings), str(warnings))
    # schedule ไม่ได้ปิด + เอกสารไม่มีกำหนดการ -> ควรยังเตือน "จะว่าง" (ตรงพฤติกรรมเดิม)
    _check("schedule ที่ไม่ได้ปิดยังเตือน 'จะว่าง'",
           any("ตารางกำหนดการจะว่าง" in w for w in warnings), str(warnings))


def test_skip_schedule():
    print("skip schedule (memo เดินทาง สค.69: มีทั้งสอง)")
    ext = _extract(MEMO_TRIP)
    mappings, warnings, info = build_field_mappings(ext, "full_table", URL, skip_sections=["schedule"])
    sched = [a for a in mappings if _schedule_related(a)]
    _check("ไม่มี action ของ schedule เลย", not sched, str([_act_map(a) for a in sched[:4]]))
    _check("ยังมี expense mapping", any(_expense_related(a) for a in mappings))
    _check("warning ข้ามการกรอกตารางกำหนดการ", any("ข้ามการกรอกตารางกำหนดการ" in w for w in warnings), str(warnings))
    _check("ยังไม่มี warning 'ค่าใช้จ่ายจะว่าง'", not any("ตารางค่าใช้จ่ายจะว่าง" in w for w in warnings), str(warnings))


def test_skip_both():
    print("skip both sections")
    ext = _extract(MEMO_TRIP)
    mappings, warnings, info = build_field_mappings(ext, "full_table", URL, skip_sections=["expense", "schedule"])
    sec5 = [a for a in mappings if _expense_related(a) or _schedule_related(a)]
    _check("ไม่มี Section-5 action เลย", not sec5, str([_act_map(a) for a in sec5[:6]]))
    _check("Section 1-4 ยังกรอก (ข้อมูลโครงการ)", any(a.selector == "#project-document-number" for a in mappings))
    _check("warning ทั้งสอง section", sum("ข้ามการกรอกตาราง" in w for w in warnings) == 2, str(warnings))


def test_skip_no_data_no_empty_warning():
    print("skip section ที่เอกสารไม่มีข้อมูล (วิเคราะห์สาร: ไม่มีกำหนดการ)")
    ext = _extract(MEMO_ANALYZE)
    _, warnings, _ = build_field_mappings(ext, "full_table", URL, skip_sections=["schedule"])
    _check("ไม่มี warning 'ตารางกำหนดการจะว่าง'", not any("ตารางกำหนดการจะว่าง" in w for w in warnings), str(warnings))
    # เอกสารมีค่าใช้จ่ายแต่ปิด -> ต้องมี warning ข้าม
    _, warnings2, _ = build_field_mappings(ext, "full_table", URL, skip_sections=["expense"])
    _check("มี warning ข้ามค่าใช้จ่าย", any("ข้ามการกรอกตารางค่าใช้จ่าย" in w for w in warnings2), str(warnings2))


def test_annex_pdf_skip():
    print("annex_pdf + skip expense (ยังต้องมี file_attach ของ schedule)")
    ext = _extract(MEMO_TRIP)
    mappings, _, _ = build_field_mappings(ext, "annex_pdf", URL, skip_sections=["expense"])
    attach_scopes = [(a.meta or {}).get("scope_name") for a in mappings if a.action == "file_attach"]
    _check("ไม่มี file_attach ของ expense", "expense-document-source" not in attach_scopes, str(attach_scopes))
    _check("ยังมี file_attach ของ schedule", "schedule-document-source" in attach_scopes, str(attach_scopes))
    _check("ไม่มี radio click ของ expense",
           not any((a.meta or {}).get("scope_name") == "expense-document-source" for a in mappings))


def test_skip_wins_over_attach():
    print("skip ชนะ attach (ลาก PDF ของ section ที่ปิด -> ไม่แนบ)")
    ext = _extract(MEMO_TRIP)
    mappings, _, _ = build_field_mappings(ext, "full_table", URL,
                                          attach_sections=["expense"], skip_sections=["expense"])
    exp = [a for a in mappings if _expense_related(a)]
    _check("ไม่มี action expense ทั้งที่ระบุ attach", not exp, str([_act_map(a) for a in exp[:4]]))
    # schedule ยังกรอกอัตโนมัติตามปกติ
    _check("schedule ยังกรอกปกติ", any(_schedule_related(a) for a in mappings))


def test_default_no_skip_regression():
    print("default (ไม่ส่ง skip) = พฤติกรรมเดิม ยังมีทั้งสอง section")
    ext = _extract(MEMO_TRIP)
    mappings, warnings, _ = build_field_mappings(ext, "full_table", URL)
    _check("ยังมี expense mapping", any(_expense_related(a) for a in mappings))
    _check("ยังมี schedule mapping", any(_schedule_related(a) for a in mappings))
    _check("ไม่มี warning ข้าม", not any("ข้ามการกรอกตาราง" in w for w in warnings), str(warnings))


def main() -> int:
    test_skip_expense()
    test_skip_schedule()
    test_skip_both()
    test_skip_no_data_no_empty_warning()
    test_annex_pdf_skip()
    test_skip_wins_over_attach()
    test_default_no_skip_regression()
    print()
    if _failures:
        print(f"FAILED ({len(_failures)}):")
        for f in _failures:
            print("  -", f)
        return 1
    print("ALL SKIP-SECTIONS ASSERTIONS PASSED ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
