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
  docxFileInfo: $("#docx-file-info"),
  pdfList: $("#pdf-list"),
  reviewCard: $("#review-card"),
  rcType: $("#rc-type"),
  rcMeta: $("#rc-meta"),
  rcEdit: $("#rc-edit"),
  rcWarnings: $("#rc-warnings"),
  actionHub: $("#action-hub"),
  btnFill: $("#btn-fill"),
  btnExcel: $("#btn-excel"),
  btnTsv: $("#btn-tsv"),
  btnCapture: $("#btn-capture"),
  quickForm: $("#quick-form"),
  qfProfile: $("#qf-profile"),
  qfError: $("#qf-error"),
  btnRefreshForms: $("#btn-refresh-forms"),
  btnLoadTemplate: $("#btn-load-template"),
  qfFields: $("#qf-fields"),
  btnQuickFill: $("#btn-quick-fill"),
  versionBadge: $("#version-badge"),
  log: $("#log"),
};

let formsCache = []; // loaded form profiles (Quick Form)

let currentResponse = null; // last ExtractionResponse
let currentTargetUrl = "";
let lastFile = null; // re-extract when the mode changes
let userEdits = {}; // editable review card overrides: {key: value}
// PDFs ที่ผู้ใช้ลากเพื่อแนบ: [{id, base64, name, type: "expense"|"schedule"}]
let pdfItems = [];
const PDF_TYPE_LABELS = { expense: "ประมาณการค่าใช้จ่าย", schedule: "กำหนดการ" };

// Map raw select values to Thai labels for the editable review card
const SELECT_LABELS = {
  conference: "เข้าร่วมประชุม",
  seminar: "เข้าร่วมสัมมนา",
  training: "เข้าร่วมฝึกอบรม",
  workshop: "เข้าร่วม Workshop",
  "official-travel": "เดินทางไปราชการ",
  "site-visit": "ไปศึกษาดูงาน",
  domestic: "ในประเทศ",
  international: "ต่างประเทศ",
  attendee: "ผู้เข้าร่วม",
  presenter: "ผู้นำเสนอผลงาน",
};
const selLabel = (v) => SELECT_LABELS[v] || v;

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
  loadForms(); // re-fetch with the new URL (no extension reload needed)
  updateVersionBadge();
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
  handleDrop(e.dataTransfer.files);
});
els.fileInput.addEventListener("change", (e) => {
  handleDrop(e.target.files);
  e.target.value = "";
});

// ---------------------------------------------------------------------------
// PDF แนบ (แยกกล่อง ประมาณการ/กำหนดการ + dropdown + auto-assign)
// ---------------------------------------------------------------------------
function assignRemainingTypes() {
  // ถ้าไฟล์หนึ่งถูกตั้งเป็น type ใด ไฟล์อื่นที่ยังไม่มี type จะได้ type ที่เหลือ
  const used = new Set(pdfItems.map((p) => p.type).filter(Boolean));
  if (used.size === 1 && pdfItems.length === 2) {
    const free = used.has("expense") ? "schedule" : "expense";
    pdfItems.forEach((p) => {
      if (!p.type) p.type = free;
    });
  } else if (pdfItems.length === 1 && !pdfItems[0].type) {
    pdfItems[0].type = "expense"; // default ไฟล์แรก = ประมาณการ
  }
}

function renderPdfList() {
  assignRemainingTypes();
  els.pdfList.innerHTML = pdfItems
    .map((p, i) => {
      const sel = `<select data-idx="${i}">
        <option value="expense" ${p.type === "expense" ? "selected" : ""}>ประมาณการค่าใช้จ่าย</option>
        <option value="schedule" ${p.type === "schedule" ? "selected" : ""}>กำหนดการ</option>
      </select>`;
      return `<div class="pdf-row">
        <span class="pdf-name" title="${escapeHtml(p.name)}">📄 ${escapeHtml(p.name)}</span>
        ${sel}
        <button class="btn-ghost btn-sm" data-rm="${i}" title="ลบไฟล์">🗑</button>
      </div>`;
    })
    .join("");
  els.pdfList.querySelectorAll("select").forEach((sel) => {
    sel.addEventListener("change", () => {
      const i = Number(sel.dataset.idx);
      const chosen = sel.value;
      // auto-assign: ไฟล์อื่นที่มี type เดียวกัน -> สลับเป็น type ที่เหลือ
      const other = pdfItems.find((p, j) => j !== i && p.type === chosen);
      if (other) {
        const free = chosen === "expense" ? "schedule" : "expense";
        pdfItems[i].type = chosen;
        other.type = free;
      } else {
        pdfItems[i].type = chosen;
      }
      renderPdfList();
    });
  });
  els.pdfList.querySelectorAll("[data-rm]").forEach((btn) => {
    btn.addEventListener("click", () => {
      pdfItems.splice(Number(btn.dataset.rm), 1);
      renderPdfList();
    });
  });
}

