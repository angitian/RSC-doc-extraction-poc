# การ Deploy และติดตั้ง

## 1. Backend — Render Free (แนะนำ, ไม่ต้องบัตร)

1. Push โปรเจกต์ขึ้น **GitHub**
2. เข้า [render.com](https://render.com) → **New → Blueprint**
3. เลือก repo → Render อ่าน `backend/render.yaml` ให้อัตโนมัติ
   (Web Service, Docker runtime, plan **free**)
4. หลัง build เสร็จจะได้ URL `https://<name>.onrender.com`
5. ทดสอบ: `curl https://<name>.onrender.com/api/v1/health`

**ข้อจำกัด free tier:** หลับหลัง idle 15 นาที (request แรก ~1 นาที — Extension มีข้อความ "กำลังปลุกเซิร์ฟเวอร์..." ให้), 750 instance hours/เดือน, 5GB outbound/เดือน (เราใช้ ~3% ต่อ 300 ครั้ง/เดือน) แนะนำผูกบัตรเครดิตไว้กันกรณีเกิน bandwidth แล้วถูก suspend

## 2. Backend — Cloud Run (ทางเลือก, cold start เร็ว)

```bash
gcloud builds submit --tag gcr.io/<PROJECT>/rsc-api
gcloud run deploy rsc-api --image gcr.io/<PROJECT>/rsc-api \
  --allow-unauthenticated --port 8080 --memory 512Mi \
  --set-env-vars PORT=8080
```

## 3. Backend — Hugging Face Spaces (เมื่อมี PRO)

1. สร้าง Space → SDK: **Docker** → ตั้งชื่อ เช่น `rsc-extraction-api`
2. push เนื้อหาใน `backend/` (ต้องมี `main.py` อยู่ root ของ Space):

```bash
cd backend
git init
git add .
git commit -m "init"
git remote add space https://huggingface.co/spaces/<USER>/rsc-extraction-api
git push space main
```

3. `README.md` ใน `backend/` มี YAML `sdk: docker` + `app_port: 7860` ครบแล้ว
4. URL API: `https://<USER>-rsc-extraction-api.hf.space/api/v1/extract`

## 4. Chrome Extension

1. เปิด `chrome://extensions` → เปิด **Developer mode**
2. **Load unpacked** → เลือกโฟลเดอร์ `extension/`
3. คลิกไอคอนบน toolbar → เปิด Side Panel
4. **ค่า default ชี้ที่ Render แล้ว** (`https://rsc-extraction-api.onrender.com`) — ใช้ได้ทันที
   ถ้าต้องการ local/ที่อื่น → เปิดการตั้งค่า (⚙️) → เปลี่ยน API URL → บันทึก
   (หมายเหตุ: ถ้าเคยบันทึก URL เก่าไว้ (เช่น localhost) ต้องกดบันทึกใหม่เพื่อใช้ค่า default)

> ถ้าเปิดหน้าเว็บราชการจากไฟล์ในเครื่อง (`file://...`) ให้ไปที่
> `chrome://extensions` → การ์ด extension → รายละเอียด → เปิด **"อนุญาตให้เข้าถึงไฟล์ URL"**

## 5. Chrome Web Store

**นโยบายความเป็นส่วนตัว:** [PRIVACY.md](./PRIVACY.md) (โฮสต์ผ่าน GitHub Pages หรือ Google Sites)

1. สมัคร [Chrome Web Store Developer account](https://chrome.google.com/webstore/devconsole) ($5 ครั้งเดียว)
2. สร้าง zip จาก**เนื้อหาด้านใน** `extension/` (manifest.json ต้องอยู่ root ของ zip)
   ```bash
   cd extension && zip -r ../rsc-extension-store.zip . -x "*.DS_Store" "assets/icons/generate_icons.py" "assets/icons/source_logo.jpg"
   ```
3. อัปโหลด zip → กรอก listing + Privacy Policy URL + ตอบแบบฟอร์ม Data Safety
4. ตั้ง visibility เป็น **Unlisted** (เฉพาะคนมีลิงก์) สำหรับการแจกภายในหน่วยงาน

**หมายเหตุสิทธิ์ (host_permissions):** จำกัดเฉพาะ `rsc-approval.kmutt.ac.th`, Render API และ
localhost (dev) — ถ้าใช้งานกับเว็บราชการ domain อื่น ต้องเพิ่ม domain นั้นใน `manifest.json`

## 5. Demo

1. เปิด `RSC Smart Approval - ระบบบริหารจัดการโครงการ.html` ในแท็บ
2. เปิด Side Panel → ลาก `2026-08 บันทึกข้อความขออนุมัติเดินทางติดตามงาน สค.69.docx` ลงมา
3. ตรวจ Review Card → กด **🚀 ยิงข้อมูลลงแบบฟอร์ม**
4. โหมด `Summary + PDF Annex` จะแนบ PDF ให้ช่อง "เอกสารประกอบ" อัตโนมัติ

## ตัวเลข capacity (อ้างอิง)

| ตัวชี้วัด | ค่า | ภาระจริง (300 ครั้ง/เดือน) |
|---|---|---|
| Instance hours (Render free) | 750 ชม./เดือน | ~7% |
| Outbound bandwidth | 5 GB/เดือน | ~3% |
| Build pipeline | 500 นาที/เดือน | เฉพาะตอน deploy |
