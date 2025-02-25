import re
import sys
import time
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
import openai
import base64
from PIL import Image, ImageEnhance, UnidentifiedImageError
import logging
from datetime import date
import os

# Configure logging: logs are written to "ocr_script.log"
logging.basicConfig(
    filename="ocr_script.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)

# Add console handler for logging
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(levelname)s: %(message)s")
console_handler.setFormatter(console_formatter)
logging.getLogger().addHandler(console_handler)

# ---------------------------------
#  Configuration
# ---------------------------------
OBSIDIAN_VAULT_PATH = Path(r"C:\Users\dlozi\Documents\Tommy & Danielle Shared\Recipes")
DEFAULT_SOURCE = "Unknown Cookbook"
API_RATE_LIMIT_DELAY = 2  # Seconds to wait between API calls

# OpenAI API Key (from environment variable or config file)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Initialize OpenAI Client
client = None

def initialize_openai_client(api_key: str) -> bool:
    """Initialize the OpenAI client with the given API key."""
    global client
    try:
        client = openai.OpenAI(api_key=api_key)
        return True
    except Exception as e:
        logging.error(f"Failed to initialize OpenAI client: {e}")
        return False

def enhance_image(image_path: Path, enhance_contrast: bool = True) -> Optional[Path]:
    """
    Enhance the image to improve OCR results.
    
    Args:
        image_path: Path to the original image
        enhance_contrast: Whether to enhance contrast
        
    Returns:
        Path to the enhanced image or None if enhancement failed
    """
    try:
        enhanced_dir = image_path.parent / "enhanced"
        enhanced_dir.mkdir(exist_ok=True)
        
        enhanced_path = enhanced_dir / f"enhanced_{image_path.name}"
        
        with Image.open(image_path) as img:
            # Convert to grayscale for better OCR
            img = img.convert('L')
            
            if enhance_contrast:
                # Enhance contrast
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(2.0)  # Increase contrast
                
            img.save(enhanced_path)
            logging.info(f"Enhanced image saved to {enhanced_path}")
            return enhanced_path
            
    except Exception as e:
        logging.error(f"Image enhancement failed: {e}")
        return None

def extract_text_from_image(image_file: Path, enhanced: bool = False) -> str:
    """
    Extract text from an image using OpenAI's GPT-4-Vision API.

    Args:
        image_file: Path to the image file
        enhanced: Whether to use image enhancement

    Returns:
        Extracted text from the image
    """
    global client
    
    if not client:
        logging.error("OpenAI client not initialized")
        return ""
    
    try:
        # Validate image before processing
        try:
            with Image.open(image_file) as img:
                width, height = img.size
                if width < 100 or height < 100:
                    logging.warning(f"Image may be too small: {width}x{height}")
                    
                # Check if image is completely blank or black
                extrema = img.convert("L").getextrema()
                if extrema[0] == extrema[1]:
                    logging.warning(f"Image appears to be blank or solid color")
        except UnidentifiedImageError:
            logging.error(f"Could not identify image format: {image_file}")
            return ""
            
        # Process with enhancement if requested
        actual_image = enhance_image(image_file) if enhanced else image_file
        
        # Read the image and encode it as base64
        with open(actual_image if enhanced else image_file, "rb") as img:
            image_data = base64.b64encode(img.read()).decode("utf-8")

        # Send image to OpenAI's API for text extraction
        logging.info(f"Sending image to OpenAI API for text extraction")
        
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": """You are an expert OCR system specialized in cookbook indexes.
                Extract all recipe titles and their page numbers from this cookbook index image.
                Look for patterns like recipe titles followed by page numbers.
                If you detect section headings (categories like APPETIZERS, DESSERTS, etc.), include them.
                Format your response with one recipe per line as: "Recipe Title | Page Number"
                If you identify a section heading, format it as: "SECTION: [Name]"
                Preserve exact capitalization and formatting of recipe names."""},
                {"role": "user", "content": [{"type": "image", "image_data": image_data}]}
            ],
            max_tokens=1500  # Increased token limit for larger indexes
        )

        extracted_text = response.choices[0].message.content
        logging.info(f"Successfully extracted text from image")
        return extracted_text.strip()

    except openai.AuthenticationError:
        logging.error("Invalid API key. Double-check your OpenAI API key.")
        return ""
    except FileNotFoundError:
        logging.error(f"Image file not found: {image_file}")
        return ""
    except Exception as e:
        logging.error(f"Error during OCR extraction: {e}")
        return ""

def parse_extracted_text(text: str) -> Dict[str, List[Tuple[str, str]]]:
    """
    Parse the extracted text into sections and recipe entries.
    
    Args:
        text: The extracted text from the image
        
    Returns:
        Dictionary mapping section names to lists of (recipe_name, page_number) tuples
    """
    sections = {}
    current_section = "Uncategorized"
    
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    for line in lines:
        # Check if this is a section marker
        if line.startswith("SECTION:"):
            current_section = line.replace("SECTION:", "").strip()
            sections[current_section] = []
            continue
            
        # Check for pipe-separated format
        if "|" in line:
            recipe_name, page_number = line.split("|", 1)
            recipe_name = recipe_name.strip()
            page_number = page_number.strip()
        else:
            # Try to extract trailing page numbers with regex
            match = re.search(r'^(.+?)(?:\s+|\s*-\s*|\s*–\s*|\s*—\s*|\s*\(page\s+)(\d+(?:-\d+)?(?:,\s*\d+(?:-\d+)?)*)(?:\))?$', line)
            if match:
                recipe_name, page_number = match.groups()
            else:
                # If no page number found, just use the whole line as recipe name
                recipe_name, page_number = line, ""
        
        if current_section not in sections:
            sections[current_section] = []
            
        sections[current_section].append((recipe_name.strip(), page_number.strip()))
    
    return sections

def format_recipe_as_markdown(
    recipe_name: str, 
    source: str, 
    page_number: str = "", 
    section: str = "Uncategorized",
    status: str = "to_try"
) -> str:
    """
    Format the extracted text as a Markdown template with rich metadata.
    
    Args:
        recipe_name: Name of the recipe
        source: Source of the recipe (cookbook name)
        page_number: Page number in the cookbook
        section: Recipe category/section
        status: Recipe status (to_try, favorite, etc.)
        
    Returns:
        Markdown content as a string
    """
    today = date.today().isoformat()
    
    # Build tags - convert spaces to hyphens and lowercase
    tags = ["cookbook"]
    
    # Add source as tag (cleaned)
    source_tag = source.lower().replace(" ", "-")
    source_tag = re.sub(r'[^\w\-]', '', source_tag)  # Remove non-alphanumeric chars except hyphens
    if source_tag:
        tags.append(source_tag)
    
    # Add section as tag if not uncategorized
    if section and section.lower() != "uncategorized":
        section_tag = section.lower().replace(" ", "-")
        section_tag = re.sub(r'[^\w\-]', '', section_tag)
        if section_tag:
            tags.append(section_tag)
    
    tags_str = ", ".join([f'"{tag}"' for tag in tags])
    
    markdown_content = f"""---
title: "{recipe_name}"
source: "{source}"
page: "{page_number}"
category: "{section}"
tags: [{tags_str}]
date: {today}
status: "{status}"
---

# {recipe_name}

**Source:** {source}{f" (page {page_number})" if page_number else ""}

## Ingredients
- 

## Instructions
1. 

## Notes
- 
"""
    return markdown_content

def save_markdown_file(recipe_name: str, content: str, vault_path: Path, overwrite: bool = False) -> bool:
    """
    Save the recipe as a Markdown file in the specified path.
    
    Args:
        recipe_name: The name of the recipe
        content: The complete markdown content
        vault_path: The base folder to save the Markdown file in
        overwrite: Whether to overwrite existing files
        
    Returns:
        True if file was saved successfully, False otherwise
    """
    # Remove invalid filename characters
    safe_name = re.sub(r'[<>:"/\\|?*]', '', recipe_name)
    
    # Limit filename length to avoid OS errors (max 255 chars on most systems)
    safe_name = safe_name[:100]  # Keep only first 100 characters
    
    # Ensure we have a valid filename after cleaning
    if not safe_name:
        safe_name = "unnamed_recipe"
    
    # Create the file path
    file_name = f"{safe_name}.md"
    file_path = vault_path / file_name
    
    # Ensure the directory exists
    vault_path.mkdir(parents=True, exist_ok=True)
    
    # Check if file already exists
    if file_path.exists() and not overwrite:
        logging.info(f"File already exists (skipping): {file_path}")
        return False
    
    try:
        file_path.write_text(content, encoding="utf-8")
        logging.info(f"Recipe saved: {file_path}")
        return True
    except Exception as e:
        logging.error(f"Could not write file {file_path}: {e}")
        return False

def process_single_image(
    image_path: Path, 
    source: str, 
    vault_path: Path,
    enhance_images: bool = False,
    preview_only: bool = False,
    overwrite: bool = False
) -> Set[str]:
    """
    Extract, parse, and save recipes from a single image.
    
    Args:
        image_path: The Path to the image file
        source: The source of the recipe (e.g. "East Cookbook")
        vault_path: The root path where the markdown files should go
        enhance_images: Whether to enhance images before OCR
        preview_only: If True, only show extracted recipes without saving
        overwrite: Whether to overwrite existing files
        
    Returns:
        Set of recipe names that were successfully processed
    """
    logging.info(f"Processing image: {image_path}")
    
    extracted_text = extract_text_from_image(image_path, enhanced=enhance_images)
    
    if not extracted_text:
        logging.warning("No text extracted or file not found. Skipping.")
        return set()
    
    # Parse the extracted text into sections and recipes
    sections = parse_extracted_text(extracted_text)
    
    # Keep track of processed recipes
    processed_recipes = set()
    
    # Preview mode - just print the extracted recipes
    if preview_only:
        logging.info(f"PREVIEW MODE - Extracted {sum(len(recipes) for recipes in sections.values())} recipes:")
        for section, recipes in sections.items():
            logging.info(f"  Section: {section}")
            for recipe_name, page_number in recipes:
                logging.info(f"    - {recipe_name} (page {page_number})")
        return set(recipe_name for recipes in sections.values() for recipe_name, _ in recipes)
    
    # Process and save each recipe
    for section, recipes in sections.items():
        for recipe_name, page_number in recipes:
            if recipe_name:  # Ensure not empty
                markdown_content = format_recipe_as_markdown(
                    recipe_name, 
                    source, 
                    page_number,
                    section
                )
                
                success = save_markdown_file(recipe_name, markdown_content, vault_path, overwrite)
                if success:
                    processed_recipes.add(recipe_name)
    
    return processed_recipes

def process_multiple_images(
    image_paths: List[Path], 
    source: str, 
    vault_path: Path,
    enhance_images: bool = False,
    preview_only: bool = False,
    overwrite: bool = False
) -> None:
    """
    Process multiple images from the same cookbook.
    
    Args:
        image_paths: List of paths to image files
        source: The source of the recipe (cookbook name)
        vault_path: The root path where the markdown files should go
        enhance_images: Whether to enhance images before OCR
        preview_only: If True, only show extracted recipes without saving
        overwrite: Whether to overwrite existing files
    """
    all_recipes = set()  # Use a set to avoid duplicates
    
    for i, img_path in enumerate(image_paths):
        logging.info(f"Processing image {i+1}/{len(image_paths)}: {img_path}")
        
        recipes = process_single_image(
            img_path, 
            source, 
            vault_path,
            enhance_images,
            preview_only,
            overwrite
        )
        
        all_recipes.update(recipes)
        
        # Add delay between API calls to respect rate limits
        if i < len(image_paths) - 1:
            logging.info(f"Waiting {API_RATE_LIMIT_DELAY} seconds before next API call...")
            time.sleep(API_RATE_LIMIT_DELAY)
    
    logging.info(f"Processed {len(all_recipes)} unique recipes from {len(image_paths)} images")

def scan_directory_for_images(directory: Path) -> List[Path]:
    """
    Scan a directory for image files.
    
    Args:
        directory: Path to directory containing images
        
    Returns:
        List of paths to image files
    """
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
    image_files = []
    
    # Skip the "enhanced" subdirectory
    for f in directory.glob('*'):
        if f.is_file() and f.suffix.lower() in image_extensions:
            image_files.append(f)
    
    logging.info(f"Found {len(image_files)} images in {directory}")
    return sorted(image_files)  # Sort for consistent processing order

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Extract recipe titles from cookbook indexes")
    
    # Input sources
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--image", type=str, help="Path to a single image")
    input_group.add_argument("--directory", type=str, help="Path to directory containing images")
    
    # Config options
    parser.add_argument("--source", type=str, default=DEFAULT_SOURCE, 
                        help=f"Name of the cookbook (default: {DEFAULT_SOURCE})")
    parser.add_argument("--output", type=str, default=str(OBSIDIAN_VAULT_PATH),
                        help="Output directory for Markdown files")
    parser.add_argument("--api-key", type=str, 
                        help="OpenAI API key (if not set in environment variable)")
    
    # Processing options
    parser.add_argument("--enhance", action="store_true", 
                        help="Enhance images before OCR")
    parser.add_argument("--preview", action="store_true",
                        help="Preview mode - don't save files")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing files")
    
    return parser.parse_args()

def main():
    """Main script entry point."""
    args = parse_arguments()
    
    # Initialize API client
    api_key = args.api_key or OPENAI_API_KEY
    if not api_key:
        logging.error("No OpenAI API key provided. Set it with --api-key or as an environment variable.")
        return
    
    if not initialize_openai_client(api_key):
        return
    
    vault_path = Path(args.output)
    source = args.source
    
    logging.info(f"Recipe source: {source}")
    logging.info(f"Output directory: {vault_path}")
    
    if args.image:
        image_path = Path(args.image)
        if not image_path.exists():
            logging.error(f"Image not found: {image_path}")
            return
            
        logging.info(f"Processing single image: {image_path}")
        process_single_image(
            image_path, 
            source, 
            vault_path,
            enhance_images=args.enhance,
            preview_only=args.preview,
            overwrite=args.overwrite
        )
    elif args.directory:
        directory_path = Path(args.directory)
        if not directory_path.exists() or not directory_path.is_dir():
            logging.error(f"Directory not found: {directory_path}")
            return
            
        image_paths = scan_directory_for_images(directory_path)
        if image_paths:
            process_multiple_images(
                image_paths, 
                source, 
                vault_path,
                enhance_images=args.enhance,
                preview_only=args.preview,
                overwrite=args.overwrite
            )
        else:
            logging.warning(f"No images found in {directory_path}")
    
    logging.info("All processing complete.")

if __name__ == "__main__":
    main()

