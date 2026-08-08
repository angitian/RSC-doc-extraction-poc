// Content script for detecting exact HTML Element IDs and auto-filling target web forms
console.log("[DocToSmartData v1] Enhanced Content Script Loaded.");

// Mapping rules targeting exact Web Form Element IDs and Fallback Aliases
// Phase 3: Multiple candidate IDs per field for robustness against React dynamic ID changes
const EXACT_ID_MAP = [
  { ids: ['acc-field'], key: 'acc_code', type: 'select' },
  { ids: ['project-document-number'], key: 'doc_number_tail', type: 'input' },
  { ids: ['project-document-date'], key: 'doc_date_iso', type: 'date' },
  { ids: ['project-document-contact-phone'], key: 'contact_phone', type: 'input' },
  { ids: ['project-applicant-name'], key: 'requester_name', type: 'input' },
  { ids: ['project-applicant-position'], key: 'requester_position', type: 'input' },
  { ids: ['input-94', 'input-39', 'input-130'], key: 'project_title', type: 'input', labelHint: 'ชื่อโครงการ' },
  { ids: ['backgroundContext-field'], key: 'project_context', type: 'richtext', labelHint: 'ที่มา' },
  { ids: ['textarea-19', 'textarea-5', 'textarea-12'], key: 'project_objective', type: 'textarea', labelHint: 'วัตถุประสงค์' },
  { ids: ['input-93', 'input-40', 'input-88'], key: 'action_verb', type: 'input', labelHint: 'คำกริยา' },
  { ids: ['project-location-0-location', 'input-41'], key: 'location_name', type: 'input', labelHint: 'สถานที่' },
  { ids: ['project-location-0-province', 'input-42'], key: 'province_name', type: 'input', labelHint: 'จังหวัด' },
  { ids: ['project-location-shared-start-date', 'input-43'], key: 'start_date_iso', type: 'date', labelHint: 'เริ่มต้น' },
  { ids: ['project-location-shared-end-date', 'input-44'], key: 'end_date_iso', type: 'date', labelHint: 'สิ้นสุด' },
  { ids: ['target-group-name-project-target-group-2'], key: 'target_group_name', type: 'input' },
  { ids: ['target-group-quantity-project-target-group-2'], key: 'target_group_quantity', type: 'input' },
  { ids: ['target-group-unit-project-target-group-2'], key: 'target_group_unit', type: 'input' },
  { ids: ['project-additional-details'], key: 'action_details', type: 'textarea' },
  { ids: ['input-95', 'input-45', 'input-131'], key: 'budget_amount', type: 'input', labelHint: 'วงเงินรวม' }
];

const FALLBACK_ALIASES = {
  acc_code: ['acc-field', 'acc_code', 'budget_code', 'รหัสงบประมาณ'],
  doc_number_tail: ['project-document-number', 'doc_number', 'doc_no', 'เลขที่หนังสือ'],
  doc_date_iso: ['project-document-date', 'doc_date', 'document_date', 'วันที่หนังสือ'],
  contact_phone: ['project-document-contact-phone', 'contact-phone', 'phone', 'telephone', 'mobile', 'โทรศัพท์', 'เบอร์โทร'],
  requester_name: ['project-applicant-name', 'requester_name', 'applicant_name', 'ชื่อผู้ขอ'],
  requester_position: ['project-applicant-position', 'requester_position', 'ตำแหน่ง'],
  project_title: ['input-94', 'input-39', 'project_title', 'subject', 'title', 'ชื่อโครงการ'],
  project_context: ['backgroundContext-field', 'project-additional-details', 'project_context', 'ความเป็นมา', 'ที่มา'],
  project_objective: ['textarea-19', 'textarea-5', 'project_objective', 'วัตถุประสงค์'],
  action_verb: ['input-93', 'input-40', 'action_verb', 'คำกริยา'],
  target_group_name: ['target-group-name-project-target-group-2', 'target_group_name', 'กลุ่มเป้าหมาย'],
  target_group_quantity: ['target-group-quantity-project-target-group-2', 'target_group_quantity', 'จำนวน'],
  target_group_unit: ['target-group-unit-project-target-group-2', 'target_group_unit', 'หน่วย'],
  action_details: ['project-additional-details', 'action_details', 'รายละเอียดเพิ่มเติม'],
  location_name: ['project-location-0-location', 'input-41', 'location_name', 'location', 'สถานที่'],
  province_name: ['project-location-0-province', 'input-42', 'province_name', 'province', 'จังหวัด'],
  start_date_iso: ['project-location-shared-start-date', 'input-43', 'start_date', 'วันที่เริ่มต้น'],
  end_date_iso: ['project-location-shared-end-date', 'input-44', 'end_date', 'วันที่สิ้นสุด'],
  budget_amount: ['input-95', 'input-45', 'input-130', 'budget_amount', 'budget', 'amount', 'วงเงินรวม']
};

