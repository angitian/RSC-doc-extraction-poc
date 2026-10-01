# -*- coding: utf-8 -*-
"""
Template-anchored extraction engine (generic).

The canonical blank form (.docx in backend/templates/) is the master template:
its fixed text is hardcoded boilerplate and its variable slots are marked with
{{key}} placeholders. Filled documents are extracted by explicit per-form
rules (anchors / delimiters declared in the template manifest) — the engine
cuts the hardcoded text away and keeps only the variable values, then
normalizes them into the standard extracted dict used by the rest of the
pipeline (rsc_main builder, rollup, Excel/PDF).

Rule types supported by a manifest:
  - line_regex      : first paragraph matching <pattern> (named groups -> keys)
  - line_startswith : first paragraph starting with <match>, then <pattern>
  - fulltext_regex  : regex over the joined paragraphs
  - prefix_cut      : paragraph starting with <start>; capture text after the
                      first <cut_through> token found in the body
  - special         : named handlers (requester_signature / requester_position)

Rule options:
  - only_if_empty   : skip when the target key already has a value
"""
from __future__ import annotations

import io
import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import docx

from ..normalizer.thai_utils import num_to_thai_baht, parse_thai_date
from .text_pipeline import DEFAULT_FIELDS, _parse_attachment_breakdown, _parse_schedule_activities

# Thai titles used to detect a signature line like "(นายรณกร อำพันธ์ศรี)"
# Note: manifest regexes must guard "ณ" with (?<!\S)ณ(?!\S) — the letter
# appears inside many Thai words (คุณภาพ/คุณ/ณัฐ...) and must not be treated
# as the ณ-location marker.
_NAME_TITLE = r"(?:นาย|นาง|นางสาว|ดร\.|ผศ\.|รศ\.|ศ\.)"
_SIG_RE = re.compile(rf"^\(?\s*({_NAME_TITLE})\s*(.+?)\)?$")


# ---------------------------------------------------------------------------
# Loading / normalization
# ---------------------------------------------------------------------------
def normalize_text(text: str) -> str:
    """Collapse all whitespace runs to a single space (Thai text has no spaces)."""
    return re.sub(r"\s+", " ", text or "").strip()


def doc_paragraphs(file_bytes: bytes) -> List[str]:
    """Non-empty paragraphs of a .docx document (as byte payload).

    Embedded line breaks (<w:br/>) become separate entries so rules that scan
    line by line (e.g. signature "(ชื่อ)" followed by "ตำแหน่ง") see clean rows.
    """
    doc = docx.Document(io.BytesIO(file_bytes))
    out: List[str] = []
    for p in doc.paragraphs:
        for part in (p.text or "").split("\n"):
            part = part.strip()
            if part:
                out.append(part)
    return out


def template_paragraphs(path) -> List[str]:
    """Normalized non-empty paragraphs of a template .docx (file path)."""
    doc = docx.Document(str(path))
    out: List[str] = []
    for p in doc.paragraphs:
        t = normalize_text(p.text)
        if t:
            out.append(t)
    return out


def extract_marker_keys(paragraphs: List[str]) -> List[str]:
    """Collect {{key}} markers from template paragraphs (for integrity checks)."""
    keys: List[str] = []
    for p in paragraphs:
        for m in re.finditer(r"\{\{([A-Za-z_0-9]+)\}\}", p):
            keys.append(m.group(1))
    return keys


# ---------------------------------------------------------------------------
# Detection (is this document an instance of the template?)
# ---------------------------------------------------------------------------
def detect(spec: Dict[str, Any], paragraphs: List[str]) -> float:
    """Return a match score 0..1.

    All required_anchors must be present as substrings; the score is the
    coverage of optional_anchors. 0.0 when a required anchor is missing.
    """
    text = " ".join(normalize_text(p) for p in paragraphs)
    required = spec.get("required_anchors") or []
    if not all(a in text for a in required):
        return 0.0
    optional = spec.get("optional_anchors") or []
    if not optional:
        return 1.0
    hits = sum(1 for a in optional if a in text)
    return hits / len(optional)


# ---------------------------------------------------------------------------
# Rule application
# ---------------------------------------------------------------------------
def _match_lines(paragraphs: List[str], pattern: str):
    rx = re.compile(pattern)
    for p in paragraphs:
        m = rx.search(p)
        if m:
            return m
    return None


def _match_line_startswith(paragraphs: List[str], match: str, pattern: str):
    rx = re.compile(pattern)
    for p in paragraphs:
        if p.startswith(match):
            m = rx.search(p)
            if m:
                return m
    return None


def _prefix_cut(paragraphs: List[str], rule: Dict[str, Any], raw: Dict[str, str]) -> None:
    """Capture the variable text after the fixed prefix of a narrative paragraph."""
    key = rule["key"]
    if raw.get(key):
        return
    start = rule.get("start", "")
    for p in paragraphs:
        if p.startswith(start):
            body = p[len(start):].lstrip()
            for tok in rule.get("cut_through") or []:
                idx = body.find(tok)
                if idx >= 0:
                    raw[key] = body[idx + len(tok):].strip()
                    return
            raw[key] = body
            return


