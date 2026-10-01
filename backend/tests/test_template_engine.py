# -*- coding: utf-8 -*-
"""
Template-anchored extraction engine tests (executable script — no pytest dep).

Usage:
    python tests/test_template_engine.py

Covers:
  - rsc_memo template detection + field extraction on the 4 real sample memos
    (+ sample_memo.docx)
  - conference_attendance regression (must NOT be swallowed by rsc_memo)
  - explicit doc_type override precedence
  - engine internals: normalization, detection scoring, schedule date parsing,
    prefix_cut
Exit code 0 on success.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from app.extraction.dispatcher import extract_file
from app.extraction.template_engine import (
    _parse_schedule_dates,
    detect,
    extract_rules,
    normalize_text,
    postprocess,
)
from app.extraction.template_registry import get_spec, SPECS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MEMO_ANALYZE = os.path.join(ROOT, "2026-10 บันทึกข้อความขออนุมัติ วิเคราะห์สาร.docx")
MEMO_ELECTRIC = os.path.join(ROOT, "2026-02 บันทึกข้อความขออนุมัติ ค่าไฟฟ้า แม่แฮ กุมภาพันธ์.docx")
MEMO_TRIP = os.path.join(ROOT, "2026-08 บันทึกข้อความขออนุมัติเดินทางติดตามงาน สค.69.docx")
MEMO_IEC = os.path.join(ROOT, "2025-07 ขออนุมัติ จ้างเหมา ค่าจ้างเหมาประกอบเครื่องต้นแบบ IEC.docx")
SAMPLE_MEMO = os.path.join(ROOT, "sample_memo.docx")
CONFERENCE = os.path.join(ROOT, "ฟอร์มขออนุมัติเข้าร่วมประชุม.docx")


def _extract(path: str):
    raw = open(path, "rb").read()
    return extract_file(raw, ".docx")


def _read_doc(path: str):
    from app.extraction.template_engine import doc_paragraphs
    return doc_paragraphs(open(path, "rb").read())


def _check(name: str, cond: bool, detail: str = ""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        _failures.append(f"{name}: {detail}")


_failures: list = []


# ---------------------------------------------------------------------------
# Engine internals
# ---------------------------------------------------------------------------
def test_internals():
    print("internals")
    _check("normalize collapses tabs/spaces", normalize_text("ส่วนงาน\tA   B") == "ส่วนงาน A B")
    _check("normalize strips", normalize_text("  x  ") == "x")

    spec = get_spec("rsc_memo")
    _check("rsc_memo manifest registered", spec is not None)
    _check("templates dir has manifest + docx",
           os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "templates", "บันทึกข้อความ_rsc_blank.docx")))

    paras = ["ส่วนงาน ศูนย์ A โทร 053-218618", "ที่ อว. 7608.8/ วันที่ 1 ตุลาคม 2569",
             "เรื่อง X", "ตามที่ ...", "ในการนี้ ...", "ข้าพเจ้า ...", "วิศวกร",
             "ขอถัวเฉลี่ยทุกรายการ", "จึงเรียนมาเพื่อพิจารณา", "อื่นๆ"]
    score = detect(spec, paras)
    _check("detect full coverage = 1.0", score == 1.0, str(score))
    # Missing one required anchor → 0.0 regardless of optional coverage
    _check("detect missing required anchor = 0.0",
           detect(spec, ["ตามที่", "ในการนี้", "ข้าพเจ้า", "วิศวกร"]) == 0.0)
    _check("detect rejects conference-like doc",
           detect(spec, ["แบบขออนุมัติเข้าร่วมประชุม", "วันที่ 1 ธันวาคม 2568", "เรียน ผอ."]) == 0.0)

    d1 = _parse_schedule_dates("1-31 ตุลาคม 2569")
    _check("range 1-31 -> start/end",
           len(d1) == 2 and d1[0].day == 1 and d1[1].day == 31, str(d1))
    d2 = _parse_schedule_dates("3, 10, 14, 17, 21 และ 27 สิงหาคม 2569")
    _check("day list keeps all 6 days", len(d2) == 6 and d2[-1].day == 27, str([d.day for d in d2]))
    d3 = _parse_schedule_dates("15 สิงหาคม 2569 ถึงวันที่ 20 สิงหาคม 2569")
    _check("wordy range 15..20", len(d3) == 2 and d3[0].day == 15 and d3[1].day == 20,
           str([d.day for d in d3]))
    d4 = _parse_schedule_dates("")
    _check("empty schedule -> []", d4 == [])
    # tolerant: ช่วงวันที่แทรกในข้อความปน (หน่วยกลุ่มเป้าหมาย "โรงเรือน" + ข้อความต่อท้าย)
    d5 = _parse_schedule_dates("1-31 ตุลาคม 2569 โดยมีกลุ่มเป้าหมายประกอบด้วย จำนวน 1 โรงเรือน ในการซ่อมแซมหลังคาโรงเรือน")
    _check("tolerant range in polluted text",
           len(d5) == 2 and d5[0].day == 1 and d5[1].day == 31, str(d5))
    # เลขปีต้องไม่ถูกจับเป็นวัน ("2569 ถึง" -> 69 ไม่ได้)
    d6 = _parse_schedule_dates("15 สิงหาคม 2569 ถึงวันที่ 20 สิงหาคม 2569")
    _check("wordy range still works (no year false-positive)",
           len(d6) == 2 and d6[0].day == 15 and d6[1].day == 20, str(d6))

    ext = postprocess({"doc_date": "1 ตุลาคม 2569", "doc_number": "7608.8/",
                       "budget_amount": "23,350", "location_name": "ศูนย์ X ต.บาง อ.เมือง จ.เชียงใหม่",
                       "province_name": "เชียงใหม่", "schedule_text": "1-31 ตุลาคม 2569"},
                      {"action_verb": "ดำเนินงาน"})
    _check("postprocess ISO date AD", ext["doc_date_iso"] == "2026-10-01", ext["doc_date_iso"])
    _check("postprocess budget_year", ext["budget_year"] == "69")
    _check("postprocess tail completed", ext["doc_number_tail"] == "7608.8/69")
    _check("postprocess amount stripped", ext["budget_amount"] == "23350")
    _check("postprocess location cleaned",
           ext["location_name"] == "ศูนย์ X" and ext["location_province"] == "ณ ศูนย์ X จ.เชียงใหม่")
    _check("postprocess schedule range",
           ext["start_date_iso"] == "2026-10-01" and ext["end_date_iso"] == "2026-10-31")


# ---------------------------------------------------------------------------
# Real documents
# ---------------------------------------------------------------------------
def test_memo_analyze():
    print("memo วิเคราะห์สาร")
    ext, doc_type, conf = _extract(MEMO_ANALYZE)
    _check("doc_type rsc_memo", doc_type == "rsc_memo", doc_type)
    _check("conf >= 0.4", conf >= 0.4, str(conf))
    _check("agency", "ศูนย์ส่งเสริม" in ext.get("agency_name", ""), ext.get("agency_name", "")[:40])
    _check("phone", ext.get("contact_phone") == "053-218618", ext.get("contact_phone", ""))
    _check("doc_number_tail", ext.get("doc_number_tail") == "7608.8/69", ext.get("doc_number_tail", ""))
    _check("doc_date", ext.get("doc_date") == "1 ตุลาคม 2569", ext.get("doc_date", ""))
    _check("doc_date_iso AD", ext.get("doc_date_iso") == "2026-10-01", ext.get("doc_date_iso", ""))
    _check("budget_year", ext.get("budget_year") == "69")
    _check("title cleaned",
           ext.get("project_title") == "ค่าใช้จ่ายในการวิเคราะห์สารพฤกษเคมีในผักสลัดและวิเคราะห์คุณภาพน้ำ",
           ext.get("project_title", "")[:60])
    _check("requester", ext.get("requester_name") == "นายรณกร อำพันธ์ศรี", ext.get("requester_name", ""))
    _check("position", ext.get("requester_position") == "วิศวกร", ext.get("requester_position", ""))
    _check("location", ext.get("location_name") == "มหาวิทยาลัยเทคโนโลยีราชมงคลล้านนา",
           ext.get("location_name", ""))
    _check("province", ext.get("province_name") == "เชียงใหม่", ext.get("province_name", ""))
    _check("action_details", "วิเคราะห์สาร" in ext.get("action_details", ""), ext.get("action_details", "")[:60])
    _check("objective", "เพื่อให้สามารถวิเคราะห์สารเคมี" in ext.get("project_objective", ""),
           ext.get("project_objective", "")[:60])
    ctx = ext.get("project_context", "")
    # portal ต้องกรอก prefix เอง (ไม่ auto สร้าง) → ต้องเก็บเต็มย่อหน้าตั้งแต่ "ตามที่"
    _check("context keeps full ตามที่ paragraph",
           ctx.startswith("ตามที่ศูนย์ส่งเสริมและสนับสนุนมูลนิธิโครงการหลวง")
           and "ในด้านการคุณภาพผลผลิตผักสลัด" in ctx,
           ctx[:80])
    _check("objective still cuts ในการนี้ prefix",
           not ext.get("project_objective", "").startswith("ในการนี้"),
           ext.get("project_objective", "")[:40])
    _check("schedule", ext.get("schedule_text") == "1-31 ตุลาคม 2569", ext.get("schedule_text", ""))
    _check("schedule range", ext.get("start_date_iso") == "2026-10-01" and ext.get("end_date_iso") == "2026-10-31",
           f"{ext.get('start_date_iso')}..{ext.get('end_date_iso')}")
    _check("budget_amount", ext.get("budget_amount") == "23350", ext.get("budget_amount", ""))
    _check("budget_text", "สองหมื่นสามพัน" in ext.get("budget_text", ""), ext.get("budget_text", "")[:30])
    _check("budget_source", "4-KTB" in ext.get("budget_source", ""), ext.get("budget_source", ""))
    _check("closing cut hardcode", ext.get("closing_text") == "เพื่อขออนุมัติค่าใช้จ่ายจากโครงการหลวง",
           ext.get("closing_text", ""))
    _check("breakdown 7 rows", len(ext.get("breakdown") or []) == 7, str(len(ext.get("breakdown") or [])))
    _check("no schedule section", not ext.get("schedule_activities"))
    # Rollup total honors the explicit budget amount even when rows sum differs
    from app.normalizer.expense_rollup import extract_budget_rollup
    rollup = extract_budget_rollup(ext, ext.get("breakdown") or [])
    _check("rollup total 23350", rollup["total_amount"] == 23350.0, str(rollup["total_amount"]))


def test_memo_electric():
    print("memo ค่าไฟฟ้า ก.พ.")
    ext, doc_type, conf = _extract(MEMO_ELECTRIC)
    _check("doc_type rsc_memo", doc_type == "rsc_memo", doc_type)
    _check("doc_date_iso", ext.get("doc_date_iso") == "2026-04-09", ext.get("doc_date_iso", ""))
    _check("budget keeps decimals", ext.get("budget_amount") == "415.59", ext.get("budget_amount", ""))
    _check("requester from signature", ext.get("requester_name") == "นายรณกร อำพันธ์ศรี",
           ext.get("requester_name", ""))
    _check("position", ext.get("requester_position") == "วิศวกร", ext.get("requester_position", ""))
    _check("location from เรื่อง clause", ext.get("location_name") == "ศูนย์พัฒนาโครงการหลวงแม่แฮ",
           ext.get("location_name", ""))
    _check("province", ext.get("province_name") == "เชียงใหม่", ext.get("province_name", ""))
    _check("no breakdown section -> empty", not ext.get("breakdown"))
    _check("no schedule -> empty", not ext.get("schedule_activities"))
    _check("context keeps full ตามที่ paragraph",
           ext.get("project_context", "").startswith("ตามที่ศูนย์ส่งเสริม")
           and "วิจัยและพัฒนาการผลิตสตรอว์เบอร์รี่" in ext.get("project_context", ""),
           ext.get("project_context", "")[:80])
    # ไม่เติม field ว่างจากการเดา
    _check("no fabricated schedule_text", not ext.get("schedule_text"))


def test_memo_trip():
    print("memo เดินทาง สค.69")
    ext, doc_type, conf = _extract(MEMO_TRIP)
    _check("doc_type rsc_memo", doc_type == "rsc_memo", doc_type)
    _check("schedule list", ext.get("schedule_text") == "3, 10, 14, 17, 21 และ 27 สิงหาคม 2569",
           ext.get("schedule_text", ""))
    _check("schedule start/end", ext.get("start_date_iso") == "2026-08-03" and ext.get("end_date_iso") == "2026-08-27",
           f"{ext.get('start_date_iso')}..{ext.get('end_date_iso')}")
    _check("breakdown 4 rows", len(ext.get("breakdown") or []) == 4, str(len(ext.get("breakdown") or [])))
    days = ext.get("schedule_activities") or []
    _check("schedule 6 days", len(days) == 6, str(len(days)))
    _check("first day 5 items", len(days[0].get("items") or []) == 5, str(len(days[0].get("items") or [])))
    _check("budget", ext.get("budget_amount") == "21200", ext.get("budget_amount", ""))
    _check("requester", ext.get("requester_name") == "นายรณกร อำพันธ์ศรี", ext.get("requester_name", ""))
    _check("location", "ศูนย์พัฒนาโครงการหลวงแม่แฮ" in ext.get("location_name", ""), ext.get("location_name", ""))
    _check("context keeps full ตามที่ paragraph",
           ext.get("project_context", "").startswith("ตามที่ศูนย์ส่งเสริม")
           and "วิจัยด้านโรงเรือนควบคุมสภาพแวดล้อม" in ext.get("project_context", ""),
           ext.get("project_context", "")[:80])


def test_memo_iec():
    print("memo จ้างเหมา IEC")
    ext, doc_type, conf = _extract(MEMO_IEC)
    _check("doc_type rsc_memo", doc_type == "rsc_memo", doc_type)
    _check("doc_date_iso", ext.get("doc_date_iso") == "2025-08-05", ext.get("doc_date_iso", ""))
    _check("budget", ext.get("budget_amount") == "90000", ext.get("budget_amount", ""))
    _check("breakdown 3 rows (no body/attachment dup)", len(ext.get("breakdown") or []) == 3,
           str(len(ext.get("breakdown") or [])))
    _check("title", ext.get("project_title", "").startswith("ค่าใช้จ่ายในการประกอบเครื่องต้นแบบ"),
           ext.get("project_title", "")[:50])
    _check("requester", ext.get("requester_name") == "นายรณกร อำพันธ์ศรี", ext.get("requester_name", ""))
    _check("อ้างถึง line does not break extraction", ext.get("doc_number_tail") == "7608.8/68",
           ext.get("doc_number_tail", ""))
    _check("context keeps full ตามที่ (ได้รับงบประมาณ variant)",
           ext.get("project_context", "").startswith("ตามที่ศูนย์ส่งเสริม")
           and "ได้รับงบประมาณ" in ext.get("project_context", ""),
           ext.get("project_context", "")[:80])


def test_sample_memo():
    print("sample_memo")
    ext, doc_type, conf = _extract(SAMPLE_MEMO)
    _check("doc_type rsc_memo", doc_type == "rsc_memo", doc_type)
    _check("full tail", ext.get("doc_number_tail") == "7608.8.1/1234/69", ext.get("doc_number_tail", ""))
    _check("doc_seq_num", ext.get("doc_seq_num") == "1234", ext.get("doc_seq_num", ""))
    _check("requester from split signature line",
           ext.get("requester_name") == "นายรณกร อำพันธ์ศรี" and ext.get("requester_position") == "วิศวกร",
           f"{ext.get('requester_name')} / {ext.get('requester_position')}")
    _check("budget", ext.get("budget_amount") == "21200", ext.get("budget_amount", ""))


def test_memo_reenhouse_style():
    """Synthetic regression for the 'ซ่อมหลังคาโรงเรือน' memo: target-group unit
    'โรงเรือน' + trailing text after the clause must NOT swallow schedule_text —
    'ระหว่างวันที่ 1-31 ตุลาคม 2569' ต้องถูกสกัดเป็นวันที่ได้ (portal ไม่ auto กรอก)."""
    print("memo synthetic (โรงเรือน + ข้อความต่อท้าย)")
    spec = get_spec("rsc_memo")
    paras = [
        "ส่วนงาน ศูนย์ส่งเสริมและสนับสนุนมูลนิธิโครงการหลวงและโครงการตามพระราชดำริ โทร 053-218618",
        "ที่ อว. 7608.8/ วันที่ 30 กันยายน 2569",
        "เรื่อง ขออนุมัติค่าใช้จ่ายในการปรับปรุงโรงเรือนกระตุ้นตาดอกสตรอว์เบอร์รี ศูนย์พัฒนาโครงการหลวงแม่แฮ",
        "ตามที่ศูนย์ส่งเสริมและสนับสนุนมูลนิธิโครงการหลวงและโครงการตามพระราชดำริ ได้ดำเนินงาน ร่วมกับมูลนิธิโครงการหลวง",
        "ดังนั้น เพื่อให้โรงเรือนกระตุ้นตาดอกสามารถใช้งานได้ตามปกติ ข้าพเจ้า นายรณกร อำพันธ์ศรี ตำแหน่งวิศวกร "
        "ขออนุมัติดำเนินงาน ค่าใช้จ่ายในการปรับปรุงโรงเรือนกระตุ้นตาดอกสตรอว์เบอร์รี ศูนย์พัฒนาโครงการหลวงแม่แฮ "
        "ณ ศูนย์พัฒนาโครงการหลวงแม่แฮ จังหวัดเชียงใหม่ ระหว่างวันที่ 1-31 ตุลาคม 2569 "
        "โดยมีกลุ่มเป้าหมายประกอบด้วย จำนวน 1 โรงเรือน ในการซ่อมแซมหลังคาโรงเรือน",
        "ในการนี้ข้าพเจ้าจึงใคร่ขออนุมัติดำเนินงานตามวัน เวลา และสถานที่ดังกล่าว "
        "พร้อมทั้งขออนุมัติค่าใช้จ่าย จำนวน 1,600 บาท (หนึ่งพันหกร้อยบาทถ้วน) จากงบประมาณ 4-KTB พัฒนาชุมชน คกล-69",
        "จึงเรียนมาเพื่อโปรดพิจารณาอนุมัติดำเนินงานและอนุมัติงบประมาณ",
    ]
    raw, warnings = extract_rules(spec, paras)
    _check("schedule_text clean (no tail pollution)",
           raw.get("schedule_text") == "1-31 ตุลาคม 2569", raw.get("schedule_text", ""))
    _check("target unit โรงเรือน captured",
           raw.get("target_group_unit") == "โรงเรือน", raw.get("target_group_unit", ""))
    _check("target qty 1", raw.get("target_group_quantity") == "1", raw.get("target_group_quantity", ""))
    ext = postprocess(raw, spec.get("defaults") or {})
    _check("start date from ระหว่างวันที่",
           ext.get("start_date_iso") == "2026-10-01", ext.get("start_date_iso", ""))
    _check("end date from ระหว่างวันที่",
           ext.get("end_date_iso") == "2026-10-31", ext.get("end_date_iso", ""))


def test_malformed_rules_do_not_crash():
    print("malformed manifest resilience")
    paras = ["เรื่อง X", "ส่วนงาน A"]
    raw, warnings = extract_rules({"fields": [
        {"key": "bad", "type": "line_regex", "pattern": "([unclosed"},
        {"type": "unknown_type", "key": "x"},
    ]}, paras)
    _check("bad pattern -> warning not crash", any("pattern" in w for w in warnings), str(warnings))
    _check("unknown type -> warning not crash", any("ไม่รู้จัก" in w for w in warnings), str(warnings))
    _check("no ghost values from bad rules", raw == {})
    _check("unknown template id -> None", get_spec("does_not_exist") is None)


def test_conference_regression():
    print("conference regression")
    ext, doc_type, conf = _extract(CONFERENCE)
    _check("stays conference_attendance", doc_type == "conference_attendance", doc_type)
    _check("conf reasonable", conf >= 0.6, str(conf))
    _check("conference budget", ext.get("budget_amount") == "6600", ext.get("budget_amount", ""))
    _check("conference requester", ext.get("requester_name") == "นายรณกร อำพันธ์ศรี", ext.get("requester_name", ""))
    _check("conference event title", "อนุกรรมการ" in ext.get("event_title", ""), ext.get("event_title", "")[:40])
    _check("conference vehicle details", (ext.get("vehicle_details") or "").count("\n") >= 1)
    _check("conference schedule", len(ext.get("schedule_activities") or []) >= 1)


def test_override():
    print("explicit override")
    raw = open(MEMO_ANALYZE, "rb").read()
    ext, doc_type, conf = extract_file(raw, ".docx", doc_type_override="conference_attendance")
    _check("override forces conference_attendance", doc_type == "conference_attendance", doc_type)
    ext2, doc_type2, conf2 = extract_file(raw, ".docx", doc_type_override="rsc_memo")
    _check("override rsc_memo", doc_type2 == "rsc_memo", doc_type2)
    _check("override rsc_memo extracts", ext2.get("budget_amount") == "23350", ext2.get("budget_amount", ""))


def main() -> int:
    print(f"loaded templates: {[s['template_id'] for s in SPECS]}")
    test_internals()
    test_memo_analyze()
    test_memo_electric()
    test_memo_trip()
    test_memo_iec()
    test_sample_memo()
    test_memo_reenhouse_style()
    test_malformed_rules_do_not_crash()
    test_conference_regression()
    test_override()
    print()
    if _failures:
        print(f"FAILED ({len(_failures)}):")
        for f in _failures:
            print("  -", f)
        return 1
    print("ALL TEMPLATE ENGINE ASSERTIONS PASSED ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
