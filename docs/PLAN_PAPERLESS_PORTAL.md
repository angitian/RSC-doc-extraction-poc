# แผน: RSC Paperless Portal (ระบบต่อยอด — ยังไม่ implement)

> แผนสำหรับ "ระบบเต็ม": login แยก user + admin แก้ข้อมูลสกัด + ฐานข้อมูล + dashboard
> + การอัปโหลดข้อมูลการเงิน (เคลียร์เอกสาร/ทำบัญชี) — เก็บไว้ให้ AI IDE พัฒนาภายหลัง

## 1. ปัญหาที่ต้องการแก้

**Flow ปัจจุบัน (หลังใช้ Smart Doc):**
```
user ร่าง docx → สกัด → กรอกฟอร์ม → admin ตรวจ
   ├─ ผ่าน → ส่งกลับ user เซนต์
   └─ ไม่ผ่าน → ส่ง user แก้ (เสียเวลาไปมา)
```
**ปัญหา:** admin แก้เอกสารเล็กน้อย (แก้คำ/ตัวเลข) ไม่ได้ → ต้องส่งกลับ user ทุกรอบ

## 2. Flow ใหม่ที่ออกแบบ (Paperless)

```
user ร่าง docx
   │
   ▼
ส่ง admin (ผ่าน Portal — สถานะ: ร่าง → ส่งตรวจ)
   │
   ▼
ADMIN ตรวจ/แก้ — แก้ที่ "ผลสกัด" ในหน้า Portal (ไม่ต้องแก้ไฟล์)
   │
   ▼
สกัด → เข้า DB (ผูก id user, สถานะ: รอ user ยืนยัน)
   │
   ▼
user เปิดฟอร์มตัวเอง (login) → ข้อมูลที่ admin แก้แล้วมา prefill
   │  user ตรวจ → กดยิงเข้าระบบราชการ (เซนต์/ยืนยันด้วยตัวเอง)
   ▼
ส่ง admin ตามระบบเดิม (สถานะ: ยืนยันแล้ว → อนุมัติ)
```

**หลักสำคัญ:** **user เป็นคน "ยิงฟอร์ม" คนสุดท้าย** (ข้อมูลส่วนตัว + เซนต์ดิจิทัลเป็นของผู้ขอ) —
admin แก้ข้อมูลให้ถูกต้องก่อน แล้ว user ตรวจ/ยิงเอง

## 3. สถาปัตยกรรม — แยก service (แนะนำ)

```
[Extension] ──สกัด──▶ [Extraction API]  (คงเดิม ไม่แตะ)
     │  ✅ แสดงผล/ยิงฟอร์ม
     └─ "บันทึกเข้าแฟ้ม" ──▶ [RSC Portal (service ใหม่)]
                              ├─ Auth (login, roles: researcher/admin)
                              ├─ Postgres: users / documents / status / financials
                              ├─ Admin Edit UI (แก้ผลสกัด)
                              └─ Dashboard + Export
```

| ส่วน | ต้องแก้? |
|---|---|
| Extraction engine (สกัด/แมป/Excel/PDF) | ❌ ไม่แตะ |
| Extraction API (main.py) | ❌ ไม่แตะ |
| Extension | ✅ เล็กน้อย: ช่อง Portal URL + Token ใน Settings, ปุ่ม "บันทึกเข้าแฟ้ม", (ภายหลัง) "ดึงจากแฟ้มของฉัน" |
| **RSC Portal** | ➕ โค้ดใหม่ทั้งหมด |

## 4. โมดูลที่ต้องสร้าง (Portal)

| โมดูล | รายละเอียด | ความยาก |
|---|---|---|
| Auth | email+password (hash) + JWT; roles researcher / admin | กลาง |
| Documents | บันทึก extracted JSON ต่อ user, รายการ, สถานะ (ร่าง/ส่งตรวจ/แก้แล้ว/รอ user/ยืนยัน/อนุมัติ) | กลาง |
| Admin Edit UI | แก้ฟิลด์หลักก่อน (ชื่อโครงการ/วันที่/ยอด/รายการ) → ค่อยขยายตาราง | กลาง |
| Financial Upload | อัปโหลดไฟล์การเงิน (Excel/PDF ใบเสร็จ) + ยอด + ผูกเอกสาร → เคลียร์/บัญชี | กลาง |
| Dashboard | นักวิจัยเห็นของตัวเอง / admin เห็นทั้งหมด (สรุปยอด/สถานะ) | กลาง |
| Extension integration | ปุ่มบันทึก/ดึงข้อมูล + token | ง่าย |

**ข้อมูลที่บันทึกต่อเอกสาร (extracted JSON ~<100KB):**
```json
{ "user_token": "...", "doc_type": "travel_request",
  "metadata": { "project_title": "...", "requester_name": "...", "budget_amount": "..." },
  "expense_summary": {}, "total_amount": 6600,
  "raw_tables": { "breakdown": [...], "schedule": [...] }, "summary": {} }
```

## 5. ฐานข้อมูล

| ตัวเลือก | ข้อดี | ข้อจำกัด |
|---|---|---|
| **Supabase** (free Postgres ~500MB) | ฟรี, persistent, ตั้งง่าย | — |
| **Neon** (free serverless Postgres) | ฟรี, หลับ/ตื่นอัตโนมัติ | — |
| **Render Postgres** ($7/เดือน) | อยู่ที่เดียวกับ API | จ่าย; **free tier ของ Render หมดอายุ 30 วัน ใช้เก็บข้อมูลจริงไม่ได้** |

Schema เริ่มต้น (ตัวอย่าง): `users` / `documents` / `document_versions` / `financial_items` / `status_log`

## 6. ขั้นตอน (Phase)

- [ ] **Phase 1**: Auth + DB schema + Documents CRUD + endpoint รับบันทึกจาก extension
- [ ] **Phase 2**: Admin Edit UI (แก้ฟิลด์หลัก) + status workflow
- [ ] **Phase 3**: Financial upload + Dashboard + Export
- [ ] **Phase 4**: Extension — ดึงข้อมูลจากแฟ้มของฉัน (prefill ฟอร์มจาก DB)

## 7. หมายเหตุ

- **docx ต้นฉบับควรเก็บใน DB ด้วย** (หลักฐาน/version) — admin แก้ผลสกัด แต่ไฟล์ต้นทางคงไว้
- Concurrency: เมื่อมี user พร้อมกัน ควรทำ `run_in_threadpool` + rate limit ก่อน (ดู ROADMAP.md แผน C)
- ต้องการแค่ "ข้อมูลไหลลง DB แยก user" → งานจริง = สร้าง Portal; ของเดิมแก้แค่ extension 2 จุด
