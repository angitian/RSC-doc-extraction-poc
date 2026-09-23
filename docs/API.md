# RSC Extraction API — Contract

Base URL เปลี่ยนตาม host ที่ deploy (ดู docs/DEPLOY.md)

## `GET /api/v1/health`

```json
{ "status": "ok", "service": "rsc-extraction-api", "version": "2.0.0" }
```

## `POST /api/v1/extract`

multipart/form-data:

| field | ประเภท | ค่า |
|---|---|---|
| `file` | File | `.docx` / `.pdf` / `.xlsx` (สูงสุด 20 MB) — `.xlsx` = เทมเพลตกรอกจาก `/api/v1/templates/{id}` (ใช้เป็นไฟล์สกัด ไม่ใช่ไฟล์แนบ) |
| `mode` | string | `full_table` (default) \| `annex_pdf` |
| `target_url` | string | URL หน้าปัจจุบันของเว็บราชการ (ใช้แมป field_mappings) |
| `doc_type` | string | (optional) override ชนิดเอกสาร — ข้าม auto-classify |
| `page_snapshot` | string | (optional) JSON array ของ `[{id, name, type, label}]` — ใช้ resolve ฟอร์มด้วย DOM signature |
| `outputs` | string | (optional) comma list `excel` \| `pdf` (default `excel`) — **PDF สร้างเฉพาะเมื่อขอ** (เช่น annex_pdf) เพื่อให้ extract เร็ว |

### Response (200) — `ExtractionResponse`

```json
{
  "doc_type": "travel_request",
  "confidence": 0.84,
  "metadata": { "...": "ทุกฟิลด์ที่สกัดได้จากเอกสาร" },
  "expense_summary": { "ค่าเช่ายานพาหนะ": 9000.0, "ค่าน้ำมันเชื้อเพลิง": 6000.0 },
  "total_amount": 21200.0,
  "raw_tables": {
    "breakdown": [["ค่าจ้างเหมาพาหนะ", "จำนวน 6 วัน x 1,500 บาท", "9,000"]],
    "schedule": [["วันที่ 3 สิงหาคม 2569", "ศูนย์...", "07.00 – 10.00 น.", "ออกเดินทาง..."]]
  },
  "field_mappings": [
    { "selector": "#project-document-number", "action": "set_value", "value": "7608.8/69" },
    { "selector": "#expense-description-0", "action": "set_value", "value": "ค่าจ้างเหมาพาหนะ" },
    { "selector": "button", "action": "click_button", "value": "เพิ่มรายการ", "repeat": 3, "delay_ms": 350 }
  ],
  "pdf_annex_base64": "JVBERi0xLjQK...",
  "pdf_annex_filename": "ประมาณการค่าใช้จ่ายและกำหนดการ.pdf",
  "excel_filled_base64": "UEsDBBQ...",
  "excel_filled_filename": "ข้อมูลโครงการและค่าใช้จ่าย.xlsx",
  "summary": {
    "doc_type": "travel_request",
    "doc_type_label": "คำขออนุมัติเดินทาง",
    "confidence": 0.84,
    "project_name": "...",
    "traveler": "นายรณกร อำพันธ์ศรี",
    "date_range": "3, 10, ... สิงหาคม 2569",
    "total_amount": 21200.0,
    "expense_items_count": 4,
    "itinerary_items_count": 30,
    "categories": { "ค่าเช่ายานพาหนะ": 9000.0 }
  },
  "warnings": []
}
```

Response เพิ่มเติม (v2.1): `form_type`, `profile_id`, `profile_name`, `page_match_confidence`,
`editable_fields` (`[{key, label, type, value}]` — ใช้กับ Editable Review Card)

### Errors

| status | กรณี |
|---|---|
| 400 | mode ไม่ถูกต้อง / ไฟล์ว่าง / ประเภทไฟล์ไม่รองรับ |
| 413 | ไฟล์ใหญ่เกิน 20 MB |
| 422 | อ่านไฟล์ไม่สำเร็จ (เสียหาย / ไม่ใช่ docx-pdf จริง) |