function setElementValueAndTriggerEvents(elem, value) {
  if (!elem || value === undefined || value === null) return false;

  elem.focus();
  const strVal = String(value).trim();
  
  if (elem.isContentEditable) {
    // Rich Text Editor (Quill / Tiptap / ProseMirror / Draft.js / Lexical)
    elem.innerText = strVal;
    elem.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: strVal }));
    elem.dispatchEvent(new Event('change', { bubbles: true }));
    elem.dispatchEvent(new Event('blur', { bubbles: true }));
  } else if (elem.tagName === 'SELECT') {
    let matchedOption = false;
    for (let option of elem.options) {
      if (option.value === strVal || option.text.includes(strVal)) {
        option.selected = true;
        matchedOption = true;
        break;
      }
    }
    if (!matchedOption && elem.options.length > 0) {
      elem.value = strVal;
    }
  } else if (elem.type === 'checkbox' || elem.type === 'radio') {
    elem.checked = Boolean(value);
  } else if (elem.type === 'date' || elem.placeholder?.toLowerCase().includes('mm/dd/yyyy') || elem.placeholder?.toLowerCase().includes('dd/mm/yyyy')) {
    // Standard HTML5 date input or Custom React Date Picker
    let dateStr = strVal;
    if (strVal.includes('/')) {
      const parts = strVal.split('/');
      if (parts.length === 3) {
        // MM/DD/YYYY or DD/MM/YYYY to YYYY-MM-DD
        let year = parts[2];
        if (parseInt(year) > 2500) year = String(parseInt(year) - 543);
        dateStr = `${year}-${parts[0].padStart(2, '0')}-${parts[1].padStart(2, '0')}`;
      }
    }
    
    // Set value and trigger native HTML5 date input setter + events
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
    if (nativeInputValueSetter) {
      nativeInputValueSetter.call(elem, dateStr);
    } else {
      elem.value = dateStr;
    }
    
    elem.dispatchEvent(new Event('input', { bubbles: true }));
    elem.dispatchEvent(new Event('change', { bubbles: true }));
    elem.dispatchEvent(new Event('blur', { bubbles: true }));
  } else {
    // For standard text inputs or textareas
    elem.value = strVal;
    elem.dispatchEvent(new Event('input', { bubbles: true }));
    elem.dispatchEvent(new Event('change', { bubbles: true }));
    elem.dispatchEvent(new Event('blur', { bubbles: true }));
  }

  // Visual highlight confirmation
  const origBg = elem.style.backgroundColor;
  elem.style.backgroundColor = '#dcfce7';
  elem.style.border = '2px solid #16a34a';
  setTimeout(() => {
    elem.style.backgroundColor = origBg;
    elem.style.border = '';
  }, 2500);

  return true;
}

