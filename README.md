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
