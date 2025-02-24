console.log("[DEBUG] content.js is running and ready.");

// Helper function to safely query selectors
function safeQueryAll(selector) {
    try {
        return document.querySelectorAll(selector);
    } catch (error) {
        console.error(`[ERROR] Failed to query selector: ${selector}`, error);
        return [];
    }
}

// Function to extract recipe data from the webpage
function extractRecipe() {
    console.log("[DEBUG] Extracting recipe from webpage...");

    // Get the title from the first <h1> or default to "Untitled Recipe"
    let title = document.querySelector("h1")?.innerText.trim() || "Untitled Recipe";
    
    // Updated selectors for ingredients
    let ingredientSelectors = [
        ".ingredient", 
        ".ingredients-item", 
        ".recipe-ingredients li", 
        "ul[class*=ingredient]", 
        "li[class*=ingredient]",
        "span[class*=ingredient]",
        "div[class*=ingredient]",
        ".tasty-recipes-ingredients-body li",
        ".ingredients",              // New: common container for ingredients
        "div.ingredients",           // New: ingredients in a div
        "section.ingredients",       // New: ingredients in a section
        "ul.ingredients li",         // New: list items within an ingredients list
        "ol.ingredients li",         // New: if ingredients are in an ordered list
        ".recipe__ingredients li"    // New: alternative naming convention
    ];
    
    let ingredients = [];
    ingredientSelectors.forEach(selector => {
        safeQueryAll(selector).forEach(el => {
            let text = el.innerText.trim();
            if (text.length > 0 && !ingredients.includes(text)) {
                ingredients.push(text);
            }
        });
    });

    // Updated selectors for instructions
    let instructionSelectors = [
        ".instruction", 
        ".instructions-step", 
        ".recipe-instructions li",
        "p[class*=instruction]",
        "div[class*=step]",
        "div[class*=directions]",
        "section[class*=directions]",
        ".tasty-recipes-instructions-body li",
        ".instructions",            // New: common container for instructions
        "div.instructions",         // New: instructions in a div
        "section.instructions",     // New: instructions in a section
        "ol.instructions li",       // New: ordered list items for instructions
        "ul.instructions li",       // New: unordered list items for instructions
        ".recipe__instructions li", // New: alternative naming convention
        "div.recipe-method li",     // New: method steps in a div
        "section.recipe-method li"  // New: method steps in a section
    ];

    let instructions = [];
    instructionSelectors.forEach(selector => {
        safeQueryAll(selector).forEach(el => {
            let text = el.innerText.trim();
            if (text.length > 0 && !instructions.includes(text)) {
                instructions.push(text);
            }
        });
    });

    // Log warnings if data is missing
    if (ingredients.length === 0) console.warn("[WARNING] Could not find ingredients.");
    if (instructions.length === 0) console.warn("[WARNING] Could not find instructions.");

    // Format as Markdown
    let markdown = `---
title: "${title}"
source: "${window.location.href}"
tags: ["recipe", "saved"]
date: ${new Date().toISOString().split("T")[0]}
---

# ${title}

## Ingredients
${ingredients.length > 0 ? ingredients.map(i => `- ${i}`).join("\n") : "*No ingredients found*"}

## Instructions
${instructions.length > 0 ? instructions.map((step, index) => `${index + 1}. ${step}`).join("\n") : "*No instructions found*"}
`;

    console.log("[DEBUG] Extracted Markdown:", markdown);
    return { title, markdown };
}

// Listen for messages from popup.js
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log("[DEBUG] content.js received message:", request);

    if (request.action === "extractRecipe") {
        console.log("[DEBUG] Extracting recipe...");
        let recipeData = extractRecipe();

        // Send extracted recipe data back to popup.js
        sendResponse({ status: "Recipe extracted", data: recipeData });

        // Also send data to background.js for saving
        chrome.runtime.sendMessage({
            action: "downloadRecipe",
            markdown: recipeData.markdown,
            filename: recipeData.title.replace(/\s+/g, "_").toLowerCase()
        }, (response) => {
            if (chrome.runtime.lastError) {
                console.error("[ERROR] Message failed:", chrome.runtime.lastError.message);
            } else {
                console.log("[DEBUG] Background response:", response);
            }
        });

        return true; // Keeps the connection alive for async response
    }
});

console.log("[DEBUG] content.js is fully loaded and waiting for a request.");



