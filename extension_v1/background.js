// Background Service Worker for Right-Click Context Menu and Clipboard Auto-Fill
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "RSC_AUTO_FILL_CLICK",
    title: "⚡ กรอกฟอร์มด้วย RSC_Approval (Auto-Fill)",
    contexts: ["page", "editable"]
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "RSC_AUTO_FILL_CLICK" && tab && tab.id) {
    try {
      // Ensure content script is loaded on the target tab
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js']
      });

      // Execute clipboard read script on the tab
      const [{ result }] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => navigator.clipboard.readText()
      });

      if (result) {
        let parsedData;
        try {
          parsedData = JSON.parse(result);
        } catch (e) {
          console.error("Invalid JSON clipboard data");
          return;
        }
        chrome.tabs.sendMessage(tab.id, { action: "AUTO_FILL_FORM", data: parsedData });
      }
    } catch (err) {
      console.error("Context menu fill error:", err);
    }
  }
});
