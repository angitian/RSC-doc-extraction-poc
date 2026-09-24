# -*- coding: utf-8 -*-
"""
Static DOM-mapping compatibility checker.

Verifies that every DOMAction in the rsc_main mapping resolves against a
target HTML snapshot (saved portal page) and/or a captured CAPTURE_FORM JSON,
so portal DOM drift is caught without opening a browser.

Usage:
    python tests/check_mapping_vs_dom.py <docx-or-pdf> [options]

Options:
    --html <path>            saved portal HTML (e.g. RSC Smart Approval - ....html)
    --snapshot <path>        captured CAPTURE_FORM JSON (array of controls)
    --expect-dangling <sel>  selector/label/button-text allowed to be missing
                             (repeatable; e.g. #expense-description-0)
    --mode <mode>            full_table (default) | annex_pdf

Exit code 0 when every mapping entry resolves (or is declared dangling).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.extraction.dispatcher import extract_file
from app.generators.field_mapper import build_field_mappings


# ---------------------------------------------------------------------------
# DOM model helpers (regex-based — enough for static analysis)
# ---------------------------------------------------------------------------
def _ids_in_html(html: str) -> set:
    return set(re.findall(r'id="([^"]+)"', html))


def _names_in_html(html: str) -> set:
    return set(re.findall(r'name="([^"]+)"', html))


def _has_label_text(html: str, text: str) -> bool:
    if not text:
        return False
    esc = re.escape(text)
    return bool(re.search(esc, html))


def _has_button_text(html: str, text: str) -> bool:
    """Button-ish text anywhere in the snapshot (buttons/aria/visible labels)."""
    if not text:
        return False
    esc = re.escape(text)
    return bool(re.search(esc, html))


def _has_file_input(html: str) -> bool:
    return 'type="file"' in html or "type='file'" in html


def _selector_target(selector: str) -> str | None:
    """Extract the primary id/name a CSS selector points at, if simple."""
    s = selector.strip()
    if s.startswith("#"):
        return s[1:].split(" ")[0].split(":")[0]
    if s.startswith("["):
        m = re.search(r'id="([^"]+)"', s)
        if m:
            return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------
class DOMProbe:
    def __init__(self, html: str = "", snapshot: list | None = None):
        self.html = html
        self.snapshot = snapshot or []
        self.ids = _ids_in_html(html) if html else set()
        self.names = _names_in_html(html) if html else set()
        self.snap_ids = {str(c.get("id", "")).lower() for c in self.snapshot if c.get("id")}
        self.snap_names = {str(c.get("name", "")).lower() for c in self.snapshot if c.get("name")}
        self.snap_labels = {str(c.get("label", "")).lower() for c in self.snapshot if c.get("label")}

    def id_present(self, cid: str) -> bool:
        if cid in self.ids:
            return True
        return cid.lower() in self.snap_ids

    def name_present(self, name: str) -> bool:
        if name in self.names:
            return True
        return name.lower() in self.snap_names

    def label_present(self, text: str) -> bool:
        if not text:
            return False
        if self.html and _has_label_text(self.html, text):
            return True
        return text.lower() in self.snap_labels

    def button_present(self, text: str) -> bool:
        if not text:
            return False
        if self.html and _has_button_text(self.html, text):
            return True
        return text.lower() in self.snap_labels

    def file_input_present(self) -> bool:
        if self.html and _has_file_input(self.html):
            return True
        return any(c.get("type") == "file" for c in self.snapshot)

    def radio_scope_present(self, name: str, label: str) -> bool:
        """Radio group + a label matching the desired option text."""
        if not name:
            return self.label_present(label)
        has_name = self.name_present(name) or self.id_present(name)
        return has_name and self.label_present(label)


def check_action(probe: DOMProbe, act: dict) -> tuple[bool, str]:
    """Return (ok, detail)."""
    a = act.get("action", "set_value")
    selector = act.get("selector") or ""
    label = act.get("label") or ""
    value = act.get("value") or ""
    meta = act.get("meta") or {}
    scope = meta.get("scope_name") or ""

    if a == "file_attach":
        return (probe.file_input_present(), "file input")

    if a in ("click_button", "ensure_click"):
        texts = meta.get("texts") or [value]
        found = any(probe.button_present(t) for t in texts)
        # verify_selector: ถ้าอยู่ใน DOM แล้ว = action จะ skip (ถือว่า OK)
        vs = meta.get("verify_selector")
        if not found and vs:
            tgt = _selector_target(vs)
            if tgt and (probe.id_present(tgt) or probe.name_present(tgt)):
                found = True
        return (found, f"button text {'/'.join(texts)!r}")

    if a == "wait":
        return (True, "wait")

    if a == "click" and scope and label:
        return (probe.radio_scope_present(scope, label), f"radio scope={scope} label={label!r}")

    if a == "set_radio":
        # selector may be the radio input id/name
        tgt = _selector_target(selector)
        if tgt and (probe.id_present(tgt) or probe.name_present(tgt)):
            return (True, f"radio {tgt}")
        return (probe.label_present(label), f"radio label={label!r}")

    # set_value / set_select / click
    tgt = _selector_target(selector) if selector else None
    if tgt:
        ok = probe.id_present(tgt) or probe.name_present(tgt)
        if ok:
            return (True, f"#{tgt}")
        # container selectors like article:has(#schedule-date-0): probe inner id
        if ":has(" in selector:
            inner = re.search(r"#([\w-]+)", selector)
            if inner and probe.id_present(inner.group(1)):
                return (True, f"container :has(#{inner.group(1)})")
        return (False, f"selector {selector!r}")
    if label:
        return (probe.label_present(label), f"label {label!r}")
    return (False, f"no selector/label ({selector!r})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows console cp437 -> UTF-8
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("doc", help="sample .docx/.pdf to build mappings from")
    ap.add_argument("--html", default="", help="saved portal HTML")
    ap.add_argument("--snapshot", default="", help="captured CAPTURE_FORM JSON")
    ap.add_argument("--expect-dangling", nargs="+", default=[],
                    help="selector/label/button-text allowed to be missing (space-separated)")
    ap.add_argument("--mode", default="full_table", choices=["full_table", "annex_pdf"])
    args = ap.parse_args()

    raw = open(args.doc, "rb").read()
    ext = os.path.splitext(args.doc)[1].lower()
    extracted, doc_type, confidence = extract_file(raw, ext)

    snapshot = []
    if args.snapshot:
        with open(args.snapshot, encoding="utf-8") as f:
            snapshot = json.load(f)

    mappings, warnings, info = build_field_mappings(
        extracted, args.mode, "https://rsc-approval.kmutt.ac.th/approval", page_snapshot=snapshot)
    if not mappings:
        print("NO MAPPINGS — profile not resolved")
        return 2

    probe = DOMProbe(html=open(args.html, encoding="utf-8").read() if args.html else "", snapshot=snapshot)
    expected_dangling = set(args.expect_dangling)

    print(f"doc_type   : {doc_type} (conf {confidence})  profile: {info.get('profile_id')}")
    print(f"mappings   : {len(mappings)}  mode={args.mode}")
    print(f"DOM source : {'html+snapshot' if args.html and args.snapshot else ('html' if args.html else ('snapshot' if args.snapshot else 'NONE (only labels)'))}")
    print()

    dangling = []
    rows = []
    for i, act in enumerate(mappings):
        if hasattr(act, "model_dump"):
            act = act.model_dump()
        ok, detail = check_action(probe, act)
        tag = act.get("action", "?")
        loc = act.get("selector") or act.get("label") or detail
        rows.append((ok, tag, loc, detail))

    def is_declared(loc: str) -> bool:
        for e in expected_dangling:
            if loc == e or loc.startswith(e) or e in loc:
                return True
        return False

    for ok, tag, loc, detail in rows:
        mark = "OK " if ok else "?? "
        if not ok:
            if is_declared(loc):
                mark = "DK "  # declared dangling
            else:
                dangling.append((tag, loc, detail))
        print(f"  [{mark}] {tag:<11} {loc}")

    print()
    if dangling:
        print("DANGLING (unexpected - fix mapping or declare --expect-dangling):")
        for tag, loc, detail in dangling:
            print(f"  - {tag}: {loc}  ({detail})")
        return 1
    print("ALL RESOLVED (dangling only as declared)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