function addPdfFiles(files) {
  let added = 0;
  Array.from(files || []).forEach((file) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) return;
    const reader = new FileReader();
    reader.onload = () => {
      const b64 = String(reader.result).split(",")[1] || "";
      pdfItems.push({ id: Date.now() + "-" + added, base64: b64, name: file.name, type: null });
      added++;
      renderPdfList();
    };
    reader.readAsDataURL(file);
  });
  if (!added) setStatus("ต้องเป็นไฟล์ .pdf", "err");
}

// ---------------------------------------------------------------------------
// ช่องลากเดียว: แยกไฟล์อัตโนมัติ (docx/xlsx = สกัด, pdf = แนบ)
// ---------------------------------------------------------------------------
async function handleDrop(files) {
  let docAdded = false;
  let pdfAdded = 0;
  Array.from(files || []).forEach((file) => {
    const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
    if (ext === ".pdf") {
      addPdfFiles([file]);
      pdfAdded++;
    } else if ([".docx", ".xlsx"].includes(ext)) {
      if (!docAdded) {
        lastFile = file; // เอาอันแรกเป็นไฟล์สกัด
        els.docxFileInfo.textContent = `✅ เอกสารสกัด: ${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
        docAdded = true;
      }
    }
  });
  if (docAdded || pdfAdded) {
    setStatus("พร้อมยิง — กด 🚀", "idle");
  } else {
    setStatus("ไม่รองรับไฟล์นี้ (docx/xlsx/pdf)", "err");
  }
}

// ---------------------------------------------------------------------------
// Review card (editable)
// ---------------------------------------------------------------------------
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function renderReview(data) {
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
          const rawVal = userEdits[key] !== undefined ? userEdits[key] : f.value ?? "";
          // Show Thai labels for select values (conference -> เข้าร่วมประชุม)
          const val = f.type === "select" ? selLabel(rawVal) : rawVal;
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
  const tab = await getActiveTab();
  if (!tab.id) {
    setStatus("ไม่พบแท็บที่ใช้งาน", "err");
    return;
  }
  if (!lastFile && !pdfItems.length) {
    setStatus("ลาก DOCX (สกัด) หรือ PDF (แนบ) ก่อน", "err");
    return;
  }
  els.btnFill.disabled = true;
  setStatus("กำลังสกัด + เตรียมยิง...", "busy");

  const attach = [...new Set(pdfItems.map((p) => p.type).filter(Boolean))];
  currentTargetUrl = tab.url || "";
  const snapshot = await capturePageSnapshot(tab.id);
  const pdfFiles = pdfItems.map((p) => ({ base64: p.base64, filename: p.name, mime: "application/pdf" }));

  try {
    let data;
    if (lastFile) {
      // มี DOCX → สกัด + กรอกฟิลด์ + แนบ PDF (per-section)
      const form = new FormData();
      form.append("file", lastFile);
      form.append("mode", "full_table");
      form.append("outputs", "excel");
      form.append("target_url", currentTargetUrl);
      if (attach.length) form.append("attach_sections", attach.join(","));
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
        data = await res.json();
      } finally {
        clearTimeout(timer);
      }
    } else {
      // ไม่มี DOCX → แนบ PDF อย่างเดียว (attach-only)
      const res = await fetch(`${getApiUrl()}/api/v1/fill`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_id: "",
          target_url: currentTargetUrl,
          page_snapshot: snapshot,
          mode: "annex_pdf",
          values: {},
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      data = await res.json();
    }

    if (!data.field_mappings.length) {
      throw new Error("ได้ mapping ว่าง — ตรวจสอบว่าเปิดฟอร์มที่รองรับอยู่");
    }
    currentResponse = data;
    userEdits = {};
    renderReview(data);

    const hasAttachAction = data.field_mappings.some((m) => m.action === "file_attach");
    if (pdfFiles.length && !hasAttachAction) {
      log("⚠️ ฟอร์มนี้ไม่มีช่องอัปโหลด PDF — ข้ามการแนบ (ไฟล์ PDF ถูกเพิกเฉย)", "err");
    }
    log(`ฟอร์ม: ${data.profile_name || data.form_type || "?"} — mappings ${data.field_mappings.length}${attach.length ? ` | แนบ PDF: ${attach.join(", ")}` : ""}`);

    // ใส่ PDF ของผู้ใช้เข้า file_attach (ถ้ามี) + override ที่แก้ใน review card
    let mappings = applyOverrides(data.field_mappings);
    if (pdfFiles.length && hasAttachAction) {
      mappings = mappings.map((m) =>
        m.action === "file_attach"
          ? { ...m, meta: { ...m.meta, files: pdfFiles } }
          : m
      );
    }

    setStatus("กำลังยิงข้อมูลลงฟอร์ม...", "busy");
    const res = await chrome.runtime.sendMessage({
      action: "FILL_FORM",
      tabId: tab.id,
      payload: {
        field_mappings: mappings,
        annex_base64: "",
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
  if (!currentResponse || !currentResponse.excel_filled_base64) {
    log("ℹ️ ไม่มีไฟล์ Excel ในผลลัพธ์นี้ (Quick Form/อัปโหลดเองไม่สร้าง Excel)", "info");
    return;
  }
  downloadBase64(currentResponse.excel_filled_base64, currentResponse.excel_filled_filename || "ข้อมูล.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
  log("📊 ดาวน์โหลด Excel แล้ว", "ok");
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
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    formsCache = data.forms || [];
    els.qfProfile.innerHTML = formsCache
      .map((f) => `<option value="${escapeHtml(f.profile_id)}">${escapeHtml(f.name)}</option>`)
      .join("");
    els.qfError.classList.add("hidden");
    renderQuickFields(formsCache[0]);
    return formsCache;
  } catch (err) {
    formsCache = [];
    els.qfProfile.innerHTML = "";
    els.qfError.classList.remove("hidden");
    els.qfError.textContent = `⚠️ เชื่อมต่อ API ไม่ได้ (${getApiUrl()}) — ตรวจสอบการตั้งค่า URL หรือเริ่มเซิร์ฟเวอร์ backend`;
    log("❌ โหลดฟอร์มไม่สำเร็จ: " + err.message, "err");
    return [];
  }
}

els.btnRefreshForms.addEventListener("click", () => {
  loadForms();
  setStatus("รีเฟรชฟอร์มแล้ว", "idle");
});

// Version badge — extension build + backend API version (ยืนยัน build ที่ใช้)
async function updateVersionBadge() {
  const extVer = chrome.runtime.getManifest().version;
  let apiVer = "?";
  let offline = true;
  try {
    const res = await fetch(`${getApiUrl()}/api/v1/health`);
    if (res.ok) {
      const h = await res.json();
      apiVer = h.version || "?";
      offline = false;
    }
  } catch (_) {}
  els.versionBadge.textContent = `ext v${extVer} · API v${apiVer}`;
  els.versionBadge.classList.toggle("offline", offline);
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
  if (!profileId) {
    els.qfError.classList.remove("hidden");
    els.qfError.textContent = "⚠️ ยังไม่มีฟอร์มให้เลือก — เชื่อมต่อ API ให้ได้ก่อน (ตรวจ URL ใน ⚙️ ตั้งค่า)";
    return;
  }
  try {
    const res = await fetch(`${getApiUrl()}/api/v1/templates/${profileId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    downloadBase64(data.base64, data.filename, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    log("📥 ดาวน์โหลด Excel template แล้ว", "ok");
  } catch (err) {
    log("❌ ดาวน์โหลด template ไม่สำเร็จ: " + err.message, "err");
    els.qfError.classList.remove("hidden");
    els.qfError.textContent = `⚠️ ดาวน์โหลด template ไม่ได้ (${getApiUrl()}) — ตรวจสอบเซิร์ฟเวอร์`;
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
updateVersionBadge();
// Quick Form starts collapsed to keep the panel tidy (ย่อไว้ก่อน)
els.quickForm.removeAttribute("open");
setStatus("พร้อมใช้งาน", "idle");
