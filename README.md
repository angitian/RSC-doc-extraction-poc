# RSC-doc-extraction-poc

PoC สำหรับดึงข้อมูลจากเอกสารบันทึกข้อความ (.docx) ของมหาวิทยาลัย พร้อมสร้าง Word / PDF / Excel แบบอัตโนมัติ ผ่าน Streamlit

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Cloud

1. Create a GitHub repository named `RSC-doc-extraction-poc`
2. Push the following files:
   - `app.py`
   - `requirements.txt`
   - `kmutt_logo.png`
   - `README.md`
   - `.gitignore`
3. Go to [share.streamlit.io](https://share.streamlit.io) and connect the repository
4. Set the main file to `app.py` (or rename it to `streamlit_app.py`)

## Optional: Thai font for PDF

If you want Thai text in the exported PDF to render correctly, place a Thai TrueType font such as `THSarabunNew.ttf` or `Sarabun-Regular.ttf` in the repository root. The app will look for those files automatically.
