# สรุปสเปคและเทคโนโลยี — โปรเจค "Doc to Smart Data" (RSC Administrative Productivity Suite)

> เอกสารสรุปสถาปัตยกรรม เทคโนโลยี และกลไกการสกัด/จัดการเอกสารราชการไทยของโปรเจคนี้
> ใช้เป็นข้อมูลตั้งต้นสำหรับออกแบบระบบ **Smart Doc** ใหม่ ได้แก่
> (1) สกัดเอกสาร (2) วิเคราะห์ template จาก docx (3) สร้างฟอร์ม (4) เรนเดอร์เอกสารให้เหมือนต้นฉบับ

---

## 1. ภาพรวมระบบ (Spec)

| หัวข้อ | รายละเอียด |
|---|---|
| ชื่อระบบ | RSC Administrative Productivity Suite ("Doc to Smart Data") |
| เป้าหมาย | สกัดข้อมูลจากเอกสารราชการไทย (`.docx` / `.pdf` / `.xlsx`) → Structured Data ชุดเดียว → ส่งออก 3 ทิศทาง (Tri-Action Hub) |
| กลุ่มผู้ใช้ | นักวิจัย/เจ้าหน้าที่หน่วยงานราชการ (KMUTT RSC — ศูนย์ส่งเสริมฯ มูลนิธิโครงการหลวง) |
| สถานะ | ใช้งานได้จริง (v2.1) — มี legacy PoC (Streamlit `app.py`) เก็บเป็น reference |

**Tri-Action Hub — ส่งออก 3 ทิศทาง:**

1. 🚀 **ยิงข้อมูลลงฟอร์มเว็บราชการ** — Backend ส่ง `field_mappings` (Dynamic DOM Instructions) ให้ Content Script กรอกฟอร์มให้อัตโนมัติ
2. 📊 **ดาวน์โหลด Excel / คัดลอก TSV** — workbook 3 sheets (ข้อมูลโครงการ / ประมาณการค่าใช้จ่าย / กำหนดการ) + TSV สำหรับวางใน Excel
3. 📄 **PDF เอกสารแนบ** — สร้าง "ประมาณการค่าใช้จ่ายและกำหนดการ" ด้วย fpdf2 + ฟอนต์ไทย Sarabun

**หลักการสำคัญ (Dynamic Mapping Paradigm):**

- Extension **ไม่ hard-code DOM Selector** — Backend ส่งโครงสร้างข้อมูลพร้อม `field_mappings` (Selectors + Actions + ป้ายภาษาไทย) ตาม `target_url`
- เว็บเปลี่ยนโครงสร้าง / เพิ่มเอกสารประเภทใหม่ → อัปเดตที่ Backend เท่านั้น ไม่ต้องแตะ Extension
- Content Script มี **label-based fallback** — ถ้า CSS selector หาไม่เจอ (React auto-ID เช่น `input-94` เปลี่ยนทุก build) จะหา element จากป้ายภาษาไทย (`label[for]` / label ครอบ / aria-label / placeholder)

---

## 2. สถาปัตยกรรม

```
[Chrome Extension MV3 — Side Panel]  ──POST /api/v1/extract──▶  [FastAPI Backend (Docker)]
        │  Review Card + Tri-Action Hub                            ├─ python-docx / PyMuPDF (สกัด)
        ▼                                                          ├─ Template Registry (ฟอร์ม hardcode)
[Content Script: field_mappings]                                   ├─ Category Rollup (หมวดราชการ)
        │  set_value / click / set_select / file_attach            └─ field_mapper (dynamic selectors)
        ▼
[เว็บราชการ Portal]
```

**Flow การทำงานปัจจุบัน:**

```
user ร่าง docx  →  สกัด (backend)  →  ตรวจ/แก้ (Editable Review Card ใน side panel)
     →  ยิงฟอร์มเว็บอัตโนมัติ / ดาวน์โหลด Excel / แนบ PDF  →  admin ตรวจตามระบบเดิม
```

