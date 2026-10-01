# วิธีเพิ่มเอกสาร/ฟอร์มใหม่ (case-by-case)

ระบบออกแบบให้เพิ่ม "เอกสารรูปแบบใหม่ + ฟอร์มเว็บใหม่" ได้โดยไม่ต้องแก้โค้ดหลัก
แต่ละคู่ใช้ไฟล์ 1-2 ไฟล์:

```
doc_type (จากเอกสาร)          form_type (จากหน้าเว็บ)
     │                              │
conference_extractor.py  ──►  rsc_conference.json
(โค้ดสกัดเฉพาะ)             (profile: ฟิลด์ + mapping)
```

## ฟอร์ม hardcode แบบ template-anchored (วิธียอดนิยมใหม่)

ฟอร์มที่มีโครงสร้างตายตัว (เช่น บันทึกข้อความ RSC) **ไม่ต้องเขียน extractor** —
วาง blank template + manifest แล้วระบุ rule สกัด:

```
backend/templates/
  บันทึกข้อความ_rsc_blank.docx   ← ฟอร์มต้นฉบับ (ช่องตัวแปร mark ด้วย {{key}})
  rsc_memo.json                  ← manifest (anchors + field rules)
        │
        ▼
template_registry.try_extract() ──► template_engine.extract_rules()
(เลือก template ที่ match ดีสุด)    (ตัดคำ hardcode ออก เหลือค่าตัวแปร)
        │
        ▼
   extracted dict เดิม ──► rollup / field_mappings (ไม่ต้องแก้)
```

**ขั้นตอนเพิ่มฟอร์ม hardcode ใหม่:**

1. **วาง blank .docx** ใน `backend/templates/` — ข้อความตายตัวของฟอร์ม = hardcode;
   ช่องที่กรอกได้ = `{{field_key}}` (ทำ marker นี้ให้ครบทุก key ใน rules)
2. **สร้าง manifest** `<template_id>.json`:
   - `required_anchors` = วลีที่ฟอร์มนี้ต้องมีเสมอ (ใช้แยกชนิดเอกสาร;
     อย่าใช้วลีร่วมกับฟอร์มอื่น เช่น "ประมาณการค่าใช้จ่าย" มีทั้ง conference และ memo)
   - `optional_anchors` + `optional_threshold` = คะแนน coverage สำหรับตรวจจับ
   - `defaults` = ค่าคงที่ของฟอร์ม (เช่น `action_verb`)
   - `fields` = field rules:
     - `line_regex` — regex กับแต่ละย่อหน้า (named groups → keys)
     - `line_startswith` — ย่อหน้าที่ขึ้นต้นด้วยคำที่กำหนด แล้ว regex
     - `fulltext_regex` — regex กับข้อความทั้งฉบับ
     - `prefix_cut` — ตัดคำนำหน้าตายตัวหน้าข้อความบรรยาย (start + cut_through)
     - `special` — `requester_signature` / `requester_position` (ชื่อในวงเล็บหลัง "จึงเรียนมา")
   - ตัวเลือก `only_if_empty: true` = fallback (ไม่ทับค่าที่ capture ได้แล้ว)
3. **generate template** ด้วยสคริปต์ (เช่น `tests/make_memo_template.py`) —
   commit ไฟล์ .docx ที่สร้างด้วย
4. **ทดสอบ** `python tests/test_template_engine.py` (เพิ่ม assertions ของฟอร์มใหม่)

**กติกาการเขียน rule:**
- anchor ภาษาไทยต้องระบุขอบเขตชัด; อย่าใช้ token-diff แบบคลุมเครือ
- `ณ` ต้องใช้ `(?<!\S)ณ(?!\S)` — ตัวอักษร "ณ" ซ่อนในคำไทย (คุณภาพ/คุณ/ณัฐ)
- ค่าที่เป็นข้อความบรรยายยาว (เช่น context) ให้เก็บทั้งช่วง อย่าตัดกลางคำ
- field ที่ portal ต้องกรอกเองทั้งย่อหน้า (เช่น "ที่มาและบริบทของโครงการ" ที่ไม่ auto สร้าง prefix "ตามที่…")
  ให้ใช้ `line_regex` จับทั้งบรรทัด (`^ตามที่(?P<key>.*)$`) — อย่าตัดคำนำหน้าทิ้ง
