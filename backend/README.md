---
title: RSC Extraction API
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# RSC Extraction API

FastAPI backend สำหรับ RSC Administrative Productivity Suite —
สกัดข้อมูลจากบันทึกข้อความ (.docx / .pdf) แล้วส่งกลับเป็น JSON พร้อม
`field_mappings` (คำสั่ง DOM แบบไดนามิก), Excel และ PDF เอกสารแนบ

## API

| Endpoint | Method | คำอธิบาย |
|---|---|---|
| `/api/v1/health` | GET | เช็คสถานะบริการ |
| `/api/v1/extract` | POST | multipart: `file` (.docx/.pdf), `mode` (`full_table`\|`annex_pdf`), `target_url` |

## รัน local

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

ทดสอบ:

```bash
curl -F "file=@2026-08 บันทึกข้อความขออนุมัติเดินทางติดตามงาน สค.69.docx" \
     -F "mode=full_table" -F "target_url=https://rsc.app" \
     http://127.0.0.1:8000/api/v1/extract
```

## Deploy (ฟรี tier)

### Render (แนะนำ — git push, ไม่ต้องบัตร)

1. Push repo ขึ้น GitHub
2. Render Dashboard → **New → Blueprint** → เลือก repo → `render.yaml` จะถูกอ่านอัตโนมัติ
   (web service, Docker runtime, free plan)
3. หลัง deploy จะได้ URL `https://<name>.onrender.com` — นำไปใส่ใน **API URL** ของ Extension

หมายเหตุ free tier: service หลับหลัง idle 15 นาที → request แรกช้า ~1 นาที
(extension แสดง "กำลังปลุกเซิร์ฟเวอร์..." อัตโนมัติ) — 750 ชม./เดือน, 5GB bandwidth/เดือน

### Google Cloud Run (ทางเลือก, cold start เร็ว)

```bash
gcloud builds submit --tag gcr.io/<PROJECT>/rsc-api
gcloud run deploy rsc-api --image gcr.io/<PROJECT>/rsc-api \
  --allow-unauthenticated --port 8080 --memory 512Mi \
  --set-env-vars PORT=8080
```

### Hugging Face Spaces (เมื่อบัญชีมี PRO)

1. สร้าง Space ใหม่ → SDK: **Docker**
2. Push เนื้อหาใน `backend/` ขึ้น Space repo:
   ```bash
   git push https://huggingface.co/spaces/<USER>/<SPACE> main
   ```
3. `README.md` ด้านบนมี YAML `sdk: docker` + `app_port: 7860` ครบแล้ว
   (ค่าเริ่มต้นของ `main.py` คือพอร์ต 7860)
4. URL API: `https://<USER>-<SPACE>.hf.space/api/v1/extract`

## CORS

ใช้ `allow_origins=["*"]` โดยไม่ใช้ credentials —
เข้ากันได้กับ `chrome-extension://` origin และ proxy ของ HF Spaces