## `GET /api/v1/forms`

รายการฟอร์ม (profile) ที่ลงทะเบียน + schema ฟิลด์ — ใช้กับ Quick Form

## `POST /api/v1/fill`

Quick Form — ไม่ต้องมีเอกสาร:

```json
{
  "profile_id": "rsc_conference",
  "target_url": "https://...",
  "page_snapshot": [{"id": "..."}],
  "mode": "full_table",
  "values": { "event_title": "...", "per_diem": 200, "...": "..." }
}
```
→ คืน `ExtractionResponse` (field_mappings พร้อมยิง)

**`mode: "annex_pdf"` + values ว่าง = attach-only** — คืน mappings แค่ radios "แนบไฟล์ PDF" + `file_attach` (สำหรับโหมด "อัปโหลด PDF แนบเอง" — ผู้ใช้เลือกไฟล์ในเครื่อง ไม่ต้องสกัด; ใช้ `profile_id` หรือให้ระบบ resolve จาก `page_snapshot` ก็ได้)

## `GET /api/v1/templates/{profile_id}`

ดาวน์โหลด Excel template (.xlsx) — คอลัมน์ A = ป้ายฟิลด์, B = ค่า (กรอกแล้วอัปโหลดกลับผ่าน `/api/v1/extract`)

## DOMAction — คำสั่งที่ Content Script รองรับ

| action | selector | value | หมายเหตุ |
|---|---|---|---|
| `set_value` | CSS | ข้อความ/ตัวเลข/วันที่ (ISO) | ใช้ native setter + dispatch input/change/blur (React/Vue ครบ) |
| `set_select` | CSS | text หรือ option value | เลือก option แบบ contains ด้วย |
| `set_radio` | CSS (radio ตัวใดใน group) | radio value | คลิก radio ที่ตรง value ใน name group เดียวกัน |
| `click` | CSS | — | คลิก element แรก |
| `click_button` | CSS container (ว่างได้) | ข้อความปุ่ม | หา `<button>` ที่มีข้อความตรง (`:has()` ใช้ scope ได้) |
| `file_attach` | CSS ของ `<input type=file>` (optional) | base64 | ผ่าน DataTransfer + change event — ถ้า selector ไม่เจอ จะ fallback ไป `input[type="file"]` → `input[accept*="pdf"]` อัตโนมัติ (กัน React ID เปลี่ยน) |
| `wait` | — | — | หน่วงเวลา `delay_ms` |

ฟิลด์เพิ่มเติม:
- `label` (string) — **ป้ายภาษาไทยของฟิลด์** เช่น `"วัตถุประสงค์"`, `"ชื่อโครงการ/โครงการย่อย"`, `"วงเงินรวม (บาท)"` — Content Script ใช้เป็นตัวชี้หลักสำรอง: ถ้า CSS selector หาไม่เจอ (React auto-ID เช่น `input-94`/`textarea-19` เปลี่ยนทุก build) จะหา element จาก label (`label[for]` → label ครอบ → aria-label/placeholder) แทน
- `key` (string) — metadata key ที่ค่ามาจาก — Side Panel ใช้แทนค่าจาก Editable Review Card ก่อนยิง
- `skip_if_value_present` (bool) — ถ้า element มีค่าอยู่แล้ว (เว็บเติมเองจากโปรไฟล์/ACC) ให้ข้ามไม่ทับ
- `meta.scope_name` — ใช้กับ radio โดยเฉพาะ เพื่อแยกกลุ่ม เช่น `"expense-document-source"` กับ `"schedule-document-source"`
- `index` (เลือก element ลำดับที่ N), `repeat` (ทำซ้ำ เช่น คลิกเพิ่มแถว), `delay_ms`
