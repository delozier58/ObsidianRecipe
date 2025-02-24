document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("extractRecipe").addEventListener("click", () => {
        console.log("[DEBUG] Button clicked - Sending message to content.js");

        // ✅ Send a message to content.js to extract the recipe
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs.length === 0) {
                console.error("[ERROR] No active tab found.");
                return;
            }
            chrome.runtime.sendMessage({ action: "extractRecipe" }, (response) => {
                if (chrome.runtime.lastError) {
                    console.error("[ERROR] Message failed:", chrome.runtime.lastError.message);
                } else {
                    console.log("[DEBUG] Response from content.js:", response);
                }
            });
        });
    });
});