**โครงสร้างโฟลเดอร์:**

```
backend/          → FastAPI (main.py, app/models.py, extraction/, normalizer/, generators/, profiles/, templates/, Dockerfile)
extension/        → Chrome Extension MV3 (manifest.json, sidepanel/, scripts/content.js, background.js)
docs/             → API.md (contract), HOW_TO_ADD_NEW_FORM.md, DEPLOY.md, ROADMAP.md, PLAN_*.md, PRIVACY.md
app.py            → (legacy) Streamlit PoC เดิม — เก็บเป็น reference (มี generate_docx_bytes)
app_v1.py         → (legacy) PoC รอบแรก
extension_v1/     → (legacy) Extension v1 แบบ hard-coded selector
*.docx / *.pdf    → เอกสารราชการตัวอย่างจริง (บันทึกข้อความขออนุมัติ หลายฉบับ)
```

---

## 3. เทคโนโลยี (Tech Stack)

| ชั้น | เทคโนโลยี | หมายเหตุ |
|---|---|---|
| Backend | Python 3.10+, FastAPI, Pydantic v2 | stateless, ไม่มี DB |
| การสกัด DOCX | python-docx ≥ 1.1.0 | ย่อหน้า + ตาราง |
| การสกัด PDF | PyMuPDF ≥ 1.24.0 | `get_text` + `find_tables` |
| การสกัด XLSX | openpyxl ≥ 3.1.0 | sheet "ฟอร์ม" (label→value) |
| PDF output | fpdf2 ≥ 2.7.0 | + Sarabun-Regular.ttf (ฟอนต์ไทย) |
| Excel output | openpyxl | 3 sheets + ฟอนต์ Sarabun |
| Extension | Chrome Manifest V3, Side Panel, `chrome.scripting` | inject on demand |
| DOM automation | native-setter + dispatch input/change/blur, MutationObserver, DataTransfer | รองรับ React/Vue |
| Deploy | Docker (port 7860/8000/`$PORT`) | Render Free / Cloud Run / HF Spaces |
| Data (แผนต่อยอด) | Postgres — Supabase / Neon / Render | ยังไม่มีในระบบปัจจุบัน |

---

## 4. API (contract v2.1)

| Endpoint | คำอธิบาย |
|---|---|
| `GET /api/v1/health` | เช็คสถานะบริการ |
| `POST /api/v1/extract` | multipart: `file` (.docx/.pdf/.xlsx ≤20MB), `mode` (`full_table` \| `annex_pdf`), `target_url`, `doc_type` (override), `page_snapshot` (JSON สำหรับ DOM signature), `outputs` (excel\|pdf), `attach_sections`/`skip_sections` (expense\|schedule) → `ExtractionResponse` |
| `GET /api/v1/forms` | รายการฟอร์ม (profile) + field schema — ใช้กับ Quick Form |
| `POST /api/v1/fill` | Quick Form — สร้าง `field_mappings` จากค่าที่กรอกเอง (ไม่ต้องมีเอกสาร) |
| `GET /api/v1/templates/{profile_id}` | ดาวน์โหลด Excel template (.xlsx) — คอลัมน์ A=label, B=value |

**`ExtractionResponse` (โครงสร้างหลัก):**

```json
{
  "doc_type": "travel_request",
  "confidence": 0.84,
  "metadata": { "...": "ทุกฟิลด์ที่สกัดได้จากเอกสาร" },
  "expense_summary": { "ค่าเช่ายานพาหนะ": 9000.0 },
  "total_amount": 21200.0,
  "raw_tables": { "breakdown": [[...]], "schedule": [[...]] },
  "form_type": "travel_request",
  "profile_id": "rsc_main",
  "profile_name": "...",
  "page_match_confidence": 1.0,
  "editable_fields": [{ "key", "label", "type", "value" }],
  "field_mappings": [ { DOMAction... } ],
  "pdf_annex_base64": "...", "pdf_annex_filename": "ประมาณการค่าใช้จ่ายและกำหนดการ.pdf",
  "excel_filled_base64": "...", "excel_filled_filename": "ข้อมูลโครงการและค่าใช้จ่าย.xlsx",
  "summary": { "doc_type_label", "project_name", "traveler", "date_range", "total_amount", "categories" },
  "warnings": []
}
```