- field ที่ portal auto สร้างส่วนนำหน้าให้ (เช่น objective "ในการนี้…") ให้คงการตัดส่วนนั้นด้วย prefix_cut/line_startswith
- field ที่ไม่รู้จัก/ambiguous → ปล่อยว่าง + warning (ห้ามเดาค่า)

## กรณี 1: เอกสารรูปแบบใหม่ (ต้องมี extractor ใหม่)

1. **สร้าง `backend/app/extraction/<ชื่อ>_extractor.py`** — สกัดจากเอกสารแล้วคืน dict ปกติ
   (key ภาษาไทยตาราง: breakdown/schedule ใช้ชุดเดียวกัน; ฟิลด์ใหม่ใช้ key อังกฤษ)
2. **ลงทะเบียนใน `dispatcher.py`**:
   ```python
   REGISTRY["<doc_type>"] = {"extensions": {".docx"}, "extractor": extract_<ชื่อ>}
   ```
3. **เพิ่ม keyword ใน `classifier.py`** `TYPE_RULES["<doc_type>"]` + label
4. ทดสอบ: `python tests/smoke_test.py <ไฟล์ตัวอย่าง>`

## กรณี 2: ฟอร์มเว็บใหม่ (ส่วนใหญ่ใช้ profile JSON ล้วน)

สร้าง `backend/app/profiles/<form_id>.json`:

```json
{
  "profile_id": "rsc_xxx",
  "name": "ชื่อฟอร์ม",
  "form_type": "<doc_type ที่คู่กัน>",
  "url_patterns": ["คำใน URL"],
  "dom_signature": ["id-เด่น-1", "id-เด่น-2"],
  "fields": [
    { "target": "#input-id", "label": "ป้ายภาษาไทย", "from": "key_in_extracted",
      "transform": "strip_commas", "type": "text" },
    { "target": "", "label": "ฟิลด์ที่ React เปลี่ยน ID", "from": "project_title" },
    { "gen": "conference_expense_number", "label": "2. ค่าเบี้ยเลี้ยง (บาท)", "from": "per_diem" }
  ]
}
```

**กติกา:**
- `target` = CSS selector (optional) / `label` = ป้ายไทย (ตัวชี้หลักสำรอง — ควรมีเสมอ)
- `from` = key ใน extracted dict / `transform`: `strip_commas` | `number`
- `skip_if_value_present: true` = ไม่ทับฟิลด์ที่เว็บเติมเอง (ชื่อ/ตำแหน่ง/ACC)
- `gen` ที่มีอยู่: `conference_select_travel_type`, `conference_select_region`,
  `conference_select_acc`, `conference_select_participant_role`,
  `conference_expense_number`, `conference_travelers`
- ฟอร์มซับซ้อน (ตาราง dynamic) → ใช้ `"builder": "rsc_main"` อ้าง Python builder ที่มีอยู่

**วิธีหา `dom_signature`:** เปิดหน้าเว็บ → คลิก "🔍 จับฟอร์ม" ใน extension → ดู ID เด่น
(ควรเลือก ID ที่ semantic เช่น `conference-*`, `project-*` ไม่ใช่ `input-123` ที่ React สุ่ม)

## DOCX / Excel template

- DOCX template มาตรฐาน: `backend/templates/*.docx` + script
  `backend/tests/make_conference_template.py` (แก้ตาม convention)
- Excel template: ระบบสร้างให้อัตโนมัติจาก profile ที่ `/api/v1/templates/<profile_id>`
  (คอลัมน์ A = ป้ายฟิลด์, B = ค่า; section "รายชื่อผู้ร่วมเดินทาง" = ตาราง 6 คอลัมน์)

## Checklist เวลาเพิ่ม

- [ ] extractor คืนค่า dict ครบ (breakdown/schedule ใช้ format เดิม)
- [ ] classifier จับ doc_type ได้ (conf > 0.6)
- [ ] profile resolve จาก dom_signature (ทดสอบกับ HTML จริง)
- [ ] `python tests/smoke_test.py <ไฟล์>` ผ่าน
- [ ] ทดสอบ label→element กับหน้าจริง (extension "จับฟอร์ม" + log)
