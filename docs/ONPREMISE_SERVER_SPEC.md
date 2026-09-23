# สเปคเครื่อง Server ในสำนักงาน (On-Premise) — เอกสารอ้างอิง

> สรุปสเปคที่ตกลงกัน + เหตุผล + แนวทางติดตั้ง — สำหรับตั้งเครื่องในสำนักงาน
> รันระบบสกัดเอกสาร + (อนาคต) RSC Portal + ระบบอื่นๆ ของหน่วยงาน

## 1. สเปคเครื่อง (ยืนยันแล้ว)

| ส่วน | สเปค | หมายเหตุ |
|---|---|---|
| **CPU** | Ryzen 7 / 9 หรือ Core i5 / i7 (เจนล่าสุด หรือ 1-2 เจนก่อน) | Ryzen 7 (8C/16T) / i7 (8C) = จุดหวาน; i5 (6C) พอ; Ryzen 9/i9 เผื่อหลายปี |
| **RAM** | **32 GB** | เหลือเฟือ — ตั้ง Postgres cache ได้เต็ม + OCR burst ไม่กระทบ |
| **OS drive** | M.2 NVMe **512 GB** | ไว้ OS + Docker + โปรแกรม (ห้ามเก็บข้อมูลลงนี้) |
| **Data drive** | SSD **1 TB** | ข้อมูลทั้งหมด: DB + รูป OCR + เอกสารต้นฉบับ |
| **OS** | Ubuntu 24.04 LTS | เสถียร + Docker/TimescaleDB รองรับดี |
| **อื่นๆ** | UPS, ระบบสำรองไฟ, ระบายอากาศ | สำคัญกว่าสเปคสำหรับ server ในสำนักงาน |

## 2. Workload ที่เครื่องต้องรัน

| ระบบ | ลักษณะงาน | ความต้องการ |
|---|---|---|
| **RSC Extraction (ระบบนี้)** | สกัด DOCX/PDF (0.5-2 วิ/ครั้ง), <10-15 คน | น้อยมาก (2 core/1GB ก็รันได้) |
| **RSC Portal (แผนอนาคต)** | Auth + Postgres + dashboard, ~100 คนดู | กลาง |
| **IoT Dashboard** | **400-500 จุด** หลายแปลง/พื้นที่, คำนวณ VPD + จุดอับลม, กราฟ 2D | **ตัวหลัก** — CPU (คำนวณ) + DB (time-series) |
| **OCR Logbook** | ~50 แปลง, รันเป็นช่วง (POC), ประมวลผลภาพ | **burst** — CPU/RAM พุ่งตอนรัน ต้องจำกัด resource |
| **ฐานข้อมูลรวม** | Postgres (portal) + TimescaleDB (sensor) + อื่นๆ | RAM + disk |

**ข้อสรุป:** คอขวดจริง = **IoT (CPU + DB write)** และ **OCR (burst)** — ไม่ใช่ระบบสกัดเอกสาร

## 3. การจัดวาง Storage (สำคัญ)

```
M.2 512 GB (OS drive)   → OS + Docker images/volumes + โปรแกรม
SSD 1 TB (Data drive)   → /data
                          ├─ postgres/        (Portal DB)
                          ├─ timescaledb/     (sensor data — IoT)
                          ├─ ocr_images/      (รูป logbook ~50 แปลง)
                          ├─ documents/       (docx ต้นฉบับ + PDF ที่สกัด)
                          └─ backups/staging  (backup ชั่วคราวก่อนส่ง NAS)
```

- **ห้าม**เก็บข้อมูลลง M.2 512 — เดี๋ยวเต็มเร็ว
- **Backup ต้องไปเครื่องอื่น** (NAS/HDD ภายนอก) — 1TB เป็นที่เก็บหลักไม่ใช่ที่สำรอง;
  sensor ไหลตลอด → backup รายวัน (pg_dump + สำเนารูป OCR)

## 4. แนวทางติดตั้ง (Docker Compose)

```yaml
services:
  # ระบบสกัดเอกสาร (ปัจจุบัน)
  rsc-api:
    build: ./backend
    ports: ["8000:8000"]
    environment: [PORT=8000]

  # Portal (อนาคต)
  rsc-portal:
    build: ./portal
    ports: ["8080:8080"]
    depends_on: [postgres]

  # ฐานข้อมูล
  postgres:            # Portal DB
    image: postgres:16
    volumes: ["/data/postgres:/var/lib/postgresql/data"]
  timescaledb:         # IoT sensor (time-series)
    image: timescaledb/timescaledb:latest-pg16
    volumes: ["/data/timescaledb:/var/lib/postgresql/data"]
    deploy:
      resources:
        limits: { cpus: "2.0", memory: 4G }

  # OCR (burst — จำกัด resource กันกระทบ dashboard)
  ocr:
    build: ./ocr
    deploy:
      resources:
        limits: { cpus: "4.0", memory: 6G }

  caddy:               # reverse proxy + HTTPS
    image: caddy:2
    ports: ["80:80", "443:443"]
```

**หลักการ:** ทุก service แยก container + ตั้ง `resource limits` — กัน OCR กิน CPU/RAM จน IoT dashboard ค้าง

## 5. จุดที่ต้องออกแบบให้ดี (สำคัญกว่าสเปค)

1. **Sensor DB ใช้ TimescaleDB** — 500 จุด × 96 ครั้ง/วัน ≈ 17M แถว/ปี; TimescaleDB บีบอัด + partition อัตโนมัติ → ประหยัด disk 5-10 เท่า (Postgres ธรรมดาจะช้า/โต)
2. **Dashboard 100 คน** — render ฝั่ง client (Chart.js) หรือ cache ฝั่ง server + query cache — กัน DB พังตอนดูพร้อมกัน
3. **Backup อัตโนมัติรายวัน** ไป NAS — sensor ไหลตลอด อย่าเสี่ยง
4. **UPS + สำรองไฟ** — ข้อมูลต่อเนื่อง เสียหายแล้วกู้ยาก

## 6. สรุปความเพียงพอ

| สเปคที่วาง | เทียบคำแนะนำ | ผล |
|---|---|---|
| CPU Ryzen 7/i7 8C | 8 cores | ✅ พอดี (i5 พอ, Ryzen 9 เผื่อ) |
| RAM 32 GB | 16 GB | ✅ เหลือเฟือ |
| M.2 512 (OS) + SSD 1TB (data) | 1TB data | ✅ ถูกต้อง |
| อายุการใช้งาน | — | 5+ ปี ไม่ต้องอัปเกรดกลางคัน |

**ถ้า user เยอะเกิน ~100 คน** → ย้ายขึ้น VPS (Docker พร้อมย้าย) — แก้แค่ IP/domain
