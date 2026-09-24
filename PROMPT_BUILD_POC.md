# Technical Specification & Context: Streamlit PoC (v.1) for DOCX Memo Extractor & Chrome Auto-Fill Extension

## 1. System Goal & Core Value Proposition (v.1)
- **Problem:** ระบบเดิมใช้ Wizard Form / Accordion หลายขั้นตอน บังคับให้ผู้ใช้กรอกข้อมูลทีละช่องบนเว็บปลายทางโดยไม่มีระบบ Auto-fill จากเอกสาร DOCX เดิม
- **Solution (v.1):** 
  1. สกัดข้อมูลจาก DOCX บันทึกข้อความผ่าน [app_v1.py](file:///e:/project/doc%20to%20smart%20data/app_v1.py)
  2. ส่งออกโครงสร้าง JSON Standard
  3. ใช้งาน Chrome Extension (v.1) ในการอ่านค่า JSON และ Auto-Fill ลงฟิลด์ฟอร์มบนเว็บปลายทางให้อัตโนมัติ

---

## 2. File & Project Structure (v.1)
```
doc to smart data/
├── app_v1.py              # Main Streamlit Application v.1 (UI, Extraction, Live Preview, JSON Export)
├── PROMPT_BUILD_POC_v1.md # Technical Context & Specification v.1
├── requirements.txt       # Dependencies
└── extension_v1/          # Chrome Extension (v.1)
    ├── manifest.json      # Chrome Extension Manifest V3
    ├── popup.html         # Extension UI Modal
    ├── popup.js           # Clipboard reader & Message sender logic
    └── content.js         # Intelligent Form Injector & Auto-filler
```

---

## 3. Data Field Extraction & Mapping Standard (v.1)

| Field Key | Thai Label / Description | Target Input Selector / Aliases |
| :--- | :--- | :--- |
| `doc_number` | เลขที่หนังสือ | `doc_number`, `doc_no`, `document_no`, `เลขที่หนังสือ`, `ที่` |
| `doc_date` | วันที่หนังสือ | `doc_date`, `document_date`, `วันที่หนังสือ`, `วันที่` |
| `agency_name` | ส่วนงาน / หน่วยงาน | `agency_name`, `department`, `ส่วนงาน`, `หน่วยงาน` |
| `recipient_title` | เรียน (ผู้รับหนังสือ) | `recipient_title`, `เรียน`, `ผู้รับหนังสือ` |
| `requester_name` | ชื่อผู้ขออนุมัติ | `requester_name`, `applicant_name`, `ชื่อผู้ขอ`, `ผู้ขออนุมัติ` |
| `requester_position` | ตำแหน่งผู้ขออนุมัติ | `requester_position`, `position`, `ตำแหน่ง` |
| `project_title` | เรื่อง / ชื่อโครงการ | `project_title`, `subject`, `title`, `เรื่อง`, `ชื่อโครงการ` |
| `project_context` | บริบทโครงการ (ย่อหน้า 1) | `project_context`, `context`, `รายละเอียด`, `ความเป็นมา` |
| `project_objective` | วัตถุประสงค์ (ย่อหน้า 2) | `project_objective`, `objective`, `วัตถุประสงค์` |
| `action_details` | การดำเนินงาน | `action_details`, `action`, `การดำเนินงาน` |
| `location_name` | สถานที่ | `location_name`, `location`, `สถานที่` |
| `province_name` | จังหวัด | `province_name`, `province`, `จังหวัด` |
| `schedule_text` | วันที่/กำหนดการ | `schedule_text`, `schedule`, `กำหนดการ`, `ระยะเวลา` |
| `budget_amount` | วงเงินรวม (ตัวเลข) | `budget_amount`, `budget`, `amount`, `จำนวนเงิน`, `วงเงิน` |
| `budget_text` | วงเงินรวม (ตัวอักษร) | `budget_text`, `budget_str`, `จำนวนเงินตัวอักษร` |
| `acc_code` | รหัสงบประมาณ | `acc_code`, `budget_code`, `รหัสงบประมาณ` |

---

## 4. Chrome Extension (v.1) Installation & Usage

1. เปิด Chrome ไปที่ `chrome://extensions/`
2. เปิดใช้งาน **Developer mode** (โหมดผู้พัฒนา) มุมขวาบน
3. กด **Load unpacked** (โหลดส่วนขยายที่ถอดรหัสแล้ว)
4. เลือกโฟลเดอร์ `e:\project\doc to smart data\extension_v1`
5. เมื่อใช้งาน Streamlit `app_v1.py` ให้กดปุ่ม **สร้าง JSON Payload** แล้วคัดลอก JSON มาเปิดส่วนขยาย Chrome Extension แล้วกด **⚡ กรอกฟอร์มหน้าเว็บปลายทาง (Auto-Fill)**