// Helper to wait for DOM element to exist (legacy, kept for compatibility)
function waitForElement(id, timeoutMs = 1500) {
  return new Promise((resolve) => {
    const existing = document.getElementById(id);
    if (existing) return resolve(existing);

    const observer = new MutationObserver(() => {
      const el = document.getElementById(id);
      if (el) {
        observer.disconnect();
        resolve(el);
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => {
      observer.disconnect();
      resolve(document.getElementById(id));
    }, timeoutMs);
  });
}

// Phase 1: Wait for element to exist AND remain stable in DOM for stableMs
// This prevents race conditions where React re-renders and removes/re-adds elements
async function waitForElementStable(id, timeoutMs = 5000, stableMs = 400) {
  const startTime = Date.now();
  let el = document.getElementById(id);

  while (Date.now() - startTime < timeoutMs) {
    if (el) {
      // Wait for stability period to confirm React has finished reconciling
      await new Promise(r => setTimeout(r, stableMs));
      const reCheck = document.getElementById(id);
      if (reCheck) return reCheck;
    }
    // Use MutationObserver to wait for next DOM change
    el = await new Promise((resolve) => {
      const existing = document.getElementById(id);
      if (existing) return resolve(existing);

      const observer = new MutationObserver(() => {
        const found = document.getElementById(id);
        if (found) {
          observer.disconnect();
          resolve(found);
        }
      });

      observer.observe(document.body, { childList: true, subtree: true });
      const remaining = timeoutMs - (Date.now() - startTime);
      setTimeout(() => {
        observer.disconnect();
        resolve(document.getElementById(id));
      }, Math.max(remaining, 100));
    });
  }
  return document.getElementById(id);
}

// Helper to click button safely with MouseEvent and wait for dynamic UI update
async function clickButtonWithTextAsync(targetText, waitMs = 300) {
  const btns = Array.from(document.querySelectorAll('button'));
  const targetBtn = btns.find(b => (b.innerText || b.textContent || '').trim().includes(targetText));
  if (targetBtn) {
    targetBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, waitMs));
    return true;
  }
  return false;
}

// Phase 1: Click button with specific text inside a scoped container only
function clickButtonInContainer(container, buttonText) {
  if (!container) return false;
  const btns = Array.from(container.querySelectorAll('button'));
  const targetBtn = btns.find(b => (b.innerText || b.textContent || '').trim().includes(buttonText));
  if (targetBtn) {
    targetBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    return true;
  }
  return false;
}

// Phase 1: Find the day container for a given schedule-day index d
function findDayContainer(d) {
  const dateInput = document.getElementById(`schedule-date-${d}`);
  if (!dateInput) return null;
  // Walk up to find the card/section container
  return dateInput.closest('[class*="rounded"], [class*="border"], [class*="card"], fieldset, section') || dateInput.parentElement?.parentElement?.parentElement || null;
}

