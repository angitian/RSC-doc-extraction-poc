// ============================================================================
// RSC Doc to Smart Data — Side Panel controller  v2.0.0
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
  rcBody: $("#rc-body"),
  rcWarnings: $("#rc-warnings"),
  actionHub: $("#action-hub"),
  btnFill: $("#btn-fill"),
  btnExcel: $("#btn-excel"),
  btnTsv: $("#btn-tsv"),
  btnPdf: $("#btn-pdf"),
  log: $("#log"),
};

let currentResponse = null; // last ExtractionResponse
let currentTargetUrl = "";
let lastFile = null; // re-extract when the mode changes

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

// ---------------------------------------------------------------------------
// Logging
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
// Extraction
// ---------------------------------------------------------------------------
async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  return tab || { url: "", id: null };
}

async function handleFile(file) {
  lastFile = file;
  const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
  if (![".docx", ".pdf"].includes(ext)) {
    setStatus("ไฟล์ต้องเป็น .docx/.pdf", "err");
    return;
  }

  const apiUrl = (els.apiUrl.value.trim().replace(/\/+$/, "") || DEFAULT_API);
  const mode = document.querySelector('input[name="mode"]:checked').value;
  const tab = await getActiveTab();
  currentTargetUrl = tab.url || "";

  setStatus("กำลังสกัดข้อมูล...", "busy");
  log(`ยิง API: ${apiUrl}/api/v1/extract (${file.name}, mode=${mode})`);

  const form = new FormData();
  form.append("file", file);
  form.append("mode", mode);
  form.append("target_url", currentTargetUrl);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const res = await fetch(`${apiUrl}/api/v1/extract`, { method: "POST", body: form, signal: controller.signal });
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
    renderReview(data);
    setStatus("สกัดสำเร็จ", "ok");
    log("สกัดสำเร็จ — พร้อมตรวจสอบข้อมูล", "ok");
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

// Re-extract when the user switches mode (full_table <-> annex_pdf)
document.querySelectorAll('input[name="mode"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    if (lastFile) handleFile(lastFile);
  });
});

// ---------------------------------------------------------------------------
// Review card
// ---------------------------------------------------------------------------
function renderReview(data) {
  els.modeSection.classList.remove("hidden");
  els.reviewCard.classList.remove("hidden");
  els.actionHub.classList.remove("hidden");

  const s = data.summary || {};
  els.rcType.textContent = `${s.doc_type_label || data.doc_type} · ${Math.round((data.confidence || 0) * 100)}%`;

  const fmt = (n) => (typeof n === "number" ? n.toLocaleString("th-TH", { minimumFractionDigits: 2 }) : n);
  const rows = [
    ["ชื่อโครงการ", s.project_name],
    ["ผู้ขอ/ผู้เดินทาง", s.traveler],
    ["ช่วงเวลา", s.date_range],
    ["จำนวนรายการค่าใช้จ่าย", s.expense_items_count + " รายการ"],
    ["จำนวนกิจกรรมกำหนดการ", s.itinerary_items_count + " รายการ"],
  ];
  let html = '<div class="rc-grid">';
  rows.forEach(([k, v]) => {
    if (!v) return;
    html += `<div class="rc-item"><span class="k">${escapeHtml(k)}</span><span class="v">${escapeHtml(String(v))}</span></div>`;
  });
  html += `<div class="rc-item"><span class="k">ยอดรวมทั้งสิ้น</span><span class="v rc-total">฿ ${fmt(s.total_amount)}</span></div>`;
  html += "</div>";

  const cats = s.categories || {};
  const catKeys = Object.keys(cats);
  if (catKeys.length) {
    html += '<div class="chips">' + catKeys.map((c) => `<span class="chip">${escapeHtml(c)}: ${fmt(cats[c])}</span>`).join("") + "</div>";
  }
  els.rcBody.innerHTML = html;

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

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------------------------------------------------------------------------
// Tri-Action Hub
// ---------------------------------------------------------------------------
els.btnFill.addEventListener("click", async () => {
  if (!currentResponse) return;
  const tab = await getActiveTab();
  if (!tab.id) {
    setStatus("ไม่พบแท็บที่ใช้งาน", "err");
    return;
  }
  els.btnFill.disabled = true;
  setStatus("กำลังยิงข้อมูลลงฟอร์ม...", "busy");
  log(`ยิง field_mappings ${currentResponse.field_mappings.length} คำสั่ง ไปยังแท็บ`);

  try {
    const res = await chrome.runtime.sendMessage({
      action: "FILL_FORM",
      tabId: tab.id,
      payload: {
        field_mappings: currentResponse.field_mappings,
        annex_base64: currentResponse.pdf_annex_base64 || "",
      },
    });
    if (res && res.ok) {
      const r = res.result;
      const okCount = r && typeof r.filled === "number" ? r.filled : 0;
      const errCount = r && typeof r.failed === "number" ? r.failed : 0;
      setStatus(`กรอกสำเร็จ ${okCount}/${r.total}`, errCount > 0 ? "busy" : "ok");
      log(`✅ กรอกสำเร็จ ${okCount} จาก ${r.total}${errCount ? ` | ❌ ล้มเหลว ${errCount}` : ""}`, errCount ? "err" : "ok");
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
setStatus("พร้อมใช้งาน", "idle");
