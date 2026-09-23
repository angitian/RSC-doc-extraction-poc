# Roadmap — แผนต่อยอดระบบ (เก็บไว้สำหรับพัฒนาในภายหลัง)

> เอกสารนี้สรุปแผนต่อยอดทั้งหมดที่วางไว้ ยัง **ไม่เริ่ม implement** —
> ใช้เป็นข้อมูลส่งต่อให้ AI IDE (Claude Code / Cursor / Windsurf / Devin) อ่านแล้วพัฒนาต่อได้

## สถานะปัจจุบัน (ใช้งานได้แล้ว)

| ความสามารถ | สถานะ |
|---|---|
| สกัด DOCX/PDF/XLSX → กรอกฟอร์มเว็บอัตโนมัติ (2 ฟอร์ม: หลัก + เข้าร่วมประชุม) | ✅ |
| แนบ PDF แยกกล่อง (ประมาณการ/กำหนดการ) + auto-assign | ✅ |
| Editable Review Card / Quick Form / Excel template / TSV | ✅ |
| Dynamic Mapping (label-based ทน React ID เปลี่ยน) | ✅ |
| Deploy: Docker (Render/Cloud Run/HF พร้อม) | ✅ ยังไม่ deploy จริง |

## แผนต่อยอด (เรียงตามความสำคัญ)

### แผน A — Paperless Portal (login + admin แก้ + dashboard)
**รายละเอียดเต็ม:** [PLAN_PAPERLESS_PORTAL.md](./PLAN_PAPERLESS_PORTAL.md)

แก้ปัญหาหลัก: ปัจจุบัน admin **แก้เอกสารเล็กน้อยไม่ได้** → ต้องส่งกลับไปมาระหว่าง user ↔ admin เสียเวลา

- Flow ใหม่: user ร่าง docx → ส่ง admin → **admin ตรวจ/แก้ที่ผลสกัด** → สกัดเข้า DB → user login → ยิงฟอร์มตัวเอง → ส่ง admin ตามระบบ
- สถาปัตยกรรม: **แยก service ใหม่ (RSC Portal)** — extraction API ไม่แตะ; extension เพิ่มช่อง token + ปุ่ม "บันทึกเข้าแฟ้ม"
- โมดูล: Auth (JWT), Documents+สถานะ workflow, หน้า Admin แก้ข้อมูล, อัปโหลดข้อมูลการเงิน, Dashboard
- ฐานข้อมูล: Supabase/Neon (free Postgres) หรือ Render Postgres ($7/เดือน) — **Render free ไม่มี disk persistent**

### แผน B — Reconciliation Engine (กระทบยอดเงินยืมวิจัย)
**รายละเอียดเต็ม:** [PLAN_RECONCILIATION_ENGINE.md](./PLAN_RECONCILIATION_ENGINE.md)

ระบบช่วยคัดแยกบิล/ทำบัญชีส่งส่วนกลาง (เงินยืมวิจัย) — Excel input → Knapsack auto-match → Export รายงาน

### แผน C — Concurrency / Hardening (เล็ก, ทำได้ทุกเมื่อ)
- [ ] `run_in_threadpool` ใน `/api/v1/extract` + `/api/v1/fill` — กัน event loop ถูกบล็อกเมื่อ user ยิงพร้อมกัน
- [ ] Rate limit เบาๆ (กัน URL สาธารณะถูกยิง spam)
- [ ] (ทางเลือก) Shared token — กันคนนอกใช้

### แผน D — On-Premise Server (เครื่องในสำนักงาน)
**รายละเอียดเต็ม:** [ONPREMISE_SERVER_SPEC.md](./ONPREMISE_SERVER_SPEC.md)

- สเปค: Ryzen 7/i7 (8C) / RAM 32GB / M.2 512 (OS) + SSD 1TB (data)
- รัน: ระบบสกัด + Portal + **IoT dashboard (500 จุด)** + OCR + DB รวม
- แนวทาง: Docker Compose + TimescaleDB (sensor) + resource limits (กัน OCR กระทบ) + backup รายวันไป NAS

## ข้อสรุปเชิงสถาปัตยกรรม (สำคัญ)

1. **Extraction engine (backend/app/extraction, normalizer, generators, profiles) ใช้ซ้ำได้ 100%** — ทั้ง Portal และ Reconciliation ไม่ต้องแก้
2. ระบบใหม่ควรเป็น **service แยก** (RSC Portal) ไม่ใช่ต่อใน backend เดิม — กันเสี่ยงระบบที่ใช้งานได้อยู่ + เลือก stack อิสระ
3. ต้องมี **DB persistent** — free tier ของ Render ไม่พอ (disk หายทุก restart)
4. Extension เป็นตัวเชื่อม: เพิ่มช่อง token/user + endpoint ของ portal — แก้เล็กน้อย
