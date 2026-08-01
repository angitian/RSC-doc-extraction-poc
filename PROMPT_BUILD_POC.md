# Technical Specification & Context: Streamlit PoC for DOCX Memo Extractor & Auto-Fill System

## 1. System Goal & Core Value Proposition
- **Problem:** ระบบเดิมใช้ Wizard Form / Accordion 5-7 ขั้นตอน บังคับให้ผู้ใช้กรอกข้อมูลมือทีละช่อง โดยไม่มีระบบ Auto-fill จากไฟล์ Word (DOCX) เดิม
- **Solution:** สร้าง PoC บน Streamlit เพื่อพิสูจน์แนวคิด: "Upload DOCX -> Auto-Extract & Map to Blocks -> Auto-fill Form & Live Preview -> Export to DB/Excel/JSON"

---

## 2. File & Project Structure Required
my-doc-extraction-poc/
├── app.py              # Main Application (UI, Logic, Auto-fill Mapping, Live Preview)
├── requirements.txt    # Python Dependencies (streamlit, python-docx, pandas, openpyxl)
└── PROMPT_BUILD_POC.md # This Context Specification File

---

## 3. Data Field Extraction & Mapping Rules

### Group A: Auto-Extractable Fields (จากไฟล์ DOCX บันทึกข้อความ)
1. **เลขที่หนังสือ (`doc_number`):** Regex แพทเทิร์น `อว\.?\s*\d+(\.\d+)*/.*` หรือข้อความหลัง "ที่"
2. **วันที่หนังสือ (`doc_date`):** ข้อความหลัง "วันที่" แปลงเป็น String/Date
3. **ชื่อ-นามสกุล ผู้ขอ (`requester_name`):** ข้อความในวงเล็บใต้บล็อกลายเซ็น เช่น `(นายรณกร อำพันธ์ศรี)`
4. **ตำแหน่ง ผู้ขอ (`requester_position`):** ข้อความบรรทัดถัดจากชื่อผู้ขอ เช่น `วิศวกร`
5. **เรื่อง / ชื่อโครงการ (`project_title`):** ข้อความหลังคำว่า "เรื่อง"
6. **บริบทโครงการ / ย่อหน้าแรก (`project_context`):** ย่อหน้าแรกที่ขึ้นต้นด้วย "ตามที่..."
7. **วัตถุประสงค์ & คำกริยา (`project_objective`):** ย่อหน้าที่ขึ้นต้นด้วย "ในการนี้..."
8. **สถานที่ & จังหวัด (`location_province`):** ข้อความหลัง "ณ ..." และ "จ...."
9. **วันที่ดำเนินงาน (`schedule_text`):** ช่วงวันที่ที่ระบุในเนื้อหาหรือตารางกำหนดการ
10. **วงเงินรวม (บาท) (`budget_amount`):** ตัวเลขรวมงบประมาณ เช่น `21200`
11. **วงเงินรวม (ตัวอักษร) (`budget_text`):** สกัดจากวงเล็บหลังตัวเลข หรือใช้ Logic แปลงตัวเลขอัตโนมัติ

### Group B: Manual Input / System Integration Fields (ผู้ใช้เลือก/กรอกเพิ่ม)
1. **รหัสงบประมาณ (`acc_code`):** Dropdown ให้ผู้ใช้เลือก (e.g. `ACC-2026-RD68`, `ACC-2026-SF01`)
2. **ปีงบประมาณ (`budget_year`):** Auto-fill จาก ACC Code ที่เลือก
3. **แหล่งงบประมาณ (`budget_source`):** Auto-fill จาก ACC Code ที่เลือก
4. **เอกสารแนบ (`attachment_pdf`):** File Uploader เพิ่มเติมสำหรับแนบ PDF

---

## 4. UI/UX Requirements for Streamlit App (`app.py`)

1. **Top Section (Smart Import Zone):**
   - File Uploader สำหรับลากไฟล์ DOCX มาวาง
   - เมื่ออัปโหลดไฟล์ ให้รัน `python-docx` สกัดข้อมูลตาม Rule Group A แล้วเขียนลง `st.session_state` ทันที

2. **Main Layout (Split Screen / 2 Columns):**
   - **Left Column (Form / Block Editor):**
     - แบ่งเป็น 5 Sections ตามฟอร์มเดิม (1. ข้อมูลทั่วไป, 2. ข้อมูลผู้ขอ, 3. รายละเอียดโครงการ, 4. สถานที่/วันที่, 5. วงเงิน)
     - ช่อง Input ทั้งหมดจะถูก **Auto-fill** จากข้อมูลที่สกัดได้
     - มี Dropdown `ACC Code` ใน Section 1 ให้ผู้ใช้เลือกเพิ่ม
     - รองรับการแก้ไขข้อมูลในกล่องข้อความ และ `st.data_editor` สำหรับตาราง
   - **Right Column (Live A4 Preview):**
     - เรนเดอร์กระดาษ A4 (HTML/CSS) พรีวิวบันทึกข้อความจริงแบบ Real-time
     - ข้อมูลใน A4 จะสะท้อนการเปลี่ยนแปลงจาก Form ฝั่งซ้ายมือทันที

3. **Export Section:**
   - ปุ่ม **Download JSON** (สำหรับส่งต่อให้ Database/API)
   - ปุ่ม **Download Excel** (สำหรับ Export ข้อมูลลงตาราง Excel)

---

## 5. Technical Requirements & Dependencies
- Use **Pure Python** with `streamlit`, `python-docx`, `pandas`, `openpyxl`.
- Avoid hardcoded local paths (Use `io.BytesIO` for uploaded files).
- Provide clean Error Handling if uploaded DOCX misses some sections.