chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log("[DEBUG] Background script received message:", request);

    if (request.action === "extractRecipe") {
        console.log("[DEBUG] Preparing to download recipe...");

        // Using Data URL instead of Blob URL
        let dataUrl = 'data:text/markdown;charset=utf-8,' + encodeURIComponent(request.markdown);
        
        chrome.downloads.download({
            url: dataUrl,
            filename: `${request.filename}.md`,
            conflictAction: "overwrite",
            saveAs: true
        }, (downloadId) => {
            if (chrome.runtime.lastError) {
                console.error("[ERROR] Download failed:", chrome.runtime.lastError.message);
            } else {
                console.log("[SUCCESS] Download started! Download ID:", downloadId);
            }
        });

        sendResponse({ status: "done" });
    }

    return true; // Keeps connection alive
});

console.log("[DEBUG] Background script loaded successfully.");