---

## 5. การสกัดเอกสาร (Extraction Pipeline)

### 5.1 Dispatcher — ลำดับการเลือก extractor (`dispatcher.py`)

```
extract_file(bytes, ext, doc_type_override)
  1. doc_type_override  →  REGISTRY extractor หรือ template spec ตาม id
  2. auto: template_registry.try_extract()   ← ฟอร์ม hardcode ชนะเสมอ (.docx)
  3. fallback: generic memo pipeline + classify_document()
```

| doc_type | extensions | extractor |
|---|---|---|
| `conference_attendance` | .docx | `conference_extractor.py` (ฟอร์มตายตัว HR-SD-S-F13) |
| memo (default) | .docx / .pdf / .xlsx | `docx_extractor` / `pdf_extractor` / `excel_extractor` → `text_pipeline` |

### 5.2 แหล่งข้อมูลแต่ละประเภท

| ไฟล์ | กลไก |
|---|---|
| DOCX | python-docx → ย่อหน้า (แยก `<w:br/>` เป็นบรรทัดใหม่) + ตาราง → `extract_from_text()` |
| PDF | PyMuPDF `page.get_text("text")` + best-effort `find_tables()` → `extract_from_text()` |
| XLSX | openpyxl อ่าน sheet `"ฟอร์ม"` — คอลัมน์ A = ป้ายฟิลด์, B = ค่า; section `"รายชื่อผู้ร่วมเดินทาง"` = ตาราง 6 คอลัมน์ |

### 5.3 ฟิลด์ที่สกัดได้ (text_pipeline ~40 ฟิลด์)

| กลุ่ม | ฟิลด์ |
|---|---|
| ต้นทาง | `agency_name` (ส่วนงาน), `contact_phone` (โทร) |
| เลขที่หนังสือ | `doc_number` (`อว 7608.8.1/xx/69`), `doc_number_tail`, `doc_seq_num` |
| วันที่ | `doc_date` (ไทย), `doc_date_iso`, `budget_year` (พ.ศ. 2 หลัก) |
| ผู้รับ/ปิด | `recipient_title` (เรียน — ใช้ตัวสุดท้าย = สายอนุมัติ), `closing_text` (จึงเรียนมา) |
| เรื่อง/เนื้อหา | `project_title`, `project_context` (เต็มย่อหน้า "ตามที่…" — ไม่ตัด prefix), `project_objective` (ตัด "ในการนี้…" เพราะ portal auto สร้าง), `action_verb`, `action_details` |
| กลุ่มเป้าหมาย | `target_group_name`, `target_group_quantity`, `target_group_unit` |
| สถานที่ | `location_name`, `province_name`, `location_province` (ณ … จ.…) |
| เวลา | `schedule_text`, `start_date_iso`, `end_date_iso` |
| งบประมาณ | `budget_amount`, `budget_text` (ตัวอักษร — auto จาก `num_to_thai_baht`) |
| ลายเซ็น | `requester_name`, `requester_position`, `approver_left_name/pos`, `approver_right_name/pos` |
| ตาราง | `breakdown` (ค่าใช้จ่าย), `schedule_activities` (กำหนดการ) |
| เฉพาะ conference | `department`, `faculty`, `event_title`, `organizer`, `traveler_count`, `travelers[]`, `expense_categories{}`, `vehicle_details`, `approval_chain[]`, `event_type` |

