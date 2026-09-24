// ============================================================================
// RSC Doc to Smart Data — Content Script (DOM Action Executor)  v2.0.0
//
// Executes a dynamic list of DOMAction instructions received from the backend:
//   set_value | set_select | set_radio | click | click_button | file_attach | wait
//
// Key principles:
//   - Never hard-codes form selectors — everything comes from field_mappings.
//   - Always dispatches native events (input/change) so React/Vue/jQuery
//     frameworks register the values (native setter trick).
//   - Waits for DOM stability (MutationObserver) + configurable delays after
//     row-add clicks so dynamic tables render before the next fill.
// ============================================================================
(() => {
  if (window.__RSC_FILL_EXECUTOR_LOADED__) return;
  window.__RSC_FILL_EXECUTOR_LOADED__ = true;

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // --------------------------------------------------------------------------
  // DOM waiting helpers
  // --------------------------------------------------------------------------
  const norm = (s) => String(s || "").replace(/\s+/g, " ").trim().toLowerCase();

  // Find a form control by its Thai label text. React auto-generates numeric
  // IDs (input-94, textarea-19) that change on every build, while the visible
  // label stays stable — this is the robust fallback.
  function findByLabel(labelText, scopeName) {
    if (!labelText) return null;
    const target = norm(labelText);
    const isRadio = Boolean(scopeName);

    const pick = (list) => {
      if (isRadio) {
        return (
          list.find((el) => el.type === "radio" && el.name === scopeName && norm(el.closest("label")?.innerText).includes(target)) ||
          list.find((el) => el.type === "radio" && el.name === scopeName) ||
          null
        );
      }
      return list[0] || null;
    };

    // 1. label[for=...] with exact / startsWith / includes text
    const labels = Array.from(document.querySelectorAll("label")).filter((l) => {
      const t = norm(l.innerText);
      return t === target || t.startsWith(target) || t.includes(target);
    });
    const byFor = labels.map((l) => (l.htmlFor ? document.getElementById(l.htmlFor) : null)).filter(Boolean);
    const byLabelFor = pick(byFor);
    if (byLabelFor) return byLabelFor;

    // 2. label wrapping the control directly
    const wrapping = labels.map((l) => l.querySelector("input, textarea, select")).filter(Boolean);
    const byWrap = pick(wrapping);
    if (byWrap) return byWrap;

    // 3. aria-label / placeholder hints
    const attr = Array.from(document.querySelectorAll("input, textarea, select")).find((el) => {
      if (isRadio && el.name !== scopeName) return false;
      const aria = norm(el.getAttribute("aria-label"));
      const ph = norm(el.placeholder);
      return aria.includes(target) || ph.includes(target);
    });
    if (attr) return attr;

    return null;
  }

  // Bare-tag selectors ('input', 'textarea', ...) match MANY elements and the
  // first match is often the wrong field — when a label hint exists, prefer it.
  const BARE_TAG_RE = /^(input|textarea|select|button|a|label)$/i;

  function waitForElement(selector, index, timeoutMs = 6000, label, scopeName, opts = {}) {
    // opts: { stableMs, candidates } — candidates = fallback selector list
    // (React auto-IDs drift between portal builds); stableMs waits for the
    // element to survive a React re-render before resolving (v1 parity).
    const { stableMs = 0, candidates = null } = opts || {};
    return new Promise((resolve) => {
      const bySel = (sel) => {
        try {
          const nodes = document.querySelectorAll(sel);
          return nodes[index ?? 0] || (index === undefined || index === null ? nodes[0] : null);
        } catch (_) {
          return null;
        }
      };
      const find = () => {
        if (selector && label && BARE_TAG_RE.test(selector.trim())) {
          // generic selector + label -> resolve by label first
          const byLabel = findByLabel(label, scopeName);
          if (byLabel) return byLabel;
        }
        if (selector) {
          const el = bySel(selector);
          if (el) return el;
        }
        if (candidates && candidates.length) {
          for (const sel of candidates) {
            const el = bySel(sel);
            if (el) return el;
          }
        }
        if (label) {
          const el = findByLabel(label, scopeName);
          if (el) return el;
        }
        return null;
      };

      const started = Date.now();
      let settled = false;
      const done = (el) => {
        if (settled) return;
        settled = true;
        resolve(el);
      };
      const tryFind = () => {
        if (settled) return;
        const el = find();
        if (el) {
          if (stableMs > 0) {
            // React may replace the node right after render — re-query after
            // the stability window and only resolve if it survived.
            setTimeout(() => {
              if (settled) return;
              const again = find();
              if (again) done(again);
              // else keep waiting (observer + final timeout still active)
            }, stableMs);
          } else {
            done(el);
          }
        } else if (Date.now() - started > timeoutMs) {
          done(null);
        }
      };

      const observer = new MutationObserver(tryFind);
      observer.observe(document.body, { childList: true, subtree: true });
      tryFind();
      setTimeout(() => {
        observer.disconnect();
        if (!settled) done(find() || null);
      }, timeoutMs + stableMs + 100);
    });
  }

  // --------------------------------------------------------------------------
  // Native value setting (React/Vue friendly)
  // --------------------------------------------------------------------------
  function setNativeValue(el, value) {
    const proto =
      el instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : el instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, "value");
    if (desc && desc.set) {
      desc.set.call(el, value);
    } else {
      el.value = value;
    }
  }

  function dispatchEvents(el, value) {
    el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: value }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.dispatchEvent(new Event("blur", { bubbles: true }));
  }

  function fillElement(el, value) {
    if (!el) return false;
    el.scrollIntoView({ block: "center", behavior: "instant" });
    el.focus();

    if (el.isContentEditable) {
      // Rich text editors (Quill / Tiptap / ProseMirror / Lexical / contenteditable)
      el.innerText = String(value);
      dispatchEvents(el, String(value));
      return true;
    }

    const tag = el.tagName.toLowerCase();

    if (tag === "select") {
      const strVal = String(value);
      let matched = false;
      for (const opt of Array.from(el.options)) {
        if (opt.value === strVal || opt.text.includes(strVal)) {
          setNativeValue(el, opt.value);
          matched = true;
          break;
        }
      }
      if (!matched && el.options.length > 0) {
        // Try fuzzy: option text containing the value (e.g. budget year "69")
        const fuzzy = Array.from(el.options).find((o) => {
          const text = (o.textContent || "").trim();
          const v = String(value);
          return text.includes(v) || v.includes(text);
        });
        if (fuzzy) setNativeValue(el, fuzzy.value);
      }
      el.dispatchEvent(new Event("change", { bubbles: true }));
      el.dispatchEvent(new Event("blur", { bubbles: true }));
      return true;
    }

    if (el.type === "checkbox" || el.type === "radio") {
      if (String(value).toLowerCase() === "true" || String(value) === "1") el.checked = true;
      el.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    }

    // Normal input / textarea / date / number
    const strVal = String(value);
    setNativeValue(el, strVal);
    dispatchEvents(el, strVal);
    highlight(el);
    return true;
  }

  function highlight(el) {
    const origBg = el.style.backgroundColor;
    el.style.backgroundColor = "#d1fae5";
    el.style.border = "2px solid #10b981";
    setTimeout(() => {
      el.style.backgroundColor = origBg;
      el.style.border = "";
    }, 1800);
  }

  function clickElement(el) {
    if (!el) return false;
    el.scrollIntoView({ block: "center", behavior: "instant" });

    // Radio: mirror the v1 approach that works on the RSC portal —
    // set checked + change natively, then click the associated <label>
    // (React state changes on the label click reliably).
    if (el.type === "radio") {
      el.checked = true;
      el.dispatchEvent(new Event("change", { bubbles: true }));
      const label =
        (el.id ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`) : null) ||
        el.closest("label");
      if (label) {
        label.click();
        label.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
      } else {
        el.click();
        el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
      }
      return true;
    }

    el.click();
    el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
    return true;
  }

  // --------------------------------------------------------------------------
  // click_button: find a <button> whose visible text contains `value`,
  // optionally scoped inside `selector` (CSS container, supports :has())
  // --------------------------------------------------------------------------
  function findButtonByText(container, text) {
    const root = container || document;
    const candidates = root.querySelectorAll("button, [role='button'], input[type='button'], input[type='submit']");
    for (const b of Array.from(candidates)) {
      const t = (b.innerText || b.textContent || "").trim();
      if (t.includes(text)) return b;
      const aria = (b.getAttribute("aria-label") || "");
      if (aria.includes(text)) return b;
    }
    return null;
  }

  // --------------------------------------------------------------------------
  // file_attach: inject a base64 payload into <input type=file> via DataTransfer
  //
  // Robustness: the backend sends a generic selector (e.g. 'input[type="file"]').
  // If that misses (React-generated IDs change between builds), fall back to
  // any file input, then to one that accepts PDF.
  // --------------------------------------------------------------------------
  async function resolveFileInput(selector, index, label) {
    const candidates = [];
    if (selector) candidates.push(selector);
    candidates.push('input[type="file"]', 'input[accept*="pdf"]');

    for (const sel of candidates) {
      let el = null;
      try {
        el = await waitForElement(sel, index, 1500, label);
      } catch (_) {
        el = null;
      }
      if (el && el.type === "file") return el;
    }
    return null;
  }

  // Find a file input scoped to a section by DOM order: the per-section upload
  // input appears right after its radio group (it may be OUTSIDE the <fieldset>
  // — a sibling — so ancestor walking is unreliable). Layouts:
  //   [expense radios] [expense file input] [schedule radios] [schedule file input] [shared input]
  //   or a single shared "เอกสารเพิ่มเติม" input (fallback).
  function locateScopedFileInput(scopeName) {
    const ordered = Array.from(
      document.querySelectorAll('input[type="radio"][name$="-document-source"], input[type="file"]')
    ).sort((a, b) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));

    const files = ordered.filter((el) => el.type === "file");
    if (!files.length) return { found: null, fallback: null };

    const groupIdx = [];
    ordered.forEach((el, i) => {
      if (el.type === "radio" && el.name === scopeName) groupIdx.push(i);
    });
    if (!groupIdx.length) return { found: null, fallback: files[0] };

    const groupEnd = Math.max(...groupIdx);
    let nextGroupStart = ordered.length;
    for (let i = groupEnd + 1; i < ordered.length; i++) {
      if (ordered[i].type === "radio" && ordered[i].name !== scopeName) {
        nextGroupStart = i;
        break;
      }
    }
    for (let i = groupEnd + 1; i < nextGroupStart; i++) {
      if (ordered[i].type === "file") return { found: ordered[i], fallback: files[0] };
    }
    return { found: null, fallback: files[0] };
  }

  async function resolveScopedFileInput(scopeName) {
    if (!scopeName) return null;
    let r = locateScopedFileInput(scopeName);
    if (r.found) return r.found;
    // รอให้ React render input ของ section (สูงสุด ~1.5s) แล้วค่อย fallback
    for (let i = 0; i < 6; i++) {
      await sleep(250);
      r = locateScopedFileInput(scopeName);
      if (r.found) return r.found;
    }
    return r.fallback;
  }

  async function fileAttach(selector, index, base64Data, filename, mime, label, files, scopeName) {
    // 1) per-section input (ใน container ของ radio) ก่อน; 2) fallback ช่องกลาง/ตัวแรก
    let el = scopeName ? await resolveScopedFileInput(scopeName) : null;
    if (!el) el = await resolveFileInput(selector, index, label);
    if (!el) return { ok: false, reason: "ไม่พบ <input type=file> (ลองแล้วทั้ง input[type=file] และ input[accept*=pdf])" };

    el.scrollIntoView({ block: "center", behavior: "instant" });

    const dt = new DataTransfer();
    // Accumulate: เก็บไฟล์ที่แนบไปแล้ว (กัน action ถัดไปเขียนทับเมื่อช่องกลางเดียว)
    Array.from(el.files || []).forEach((f) => dt.items.add(f));
    const add = (b64, name, mimeType) => {
      if (!b64) return;
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      dt.items.add(new File([bytes], name || "annex.pdf", { type: mimeType || "application/pdf" }));
    };

    // Multiple files (meta.files) — ช่อง file input เป็น multiple แนบทีละหลายไฟล์
    if (files && files.length) {
      files.forEach((f) => add(f.base64, f.filename, f.mime));
    } else {
      add(base64Data, filename, mime);
    }
    if (dt.items.length === 0) {
      return { ok: false, reason: "ไม่มีไฟล์ให้แนบ" };
    }

    el.files = dt.files;
    el.dispatchEvent(new Event("change", { bubbles: true }));
    highlight(el);

    // Verify the framework actually received the file(s)
    if (!el.files || el.files.length === 0) {
      return { ok: false, reason: "ตั้งค่าไฟล์ไม่สำเร็จ (files ว่างหลัง dispatch change)" };
    }
    return { ok: true, count: dt.items.length, scoped: Boolean(scopeName) };
  }

  // --------------------------------------------------------------------------
  // Action runner
  // --------------------------------------------------------------------------
  async function runAction(action) {
    const { selector = "", action: act = "set_value", value, label, index, repeat = 1, delay_ms = 150, meta = {} } = action;
    const scopeName = meta.scope_name || null;
    let filled = 0;
    let failed = 0;
    let skipped = 0;
    const errors = [];

    for (let i = 0; i < repeat; i++) {
      try {
        if (act === "wait") {
          await sleep(delay_ms || 150);
          continue;
        }

        if (act === "click_button") {
          // selector is the optional container CSS; value is the button text.
          // bare-tag selector ("button") = ไม่มี container -> ค้นปุ่มทั้งหน้า
          // (ห้าม waitForElement("button") เพราะจะคืนปุ่มแรกสุดแทน container)
          const isBareTag = selector && BARE_TAG_RE.test(selector.trim());
          const container = selector && !isBareTag
            ? await waitForElement(selector, undefined, 6000, label, scopeName)
            : null;
          if (selector && !isBareTag && !container) {
            errors.push(`ไม่พบ container: ${selector}`);
            failed++;
            continue;
          }
          // meta.texts = candidate button texts (label เปลี่ยนตาม portal build)
          const texts = (meta.texts && meta.texts.length) ? meta.texts : [String(value || "")];
          let btn = null;
          for (const t of texts) {
            btn = findButtonByText(container, t);
            if (btn) break;
          }
          if (btn && clickElement(btn)) {
            filled++;
            await sleep(delay_ms || 150);
            // meta.retry + verify_selector: คลิกเพิ่มแถวแล้วฟิลด์ถัดไปยังไม่เกิด
            // -> คลิกซ้ำอีกครั้ง (v1 parity — React re-render บางทีต้อง click 2 ครั้ง)
            if (meta.retry && meta.verify_selector) {
              const appeared = await waitForElement(meta.verify_selector, undefined, 2500, null, null);
              if (!appeared) {
                const btn2 = findButtonByText(container, texts[0] || String(value || ""));
                if (btn2 && clickElement(btn2)) await sleep(delay_ms || 150);
              }
            }
          } else {
            errors.push(
              `ไม่พบปุ่ม "${texts.join('" หรือ "')}"${selector && !isBareTag ? ` ใน ${selector}` : ""}`
            );
            failed++;
          }
          continue;
        }

        if (act === "ensure_click") {
          // คลิกปุ่มเพิ่มแถว/กิจกรรม เฉพาะเมื่อ verify_selector ยังไม่มีอยู่
          // (sweep self-heal) — ถ้ามีแล้ว = แถวครบแล้ว -> skip (ไม่เพิ่มซ้ำ)
          const isBareTag = selector && BARE_TAG_RE.test(selector.trim());
          const container = selector && !isBareTag
            ? await waitForElement(selector, undefined, 6000, label, scopeName)
            : null;
          if (selector && !isBareTag && !container) {
            errors.push(`ไม่พบ container: ${selector}`);
            failed++;
            continue;
          }
          const already = await waitForElement(meta.verify_selector, undefined, 300, null, null);
          if (already) {
            skipped++;
            continue;
          }
          const texts = (meta.texts && meta.texts.length) ? meta.texts : [String(value || "")];
          let btn = null;
          for (const t of texts) {
            btn = findButtonByText(container, t);
            if (btn) break;
          }
          if (!btn) {
            errors.push(`ไม่พบปุ่ม "${texts.join('" หรือ "')}" (ensure_click)`);
            failed++;
            continue;
          }
          clickElement(btn);
          await sleep(delay_ms || 300);
          // verify แถวเกิดจริง; ยังไม่เกิด -> คลิกซ้ำอีกครั้ง
          const appeared = await waitForElement(meta.verify_selector, undefined, 2500, null, null);
          if (!appeared) {
            const btn2 = findButtonByText(container, texts[0] || String(value || ""));
            if (btn2 && clickElement(btn2)) await sleep(delay_ms || 300);
          }
          filled++;
          continue;
        }

        if (act === "file_attach") {
          const res = await fileAttach(selector, index, value, meta.filename, meta.mime, label, meta.files, meta.scope_name);
          if (res.ok) filled++;
          else {
            errors.push(res.reason);
            failed++;
          }
          await sleep(delay_ms || 200);
          continue;
        }

        // timeout 4000ms: ฟิลด์ที่ไม่มีจริง (เช่นแถวที่เพิ่มไม่สำเร็จ) จะ fail เร็ว ไม่ค้างเป็นนาที
        const el = await waitForElement(selector, index, 4000, label, scopeName, {
          stableMs: meta.stable_ms || 0,
          candidates: meta.candidates || null,
        });
        if (!el) {
          errors.push(
            `ไม่พบ element: ${selector}${label ? ` (label "${label}")` : ""}${index !== undefined && index !== null ? `[${index}]` : ""}`
          );
          failed++;
          continue;
        }

        // D: skip fields the portal already filled (auto-fill from profile/ACC)
        if (action.skip_if_value_present && el.value && String(el.value).trim() !== "") {
          skipped++;
          continue;
        }

        switch (act) {
          case "click":
            if (clickElement(el)) filled++;
            else failed++;
            break;
          case "set_radio": {
            // value = radio input value to select within the same name group
            const name = el.name;
            let target = el;
            if (name && value) {
              const radios = document.querySelectorAll(`input[type='radio'][name='${CSS.escape(name)}']`);
              target =
                Array.from(radios).find((r) => r.value === value) ||
                Array.from(radios).find((r) => (r.nextSibling?.textContent || "").includes(String(value))) ||
                el;
            }
            if (clickElement(target)) filled++;
            else failed++;
            break;
          }
          case "set_select":
          case "set_value":
          default:
            if (fillElement(el, value)) filled++;
            else failed++;
            break;
        }
        if (delay_ms && act !== "set_radio") await sleep(delay_ms);
      } catch (e) {
        errors.push(String(e && e.message ? e.message : e));
        failed++;
      }
    }

    return { filled, failed, skipped, errors };
  }

  // --------------------------------------------------------------------------
  // Message listener
  // --------------------------------------------------------------------------
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request && request.action === "CAPTURE_FORM") {
      // Diagnostic: dump the live form controls so the backend profile and
      // dynamic tables (e.g. traveler rows) can be mapped precisely.
      const controls = Array.from(document.querySelectorAll("input, textarea, select")).map((el) => ({
        id: el.id || "",
        name: el.name || "",
        type: el.type || el.tagName.toLowerCase(),
        label: (el.closest("label") ? el.closest("label").innerText : "").trim().slice(0, 60),
        placeholder: (el.placeholder || "").slice(0, 60),
        aria: (el.getAttribute("aria-label") || "").slice(0, 60),
        value: el.type === "password" ? "" : String(el.value || "").slice(0, 40),
      }));
      sendResponse({ controls, url: location.href });
      return true;
    }

    if (request && request.action === "FILL_FORM") {
      (async () => {
        const mappings = (request.payload && request.payload.field_mappings) || [];
        // Resolve file_attach placeholders: the side panel injects the real
        // base64 payload into actions whose meta says "value from backend".
        const resolved = mappings.map((m) => {
          if (m.action === "file_attach" && request.payload.annex_base64 && !m.value) {
            return { ...m, value: request.payload.annex_base64 };
          }
          return m;
        });

        const report = { total: resolved.length, filled: 0, failed: 0, skipped: 0, errors: [], step: 0 };
        for (const act of resolved) {
          report.step++;
          const r = await runAction(act);
          report.filled += r.filled;
          report.failed += r.failed;
          report.skipped += r.skipped || 0;
          report.errors.push(...r.errors.map((e) => `[${act.selector || act.action}] ${e}`));
          try {
            chrome.runtime.sendMessage({ action: "FILL_PROGRESS", step: report.step, total: resolved.length, filled: report.filled, failed: report.failed, skipped: report.skipped });
          } catch (_) {}
        }
        sendResponse(report);
      })();
      return true;
    }
    return false;
  });
})();