// Phase 3: Helper to find input/textarea element by associated label text (enhanced)
function findElementByLabelHint(labelHint) {
  if (!labelHint) return null;
  const hintLower = labelHint.toLowerCase();

  // 1. Try data-field attribute first (most reliable if available)
  const dataFieldEl = document.querySelector(`[data-field="${labelHint}"]`);
  if (dataFieldEl) return dataFieldEl;

  // 2. Try aria-label match
  const ariaEl = Array.from(document.querySelectorAll('[aria-label]')).find(el =>
    (el.getAttribute('aria-label') || '').toLowerCase().includes(hintLower)
  );
  if (ariaEl) return ariaEl;

  // 3. Try label text match
  const labels = Array.from(document.querySelectorAll('label'));
  const targetLabel = labels.find(l =>
    (l.innerText || l.textContent || '').toLowerCase().includes(hintLower)
  );
  if (targetLabel) {
    if (targetLabel.htmlFor) {
      const el = document.getElementById(targetLabel.htmlFor);
      if (el) return el;
    }
    // Look in parent container (expanded from 3 to 5 levels)
    let container = targetLabel.parentElement;
    for (let i = 0; i < 5 && container; i++) {
      const inputEl = container.querySelector('input, textarea, select, [contenteditable="true"]');
      if (inputEl) return inputEl;
      container = container.parentElement;
    }
  }

  // 4. Try placeholder match
  const placeholderEl = Array.from(document.querySelectorAll('input, textarea')).find(el =>
    (el.placeholder || '').toLowerCase().includes(hintLower)
  );
  if (placeholderEl) return placeholderEl;

  return null;
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'AUTO_FILL_FORM') {
    (async () => {
      const payload = request.data || {};
      let filledCount = 0;
      const filledElements = new Set();

      // 0. Ensure target sections are visible if collapsed
      EXACT_ID_MAP.forEach(item => {
        for (const cid of item.ids) {
          const elem = document.getElementById(cid);
          if (elem) {
            let parent = elem.parentElement;
            while (parent && parent !== document.body) {
              if (window.getComputedStyle(parent).display === 'none') {
                parent.style.display = 'block';
              }
              parent = parent.parentElement;
            }
            break;
          }
        }
      });

      // 1. Direct ID Fill & Label Hint Fallback Search (Phase 3: multiple candidate IDs)
      for (const item of EXACT_ID_MAP) {
        let elem = null;
        for (const cid of item.ids) {
          elem = document.getElementById(cid);
          if (elem) break;
        }
        if (!elem && item.labelHint) {
          elem = findElementByLabelHint(item.labelHint);
        }

        // Fallback search for textareas & rich text editors if exact ID didn't match directly
        if (!elem) {
          const textareas = document.querySelectorAll('textarea, [contenteditable="true"], .ql-editor');
          for (let ta of textareas) {
            if (filledElements.has(ta)) continue;
            
            let parentNode = ta.parentElement;
            let containerText = '';
            for (let level = 0; level < 8 && parentNode; level++) {
              containerText += ' ' + (parentNode.innerText || '');
              parentNode = parentNode.parentElement;
            }
            const placeholder = (ta.placeholder || '').toLowerCase();
            
            if (item.key === 'project_context') {
              if (containerText.includes('ที่มา') || containerText.includes('บริบท') || placeholder.includes('ที่มา') || placeholder.includes('บริบท')) {
                elem = ta;
                break;
              }
            } else if (item.key === 'project_objective') {
              if (containerText.includes('วัตถุประสงค์') || placeholder.includes('วัตถุประสงค์')) {
                elem = ta;
                break;
              }
            }
          }
        }

        let val = payload[item.key];
        if (item.key === 'doc_number_tail' && val) {
          val = String(val).replace(/^(?:อว\.?|\.)\s*/i, '').replace(/\s+/g, ' ').trim();
        }
        if ((item.key === 'requester_name' || item.key === 'approver_left_name' || item.key === 'approver_right_name') && val) {
          val = String(val).replace(/^[\(\（\s]+|[\)\）\s]+$/g, '').trim();
        }
        if (elem && val) {
          if (setElementValueAndTriggerEvents(elem, val)) {
            filledCount++;
            filledElements.add(elem);
          }
        }
      }

      // 1.5 Dedicated Rich Text Editor / Textarea Backup Fill by DOM order
      const allTextareas = document.querySelectorAll('textarea, [contenteditable="true"], .ql-editor');
      if (allTextareas.length >= 2) {
        if (payload.project_context && !Array.from(filledElements).some(el => (el.innerText || el.value || '').includes('ตามที่'))) {
          setElementValueAndTriggerEvents(allTextareas[0], payload.project_context);
          filledElements.add(allTextareas[0]);
        }
        if (payload.project_objective && !Array.from(filledElements).some(el => (el.innerText || el.value || '').includes('ในการนี้'))) {
          setElementValueAndTriggerEvents(allTextareas[1], payload.project_objective);
          filledElements.add(allTextareas[1]);
        }
      }

      // 1.6 Dedicated Smart Search for doc_number_tail and contact_phone
      const allInputs = document.querySelectorAll('input');
      allInputs.forEach(input => {
        if (filledElements.has(input)) return;

        let labelEl = input.id ? document.querySelector(`label[for="${input.id}"]`) : null;
        let labelText = labelEl ? labelEl.innerText.toLowerCase() : '';
        
        let pNode = input.parentElement;
        let containerText = '';
        for (let l = 0; l < 4 && pNode; l++) {
          containerText += ' ' + (pNode.innerText || '').toLowerCase();
          pNode = pNode.parentElement;
        }
        const ph = (input.placeholder || '').toLowerCase();

        if (payload.contact_phone && (labelText.includes('โทรศัพท์') || containerText.includes('โทรศัพท์') || ph.includes('9682') || ph.includes('02-470'))) {
          if (!containerText.includes('เลขที่หนังสือ') && !labelText.includes('เลขที่')) {
            if (setElementValueAndTriggerEvents(input, payload.contact_phone)) {
              filledCount++;
              filledElements.add(input);
              return;
            }
          }
        }

        if (payload.doc_number_tail && (labelText.includes('เลขที่') || containerText.includes('เลขที่หนังสือ') || containerText.includes('อว.') || input.id === 'project-document-number')) {
          if (!containerText.includes('โทรศัพท์') && !labelText.includes('โทรศัพท์')) {
            let cleanTail = String(payload.doc_number_tail)
              .replace(/^(?:อว\.?|\.)\s*/i, '')
              .replace(/\s+/g, ' ')
              .trim();
            
            if (cleanTail.endsWith('/') && payload.budget_year) {
              const yrSuffix = String(payload.budget_year).slice(-2);
              cleanTail = `${cleanTail}${yrSuffix}`;
            }

            if (setElementValueAndTriggerEvents(input, cleanTail)) {
              filledCount++;
              filledElements.add(input);
              return;
            }
          }
        }
      });

      // 2. Fallback Heuristic Match for remaining elements
      const inputs = document.querySelectorAll('input, textarea, select');
      inputs.forEach(input => {
        if (filledElements.has(input)) return;

        const id = (input.id || '').toLowerCase();
        const name = (input.name || '').toLowerCase();
        const placeholder = (input.placeholder || '').toLowerCase();
        
        let labelText = '';
        if (input.id) {
          const label = document.querySelector(`label[for="${input.id}"]`);
          if (label) labelText = label.innerText.toLowerCase();
        }
        if (!labelText && input.closest('label')) {
          labelText = input.closest('label').innerText.toLowerCase();
        }

        for (const [key, aliases] of Object.entries(FALLBACK_ALIASES)) {
          const val = payload[key];
          if (!val) continue;

          const isMatch = aliases.some(alias => {
            const a = alias.toLowerCase();
            return id.includes(a) || name.includes(a) || placeholder.includes(a) || labelText.includes(a);
          });

          if (isMatch) {
            if (setElementValueAndTriggerEvents(input, val)) {
              filledCount++;
              filledElements.add(input);
              break;
            }
          }
        }
      });

      // 1.7 Dynamic Budget Amount Fill
      if (payload.budget_amount) {
        const budgetInps = document.querySelectorAll('input');
        budgetInps.forEach(inp => {
          if (filledElements.has(inp)) return;
          const id = (inp.id || '').toLowerCase();
          let labelText = '';
          if (inp.id) {
            const l = document.querySelector(`label[for="${inp.id}"]`);
            if (l) labelText = l.innerText.toLowerCase();
          }
          if (!labelText && inp.closest('label')) labelText = inp.closest('label').innerText.toLowerCase();
          if (id === 'input-130' || id === 'input-45' || labelText.includes('วงเงินรวม')) {
            setElementValueAndTriggerEvents(inp, payload.budget_amount);
            filledElements.add(inp);
            filledCount++;
          }
        });
      }

      // 1.8 Auto-fill Dynamic Expense Breakdown Table (Phase 2: stable wait + row count verification)
      if (payload.breakdown && Array.isArray(payload.breakdown) && payload.breakdown.length > 0) {
        const expGeneratedRadio = document.getElementById('expense-document-source-generated');
        if (expGeneratedRadio) {
          expGeneratedRadio.checked = true;
          expGeneratedRadio.dispatchEvent(new Event('change', { bubbles: true }));
          const labelForExp = document.querySelector('label[for="expense-document-source-generated"]');
          if (labelForExp) labelForExp.click();
          else expGeneratedRadio.click();
          await new Promise(r => setTimeout(r, 500));
        }

        const expProjInput = document.getElementById('generated-expense-project-name');
        const expDeptInput = document.getElementById('generated-expense-department');
        if (expProjInput && payload.project_title) setElementValueAndTriggerEvents(expProjInput, payload.project_title);
        if (expDeptInput && payload.agency_name) setElementValueAndTriggerEvents(expDeptInput, payload.agency_name);

        // Ensure enough breakdown rows exist with stable DOM wait
        for (let i = 0; i < payload.breakdown.length; i++) {
          let descInput = document.getElementById(`expense-description-${i}`);
          if (!descInput && i > 0) {
            // Count existing rows before clicking
            const existingRows = document.querySelectorAll('[id^="expense-description-"]').length;
            await clickButtonWithTextAsync('เพิ่มรายการ', 300);
            descInput = await waitForElementStable(`expense-description-${i}`, 5000, 400);
            // Verify row count increased; retry once if not
            if (!descInput) {
              console.warn(`[DocToSmartData] Expense row ${i} not found after click, retrying...`);
              await new Promise(r => setTimeout(r, 800));
              await clickButtonWithTextAsync('เพิ่มรายการ', 300);
              descInput = await waitForElementStable(`expense-description-${i}`, 5000, 400);
            }
          }
        }

        // Fill dynamic rows
        for (let idx = 0; idx < payload.breakdown.length; idx++) {
          const row = payload.breakdown[idx];
          let typeSelect = document.getElementById(`expense-row-type-${idx}`);
          let numInput = document.getElementById(`expense-number-${idx}`);
          let descInput = document.getElementById(`expense-description-${idx}`);
          let calcInput = document.getElementById(`expense-calculation-${idx}`);
          let loanInput = document.getElementById(`expense-loan-${idx}`);

          if (typeSelect) setElementValueAndTriggerEvents(typeSelect, 'item');
          if (numInput) setElementValueAndTriggerEvents(numInput, String(idx + 1));

          const itemName = row['รายการ'] || row['item'] || '';
          const itemDetail = row['รายละเอียด'] || row['detail'] || '';
          const itemAmount = String(row['จำนวนเงิน (บาท)'] || row['amount'] || '').replace(/,/g, '').trim();

          if (descInput && itemName) setElementValueAndTriggerEvents(descInput, itemName);
          if (calcInput && itemDetail && itemDetail !== '-') setElementValueAndTriggerEvents(calcInput, itemDetail);
          if (loanInput && itemAmount) setElementValueAndTriggerEvents(loanInput, itemAmount);
          await new Promise(r => setTimeout(r, 150));
        }
      }

      // 1.9 Auto-fill Dynamic Schedule Activities (Phase 1: stable wait + container scoping + retry)
      if (payload.schedule_document_title || (payload.schedule_activities && payload.schedule_activities.length > 0)) {
        const schedGeneratedRadio = document.getElementById('schedule-document-source-generated');
        if (schedGeneratedRadio) {
          schedGeneratedRadio.checked = true;
          schedGeneratedRadio.dispatchEvent(new Event('change', { bubbles: true }));
          const labelForSched = document.querySelector('label[for="schedule-document-source-generated"]');
          if (labelForSched) {
            labelForSched.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
          } else {
            schedGeneratedRadio.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
          }
          await new Promise(r => setTimeout(r, 600));
        }

        const schedTitleInput = document.getElementById('generated-schedule-title');
        if (schedTitleInput && payload.project_title) {
          setElementValueAndTriggerEvents(schedTitleInput, payload.schedule_document_title || `กำหนดการ${payload.project_title}`);
        }

        if (Array.isArray(payload.schedule_activities)) {
          for (let d = 0; d < payload.schedule_activities.length; d++) {
            const dayData = payload.schedule_activities[d];
            if (!dayData) continue;

            // 1. Ensure Day Block d exists
            let dateInput = document.getElementById(`schedule-date-${d}`);
            if (!dateInput) {
              if (d > 0) {
                await clickButtonWithTextAsync('เพิ่มวันหรือช่วงกิจกรรม', 500);
                dateInput = await waitForElementStable(`schedule-date-${d}`, 5000, 500);
                // Retry once if not found
                if (!dateInput) {
                  console.warn(`[DocToSmartData] schedule-date-${d} not found after click, retrying...`);
                  await new Promise(r => setTimeout(r, 800));
                  await clickButtonWithTextAsync('เพิ่มวันหรือช่วงกิจกรรม', 500);
                  dateInput = await waitForElementStable(`schedule-date-${d}`, 5000, 500);
                }
              } else {
                dateInput = document.getElementById('schedule-date-0');
              }
            }

            if (!dateInput) {
              console.warn(`[DocToSmartData] Could not find schedule-date-${d}, skipping day ${d}`);
              continue;
            }

            let locInput = document.getElementById(`schedule-location-${d}`);

            // 2. Fill Day Header
            if (dayData.date_title) setElementValueAndTriggerEvents(dateInput, dayData.date_title);
            if (locInput && dayData.location) setElementValueAndTriggerEvents(locInput, dayData.location);
            await new Promise(r => setTimeout(r, 300));

            // 3. Process Activity Items — strictly sequential with stable DOM wait
            if (Array.isArray(dayData.items)) {
              for (let a = 0; a < dayData.items.length; a++) {
                const actData = dayData.items[a];
                if (!actData) continue;

                let actInput = document.getElementById(`schedule-activity-${d}-${a}`);
                let timeInput = document.getElementById(`schedule-time-${d}-${a}`);

                // If activity (d, a) doesn't exist yet, click add button scoped to day d's container
                if (!actInput || !timeInput) {
                  if (a > 0) {
                    // Find the day container using our helper
                    const dayContainer = findDayContainer(d);
                    let clicked = false;

                    if (dayContainer) {
                      clicked = clickButtonInContainer(dayContainer, 'เพิ่มกิจกรรมในช่วงนี้');
                    }

                    // Fallback: if container-scoped click failed, try global search by index
                    if (!clicked) {
                      const allAddBtns = Array.from(document.querySelectorAll('button')).filter(
                        b => (b.innerText || b.textContent || '').trim().includes('เพิ่มกิจกรรมในช่วงนี้')
                      );
                      if (allAddBtns[d]) {
                        allAddBtns[d].dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                        clicked = true;
                      } else if (allAddBtns.length > 0) {
                        allAddBtns[allAddBtns.length - 1].dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                        clicked = true;
                      }
                    }

                    if (clicked) {
                      actInput = await waitForElementStable(`schedule-activity-${d}-${a}`, 5000, 500);
                      timeInput = document.getElementById(`schedule-time-${d}-${a}`);
                    }

                    // Retry once if still not found
                    if (!actInput || !timeInput) {
                      console.warn(`[DocToSmartData] schedule-activity-${d}-${a} not found, retrying...`);
                      await new Promise(r => setTimeout(r, 800));
                      const retryContainer = findDayContainer(d);
                      if (retryContainer) {
                        clickButtonInContainer(retryContainer, 'เพิ่มกิจกรรมในช่วงนี้');
                      }
                      await new Promise(r => setTimeout(r, 500));
                      actInput = await waitForElementStable(`schedule-activity-${d}-${a}`, 5000, 500);
                      timeInput = document.getElementById(`schedule-time-${d}-${a}`);
                    }
                  } else {
                    // First activity (a=0) should already exist with the day block
                    actInput = await waitForElementStable(`schedule-activity-${d}-0`, 3000, 300);
                    timeInput = document.getElementById(`schedule-time-${d}-0`);
                  }
                }

                // Fill current activity item
                if (timeInput && actData.time) setElementValueAndTriggerEvents(timeInput, actData.time);
                if (actInput && actData.activity) setElementValueAndTriggerEvents(actInput, actData.activity);
                await new Promise(r => setTimeout(r, 250));
              }
            }
          }
        }
      }

      sendResponse({ status: 'success', filledCount: filledCount });
    })();
  }
  return true;
});