### 5.4 ตารางค่าใช้จ่าย — 3 กลยุทธ์ (กลยุทธ์แรกที่ได้ผลชนะ)

1. `_parse_attachment_breakdown` — section "ประมาณการค่าใช้จ่าย" (บรรทัด tab-separated)
2. `_parse_doc_tables` — native tables ของ docx/pdf
3. `_parse_plaintext_breakdown` — บรรทัดที่ลงท้าย `<จำนวนเงิน> บาท` ในเนื้อหา

### 5.5 Normalizer

| ฟังก์ชัน | รายละเอียด |
|---|---|
| `parse_thai_date` | รองรับ `10 สิงหาคม 2569` / `10 ส.ค. 69` / `10/08/2569` / ISO — แปลง พ.ศ.→ค.ศ. อัตโนมัติ |
| `num_to_thai_baht` | ตัวเลข → ตัวอักษรไทย (`สองหมื่นเอ็ดพันสองร้อยบาทถ้วน`) |
| `parse_amount` | `12,000.50 บาท` → 12000.5 |
| `extract_budget_rollup` | รวมยอด + จัดหมวด — ยอดรวมแบบ explicit (วงเงิน) ชนะผลรวมแถว ถ้าต่างกัน >1% |

**หมวดค่าใช้จ่ายราชการ 11 หมวด (expense_rollup) — keyword substring match:**

`ค่าเบี้ยเลี้ยง` · `ค่าที่พัก` · `ค่าน้ำมันเชื้อเพลิง` · `ค่าเช่ายานพาหนะ` · `ค่าเดินทาง (เหมาจ่าย)` · `ค่าวัสดุ/อุปกรณ์` · `ค่าจ้าง/ค่าตอบแทน` · `ค่าอาหาร/เครื่องดื่ม` · `ค่าเช่าสถานที่` · `ค่าโทรศัพท์/สื่อสาร` · `ค่าธรรมเนียม/อื่นๆ`

### 5.6 Classifier (`classifier.py`)

Keyword buckets 4 ประเภท + confidence:

| doc_type | keywords ตัวอย่าง |
|---|---|
| `conference_attendance` | แบบขออนุมัติเข้าร่วมประชุม, hr-sd-s-f13, ค่าลงทะเบียน, เงินชดเชยพาหนะส่วนตัว |
| `travel_request` | เดินทาง, ติดตามงาน, ไปราชการ, เบี้ยเลี้ยง, ค่าที่พัก, กำหนดการเดินทาง |
| `expense_settlement` | เบิกจ่าย, รายงานผลการใช้จ่าย, ใบเสร็จ, ขอยืมเงิน |
| `work_report` | รายงานผลการดำเนินงาน, สรุปผลโครงการ, เสร็จสิ้น |

Confidence = `0.5 + (สัดส่วน hits) * 0.45` (cap 0.95) — ไม่มี hits → default `travel_request` 0.35

---

## 6. การวิเคราะห์ Template จาก DOCX (Template-anchored Extraction)

### 6.1 แนวคิด

ฟอร์มที่โครงสร้างตายตัว **ไม่ต้องเขียน extractor** — วาง blank template + manifest แล้วระบุ rule สกัด:

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

### 6.2 องค์ประกอบของ Manifest (`rsc_memo.json`)

```json
{
  "template_id": "rsc_memo",
  "label": "บันทึกข้อความขออนุมัติดำเนินงาน/งบประมาณ (ศูนย์ส่งเสริมฯ RSC)",
  "docx": "บันทึกข้อความ_rsc_blank.docx",
  "required_anchors": ["ส่วนงาน", "ที่ อว", "เรื่อง", "จึงเรียนมา"],
  "optional_anchors": ["โทร", "วันที่", "ตามที่", "ในการนี้", "ขอถัวเฉลี่ย", "ข้าพเจ้า", "วิศวกร"],
  "optional_threshold": 0.4,
  "defaults": { "action_verb": "ดำเนินงาน", "target_group_name": "ผู้เข้าร่วม", "target_group_quantity": "1", "target_group_unit": "คน" },
  "fields": [ ... ]
}
```

