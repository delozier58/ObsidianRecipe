import re
import sys
from pathlib import Path
from typing import List
import openai
import base64
from PIL import Image, UnidentifiedImageError
import logging
from datetime import date

# Configure logging: logs are written to "ocr_script.log"
logging.basicConfig(
    filename="ocr_script.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)

# ---------------------------------
#  Configuration
# ---------------------------------
OBSIDIAN_VAULT_PATH = Path(r"C:\Users\dlozi\Documents\Tommy & Danielle Shared\Recipes")
IMAGE_PATH = Path("eastrecipe1.jpg")  # Adjust to your actual image path
RECIPE_SOURCE = "East Cookbook"       # Update if the cookbook name is different

# ✅ Set Your OpenAI API Key (replace with a valid key)
OPENAI_API_KEY = "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"

# ✅ Initialize OpenAI Client
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def extract_text_from_image(image_file: Path) -> str:
    """
    Extract text from an image using OpenAI's GPT-4-Vision API.

    :param image_file: Path to the image file.
    :return: Extracted text from the image.
    """
    try:
        # ✅ Read the image and encode it as base64
        with open(image_file, "rb") as img:
            image_data = base64.b64encode(img.read()).decode("utf-8")

        # ✅ Send image to OpenAI's API for text extraction
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "Extract all the recipe titles from this image accurately."},
                {"role": "user", "content": [{"type": "image", "image_data": image_data}]}
            ],
            max_tokens=500  # Adjust token limit if needed
        )

        extracted_text = response.choices[0].message.content
        return extracted_text.strip()

    except openai.AuthenticationError:
        logging.error("Invalid API key. Double-check your OpenAI API key.")
        return ""
    except FileNotFoundError:
        logging.error(f"Image file not found: {image_file}")
        return ""
    except Exception as e:
        logging.error(f"Unexpected error during OCR extraction: {e}")
        return ""

def group_recipe_titles_by_page_number(text: str) -> List[str]:
    """
    Groups lines into full recipe titles using page numbers as boundaries.

    The logic looks for lines with trailing digits (1–3 in length)
    to indicate a page number boundary, then merges preceding lines 
    until that boundary is encountered.

    :param text: The entire extracted text from the image.
    :return: A list of merged recipe title lines.
    """
    recipe_titles = []
    current_recipe_lines = []

    for raw_line in text.split("\n"):
        line = raw_line.strip()

        # Skip blank lines
        if not line:
            continue

        # Add to the current recipe lines
        current_recipe_lines.append(line)

        # If this line ends with 1-3 digits (e.g., "102" or "143")
        # treat that as the end of a recipe title.
        if re.search(r"\d{1,3}$", line):
            combined_recipe = " ".join(current_recipe_lines)
            recipe_titles.append(combined_recipe)
            current_recipe_lines = []

    # In case there's a trailing set of lines without a page number
    if current_recipe_lines:
        recipe_titles.append(" ".join(current_recipe_lines))

    return recipe_titles

def strip_page_number(recipe_title: str) -> str:
    """
    Remove trailing page numbers or page ranges from a recipe title.

    Matches:
      - Single number at the end (e.g., "Pilau 143")
      - Number pairs with a comma (e.g., "Pilau 64,65")
      - Number ranges with a dash (e.g., "Pilau 102-111")

    If no number is found, the title remains unchanged.

    :param recipe_title: Raw recipe title with possible page info.
    :return: Cleaned-up recipe title.
    """
    recipe_title = recipe_title.strip()
    
    # Match trailing numbers, number pairs (64,65), or ranges (102-111)
    pattern = r"\s(\d{1,3}(-\d{1,3})?|\d{1,3},\d{1,3})$"

    # Remove the trailing number if found, otherwise return the original title
    cleaned_title = re.sub(pattern, "", recipe_title).strip()
    
    return cleaned_title if cleaned_title else recipe_title  # Keep valid titles

def format_recipe_as_markdown(recipe_name: str, source: str) -> str:
    """
    Format the extracted text as a Markdown template.

    :param recipe_name: Name of the recipe.
    :param source: Source of the recipe.
    :return: A string with Markdown content.
    """
    today = date.today().isoformat()  # Use current date dynamically
    markdown_content = f"""---
title: "{recipe_name}"
source: "{source}"
tags: ["cookbook"]
date: {today}
---

# {recipe_name}

**Source:** {source}

## Ingredients
- 

## Instructions
1. 
"""
    return markdown_content

def save_markdown_file(recipe_name: str, content: str, vault_path: Path) -> None:
    """
    Save the recipe as a Markdown file in Obsidian, ensuring the filename is valid and not too long.

    :param recipe_name: The name of the recipe, used to create a valid filename.
    :param content: The complete markdown content.
    :param vault_path: The base folder to save the Markdown file in.
    """
    # Remove invalid filename characters
    safe_name = re.sub(r'[<>:"/\\|?*]', '', recipe_name)

    # Limit filename length to avoid OS errors
    safe_name = safe_name[:50]  # Keep only first 50 characters

    # Create the file path
    file_name = f"{safe_name}.md"
    file_path = vault_path / file_name

    # Ensure the directory exists
    vault_path.mkdir(parents=True, exist_ok=True)

    logging.info(f"Saving recipe to: {file_path}")

    try:
        file_path.write_text(content, encoding="utf-8")
    except Exception as e:
        logging.error(f"Could not write file {file_path}: {e}")
    else:
        logging.info(f"Recipe saved: {file_path}")

def process_single_image(image_path: Path, source: str, vault_path: Path) -> None:
    """
    Extract, parse, and save recipes from a single image.

    :param image_path: The Path to the image file.
    :param source: The source of the recipe (e.g. "East Cookbook").
    :param vault_path: The root path (Obsidian vault) where the markdown files should go.
    """
    extracted_text = extract_text_from_image(image_path)

    if not extracted_text:
        logging.warning("No text extracted or file not found. Skipping.")
        return

    # Group all possible recipe titles
    raw_titles = group_recipe_titles_by_page_number(extracted_text)

    # Strip out the page numbers and ignore empty results
    clean_titles = [strip_page_number(title) for title in raw_titles if title.strip()]

    # Create markdown for each clean title and save
    for recipe_title in clean_titles:
        if recipe_title:  # Ensure not empty
            markdown_content = format_recipe_as_markdown(recipe_title, source)
            save_markdown_file(recipe_title, markdown_content, vault_path)

def main() -> None:
    """
    Main script entry point. Processes a single image (or multiple images if desired).
    """
    process_single_image(IMAGE_PATH, RECIPE_SOURCE, OBSIDIAN_VAULT_PATH)
    logging.info("All recipes processed.")

if __name__ == "__main__":
    main()

