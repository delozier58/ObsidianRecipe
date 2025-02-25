let extractedData = null;

document.addEventListener("DOMContentLoaded", () => {
    const extractButton = document.getElementById("extractButton");
    const downloadButton = document.getElementById("downloadButton");
    const copyButton = document.getElementById("copyButton");
    const previewElement = document.getElementById("preview");
    const actionButtons = document.getElementById("actionButtons");
    const statusElement = document.getElementById("status");
    
    extractButton.addEventListener("click", () => {
        statusElement.textContent = "Extracting recipe...";
        extractButton.disabled = true;
        
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs.length === 0) {
                statusElement.textContent = "Error: No active tab found.";
                extractButton.disabled = false;
                return;
            }
            
            chrome.tabs.sendMessage(tabs[0].id, { action: "extractRecipe" }, (response) => {
                extractButton.disabled = false;
                
                if (chrome.runtime.lastError) {
                    statusElement.textContent = "Error: Could not extract recipe.";
                    console.error("[ERROR]", chrome.runtime.lastError.message);
                    return;
                }
                
                if (!response || !response.data) {
                    statusElement.textContent = "Error: No recipe data received.";
                    return;
                }
                
                // Store the extracted data
                extractedData = response.data;
                
                // Update the preview
                document.getElementById("recipeTitle").textContent = extractedData.title;
                
                // Format ingredients
                const ingredientsList = document.getElementById("ingredientsList");
                ingredientsList.innerHTML = "";
                if (extractedData.ingredients && extractedData.ingredients.length > 0) {
                    const ul = document.createElement("ul");
                    extractedData.ingredients.forEach(ingredient => {
                        const li = document.createElement("li");
                        li.textContent = ingredient;
                        ul.appendChild(li);
                    });
                    ingredientsList.appendChild(ul);
                } else {
                    ingredientsList.textContent = "No ingredients found.";
                }
                
                // Format instructions
                const instructionsList = document.getElementById("instructionsList");
                instructionsList.innerHTML = "";
                if (extractedData.instructions && extractedData.instructions.length > 0) {
                    const ol = document.createElement("ol");
                    extractedData.instructions.forEach(instruction => {
                        const li = document.createElement("li");
                        li.textContent = instruction;
                        ol.appendChild(li);
                    });
                    instructionsList.appendChild(ol);
                } else {
                    instructionsList.textContent = "No instructions found.";
                }
                
                // Show the preview and action buttons
                previewElement.style.display = "block";
                actionButtons.style.display = "flex";
                statusElement.textContent = "Recipe extracted successfully!";
            });
        });
    });
    
    downloadButton.addEventListener("click", () => {
        if (!extractedData) {
            statusElement.textContent = "No recipe data to save.";
            return;
        }
        
        statusElement.textContent = "Saving recipe...";
        
        chrome.runtime.sendMessage({
            action: "extractRecipe",
            markdown: extractedData.markdown,
            filename: extractedData.title.replace(/\s+/g, "_").toLowerCase()
        }, (response) => {
            if (chrome.runtime.lastError) {
                statusElement.textContent = "Error: Failed to save recipe.";
                console.error("[ERROR]", chrome.runtime.lastError.message);
            } else {
                statusElement.textContent = "Recipe saved successfully!";
            }
        });
    });
    
    copyButton.addEventListener("click", () => {
        if (!extractedData) {
            statusElement.textContent = "No recipe data to copy.";
            return;
        }
        
        navigator.clipboard.writeText(extractedData.markdown)
            .then(() => {
                statusElement.textContent = "Markdown copied to clipboard!";
            })
            .catch(err => {
                statusElement.textContent = "Failed to copy to clipboard.";
                console.error("[ERROR] Copy failed:", err);
            });
    });
});