### 6.3 Rule Types (5 แบบ)

| type | กลไก | ตัวอย่าง |
|---|---|---|
| `line_regex` | regex กับทีละย่อหน้า (named groups → keys) | `^ส่วนงาน\s+(?P<agency_name>.+?)\s+โทร[:.]?\s*(?P<contact_phone>[0-9...])$` |
| `line_startswith` | ย่อหน้าที่ขึ้นต้นด้วยคำที่กำหนด แล้ว regex | `^เรื่อง\s*[:：]?\s*(?P<project_title>.+)$` |
| `fulltext_regex` | regex กับข้อความทั้งฉบับ (joined) | `(?<!\S)ณ(?!\S)\s*(?P<location_name>...)\s*(?:จ\.|จังหวัด)\s*(?P<province_name>...)` |
| `prefix_cut` | ตัดคำนำหน้าตายตัวหน้าข้อความบรรยาย (start + cut_through) | `start: "หัวเรื่อง"`, `cut_through: ["คำเชื่อม"]` |
| `special` | handler พิเศษ | `requester_signature` (ชื่อในวงเล็บหลัง "จึงเรียนมา"), `requester_position` |

ตัวเลือกเพิ่ม: `only_if_empty: true` = fallback (ไม่ทับค่าที่ capture ได้แล้ว)

### 6.4 Detection & Integrity

- **`detect()`**: ต้องมี `required_anchors` ครบทุกตัว (ไม่ครบ = 0.0) → คะแนน = coverage ของ `optional_anchors` → ผ่าน threshold → เลือก best match
- **`_validate_markers()`**: ตรวจว่า key ทุกตัวใน rules มี `{{key}}` อยู่ใน blank template จริง (soft check — พิมพ์ warning ถ้าไม่ครบ)
- **Bad manifest ถูกข้ามตอน load** — ไม่ทำให้ server ล้ม
- **Post-match sanity:** เอกสารที่ match ต้องมีอย่างน้อย `project_title` หรือ `doc_date` — ไม่งั้นถือเป็น false positive

### 6.5 ข้อควรระวัง (lesson learned จากกติกาเขียน rule)

- Anchor ภาษาไทยต้องระบุขอบเขตชัด; อย่าใช้ token-diff แบบคลุมเครือ
- `ณ` ต้องใช้ `(?<!\S)ณ(?!\S)` — ตัวอักษร "ณ" ซ่อนอยู่ในคำไทยทั่วไป (คุณภาพ/คุณ/ณัฐ)
- ค่าที่เป็นข้อความบรรยายยาว (context) ให้เก็บทั้งช่วง อย่าตัดกลางคำ
- field ที่ไม่รู้จัก/ambiguous → ปล่อยว่าง + warning (ห้ามเดาค่า)

> ⚠️ **ข้อจำกัดสำคัญ:** ปัจจุบัน template analysis **ไม่ใช่อัตโนมัติ** — ต้องมีคนเขียน `{{key}}` marker ใน docx (ด้วยสคริปต์ `make_memo_template.py`) + เขียน regex rules ใน manifest เองต่อฟอร์ม (ตอนนี้มี manifest แค่ 1 ตัว: `rsc_memo`)

---

## 7. การสร้างฟอร์ม (Form Profiles + Field Mappings)

### 7.1 Profile Registry (`app/profiles/*.json`)

| profile_id | ฟอร์ม | ลักษณะ |
|---|---|---|
| `rsc_main` | บันทึกข้อความ (ฟอร์มหลัก) | ซับซ้อน — ใช้ **Python builder** (`_build_rsc_mappings`) ตาราง dynamic + โหมด PDF |
| `rsc_conference` | ขออนุมัติเข้าร่วมประชุม/อบรม/สัมมนา | **declarative JSON fields** — 20+ ฟิลด์ + gen functions |

