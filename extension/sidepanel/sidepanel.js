// ============================================================================
// RSC Doc to Smart Data — Side Panel controller  v2.1
// Tri-Action Hub + Editable Review Card (A) + Quick Form (B) + Excel (C)
// ============================================================================
"use strict";

const DEFAULT_API = "http://127.0.0.1:8000";
const REQUEST_TIMEOUT_MS = 95_000; // cold start on free hosts can take ~60s

const $ = (sel) => document.querySelector(sel);
const els = {
  status: $("#status-pill"),
  apiUrl: $("#api-url"),
  saveApi: $("#save-api"),
  apiSaved: $("#api-saved"),
  dropZone: $("#drop-zone"),
  fileInput: $("#file-input"),
  modeSection: $("#mode-section"),
  reviewCard: $("#review-card"),
  rcType: $("#rc-type"),
  rcMeta: $("#rc-meta"),
  rcEdit: $("#rc-edit"),
  rcWarnings: $("#rc-warnings"),
  actionHub: $("#action-hub"),
  btnFill: $("#btn-fill"),
  btnExcel: $("#btn-excel"),
  btnTsv: $("#btn-tsv"),
  btnPdf: $("#btn-pdf"),
  btnCapture: $("#btn-capture"),
  quickForm: $("#quick-form"),
  qfProfile: $("#qf-profile"),
  btnLoadTemplate: $("#btn-load-template"),
  qfFields: $("#qf-fields"),
  btnQuickFill: $("#btn-quick-fill"),
  log: $("#log"),
};

let currentResponse = null; // last ExtractionResponse
let currentTargetUrl = "";
let lastFile = null; // re-extract when the mode changes
let userEdits = {}; // editable review card overrides: {key: value}

// ---------------------------------------------------------------------------
// Storage helpers
// ---------------------------------------------------------------------------
async function loadApiUrl() {
  const { apiUrl } = await chrome.storage.sync.get("apiUrl");
  els.apiUrl.value = apiUrl || DEFAULT_API;
}

async function saveApiUrl() {
  const url = els.apiUrl.value.trim().replace(/\/+$/, "");
  await chrome.storage.sync.set({ apiUrl: url });
  els.apiSaved.textContent = "บันทึกแล้ว ✓";
  setTimeout(() => (els.apiSaved.textContent = ""), 2000);
}

function getApiUrl() {
  return els.apiUrl.value.trim().replace(/\/+$/, "") || DEFAULT_API;
}

// ---------------------------------------------------------------------------
// Logging / status
// ---------------------------------------------------------------------------
function log(msg, cls = "info") {
  els.log.classList.remove("hidden");
  const div = document.createElement("div");
  div.className = cls;
  div.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  els.log.appendChild(div);
  els.log.scrollTop = els.log.scrollHeight;
}

function setStatus(text, cls) {
  els.status.textContent = text;
  els.status.className = `pill pill-${cls}`;
}

// ---------------------------------------------------------------------------
// Active tab helpers
// ---------------------------------------------------------------------------
async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  return tab || { url: "", id: null };
}

async function capturePageSnapshot(tabId) {
  // Ask the content script for the live form controls (DOM signature)
  try {
    const res = await chrome.runtime.sendMessage({ action: "CAPTURE_FORM", tabId });
    if (res && res.ok && res.result && res.result.controls) {
      return res.result.controls.map((c) => ({ id: c.id, name: c.name, type: c.type, label: c.label }));
    }
  } catch (_) {}
  return null;
}

// ---------------------------------------------------------------------------
// File selection
// ---------------------------------------------------------------------------
function openFilePicker() {
  els.fileInput.click();
}

els.dropZone.addEventListener("click", openFilePicker);
els.dropZone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    openFilePicker();
  }
});
els.dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  els.dropZone.classList.add("dragover");
});
els.dropZone.addEventListener("dragleave", () => els.dropZone.classList.remove("dragover"));
els.dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  els.dropZone.classList.remove("dragover");
  const file = e.dataTransfer.files && e.dataTransfer.files[0];
  if (file) handleFile(file);
});
els.fileInput.addEventListener("change", (e) => {
  if (e.target.files && e.target.files[0]) handleFile(e.target.files[0]);
});

