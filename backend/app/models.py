# -*- coding: utf-8 -*-
"""
Pydantic schemas for the RSC extraction API.

Dynamic Mapping Paradigm: the extension never hard-codes DOM selectors.
The backend sends back a list of DOMAction instructions (selectors + actions)
so the content script can fill any target web form without an extension update.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DOMAction(BaseModel):
    """A single instruction for the content script to execute on the target page.

    action values supported by the content script engine:
      - "set_value"    : set text/number/date value on input/textarea
      - "set_select"   : select an <option> by value or by text containment
      - "set_radio"    : check a radio input (value is the radio value)
      - "click"        : click the first element matching selector
      - "click_button" : click a <button> whose visible text contains `value`
                         (optionally scoped inside `selector` container)
      - "file_attach"  : inject a File into <input type=file> (value = base64,
                         extra data passed via value_format / filename in `meta`)
      - "wait"         : wait `delay_ms` (used after row-add clicks)
    """

    selector: str = ""
    action: str = "set_value"
    value: Optional[str] = None
    # Thai label hint — the content script falls back to resolving the field
    # by its visible label when the CSS selector is stale (React auto-generated
    # IDs like `input-94` change on every portal build; labels stay stable).
    label: Optional[str] = None
    # Metadata key the value came from — lets the side panel override values
    # via the editable review card before filling.
    key: Optional[str] = None
    # When true, the content script skips filling if the field already has a
    # value (portal auto-fill from user profile / ACC must not be overwritten).
    skip_if_value_present: bool = False
    index: Optional[int] = None
    repeat: int = 1
    delay_ms: int = 150
    # Extra payload for special actions (e.g. file_attach filename / mime,
    # radio scope name)
    meta: Dict[str, Any] = Field(default_factory=dict)


class ExtractionResponse(BaseModel):
    """The master JSON payload returned by POST /api/v1/extract."""

    doc_type: str = "unknown"            # travel_request | expense_settlement | work_report
    confidence: float = 0.0
    # 1. General metadata (project title, dates, requester, ...)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # 2. Government expense categories rollup
    expense_summary: Dict[str, float] = Field(default_factory=dict)
    total_amount: float = 0.0
    # 3. Raw tables for TSV / Excel export
    raw_tables: Dict[str, List[List[str]]] = Field(default_factory=dict)
    # 3.5 Form profile resolution (which web form matched the target page)
    form_type: Optional[str] = None
    profile_id: Optional[str] = None
    profile_name: Optional[str] = None
    page_match_confidence: float = 0.0
    # Editable fields for the review card (key/label/type/value)
    editable_fields: List[Dict[str, Any]] = Field(default_factory=list)
    # 4. Dynamic DOM instructions for the current target page
    field_mappings: List[DOMAction] = Field(default_factory=list)
    # 5. Base64 assets (optional, only when mode requires them)
    pdf_annex_base64: Optional[str] = None
    pdf_annex_filename: Optional[str] = None
    excel_filled_base64: Optional[str] = None
    excel_filled_filename: Optional[str] = None
    # 6. Human-readable summary for the review card
    summary: Dict[str, Any] = Field(default_factory=dict)
    # 7. Diagnostics / warnings collected during extraction
    warnings: List[str] = Field(default_factory=list)