**การ resolve ฟอร์ม** (`resolve_profile`):

1. `page_snapshot` (DOM signature จากปุ่ม "จับฟอร์ม") — ถ้า match > 0.6 ชนะ
2. `url_patterns` (substring ใน URL)

### 7.2 DOMAction — คำสั่งที่ Content Script รองรับ

| action | ความหมาย |
|---|---|
| `set_value` | ตั้งค่า input/textarea/date/number — native setter + dispatch input/change/blur (React/Vue ครบ) |
| `set_select` | เลือก `<option>` โดย value หรือ text containment (fuzzy) |
| `set_radio` | คลิก radio ที่ตรง value ใน name group เดียวกัน |
| `click` | คลิก element แรก |
| `click_button` | คลิกปุ่มจากข้อความ (`:has()` ใช้ scope container ได้) + `meta.retry` คลิกซ้ำถ้าแถวไม่ render |
| `ensure_click` | self-heal — คลิกเพิ่มแถวเฉพาะเมื่อ verify_selector ยังไม่มี (sweep ไม่เพิ่มซ้ำ) |
| `file_attach` | inject File ผ่าน DataTransfer — scoped ตาม radio group (`meta.scope_name`) + fallback `input[type=file]` / `input[accept*=pdf]` + accumulate หลายไฟล์ |
| `wait` | หน่วงเวลา `delay_ms` |

**ฟิลด์เสริมของ action:**

- `label` (ป้ายไทย) — ตัวชี้หลักสำรองเมื่อ selector พัง (React auto-ID เปลี่ยนทุก build)
- `key` — metadata key → Side Panel ใช้แทนค่าจาก Editable Review Card ก่อนยิง
- `skip_if_value_present` — ไม่ทับฟิลด์ที่เว็บเติมเอง (ชื่อ/ตำแหน่ง/ACC)
- `index` / `repeat` / `delay_ms` / `meta.stable_ms` (รอ React settle) / `meta.candidates` (fallback selectors)

### 7.3 Generator functions (สำหรับ field พิเศษใน profile conference)

`conference_select_travel_type` (event_type mapping) · `conference_select_region` · `conference_select_acc` (ACC/ปีงบประมาณ) · `conference_select_participant_role` (presenter/attendee) · `conference_expense_number` (6 หมวด) · `conference_travelers` (เพิ่มแถวรายชื่อ)

---

## 8. การเรนเดอร์เอกสาร — สถานะปัจจุบัน (จุดอ่อนหลัก)

| ทาง | ไฟล์ | ลักษณะ | เหมือนต้นฉบับ? |
|---|---|---|---|
| PDF แนบ | `pdf_generator.py` (fpdf2 + Sarabun) | หัวเรื่อง + ข้อมูลโครงการ + ตารางค่าใช้จ่าย/กำหนดการ + บล็อกลายเซ็น | ❌ layout มาตรฐานเขียนตายตัว — ไม่ใช่สำเนาต้นฉบับ |
| DOCX | `generate_docx_bytes()` ใน legacy `app.py` (python-docx) | สร้าง docx ใหม่จาก scratch (หัวตาราง 3 คอลัมน์ + logo + ข้อความ) | ❌ สูญเสียตาราง/ฟอนต์/ระยะห่าง/รูปแบบเดิม |
| Excel | `excel_generator.py` (openpyxl) | workbook 3 sheets + ฟอนต์ไทย + รวมยอด | ✅ (ไม่ใช่การเรนเดอร์เอกสารราชการ) |
| Web form | Extension content script | กรอกฟอร์มเว็บราชการจริง | ✅ (เป็นการกรอกฟอร์ม ไม่ใช่การเรนเดอร์เอกสาร) |

