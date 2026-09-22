# วิธีเพิ่มเอกสาร/ฟอร์มใหม่ (case-by-case)

ระบบออกแบบให้เพิ่ม "เอกสารรูปแบบใหม่ + ฟอร์มเว็บใหม่" ได้โดยไม่ต้องแก้โค้ดหลัก
แต่ละคู่ใช้ไฟล์ 1-2 ไฟล์:

```
doc_type (จากเอกสาร)          form_type (จากหน้าเว็บ)
     │                              │
conference_extractor.py  ──►  rsc_conference.json
(โค้ดสกัดเฉพาะ)             (profile: ฟิลด์ + mapping)
```

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
