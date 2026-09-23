# System Specification: Research Budget & Expense Reconciliation Engine
# (RSC-Suite — ระบบบัญชีและกระทบยอดเงินยืมวิจัย)

> แผน/สเปกสำหรับ AI IDE (Claude Code / Cursor / Windsurf / Devin) — ยัง **ไม่ implement**
> ระบบตัวช่วยจัดการกระทบยอดเงินยืมวิจัย (Loan Settlement Assistant) สำหรับนักวิจัย
> และ Admin ประจำสำนักงานย่อย เพื่อลดภาระการคัดแยกบิลและทำรายงานบัญชีส่งส่วนกลาง

## 1. Executive Summary & Core Constraints

### กฎเหล็กหน้างาน (Regulatory & Operational Constraints)

1. **การถัวจ่าย (Pool & Reallocate):** สัญญายืมเงินได้รับอนุมัติแบบ "ขอถัวจ่ายทุกรายการ"
   มาตั้งแต่ต้น — ไม่ต้องมีระบบสร้างบันทึกขออนุมัติถัวจ่าย
2. **ขอบเขตการคำนวณ:** ยอดรวมบิลต้อง **ไม่เกิน** ยอดเงินยืมที่ได้รับอนุมัติ

   $$\sum \text{Amount}_{\text{selected}} \le \text{Loan Amount}$$

   โดยมีเงื่อนไข Optimization: $(\text{Loan Amount} - \sum \text{Amount}_{\text{selected}})$
   ต้องมีค่าน้อยที่สุด (เงินเหลือส่งคืนน้อยที่สุด เพื่อไม่ให้เกิดการควักเนื้อ)
3. **การแยกครุภัณฑ์ (Asset Isolation):** หมวดครุภัณฑ์ (`is_asset == True`) ต้องถูกล็อก
   ห้ามนำเข้ามาคำนวณในถังถัวจ่ายโดยเด็ดขาด
4. **Data Entry Strategy:** ใช้ Excel เป็นอินพุตหลัก (Flat Table คีย์มือ) — เลี่ยง OCR
   เนื่องจากความซับซ้อนของบิลเงินสดไทย

## 2. System Architecture

```
[Excel Input: Flat Receipt Log]
         │
         ▼
[Ingestion API (FastAPI)] ──► [Database Layer (PostgreSQL / SQLite)]
                                    │
                                    ├── Projects & Loan Requests
                                    └── Actual Receipts / Expenses
                                    │
         ┌──────────────────────────┴──────────────────────────┐
         ▼                                                     ▼
[Reconciliation Core Engine]                           [Export & Reporting]
- Knapsack / Greedy Matching Algorithm                 - Excel Template Exporter (openpyxl)
- Real-time Balance Tracker                            - Consolidated PDF Annex (fpdf2)
- State Lock (Prevent Double-Claim)                    - Admin Analytics Dashboard
```

> หมายเหตุ: ใช้ stack เดียวกับระบบเดิม (FastAPI / openpyxl / fpdf2) — reuse ได้

## 3. Data Contract & Schema Specification

### 3.1 Input Excel Format (Receipt Log Template)

ตาราง 1 แถว = 1 ใบเสร็จ (ไม่จำเป็นต้องแตกรายการย่อย เว้นแต่จะฉีกยอดข้ามโครงการ)

| Column Name | Type | Description | Example |
|---|---|---|---|
| `receipt_date` | Date (DD/MM/YYYY) | วันที่ตามใบเสร็จ (ใช้ตรวจขอบเขตสัญญา) | `18/08/2569` |
| `vendor` | String | ชื่อร้านค้า/ผู้รับเงิน | `MR DIY`, `สมาร์ทเทค` |
| `bill_ref` | String (Optional) | เลขที่บิล / ลำดับที่เขียนบนหัวกระดาษ | `#012`, `รอบวางท่อ` |
| `description` | String | สรุปรายการพอสังเขป | `เซนเซอร์ T/RH 15 หัว` |
| `amount` | Decimal / Float | ยอดเงินสุทธิรวม VAT และค่าส่ง | `4173.00` |
| `category` | Enum | ค่าวัสดุ, ค่าที่พัก, ค่าตอบแทน, ค่าพาหนะ, ค่าใช้สอย, ครุภัณฑ์ | `ค่าวัสดุ` |
| `is_asset` | Boolean | เป็นครุภัณฑ์หรือไม่ (Default: False) | `False` |

### 3.2 Database Models (SQLAlchemy ORM)

