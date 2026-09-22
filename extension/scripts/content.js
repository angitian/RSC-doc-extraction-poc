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

  function waitForElement(selector, index, timeoutMs = 6000, label, scopeName) {
    return new Promise((resolve) => {
      const find = () => {
        if (selector) {
          try {
            const nodes = document.querySelectorAll(selector);
            const el = nodes[index ?? 0] || (index === undefined || index === null ? nodes[0] : null);
            if (el) return el;
          } catch (_) {
            /* invalid selector -> fall through to label lookup */
          }
        }
        if (label) {
          const el = findByLabel(label, scopeName);
          if (el) return el;
        }
        return null;
      };
      const existing = find();
      if (existing) return resolve(existing);

      const started = Date.now();
      const observer = new MutationObserver(() => {
        const el = find();
        if (el) {
          observer.disconnect();
          resolve(el);
        } else if (Date.now() - started > timeoutMs) {
          observer.disconnect();
          resolve(null);
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
      setTimeout(() => {
        observer.disconnect();
        resolve(find());
      }, timeoutMs);
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

  async function fileAttach(selector, index, base64Data, filename, mime, label) {
    const el = await resolveFileInput(selector, index, label);
    if (!el) return { ok: false, reason: "ไม่พบ <input type=file> (ลองแล้วทั้ง input[type=file] และ input[accept*=pdf])" };

    el.scrollIntoView({ block: "center", behavior: "instant" });

    const binary = atob(base64Data);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const file = new File([bytes], filename || "annex.pdf", { type: mime || "application/pdf" });

    const dt = new DataTransfer();
    dt.items.add(file);
    el.files = dt.files;
    el.dispatchEvent(new Event("change", { bubbles: true }));
    highlight(el);

    // Verify the framework actually received the file
    if (!el.files || el.files.length === 0) {
      return { ok: false, reason: "ตั้งค่าไฟล์ไม่สำเร็จ (files ว่างหลัง dispatch change)" };
    }
    return { ok: true, filename: file.name, size: file.size };
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
          // selector is the optional container CSS; value is the button text
          const container = selector ? await waitForElement(selector, undefined, 6000, label, scopeName) : null;
          if (selector && !container) {
            errors.push(`ไม่พบ container: ${selector}`);
            failed++;
            continue;
          }
          const btn = findButtonByText(container, String(value || ""));
          if (btn && clickElement(btn)) {
            filled++;
          } else {
            errors.push(`ไม่พบปุ่ม "${value}"${selector ? ` ใน ${selector}` : ""}`);
            failed++;
          }
          await sleep(delay_ms || 150);
          continue;
        }

        if (act === "file_attach") {
          const res = await fileAttach(selector, index, value, meta.filename, meta.mime, label);
          if (res.ok) filled++;
          else {
            errors.push(res.reason);
            failed++;
          }
          await sleep(delay_ms || 200);
          continue;
        }

        const el = await waitForElement(selector, index, 6000, label, scopeName);
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