def _apply_special(name: str, paragraphs: List[str], raw: Dict[str, str]) -> None:
    if name == "requester_signature":
        # First "(นาย/นาง/นางสาว ...)" line after the closing จึงเรียนมา.
        if raw.get("requester_name"):
            return
        start = next((i for i, p in enumerate(paragraphs) if p.startswith("จึงเรียนมา")), None)
        if start is None:
            return
        for p in paragraphs[start:]:
            m = _SIG_RE.search(p)
            if m:
                raw["requester_name"] = f"{m.group(1)}{m.group(2).strip()}".strip("() ")
                return
        return
    elif name == "requester_position":
        # The short non-name line right after the requester signature line.
        if raw.get("requester_position"):
            return
        start = next((i for i, p in enumerate(paragraphs) if p.startswith("จึงเรียนมา")), 0)
        name_idx = None
        for i in range(start, len(paragraphs)):
            if _SIG_RE.search(paragraphs[i]):
                name_idx = i
                break
        if name_idx is None:
            return
        for p in paragraphs[name_idx + 1: name_idx + 4]:
            if p and not _SIG_RE.search(p) and len(p) < 60:
                raw["requester_position"] = p
                return


def extract_rules(spec: Dict[str, Any], paragraphs: List[str]) -> Tuple[Dict[str, str], List[str]]:
    """Apply the manifest field rules, returning raw slot values + warnings."""
    raw: Dict[str, str] = {}
    full_text = "\n".join(paragraphs)
    warnings: List[str] = []

    for rule in spec.get("fields") or []:
        key = rule.get("key")
        if rule.get("only_if_empty") and key and raw.get(key):
            continue
        rtype = rule.get("type")
        try:
            if rtype == "line_regex":
                m = _match_lines(paragraphs, rule["pattern"])
            elif rtype == "line_startswith":
                m = _match_line_startswith(paragraphs, rule["match"], rule["pattern"])
            elif rtype == "fulltext_regex":
                m = re.search(rule["pattern"], full_text)
            elif rtype == "prefix_cut":
                _prefix_cut(paragraphs, rule, raw)
                continue
            elif rtype == "special":
                _apply_special(rule.get("name", ""), paragraphs, raw)
                continue
            else:
                warnings.append(f"rule type ที่ไม่รู้จัก: {rtype}")
                continue

            if not m:
                continue
            groups = m.groupdict()
            if groups:
                for k, v in groups.items():
                    if v is not None and str(v).strip():
                        raw[k] = str(v).strip()
            elif key and m.lastindex:
                raw[key] = m.group(1).strip()
            elif key:
                raw[key] = m.group(0).strip()
        except re.error as e:  # noqa: BLE001 — bad manifest pattern must not crash requests
            warnings.append(f"pattern ผิดพลาด ({rule.get('key', '?')}): {e}")

    return raw, warnings


# ---------------------------------------------------------------------------
# Post-processing / normalization
# ---------------------------------------------------------------------------
def _parse_schedule_dates(schedule_text: str) -> List[Any]:
    """Parse '1-31 ตุลาคม 2569' / '3, 10, 14 และ 27 สิงหาคม 2569' / single dates."""
    s = (schedule_text or "").strip()
    if not s:
        return []

    # Range: "1-31 ตุลาคม 2569" | "1 ถึง 31 ตุลาคม 2569"
    m = re.match(r"^(\d{1,2})\s*(?:[-–ถึง])\s*(\d{1,2})\s+([^\s\d]+)\s+(\d{2,4})$", s)
    if m:
        d1 = parse_thai_date(f"{m.group(1)} {m.group(3)} {m.group(4)}")
        d2 = parse_thai_date(f"{m.group(2)} {m.group(3)} {m.group(4)}")
        return [d for d in (d1, d2) if d]

    # Day list ending with month+year: "3, 10, 14, 17, 21 และ 27 สิงหาคม 2569"
    # or a wordy range: "15 สิงหาคม 2569 ถึงวันที่ 20 สิงหาคม 2569"
    m = re.match(r"^(.*?)([^\s\d]+)\s+(\d{2,4})$", s)
    if m:
        head, mon, yr = m.group(1), m.group(2), m.group(3)
        days = [int(x) for x in re.split(r"[\s,และ]+", head) if x.strip().isdigit() and 1 <= int(x) <= 31]
        if days:
            return [d for d in (parse_thai_date(f"{day} {mon} {yr}") for day in days) if d]

    # Tolerant range: "D1-D2 เดือน ปี" embedded in trailing text (capture may be
    # polluted by clauses after the date, e.g. "... โดยมีกลุ่มเป้าหมายประกอบด้วย ...")
    # guard day<=31 กัน false positive จากเลขปี (เช่น "2569 ถึง" ต้องไม่จับเป็น "69 ถึง")
    m = re.search(r"(\d{1,2})\s*(?:[-–ถึง])\s*(\d{1,2})\s+([^\s\d]+)\s+(\d{2,4})", s)
    if m and int(m.group(1)) <= 31 and int(m.group(2)) <= 31:
        d1 = parse_thai_date(f"{m.group(1)} {m.group(3)} {m.group(4)}")
        d2 = parse_thai_date(f"{m.group(2)} {m.group(3)} {m.group(4)}")
        return [d for d in (d1, d2) if d]

    d = parse_thai_date(s)
    return [d] if d else []


