// Background service worker — MV3
// 1) Opens the side panel when the toolbar action is clicked
// 2) Bridges side-panel messages to the active tab's content script
//    (injects content.js on demand so it only runs when needed)

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
});

// Ensure the panel also opens via the action on every click
chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ tabId: tab.id }).catch(() => {});
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && (msg.action === "FILL_FORM" || msg.action === "CAPTURE_FORM")) {
    const { tabId } = msg;
    (async () => {
      try {
        // Inject the content script on demand
        await chrome.scripting.executeScript({
          target: { tabId },
          files: ["scripts/content.js"],
        });
        const response = await chrome.tabs.sendMessage(tabId, {
          action: msg.action,
          payload: msg.payload,
        });
        sendResponse({ ok: true, result: response });
      } catch (err) {
        sendResponse({ ok: false, error: String(err && err.message ? err.message : err) });
      }
    })();
    return true; // keep the message channel open for async sendResponse
  }
  return false;
});
