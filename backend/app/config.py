# -*- coding: utf-8 -*-
"""Central configuration for the backend (ports, CORS, asset paths)."""
from __future__ import annotations

import os
from pathlib import Path

# Project layout
BASE_DIR = Path(__file__).resolve().parent          # backend/app
ASSETS_DIR = BASE_DIR / "assets"
FONT_THAI_PATH = ASSETS_DIR / "Sarabun-Regular.ttf"

# App port — works everywhere:
#   Render      -> $PORT (default 10000)
#   HuggingFace -> 7860 (default)
#   Cloud Run   -> $PORT (container port)
PORT = int(os.environ.get("PORT", "7860"))

# CORS: wildcard without credentials.
# chrome-extension:// origins cannot be listed one by one (unstable IDs during
# dev) — "*" + no credentials is the combination that works through the
# Hugging Face proxy (which may strip Access-Control-Allow-Credentials).
CORS_ALLOW_ORIGINS = ["*"]
CORS_ALLOW_METHODS = ["*"]
CORS_ALLOW_HEADERS = ["*"]

# Request limits
MAX_FILE_SIZE_MB = 20
ALLOWED_EXTENSIONS = {".docx", ".pdf"}

# Output names
ANNEX_FILENAME = "ประมาณการค่าใช้จ่ายและกำหนดการ.pdf"
EXCEL_FILENAME = "ข้อมูลโครงการและค่าใช้จ่าย.xlsx"

# Fallback location used when the memo has no explicit "ณ ..." clause.
# Unit-specific default (KMUTT RSC) — override via env vars if needed.
DEFAULT_LOCATION = os.environ.get("RSC_DEFAULT_LOCATION", "มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี")
DEFAULT_PROVINCE = os.environ.get("RSC_DEFAULT_PROVINCE", "กรุงเทพมหานคร")
USE_DEFAULT_LOCATION = os.environ.get("RSC_USE_DEFAULT_LOCATION", "1") != "0"