**สิ่งที่ยังไม่มีในระบบ:**

- ❌ DOCX round-trip — เติมค่าลงต้นฉบับแล้วบันทึกเป็นไฟล์ใหม่
- ❌ การ preserve layout เดิม (ตาราง/ย่อหน้า/run formatting/header/footer/page setup)
- ❌ การวิเคราะห์โครงสร้าง docx อัตโนมัติ (paragraph/table/run/style) เพื่อสร้าง template
- ❌ การสร้าง form schema อัตโนมัติจาก template

---

## 9. Gap → สิ่งที่ระบบ "Smart Doc" ใหม่ต้องออกแบบเพิ่ม

สำหรับเป้าหมาย: *สกัดเอกสาร + วิเคราะห์ template จาก docx + สร้างฟอร์ม + เรนเดอร์เอกสารให้เหมือนต้นฉบับ*

### 9.1 วิเคราะห์ template docx อัตโนมัติ

| ความสามารถ | แนวทาง |
|---|---|
| เปรียบเทียบ blank ↔ filled | diff โครงสร้าง (paragraph/table/cell sequence) — ตำแหน่งที่ต่างกัน = ช่องตัวแปร |
| จับตำแหน่งตัวแปร | แยกเป็น paragraph / run / table cell / inline (ใน run เดียวกัน) |
| แยก boilerplate vs variable | token frequency ข้ามเอกสารหลายฉบับ (คำที่ปรากฏทุกฉบับ = boilerplate), regex ไทย (วันที่/จำนวนเงิน/ชื่อ) |
| สร้าง manifest อัตโนมัติ | generate `required_anchors` + field rules จากผลวิเคราะห์ (หรือแบบกึ่งอัตโนมัติให้คนยืนยัน) |

### 9.2 เรนเดอร์เอกสารให้เหมือนต้นฉบับ

| แนวทาง | ข้อดี | ข้อเสีย |
|---|---|---|
| **template-fill (docxtpl / python-docx merge)** | preserve layout เดิม 100% (ตาราง/ฟอนต์/header/footer/page setup) | ต้องมี template ที่ดี; placeholder ซับซ้อน (ตารางซ้ำ) ต้องใช้ block ภาษา |
| **แก้ XML โดยตรง (python-docx + lxml)** | ควบคุมละเอียด ทำงานกับ structure เดิม | เทคนิคสูง ใช้เวลา |
| **Render เป็น PDF จาก layout เดิม** | ตรงกับที่ส่งราชการ | ต้อง map style → PDF engine (fpdf2/reportlab) เอง |
| **HTML/CSS render** (แปลง docx → HTML) | แก้/แสดงผลง่าย (Preview) | ความเที่ยงตรงของ layout ต่ำลง |

### 9.3 สร้างฟอร์มจาก template

- สร้าง field schema อัตโนมัติจาก `{{key}}` + type inference (date/number/select/textarea) → ป้อนเข้า profile JSON
- ผูก field → ตำแหน่ง render ใน template (สำหรับ round-trip)

### 9.4 สิ่งที่ reuse ได้ 100% จากโปรเจคนี้

- ✅ `text_pipeline.py` + normalizer (วันที่ไทย/ตัวเลข/บาทตัวอักษร) + expense rollup
- ✅ `template_engine.py` rule engine (line_regex/line_startswith/fulltext_regex/prefix_cut/special) + postprocess
- ✅ `template_registry.py` — detect/registry/integrity check paradigm
- ✅ Profile + field_mapper paradigm + DOMAction executor (ถ้าระบบใหม่ยังยิงฟอร์มเว็บ)
- ✅ Classifier (keyword bucket) — ขยาย bucket ตามเอกสารราชการชนิดใหม่

---

## 10. แผนต่อยอดที่วางไว้แล้วในโปรเจค (docs/ROADMAP.md)

