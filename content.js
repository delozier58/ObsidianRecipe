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

// Helper function to normalize text for comparison
function normalizeText(text) {
    return text.toLowerCase().replace(/\s+/g, ' ').trim();
}

// Function to clean text of common photo credits and unnecessary elements
function cleanText(text) {
    // Remove photo credits and common unwanted text
    const unwantedPatterns = [
        /DOTDASH MEREDITH FOOD STUDIOS/gi,
        /CHEF JOHN/gi,
        /PHOTO BY .+?(?=\.|\n|$)/gi,
        /CREDIT: .+?(?=\.|\n|$)/gi,
        /IMAGE BY .+?(?=\.|\n|$)/gi,
        /COURTESY OF .+?(?=\.|\n|$)/gi,
        /PHOTO: .+?(?=\.|\n|$)/gi,
        /PHOTOGRAPH BY .+?(?=\.|\n|$)/gi,
        /©.+?(?=\.|\n|$)/gi,
        /PICTURED: .+?(?=\.|\n|$)/gi,
        /ALLRECIPES MAGAZINE/gi,
        /[©®™]/g // Remove copyright and trademark symbols
    ];

    let cleanedText = text;
    unwantedPatterns.forEach(pattern => {
        cleanedText = cleanedText.replace(pattern, '');
    });

    // Remove excess whitespace
    cleanedText = cleanedText.replace(/\s+/g, ' ').trim();
    
    return cleanedText;
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
        "ul[class*=ingredient] li",
        "li[class*=ingredient]",
        "span[class*=ingredient]",
        "div[class*=ingredient] li",
        ".tasty-recipes-ingredients-body li",
        ".ingredients li",
        "div.ingredients li",
        "section.ingredients li",
        "ul.ingredients li",
        "ol.ingredients li",
        ".recipe__ingredients li"
    ];
    
    // Use a Set with normalized text to avoid duplicates
    let ingredientSet = new Set();
    let ingredients = [];
    
    ingredientSelectors.forEach(selector => {
        safeQueryAll(selector).forEach(el => {
            let text = cleanText(el.innerText.trim());
            if (text.length === 0) return;
            
            let normalizedText = normalizeText(text);
            
            // Only add if this text or a very similar version isn't already included
            if (!ingredientSet.has(normalizedText)) {
                ingredientSet.add(normalizedText);
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
        "div[class*=directions] li",
        "section[class*=directions] li",
        ".tasty-recipes-instructions-body li",
        ".instructions li",
        "div.instructions li",
        "section.instructions li",
        "ol.instructions li",
        "ul.instructions li",
        ".recipe__instructions li",
        "div.recipe-method li",
        "section.recipe-method li"
    ];

    // Use a Set for instructions too
    let instructionSet = new Set();
    let instructions = [];
    
    instructionSelectors.forEach(selector => {
        safeQueryAll(selector).forEach(el => {
            let text = cleanText(el.innerText.trim());
            if (text.length === 0) return;
            
            let normalizedText = normalizeText(text);
            
            if (!instructionSet.has(normalizedText)) {
                instructionSet.add(normalizedText);
                instructions.push(text);
            }
        });
    });

    // Post-processing: Split instructions if they contain multiple steps
    let processedInstructions = [];
    instructions.forEach(instruction => {
        // Check if instruction contains multiple steps indicated by capital letters
        // following periods, indicating possible sentences merged together
        if (instruction.match(/\.\s*[A-Z]/g)) {
            const steps = instruction.split(/(?<=\.)\s+(?=[A-Z])/g);
            steps.forEach(step => {
                const cleanStep = cleanText(step.trim());
                if (cleanStep.length > 0) {
                    processedInstructions.push(cleanStep);
                }
            });
        } else {
            processedInstructions.push(instruction);
        }
    });
    
    // Replace the original instructions with processed ones
    instructions = processedInstructions;

    // Post-processing: If we have very few items, try parent selectors as fallback
    if (ingredients.length <= 1) {
        console.log("[DEBUG] Few ingredients found, trying parent selectors");
        let parentSelectors = [
            ".ingredients", 
            "div.ingredients", 
            "section.ingredients"
        ];
        
        parentSelectors.forEach(selector => {
            const container = document.querySelector(selector);
            if (container) {
                // Try to extract text from paragraphs or direct text
                const text = cleanText(container.innerText);
                if (text && text.length > 0) {
                    // Split by newlines and filter empty lines
                    const lines = text.split('\n')
                        .map(line => cleanText(line.trim()))
                        .filter(line => line.length > 0 && !line.toLowerCase().includes('ingredient'));
                    
                    if (lines.length > 0) {
                        ingredients = lines;
                        return;
                    }
                }
            }
        });
    }

    // Similar fallback for instructions
    if (instructions.length <= 1) {
        console.log("[DEBUG] Few instructions found, trying parent selectors");
        let parentSelectors = [
            ".instructions", 
            "div.instructions", 
            "section.instructions",
            ".directions",
            "div.directions"
        ];
        
        parentSelectors.forEach(selector => {
            const container = document.querySelector(selector);
            if (container) {
                const text = cleanText(container.innerText);
                if (text && text.length > 0) {
                    const lines = text.split('\n')
                        .map(line => cleanText(line.trim()))
                        .filter(line => line.length > 0 && 
                               !line.toLowerCase().includes('instruction') && 
                               !line.toLowerCase().includes('direction'));
                    
                    if (lines.length > 0) {
                        instructions = lines;
                        return;
                    }
                }
            }
        });
    }

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
    return { title, ingredients, instructions, markdown };
}

// Listen for messages from popup.js
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log("[DEBUG] content.js received message:", request);

    if (request.action === "extractRecipe") {
        console.log("[DEBUG] Extracting recipe...");
        let recipeData = extractRecipe();

        // Send extracted recipe data back to popup.js
        sendResponse({ status: "Recipe extracted", data: recipeData });
        return true; // Keeps the connection alive for async response
    }
});

console.log("[DEBUG] content.js is fully loaded and waiting for a request.");