// ---------------------------------------------------------------------------
// Extraction (uploaded file)
// ---------------------------------------------------------------------------
async function handleFile(file) {
  lastFile = file;
  const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
  if (![".docx", ".pdf", ".xlsx"].includes(ext)) {
    setStatus("ไฟล์ต้องเป็น .docx/.pdf/.xlsx", "err");
    return;
  }

  const mode = document.querySelector('input[name="mode"]:checked').value;
  const tab = await getActiveTab();
  currentTargetUrl = tab.url || "";

  setStatus("กำลังสกัดข้อมูล...", "busy");
  log(`ยิง API: ${getApiUrl()}/api/v1/extract (${file.name}, mode=${mode})`);

  const form = new FormData();
  form.append("file", file);
  form.append("mode", mode);
  form.append("target_url", currentTargetUrl);
  const snapshot = await capturePageSnapshot(tab.id);
  if (snapshot && snapshot.length) form.append("page_snapshot", JSON.stringify(snapshot));

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const res = await fetch(`${getApiUrl()}/api/v1/extract`, { method: "POST", body: form, signal: controller.signal });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const j = await res.json();
        detail = j.detail || detail;
      } catch (_) {}
      throw new Error(detail);
    }
    const data = await res.json();
    currentResponse = data;
    userEdits = {};
    renderReview(data);
    setStatus("สกัดสำเร็จ", "ok");
    log(`สกัดสำเร็จ — ฟอร์ม: ${data.profile_name || data.form_type || "?"}`, "ok");
  } catch (err) {
    if (err.name === "AbortError") {
      setStatus("รอเซิร์ฟเวอร์ตอบนานเกินไป", "err");
      log("⏳ เซิร์ฟเวอร์ cold start หรือไม่ตอบสนอง — ลองอีกครั้ง", "err");
    } else {
      setStatus("สกัดไม่สำเร็จ", "err");
      log(`เกิดข้อผิดพลาด: ${err.message}`, "err");
    }
    hideReview();
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------------------
// Review card (editable)
// ---------------------------------------------------------------------------
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function renderReview(data) {
  els.modeSection.classList.remove("hidden");
  els.reviewCard.classList.remove("hidden");
  els.actionHub.classList.remove("hidden");

  const s = data.summary || {};
  const info = [
    ["เอกสาร", `${s.doc_type_label || data.doc_type} (${Math.round((data.confidence || 0) * 100)}%)`],
    ["ฟอร์มปลายทาง", data.profile_name || data.form_type || "?"],
  ];
  if (data.page_match_confidence) info.push(["ความตรงฟอร์ม", Math.round(data.page_match_confidence * 100) + "%"]);
  els.rcType.textContent = `${s.doc_type_label || data.doc_type} · ${Math.round((data.confidence || 0) * 100)}%`;

  let html = info.map(([k, v]) => `<div class="rc-meta-row"><span class="k">${escapeHtml(k)}</span><span class="v">${escapeHtml(String(v))}</span></div>`).join("");
  html += `<div class="rc-meta-row"><span class="k">ชื่อโครงการ</span><span class="v">${escapeHtml(s.project_name || "-")}</span></div>`;
  html += `<div class="rc-meta-row"><span class="k">ยอดรวม</span><span class="v rc-total">฿ ${Number(s.total_amount || 0).toLocaleString("th-TH", { minimumFractionDigits: 2 })}</span></div>`;
  els.rcMeta.innerHTML = html;

  // Editable fields (A)
  const fields = data.editable_fields || [];
  if (fields.length) {
    els.rcEdit.classList.remove("hidden");
    els.rcEdit.innerHTML =
      `<div class="rc-e-note">✏️ แก้ค่าก่อนยิงได้ (กรอกรวดเดียว ไม่ต้องมองทีละหัวข้อ)</div>` +
      fields
        .map((f) => {
          const key = f.key;
          const type = f.type === "date" ? "date" : f.type === "number" ? "number" : "text";
          const val = userEdits[key] !== undefined ? userEdits[key] : f.value ?? "";
          return `<div class="rc-e-row">
            <span class="rc-e-label" title="${escapeHtml(key)}">${escapeHtml(f.label)}</span>
            ${type === "textarea" ? `<textarea data-key="${escapeHtml(key)}">${escapeHtml(val)}</textarea>`
              : `<input data-key="${escapeHtml(key)}" type="${type}" value="${escapeHtml(val)}" />`}
          </div>`;
        })
        .join("");
    els.rcEdit.querySelectorAll("input, textarea").forEach((el) => {
      el.addEventListener("input", () => {
        userEdits[el.dataset.key] = el.value;
      });
    });
  } else {
    els.rcEdit.classList.add("hidden");
  }

  if (data.warnings && data.warnings.length) {
    els.rcWarnings.classList.remove("hidden");
    els.rcWarnings.innerHTML = "⚠️ " + data.warnings.map((w) => escapeHtml(w)).join("<br/>⚠️ ");
  } else {
    els.rcWarnings.classList.add("hidden");
  }
}

function hideReview() {
  els.reviewCard.classList.add("hidden");
  els.actionHub.classList.add("hidden");
}

// ---------------------------------------------------------------------------
// Tri-Action Hub
// ---------------------------------------------------------------------------
function applyOverrides(mappings) {
  return mappings.map((m) => {
    if (m.key && userEdits[m.key] !== undefined && String(userEdits[m.key]).trim() !== "") {
      return { ...m, value: String(userEdits[m.key]) };
    }
    return m;
  });
}

els.btnFill.addEventListener("click", async () => {
  if (!currentResponse) return;
  const tab = await getActiveTab();
  if (!tab.id) {
    setStatus("ไม่พบแท็บที่ใช้งาน", "err");
    return;
  }
  els.btnFill.disabled = true;
  setStatus("กำลังยิงข้อมูลลงฟอร์ม...", "busy");
  const mappings = applyOverrides(currentResponse.field_mappings);
  log(`ยิง field_mappings ${mappings.length} คำสั่ง ไปยังแท็บ${Object.keys(userEdits).length ? ` (แก้ ${Object.keys(userEdits).length} ค่า)` : ""}`);

  try {
    const res = await chrome.runtime.sendMessage({
      action: "FILL_FORM",
      tabId: tab.id,
      payload: {
        field_mappings: mappings,
        annex_base64: currentResponse.pdf_annex_base64 || "",
      },
    });
    if (res && res.ok) {
      const r = res.result;
      const okCount = r && typeof r.filled === "number" ? r.filled : 0;
      const errCount = r && typeof r.failed === "number" ? r.failed : 0;
      const skipCount = r && typeof r.skipped === "number" ? r.skipped : 0;
      setStatus(`กรอกสำเร็จ ${okCount}/${r.total}`, errCount > 0 ? "busy" : "ok");
      log(`✅ กรอกสำเร็จ ${okCount} จาก ${r.total}${skipCount ? ` | ข้าม (เว็บเติมแล้ว) ${skipCount}` : ""}${errCount ? ` | ❌ ล้มเหลว ${errCount}` : ""}`, errCount ? "err" : "ok");
      (r.errors || []).slice(0, 8).forEach((e) => log("  ↳ " + e, "err"));
    } else {
      setStatus("ยิงไม่สำเร็จ", "err");
      log("❌ " + (res && res.error ? res.error : "ไม่ทราบสาเหตุ"), "err");
    }
  } catch (err) {
    setStatus("ยิงไม่สำเร็จ", "err");
    log("❌ " + (err && err.message ? err.message : String(err)), "err");
    if (String(err).includes("file://")) {
      log("💡 หน้า file:// ต้องเปิด 'อนุญาตเข้าถึงไฟล์ URL' ใน chrome://extensions", "info");
    }
  } finally {
    els.btnFill.disabled = false;
  }
});

function downloadBase64(base64, filename, mime) {
  const bytes = atob(base64);
  const arr = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
  const blob = new Blob([arr], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
}

els.btnExcel.addEventListener("click", () => {
  if (!currentResponse || !currentResponse.excel_filled_base64) return;
  downloadBase64(currentResponse.excel_filled_base64, currentResponse.excel_filled_filename || "ข้อมูล.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
  log("📊 ดาวน์โหลด Excel แล้ว", "ok");
});

els.btnPdf.addEventListener("click", () => {
  if (!currentResponse || !currentResponse.pdf_annex_base64) return;
  downloadBase64(currentResponse.pdf_annex_base64, currentResponse.pdf_annex_filename || "annex.pdf", "application/pdf");
  log("📄 ดาวน์โหลด PDF แนบแล้ว", "ok");
});

els.btnTsv.addEventListener("click", async () => {
  if (!currentResponse) return;
  const tables = currentResponse.raw_tables || {};
  const parts = [];
  if (tables.breakdown && tables.breakdown.length) {
    parts.push("รายการ\tรายละเอียด\tจำนวนเงิน (บาท)");
    parts.push(...tables.breakdown.map((r) => r.join("\t")));
  }
  if (tables.schedule && tables.schedule.length) {
    parts.push("");
    parts.push("วันที่\tสถานที่\tเวลา\tกิจกรรม");
    parts.push(...tables.schedule.map((r) => r.join("\t")));
  }
  const tsv = parts.join("\n");
  try {
    await navigator.clipboard.writeText(tsv);
    log(`📋 คัดลอก TSV แล้ว (${tables.breakdown.length + tables.schedule.length} แถว)`, "ok");
  } catch (err) {
    log("❌ คัดลอกไม่สำเร็จ: " + err.message, "err");
  }
});

// จับฟอร์ม (debug)
els.btnCapture.addEventListener("click", async () => {
  const tab = await getActiveTab();
  if (!tab.id) return;
  const res = await chrome.runtime.sendMessage({ action: "CAPTURE_FORM", tabId: tab.id });
  if (res && res.ok && res.result) {
    const controls = res.result.controls || [];
    log(`🔍 จับฟอร์มได้ ${controls.length} ฟิลด์ — ดู JSON ใน log นี้`, "info");
    log(JSON.stringify(controls, null, 1).slice(0, 600), "info");
  } else {
    log("❌ จับฟอร์มไม่สำเร็จ: " + (res && res.error ? res.error : ""), "err");
  }
});

// ---------------------------------------------------------------------------
// Quick Form (B)
// ---------------------------------------------------------------------------
async function loadForms() {
  try {
    const res = await fetch(`${getApiUrl()}/api/v1/forms`);
    const data = await res.json();
    els.qfProfile.innerHTML = data.forms
      .map((f) => `<option value="${escapeHtml(f.profile_id)}">${escapeHtml(f.name)}</option>`)
      .join("");
    renderQuickFields(data.forms[0]);
    return data.forms;
  } catch (err) {
    log("❌ โหลดฟอร์มไม่สำเร็จ: " + err.message, "err");
    return [];
  }
}

function renderQuickFields(form) {
  if (!form) return;
  els.qfFields.innerHTML = form.fields
    .filter((f) => f.type !== "select")
    .map((f) => {
      const t = f.type === "number" ? "number" : f.type === "date" ? "date" : f.type === "textarea" ? "textarea" : "text";
      return `<div class="qf-field">
        <label>${escapeHtml(f.label)}</label>
        ${t === "textarea" ? `<textarea data-k="${escapeHtml(f.key)}"></textarea>`
          : `<input data-k="${escapeHtml(f.key)}" type="${t}" />`}
      </div>`;
    })
    .join("");
}

els.qfProfile.addEventListener("change", async () => {
  const res = await fetch(`${getApiUrl()}/api/v1/forms`);
  const data = await res.json();
  renderQuickFields(data.forms.find((f) => f.profile_id === els.qfProfile.value));
});

els.btnLoadTemplate.addEventListener("click", async () => {
  const profileId = els.qfProfile.value;
  try {
    const res = await fetch(`${getApiUrl()}/api/v1/templates/${profileId}`);
    const data = await res.json();
    downloadBase64(data.base64, data.filename, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    log("📥 ดาวน์โหลด Excel template แล้ว", "ok");
  } catch (err) {
    log("❌ ดาวน์โหลด template ไม่สำเร็จ: " + err.message, "err");
  }
});

els.btnQuickFill.addEventListener("click", async () => {
  const values = {};
  els.qfFields.querySelectorAll("input, textarea").forEach((el) => {
    if (el.value && String(el.value).trim() !== "") values[el.dataset.k] = el.value;
  });
  if (!Object.keys(values).length) {
    setStatus("กรอกข้อมูลอย่างน้อย 1 ช่องก่อน", "err");
    return;
  }
  const tab = await getActiveTab();
  currentTargetUrl = tab.url || "";
  const snapshot = await capturePageSnapshot(tab.id);

  setStatus("กำลังสร้าง mapping...", "busy");
  try {
    const res = await fetch(`${getApiUrl()}/api/v1/fill`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_id: els.qfProfile.value,
        target_url: currentTargetUrl,
        page_snapshot: snapshot,
        values,
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    currentResponse = data;
    userEdits = {};
    renderReview(data);
    log(`⚡ Quick Form: ${data.field_mappings.length} mappings พร้อมยิง`, "ok");
    setStatus("พร้อมยิง (Quick)", "ok");
  } catch (err) {
    setStatus("สร้าง mapping ไม่สำเร็จ", "err");
    log("❌ " + err.message, "err");
  }
});

// ---------------------------------------------------------------------------
// Progress from content script
// ---------------------------------------------------------------------------
chrome.runtime.onMessage.addListener((msg) => {
  if (msg && msg.action === "FILL_PROGRESS") {
    setStatus(`กำลังกรอก... ${msg.step}/${msg.total}`, "busy");
  }
});

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
loadApiUrl();
els.saveApi.addEventListener("click", saveApiUrl);
loadForms();
setStatus("พร้อมใช้งาน", "idle");