```python
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), index=True)          # เช่น FF68, FF69
    name = Column(String(255), nullable=False)
    funding_source = Column(String(150))            # แหล่งทุน
    fiscal_year = Column(Integer, default=2569)

class LoanRequest(Base):
    __tablename__ = "loan_requests"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    doc_no = Column(String(100), index=True)       # เลขที่สัญญายืมเงิน / บันทึกข้อความ
    researcher_name = Column(String(150), index=True)
    destination = Column(String(200))
    start_date = Column(Date)
    end_date = Column(Date)
    approved_amount = Column(Numeric(12, 2), nullable=False)  # ยอดเงินยืม
    status = Column(String(50), default="APPROVED")           # APPROVED, SETTLED, CLOSED
    created_at = Column(DateTime, default=datetime.utcnow)

    expenses = relationship("ActualExpense", back_populates="loan_request")

class ActualExpense(Base):
    __tablename__ = "actual_expenses"
    id = Column(Integer, primary_key=True, index=True)
    loan_request_id = Column(Integer, ForeignKey("loan_requests.id"), nullable=True)  # NULL = Unassigned Pool
    receipt_date = Column(Date, nullable=False)
    vendor = Column(String(150), nullable=False)
    bill_ref = Column(String(50))
    description = Column(String(255))
    category = Column(String(100), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    is_asset = Column(Boolean, default=False)
    status = Column(String(50), default="UNASSIGNED")         # UNASSIGNED, ALLOCATED, CLEARED
    created_at = Column(DateTime, default=datetime.utcnow)

    loan_request = relationship("LoanRequest", back_populates="expenses")
```

## 4. Business Logic & Core Algorithms

### 4.1 Ingestion Modes

1. **Single-Batch Direct Mode (เคลียร์เฉพาะกิจ):** อัปโหลดไฟล์ Excel พร้อมระบุ
   `loan_request_id` → ระบบผูกบิลเข้าสัญญานั้นโดยตรง คำนวณยอดคงเหลือทันที
2. **Holding Pool Mode (คลังบิลกลาง):** อัปโหลดบิลสะสมโดยยังไม่ระบุสัญญา
   (`loan_request_id = NULL`, `status = 'UNASSIGNED'`) เพื่อรอหยิบไปใช้ภายหลัง

### 4.2 Auto-Matching Algorithm (Knapsack / Subset Sum Variant)

- **Input:** รายการบิลที่ `status == 'UNASSIGNED'`, `is_asset == False`,
  และ `receipt_date` อยู่ในช่วงสัญญา
- **Target:** `approved_amount`
- **Objective:** ค้นหาชุดบิล $S$ ที่ทำให้:

  $$\sum_{i \in S} \text{amount}_i \le \text{approved\_amount} \quad \text{and} \quad \text{approved\_amount} - \sum_{i \in S} \text{amount}_i \to 0$$

- **Double-Claim Prevention:** เมื่อกดยืนยันเคลียร์สัญญา บิลทั้งหมดในชุด $S$ จะถูกเปลี่ยน
  `status = 'CLEARED'` และผูก `loan_request_id` ถาวร — ระบบไม่สามารถหยิบซ้ำได้

## 5. API Endpoints Plan (FastAPI)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/bills/upload` | Multipart form รับ `.xlsx` เพื่อ Import บิลเข้าสู่ DB (ระบุ `loan_id` หรือเข้า Pool) |
| `GET` | `/api/v1/bills/pool` | ดึงรายการบิลที่ยังไม่ได้ใช้ (`status = 'UNASSIGNED'`) |
| `POST` | `/api/v1/reconcile/auto-match` | รัน Knapsack อัลกอริทึม ส่งคืนรายการบิลแนะนำที่บวกกันแล้วได้ยอดใกล้เคียงที่สุด |
| `POST` | `/api/v1/reconcile/commit` | บันทึกการเลือกบิลเข้าสัญญา เปลี่ยนสถานะเป็น `CLEARED` |
| `GET` | `/api/v1/reports/summary` | ข้อมูลสรุปภาพรวมสำหรับ Admin Dashboard (แยกตามนักวิจัย/โครงการ/หมวด) |
| `GET` | `/api/v1/reports/export-central-excel` | ใช้ `openpyxl` หยอดข้อมูลลงเทมเพลต Excel มาตรฐานของส่วนกลาง |

## 6. Phased Implementation Roadmap

- [ ] **Phase 1: Database & Ingestion Scaffold**
  - ติดตั้ง SQLAlchemy + Alembic ใน `backend/app/db/`
  - สร้าง Parser สำหรับอ่าน Excel Flat Format ด้วย `pandas` หรือ `openpyxl`
  - สร้าง CRUD endpoints สำหรับจัดการ Receipt และ LoanRequest
- [ ] **Phase 2: Reconciliation Logic**
  - พัฒนาโมดูล `matcher.py` (Subset Sum / Greedy Optimizer)
  - ทำ Endpoint `/reconcile/auto-match` พร้อมระบบ Manual Override
- [ ] **Phase 3: Exporters & Templates**
  - สร้าง Service หยอดข้อมูลลงไฟล์เทมเพลตราชการ (Sheet 2/Sheet 3)
  - รันเลขลำดับบิลอัตโนมัติ (1, 2, 3...) ให้ตรงกับตารางแนบ
- [ ] **Phase 4: Admin Dashboard & Extension Integration**
  - สร้างหน้า UI น้ำหนักเบา (Tailwind + Vanilla JS หรือ Shadcn UI)
  - เชื่อมต่อ Side Panel Extension ให้เรียก API ก้อนนี้ได้แบบ Seamless

## 7. หมายเหตุเชื่อมระบบเดิม

- Reuse: `fastapi`, `openpyxl`, `fpdf2` จาก backend เดิม
- ระบบนี้เป็นอีก service/โฟลเดอร์ — ไม่แตะ extraction engine
- Extension (Side Panel) ต่อยอดได้: เพิ่ม tab "บิล/เคลียร์" เรียก API นี้