| แผน | เนื้อหา | สถานะ |
|---|---|---|
| A — Paperless Portal | login + admin แก้ผลสกัด + DB + dashboard — แยก service ใหม่ (extraction reuse) | ยังไม่ implement |
| B — Reconciliation Engine | กระทบยอดเงินยืมวิจัย (Excel → Knapsack auto-match) | ยังไม่ implement |
| C — Concurrency/Hardening | `run_in_threadpool`, rate limit, shared token | ยังไม่ implement |
| D — On-Premise Server | เครื่องในสำนักงาน (Ryzen 7/32GB) + OCR + IoT dashboard + Docker Compose | spec ครบ |

**ข้อสรุปเชิงสถาปัตยกรรม (สำคัญจาก ROADMAP):**
1. Extraction engine (extraction/normalizer/generators/profiles) **ใช้ซ้ำได้ 100%** — ระบบใหม่ไม่ต้องแก้
2. ระบบใหม่ควรเป็น **service แยก** ไม่ต่อใน backend เดิม — กันเสี่ยงระบบที่ใช้งานได้อยู่
3. ต้องมี **DB persistent** (free tier ของ Render ไม่พอ)
4. Extension เป็นตัวเชื่อม — แก้เล็กน้อย

---

## 11. ไฟล์อ้างอิงในโปรเจค

| ไฟล์ | เนื้อหา |
|---|---|
| `backend/main.py` | FastAPI endpoints (/extract, /fill, /forms, /templates) |
| `backend/app/models.py` | Pydantic schemas — `DOMAction`, `ExtractionResponse` |
| `backend/app/extraction/dispatcher.py` | เลือก extractor 3 ชั้น |
| `backend/app/extraction/text_pipeline.py` | generic memo pipeline (~40 ฟิลด์ + 3 กลยุทธ์ตาราง + schedule parser) |
| `backend/app/extraction/template_engine.py` | rule engine + postprocess (template-anchored) |
| `backend/app/extraction/template_registry.py` | detect/registry/integrity check |
| `backend/app/extraction/conference_extractor.py` | ฟอร์ม HR-SD-S-F13 |
| `backend/app/extraction/{docx,pdf,excel}_extractor.py` | ingestion แต่ละประเภทไฟล์ |
| `backend/app/normalizer/thai_utils.py` | วันที่ไทย ↔ ISO, บาทตัวอักษร |
| `backend/app/normalizer/expense_rollup.py` | หมวดค่าใช้จ่ายราชการ 11 หมวด |
| `backend/app/generators/field_mapper.py` | profile resolve + DOMAction builder (Python + JSON) |
| `backend/app/generators/{pdf,excel}_generator.py` | output PDF/Excel |
| `backend/app/profiles/*.json` | form profiles |
| `backend/templates/rsc_memo.json` + `*.docx` | template manifest + blank forms |
| `backend/tests/*` | smoke_test, test_template_engine, check_mapping_vs_dom (static checker) |
| `extension/scripts/content.js` | DOM Action Executor (label fallback, DataTransfer, MutationObserver) |
| `extension/sidepanel/sidepanel.js` | Tri-Action Hub, Review Card, Quick Form, จับฟอร์ม |
| `docs/API.md` | contract API + DOMAction เต็ม |
| `docs/HOW_TO_ADD_NEW_FORM.md` | ขั้นตอนเพิ่มฟอร์ม hardcode / extractor ใหม่ / profile ใหม่ |
| `docs/ROADMAP.md` / `docs/PLAN_PAPERLESS_PORTAL.md` | แผนต่อยอด |
| `app.py` (legacy) | Streamlit PoC + `generate_docx_bytes` (เรนเดอร์ docx จาก scratch) |

---

*เอกสารนี้สรุปจาก source code และ docs ณ วันที่ 2026-09-30 — ใช้เป็นข้อมูลตั้งต้นสำหรับออกแบบระบบ Smart Doc ใหม่*
