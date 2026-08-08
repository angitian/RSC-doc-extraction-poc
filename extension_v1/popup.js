document.addEventListener('DOMContentLoaded', () => {
  const jsonInput = document.getElementById('json-input');
  const statusTag = document.getElementById('status-tag');
  const btnPaste = document.getElementById('btn-paste');
  const btnFill = document.getElementById('btn-fill');
  const logMsg = document.getElementById('log-message');

  function log(msg) {
    logMsg.innerText = msg;
  }

  // Load saved JSON from storage
  chrome.storage.local.get(['smartDataJson'], (result) => {
    if (result.smartDataJson) {
      jsonInput.value = result.smartDataJson;
      statusTag.innerText = 'พร้อมกรอกข้อมูล';
      statusTag.className = 'status-badge status-ready';
    }
  });

  // Save changes to storage
  jsonInput.addEventListener('input', () => {
    const val = jsonInput.value.strip ? jsonInput.value.strip() : jsonInput.value.trim();
    chrome.storage.local.set({ smartDataJson: val });
    if (val) {
      statusTag.innerText = 'พร้อมกรอกข้อมูล';
      statusTag.className = 'status-badge status-ready';
    } else {
      statusTag.innerText = 'ยังไม่มีข้อมูล JSON';
      statusTag.className = 'status-badge status-empty';
    }
  });

  // Paste from clipboard button
  btnPaste.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        jsonInput.value = text;
        chrome.storage.local.set({ smartDataJson: text });
        statusTag.innerText = 'พร้อมกรอกข้อมูล';
        statusTag.className = 'status-badge status-ready';
        log('คัดลอกข้อมูลจาก Clipboard เรียบร้อย!');
      } else {
        log('ไม่พบข้อความใน Clipboard');
      }
    } catch (err) {
      log('กรุณาวางข้อความลงในช่องด้านบนโดยตรง (Ctrl+V)');
    }
  });

  // Trigger auto-fill in content script
  btnFill.addEventListener('click', async () => {
    const rawJson = jsonInput.value.trim();
    if (!rawJson) {
      log('⚠️ กรุณาวางหรือระบุข้อมูล JSON ก่อนกดกรอกฟอร์ม');
      return;
    }

    let parsedData;
    try {
      parsedData = JSON.parse(rawJson);
    } catch (e) {
      log('❌ รูปแบบ JSON ไม่ถูกต้อง');
      return;
    }

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) {
      log('❌ ไม่พบแท็บที่กำลังเปิดอยู่');
      return;
    }

    // Ensure content script is injected if not already running on the active tab
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js']
      });
    } catch (e) {
      console.log("Script already injected or permission note:", e);
    }

    chrome.tabs.sendMessage(tab.id, { action: 'AUTO_FILL_FORM', data: parsedData }, (response) => {
      if (chrome.runtime.lastError) {
        log('❌ Error: ' + chrome.runtime.lastError.message);
      } else if (response && response.status === 'success') {
        log(`✅ กรอกข้อมูลสำเร็จ! รวม ${response.filledCount} ช่อง`);
      } else {
        log('⚠️ ไม่สามารถส่งข้อมูลไปยังหน้าเว็บได้');
      }
    });
  });
});