def postprocess(raw: Dict[str, str], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Merge defaults + raw slots and derive the normalized extracted dict."""
    ext: Dict[str, Any] = dict(DEFAULT_FIELDS)
    ext.update(defaults or {})
    ext.update({k: v for k, v in raw.items() if v})

    # ---- วันที่หนังสือ -> ISO + ปีงบประมาณ ----
    d = parse_thai_date(ext.get("doc_date") or "")
    if d:
        ext["doc_date_iso"] = d.strftime("%Y-%m-%d")
        ext["budget_year"] = str((d.year + 543) % 100)

    # ---- เลขที่หนังสือ (tail + seq) ----
    if ext.get("doc_number"):
        val = str(ext["doc_number"]).strip()
        if not val.startswith("อว"):
            val = f"อว {val}"
        ext["doc_number"] = val
        num_run = re.search(r"\d[\d\.]*(?:\/[0-9\.\/]*)?", val)
        if num_run:
            tail = num_run.group(0).strip(" .")
            if tail.endswith("/"):
                yr = ext.get("budget_year") or str((date.today().year + 543) % 100)
                tail = f"{tail}{yr}"
            ext["doc_number_tail"] = tail
        else:
            ext["doc_number_tail"] = val.replace("อว", "").strip()

        seq = re.search(r"7608\.8(?:\.1)?\/([^\/\s]+)", val)
        if seq:
            ext["doc_seq_num"] = seq.group(1).strip()
        else:
            seq2 = re.search(r"\/([^\/\s]+)(?:\/\d{2})?", val)
            if seq2:
                ext["doc_seq_num"] = seq2.group(1).strip()

    # ---- เรื่อง / ชื่อโครงการ (ตัด prefix boilerplate) ----
    title = str(ext.get("project_title") or "").strip()
    cleaned = re.sub(
        r"^(?:ขออนุมัติ|ขออนุมัติดำเนินงาน|ขออนุมัติเบิกจ่าย|ดำเนินงาน)\s*", "", title
    ).strip()
    ext["project_title"] = cleaned or title

    # ---- สถานที่ / จังหวัด ----
    loc = str(ext.get("location_name") or "").strip()
    loc = re.sub(r"\s*(?:ต\.|ตำบล|อ\.|อำเภอ|จ\.|จังหวัด).*$", "", loc).strip()
    prov = str(ext.get("province_name") or "").strip()
    prov = re.sub(r"^(?:จังหวัด|จ\.)\s*", "", prov).strip()
    ext["location_name"] = loc
    ext["province_name"] = prov
    if loc and prov:
        ext["location_province"] = f"ณ {loc} จ.{prov}"
    elif loc:
        ext["location_province"] = f"ณ {loc}"

    # ---- ช่วงวันที่ ----
    dates = _parse_schedule_dates(ext.get("schedule_text") or "")
    if dates:
        ext["start_date_iso"] = min(dates).strftime("%Y-%m-%d")
        ext["end_date_iso"] = max(dates).strftime("%Y-%m-%d")

    # ---- วงเงิน ----
    amt = str(ext.get("budget_amount") or "").replace(",", "").strip()
    ext["budget_amount"] = amt
    if ext.get("budget_text"):
        bt = str(ext["budget_text"]).strip()
        ext["budget_text"] = f"({bt})" if not bt.startswith("(") else bt
    elif amt:
        auto = num_to_thai_baht(amt)
        if auto:
            ext["budget_text"] = f"({auto})"

    return ext


# ---------------------------------------------------------------------------
# Top-level extraction
# ---------------------------------------------------------------------------
def extract_with_template(file_bytes: bytes, spec: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Extract a filled document against one template spec."""
    paragraphs = doc_paragraphs(file_bytes)
    raw, warnings = extract_rules(spec, paragraphs)
    ext = postprocess(raw, spec.get("defaults") or {})

    full_text = paragraphs
    # ตารางค่าใช้จ่าย + กำหนดการ: reuse the hardened section parsers
    ext["breakdown"] = _parse_attachment_breakdown(full_text)
    ext["schedule_activities"] = _parse_schedule_activities(full_text, ext)

    # ตรวจสอบความสมเหตุสมผลหลังสกัด: เรื่อง/วันที่ต้องไม่ว่างพร้อมกัน
    if not ext.get("project_title") and not ext.get("doc_date"):
        warnings.append("template extraction ได้ผลว่าง — เอกสารอาจไม่ใช่ฟอร์มนี้")
    return ext, warnings
