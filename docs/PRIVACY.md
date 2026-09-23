# นโยบายความเป็นส่วนตัว (Privacy Policy) — RSC Doc → Smart Data

_อัปเดตล่าสุด: 23 กันยายน 2569_

## ภาษาไทย

### 1. บทนำ
ส่วนขยาย Chrome "RSC Doc → Smart Data" (ต่อไปนี้ "ส่วนขยาย") พัฒนาเพื่อช่วยบุคลากรในหน่วยงาน
สกัดข้อมูลจากเอกสารราชการ (.docx / .pdf / .xlsx) แล้วกรอกข้อมูลลงแบบฟอร์มเว็บราชการ
`https://rsc-approval.kmutt.ac.th/` โดยอัตโนมัติ

### 2. ข้อมูลที่ส่วนขยายจัดการ
- **ไฟล์เอกสารที่ผู้ใช้เลือก** — ไฟล์ .docx/.pdf/.xlsx ที่ผู้ใช้ลาก/เลือกเข้าในส่วนขยาย
  เพื่อให้ระบบสกัดข้อมูล (เช่น ชื่อโครงการ, ชื่อ-นามสกุล, ตำแหน่ง, วันที่, วงเงิน/ค่าใช้จ่าย)
- **ข้อมูลที่สกัดได้จากเอกสาร** — ข้อมูลส่วนบุคคลที่ปรากฏในเอกสาร (ชื่อ, ตำแหน่ง, หน่วยงาน)
  และข้อมูลงบประมาณ/ค่าใช้จ่าย
- **ชื่อไฟล์** และขนาดไฟล์
- **การตั้งค่าภายในเครื่อง** — API URL ที่ผู้ใช้บันทึก (เก็บใน `chrome.storage` ของเบราว์เซอร์เท่านั้น)

### 3. การใช้และการส่งข้อมูล
- เอกสารที่ผู้ใช้เลือกจะถูกส่งผ่าน **HTTPS** ไปยังเซิร์ฟเวอร์ประมวลผลของส่วนขยาย
  (`https://rsc-extraction-api.onrender.com`) เพื่อทำการสกัดและสร้างคำสั่งกรอกแบบฟอร์ม
- **เซิร์ฟเวอร์ไม่เก็บไฟล์หรือข้อมูลถาวร** — ประมวลผลแบบ stateless แล้วส่งผลกลับมาทันที
- ข้อมูลที่สกัดได้จะถูกกรอกลงแบบฟอร์มเว็บราชการ **เฉพาะเมื่อผู้ใช้กดปุ่ม "ยิงข้อมูลลงแบบฟอร์ม"** เท่านั้น

### 4. การแชร์ข้อมูล
- **ไม่มีการขายหรือแชร์ข้อมูลให้บุคคลที่สาม** ในเชิงพาณิชย์
- ข้อมูลจะถูกส่งไปยังเว็บราชการปลายทาง (`rsc-approval.kmutt.ac.th`) ตามคำสั่งของผู้ใช้เท่านั้น
- ไม่มีการส่งข้อมูลไปยัง Google หรือผู้ให้บริการอื่น

### 5. การเก็บรักษา
- ส่วนขยาย**ไม่จัดเก็บเอกสาร**ในฐานข้อมูลถาวร — ข้อมูลจะอยู่ในความจำระหว่างการใช้งานครั้งนั้นเท่านั้น
- การตั้งค่า (API URL) เก็บในเครื่องผู้ใช้ (chrome.storage) — ผู้ใช้ลบได้โดยการล้างข้อมูลส่วนขยาย

### 6. ความปลอดภัย
- การรับ-ส่งทั้งหมดผ่าน HTTPS
- ส่วนขยายไม่มีการรันโค้ดจากภายนอก (no remote code)
- ขอสิทธิ์เฉพาะที่จำเป็นต่อการทำงาน (ดูรายการสิทธิ์ใน Chrome Web Store)

### 7. สิทธิ์ของผู้ใช้
- ผู้ใช้สามารถ**ถอนสิทธิ์/ลบส่วนขยาย**ได้ทุกเมื่อผ่านการตั้งค่า Chrome
- ผู้ใช้สามารถเลือกไฟล์/กดยิงข้อมูลได้เองทุกครั้ง — ไม่มีการทำงานอัตโนมัติโดยไม่ได้รับความยินยอม

### 8. การติดต่อ
หากมีข้อสงสัยเกี่ยวกับนโยบายนี้ หรือต้องการขอให้ลบข้อมูล ติดต่อหน่วยงานผู้ดูแลระบบ:
- **หน่วยงาน:** สถาบันพัฒนาและฝึกอบรมโรงงานต้นแบบ (สรบ.) มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี

---

## English Summary

### RSC Doc → Smart Data — Chrome Extension Privacy Policy

**Data handled:**
- Document files (.docx/.pdf/.xlsx) the user chooses to upload for extraction
- Data extracted from those documents (names, positions, dates, amounts/expenses)
- Filenames and file sizes
- Local settings (API URL stored only in the browser's `chrome.storage`)

**How data is used:**
- Documents are sent over **HTTPS** to the extension's processing server
  (`https://rsc-extraction-api.onrender.com`) for extraction and form-fill instruction generation
- The server is **stateless — no files or data are stored persistently**
- Extracted data is submitted to the government portal
  (`https://rsc-approval.kmutt.ac.th/`) **only when the user clicks the fill button**

**Sharing:**
- No sale or sharing of data to third parties for commercial purposes
- Data is sent only to the government portal per the user's explicit action

**Retention & security:**
- No persistent storage of documents; all processing is transient
- All communication over HTTPS; no remote code execution

**User rights:**
- The extension can be uninstalled/revoked at any time via Chrome settings
- All fill actions are user-initiated

**Contact:** The unit administrator (RSC office), King Mongkut's University of Technology Thonburi (KMUTT).
