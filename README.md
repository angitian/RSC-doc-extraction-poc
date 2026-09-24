# RSC Administrative Productivity Suite

ระบบสกัดข้อมูลจากเอกสารราชการ (`.docx` / `.pdf`) แล้วแปลงเป็น Structured Data ชุดเดียว
เพื่อส่งออก 3 ทิศทาง (Tri-Action Hub):

1. 🚀 **ยิงข้อมูลลงแบบฟอร์มเว็บ** — Dynamic DOM Mapping (Backend ส่ง `field_mappings` ให้ Content Script)
2. 📊 **ดาวน์โหลด Excel / คัดลอก TSV** — เทมเพลต `.xlsx` + TSV สำหรับวางใน Excel
3. 📄 **PDF เอกสารแนบ** — สร้าง "ประมาณการค่าใช้จ่ายและกำหนดการ" ด้วย fpdf2 + ฟอนต์ไทย

## สถาปัตยกรรม (v2 — ยกเครื่องใหม่)

```
[Chrome Extension MV3 — Side Panel]  ──POST /api/v1/extract──▶  [FastAPI Backend (Docker)]
        │  Review Card + Tri-Action Hub                              ├─ python-docx / PyMuPDF (สกัด)
        ▼                                                            ├─ Category Rollup (หมวดราชการ)
[Content Script: field_mappings]                                     ├─ field_mapper (dynamic selectors)
        │  set_value / click / set_select / file_attach              └─ Excel (openpyxl) + PDF (fpdf2)
        ▼
[เว็บราชการ Portal]
```

**Dynamic Mapping Paradigm:** Extension **ไม่ Hard-code** DOM Selector —
Backend ส่งโครงสร้างข้อมูลพร้อม `field_mappings` (Selectors + Actions) ตาม `target_url`
เว็บเปลี่ยนโครงสร้างหรือเพิ่มเอกสารประเภทใหม่ อัปเดตที่ Backend เท่านั้น

## โครงสร้างโฟลเดอร์

```
backend/     → FastAPI (main.py, app/models.py, extraction/, normalizer/, generators/, Dockerfile, render.yaml)
extension/   → Chrome Extension MV3 (manifest.json, sidepanel/, scripts/content.js, assets/icons)
docs/        → API.md (contract) + DEPLOY.md (Render/Cloud Run/HF Spaces + demo)
app.py       → (legacy) Streamlit PoC เดิม — เก็บเป็น reference
extension_v1 → (legacy) Extension v1 แบบ hard-coded selector
```

## เริ่มต้นใช้งาน

**Backend (local):**

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
.venv/Scripts/uvicorn main:app --port 8000      # หรือ python main.py
```

**Extension:** `chrome://extensions` → Developer mode → Load unpacked → เลือก `extension/`

**Deploy:** ดู `docs/DEPLOY.md` (Render Free / Cloud Run / HF Spaces)

## API สั้นๆ

| Endpoint | คำอธิบาย |
|---|---|
| `GET /api/v1/health` | เช็คสถานะ |
| `POST /api/v1/extract` | multipart: `file` (.docx/.pdf), `mode` (full_table \| annex_pdf), `target_url` → `ExtractionResponse` |

รายละเอียดเต็ม: `docs/API.md`

## เทคโนโลยี

- **Backend:** Python 3.10+, FastAPI, Pydantic v2, python-docx, PyMuPDF, openpyxl, fpdf2
- **Extension:** Manifest V3, Side Panel, `chrome.scripting` (inject on demand), native-setter event dispatch
- **Deploy:** Docker (port 7860 default) — Render Free / Cloud Run / Hugging Face Spaces

## ทดสอบกับฟอร์มจริง (Troubleshooting)

- **หลังแก้ code extension ทุกครั้งต้อง reload ที่ `chrome://extensions`** (ปุ่ม reload บนการ์ด) — ไม่ reload = ได้ build เก่า
- **API URL**: backend local รันที่ `http://127.0.0.1:7860` (ตั้งใน ⚙️ Settings ของ side panel) — manifest รองรับ port 7860/8000 แล้ว
- **ฟอร์มที่เปิดผ่าน `file://` (HTML ที่บันทึกไว้) ยิงไม่ได้** — page เป็น static (module script ถูกบล็อก) ให้ยิงที่พอร์ทัลจริง หรือเสิร์ฟผ่าน `python -m http.server`
- **"จับฟอร์ม"**: กดปุ่มใน side panel (ตอนเปิดฟอร์มจริง) → คัดลอก JSON ครบเข้าคลิปบอร์ด → ส่งให้ dev ปรับ `field_mapper` ให้ตรง DOM จริง
- **อ่าน error**: หลังยิง ให้ดู log ใน side panel — บรรทัด `กรอกสำเร็จ x/y` + `↳ ...` ต่อท้ายบอกว่าฟิลด์ไหนไม่เจอ

## ตรวจ mapping กับ DOM (static checker)

```bash
cd backend
.venv/Scripts/python.exe tests/check_mapping_vs_dom.py "<ไฟล์ .docx ตัวอย่าง>" \
  --html "<พอร์ทัล HTML ที่บันทึก>" \
  --snapshot tests/fixtures/rsc_main_capture.json \
  --expect-dangling "#schedule-date-" "#schedule-time-" "เพิ่มรายการ" "เพิ่มกิจกรรม"
```

- `--snapshot` = JSON จากปุ่ม "จับฟอร์ม" ใน side panel (ฟิลด์ที่จับได้จริงจะถูกตรวจแบบละเอียด)
- `fixtures/rsc_main_capture.json` = capture จริงจากพอร์ทัล (Section 1-4 + ตารางค่าใช้จ่าย)
- รายการที่ยังไม่มีใน source (เช่น ตารางกำหนดการตอน capture ยังไม่ render, ปุ่มเพิ่มแถว)
  ต้องประกาศด้วย `--expect-dangling` — checker จะจับได้ทันทีถ้าพอร์ทัลเปลี่ยน DOM อีก
