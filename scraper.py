# scraper.py
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from PIL import Image, ImageOps # ImageOps for border_check_depth if used, Image for core processing
from io import BytesIO
import requests
import time
import re # For regex in CSS background image search
import traceback # For printing stack traces on error


# scraper.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service # Make sure Service is imported
import traceback # For better error logging
# ... other necessary imports like os, options, etc. ...

# scraper.py
from selenium.webdriver.chrome.service import Service

# scraper.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service # Make sure Service is imported
import os # Make sure os is imported for os.path.isfile
import traceback # For better error logging

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080") 
    options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
    
    chromedriver_path = "/usr/bin/chromedriver"  # Use the path confirmed by `which chromedriver`
    
    print(f"ℹ️ setup_driver (Docker/Chromium): Attempting chromedriver at explicit path: {chromedriver_path}")
    try:
        # Check if the path actually exists and is a file before trying to use it
        if not os.path.isfile(chromedriver_path):
            print(f"❌ ERROR: chromedriver_path '{chromedriver_path}' does not exist or is not a file.")
            # Fallback to letting Selenium try to find it in PATH if explicit path is bad
            # This might lead back to Selenium Manager issues if PATH isn't perfectly set up for Selenium's liking
            print("   Falling back to Service() without explicit path (might use Selenium Manager).")
            service = Service() 
        else:
            print(f"   Path '{chromedriver_path}' exists and is a file. Using it.")
            service = Service(executable_path=chromedriver_path)

        driver = webdriver.Chrome(service=service, options=options)
        print("✅ setup_driver (Docker/Chromium): Successfully initialized driver.")
        return driver
    except Exception as e:
        print(f"❌ setup_driver (Docker/Chromium): Failed to initialize driver: {e}")
        print(f"   Chromedriver path attempted: {chromedriver_path}")
        print(f"   Full traceback: {traceback.format_exc()}")
        raise

# --- URL Parsing ---
def extract_domain(url):
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception as e:
        print(f"Error parsing domain from URL '{url}': {e}")
        return "unknown_domain"


def search_logo_with_selenium(company_url):
    print(f"🚀 Starting Selenium search for: {company_url}")
    driver = None 
    try:
        driver = setup_driver() # Assumes setup_driver() is defined elsewhere in scraper.py
        driver.get(company_url)
        print(f"Page loaded: {company_url}")

        # Attempt 1: Specific element screenshot (example)
        try:
            logo_elem = WebDriverWait(driver, 3).until( # Short wait for this specific check
                EC.presence_of_element_located((By.CLASS_NAME, "otto2-logo")) # Example
            )
            company_name_for_screenshot = extract_domain(company_url).split('.')[0]
            if not os.path.exists("static"): os.makedirs("static")
            output_path = os.path.join("static", f"{company_name_for_screenshot}_logo_screenshot.png")
            logo_elem.screenshot(output_path)
            print(f"📸 Screenshot of specific logo element saved to {output_path}")
            return None 
        except Exception:
            print(f"ℹ️ Specific logo element (e.g., class 'otto2-logo') not found. Proceeding with general scan.")

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "lxml")
        
        parsed_company_url = urlparse(company_url)
        base_url = f"{parsed_company_url.scheme}://{parsed_company_url.netloc}"

        # Attempt 2: Inline SVG logo detection
        print("🔁 Scanning for inline SVG logos...")
        for svg_tag in soup.find_all("svg"):
            parent = svg_tag.find_parent()
            if parent:
                parent_classes = " ".join(parent.get("class", [])).lower()
                parent_id = parent.get("id", "").lower()
                aria_label = svg_tag.get("aria-label", "").lower()
                role = svg_tag.get("role", "").lower()

                if "logo" in parent_classes or "brand" in parent_classes or \
                   "logo" in parent_id or "brand" in parent_id or \
                   "logo" in aria_label or (role == "img" and "logo" in aria_label):
                    svg_str = str(svg_tag)
                    if "path" in svg_str and len(svg_str) > 100:
                        if "xmlns" not in svg_tag.attrs:
                            svg_tag["xmlns"] = "http://www.w3.org/2000/svg"
                        svg_content_to_save = str(svg_tag)
                        company_name_for_svg = extract_domain(company_url).split('.')[0]
                        if not os.path.exists("static"): os.makedirs("static")
                        try:
                            from cairosvg import svg2png
                            png_filename = f"{company_name_for_svg}_logo_from_svg.png"
                            png_output_path = os.path.join("static", png_filename)
                            # Adjust output_width/height as desired for default SVG rasterization
                            svg2png(bytestring=svg_content_to_save.encode("utf-8"), write_to=png_output_path, output_width=280, output_height=140, background_color="rgba(0,0,0,0)")
                            print(f"✅ Converted inline SVG to PNG: {png_output_path}")
                            return None 
                        except ImportError:
                            print("❌ cairosvg not installed. Cannot convert inline SVG to PNG.")
                        except Exception as e_svg_conv:
                            print(f"❌ Failed to convert inline SVG to PNG: {e_svg_conv}")
                        break 

        # Attempt 3: CSS background-image logos
        print("🔁 Scanning for CSS background-image logos...")
        for tag_with_style in soup.find_all(lambda t: t.has_attr('style') and 'background-image' in t['style'].lower()):
            class_str = " ".join(tag_with_style.get("class", [])).lower()
            id_str = tag_with_style.get("id", "").lower()
            if "logo" in class_str or "brand" in class_str or "logo" in id_str or "brand" in id_str:
                style_attr = tag_with_style.get("style", "")
                match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style_attr, re.IGNORECASE)
                if match:
                    raw_url = match.group(1)
                    if raw_url.startswith("data:image"): continue
                    
                    final_url = requests.utils.requote_uri(raw_url)
                    if final_url.startswith("//"): final_url = f"{parsed_company_url.scheme}:{final_url}"
                    elif final_url.startswith("/"): final_url = f"{base_url}{final_url}"
                    elif not final_url.startswith("http"): final_url = f"{base_url}/{final_url.lstrip('./')}"
                    
                    print(f"✅ Found potential logo via CSS background-image: {final_url}")
                    return final_url

        # Attempt 4: Fallback to <img> scanning
        print("🔁 Scanning <img> tags for logos...")
        for img_tag in soup.find_all("img"):
            src = img_tag.get("src")
            data_src = img_tag.get("data-src")
            srcset = img_tag.get("srcset")
            
            raw_src_options = [s for s in [src, data_src] if s and not s.startswith("data:image")]
            
            if srcset:
                sources = [s.strip().split()[0] for s in srcset.split(',') if s.strip() and not s.strip().startswith("data:image")]
                raw_src_options.extend(sources)

            img_id = img_tag.get("id", "").lower()
            img_class = " ".join(img_tag.get("class", [])).lower()
            img_alt = img_tag.get("alt", "").lower()
            img_title = img_tag.get("title", "").lower()
            parent = img_tag.find_parent()
            parent_classes = " ".join(parent.get("class", [])).lower() if parent else ""
            parent_id = parent.get("id", "").lower() if parent else ""

            is_likely_logo = False
            is_explicit_logo_signal = False

            logo_keywords = ["logo", "brand", "logotype", "header-logo", "site-logo", "navbar-logo", "identity", "logoหลัก", "โลโก้"] # Added Thai examples
            skip_keywords = ["icon", "avatar", "profile", "placeholder", "spinner", "loader", "close", "menu", "hamburger", "banner", "ad", "pixel", "tracker", "badge", "seal", "shield", "card", "payment", "captcha", "flag", "star", "rating", "thumbnail", "arrow", "caret", "user", "social", "feed", "widget", "promo", "slide", "map", "chart", "graph", "mini", "small", "tiny", "example", "sample", "pattern", "bg", "background", "footer-logo"] # Added more skips

            # --- STAGE 1: Check for STRONG positive logo signals FIRST ---
            strong_logo_indicators = {"id": img_id, "class": img_class, "alt": img_alt}
            for field_name, field_value in strong_logo_indicators.items():
                if any(logo_kw in field_value for logo_kw in ["logo", "brand", "logotype", "identity", "โลโก้"]): # Stricter primary keywords
                    is_explicit_logo_signal = True
                    is_likely_logo = True
                    print(f"  👍 Strong logo signal: kw in '{field_name}' ('{field_value}') for src='{src}'")
                    break
            
            # --- STAGE 2: Check for skip keywords, BUT ONLY IF NOT an explicit logo signal ---
            if not is_explicit_logo_signal:
                img_fields_for_skip_check = {
                    "id": img_id, "class": img_class, "alt": img_alt, "title": img_title,
                    "parent_class": parent_classes, "parent_id": parent_id,
                    "src": (src.lower().split('?')[0] if src and not src.startswith("data:image") else "") # Check src path part
                }
                skipped_due_to_keyword = False
                for field_name, field_value in img_fields_for_skip_check.items():
                    if not field_value: continue
                    for skip_kw in skip_keywords:
                        if skip_kw in field_value:
                            if any(logo_kw in field_value for logo_kw in ["logo", "brand"]): # If "logo" is also there, don't skip yet
                                print(f"  🤔 Field '{field_name}' ('{field_value}') contains BOTH skip_kw='{skip_kw}' AND a logo keyword. Will evaluate further.")
                            else:
                                print(f"  ⚠️ DEBUG SKIP: Matched skip_kw='{skip_kw}' in field='{field_name}' with value='{field_value}'")
                                print(f"  ⚠️ Skipping img (due to skip_kw='{skip_kw}'): src='{src}'")
                                skipped_due_to_keyword = True
                                break
                    if skipped_due_to_keyword: break
                if skipped_due_to_keyword: continue

            # --- STAGE 3: Broader likelihood checks if not already confirmed or skipped ---
            if not is_likely_logo:
                # Check general logo keywords in more fields
                current_fields_for_logo_check = [img_id, img_class, img_alt, img_title, parent_classes, parent_id]
                if src and not src.startswith("data:image"): current_fields_for_logo_check.append(src.lower().split('?')[0])

                if any(logo_kw in s_field for s_field in current_fields_for_logo_check if s_field for logo_kw in logo_keywords):
                    is_likely_logo = True
                
                # Check if image is in a common header/nav structure
                if not is_likely_logo: 
                    ancestor = img_tag
                    for _ in range(5): 
                        if not ancestor: break
                        ancestor = ancestor.find_parent()
                        if not ancestor: break
                        tag_name = ancestor.name.lower()
                        anc_classes = " ".join(ancestor.get("class", [])).lower()
                        anc_id = ancestor.get("id", "").lower()
                        if tag_name in ["header", "nav", "banner"] or \
                           any(kw in anc_classes or kw in anc_id for kw in ["header", "navbar", "top-bar", "site-head", "masthead", "branding", "logo-area"]):
                            is_likely_logo = True
                            print(f"  👍 Logo context: Found in header/nav/branding structure for src='{src}'")
                            break
            
            if not is_likely_logo:
                if src and not src.startswith("data:image"):
                    print(f"  ℹ️ Skipping img (not deemed likely logo by heuristics): src='{src}', alt='{img_alt}', class='{img_class}'")
                continue

            if not raw_src_options:
                print(f"  ℹ️ Skipping likely logo (no valid src found): alt='{img_alt}', class='{img_class}'")
                continue

            chosen_src = raw_src_options[0] 
            if srcset:
                valid_srcset_sources = [s.strip().split()[0] for s in srcset.split(',') if s.strip() and not s.strip().startswith("data:image")]
                if valid_srcset_sources:
                    chosen_src = valid_srcset_sources[-1]
                    print(f"  ⚡ Selected from srcset (last): {chosen_src}")
            
            final_url = requests.utils.requote_uri(chosen_src)
            if final_url.startswith("//"): final_url = f"{parsed_company_url.scheme}:{final_url}"
            elif final_url.startswith("/"): final_url = f"{base_url}{final_url}"
            elif not final_url.startswith("http"): final_url = f"{base_url}/{final_url.lstrip('./')}"

            print(f"✅ Found potential logo in <img>: {final_url} (alt='{img_alt}', class='{img_class}')")
            return final_url

        print("❌ No suitable logo <img> tag matched after filtering.")
        return None

    except Exception as e:
        print(f"❗ Error during Selenium processing for {company_url}: {e}")
        traceback.print_exc()
        return None
    finally:
        if driver:
            print(f"🚪 Closing Selenium driver for {company_url}")
            driver.quit()

# --- Image Processing Functions ---
def trim_whitespace(image, threshold=240, border_px=1):
    """Improved trim_whitespace that ignores transparent borders."""
    if image.mode != 'RGBA':
        image = image.convert('RGBA')

    # Create an alpha mask and invert it to find opaque areas
    alpha = image.split()[-1]
    bbox = alpha.getbbox() # Bounding box of non-zero alpha values

    if not bbox: # Image is fully transparent
        return image 

    image_trimmed_alpha = image.crop(bbox)
    
    # Now, optionally trim based on color if the remaining image is mostly opaque
    # This part is more for solid backgrounds on already alpha-trimmed images
    temp_pixels = image_trimmed_alpha.load()
    width, height = image_trimmed_alpha.size
    
    # Check if image_trimmed_alpha is mostly opaque (e.g. its new border)
    is_opaque_enough_for_color_trim = True
    if width > border_px*2 and height > border_px*2:
        opaque_count = 0
        border_pixel_count = 0
        for x in range(width):
            for y_offset in range(border_px):
                if temp_pixels[x,y_offset][3] > 200: opaque_count+=1
                if temp_pixels[x,height-1-y_offset][3] > 200: opaque_count+=1
                border_pixel_count +=2
        for y in range(border_px, height-border_px):
            for x_offset in range(border_px):
                if temp_pixels[x_offset,y][3] > 200: opaque_count+=1
                if temp_pixels[width-1-x_offset,y][3] > 200: opaque_count+=1
                border_pixel_count +=2
        if border_pixel_count > 0 and (opaque_count / border_pixel_count) < 0.8: # e.g. less than 80% opaque border
            is_opaque_enough_for_color_trim = False

    if not is_opaque_enough_for_color_trim:
        print("ℹ️ Skipping color-based trim as alpha-trimmed image has significant transparency at borders.")
        return image_trimmed_alpha

    # Color-based trim (like before, but on the alpha-cropped image)
    left, top = width, height
    right, bottom = 0, 0
    found_content = False
    for x in range(width):
        for y in range(height):
            r, g, b, a = temp_pixels[x, y]
            # Only consider opaque/semi-opaque pixels for color trimming
            if a > 128 and (r < threshold or g < threshold or b < threshold):
                left = min(left, x)
                right = max(right, x)
                top = min(top, y)
                bottom = max(bottom, y)
                found_content = True
    
    if found_content:
        return image_trimmed_alpha.crop((left, top, right + 1, bottom + 1))
    else: # No content found by color trim, return alpha-trimmed
        return image_trimmed_alpha

def resize_to_canvas(image, canvas_width=280, canvas_height=140):
    image_ratio = image.width / image.height
    canvas_ratio = canvas_width / canvas_height

    if image_ratio > canvas_ratio:
        new_width = canvas_width
        new_height = round(new_width / image_ratio)
    else:
        new_height = canvas_height
        new_width = round(new_height * image_ratio)
    
    # Ensure new dimensions are at least 1x1
    new_width = max(1, new_width)
    new_height = max(1, new_height)

    try:
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"Error during resize: {e}. Original size: {image.width}x{image.height}, Target: {new_width}x{new_height}")
        # Fallback or return original if resize fails catastrophically
        return image # Or a placeholder image

    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0)) # Fully transparent canvas
    paste_x = (canvas_width - new_width) // 2
    paste_y = (canvas_height - new_height) // 2
    canvas.paste(resized, (paste_x, paste_y), mask=resized if resized.mode == "RGBA" else None)
    return canvas

def remove_black_background_heuristic(image, border_check_depth=3, color_threshold=20, percentage_threshold=0.60):
    if image.mode != 'RGBA':
        image = image.convert('RGBA')

    width, height = image.size
    if width < border_check_depth * 2 or height < border_check_depth * 2: # Image too small for border check
        print("ℹ️ Image too small for border-based black background removal.")
        return image

    pixels = image.load()
    border_black_pixels = 0
    border_total_pixels_checked = 0

    # Simplified border check
    for i in range(width): # Top & Bottom
        for d in range(border_check_depth):
            if pixels[i, d][3] > 200 and all(c <= color_threshold for c in pixels[i, d][:3]): border_black_pixels +=1
            if pixels[i, height - 1 - d][3] > 200 and all(c <= color_threshold for c in pixels[i, height - 1 - d][:3]): border_black_pixels +=1
            border_total_pixels_checked +=2
    for i in range(border_check_depth, height - border_check_depth): # Left & Right (excluding corners already counted)
        for d in range(border_check_depth):
            if pixels[d, i][3] > 200 and all(c <= color_threshold for c in pixels[d, i][:3]): border_black_pixels +=1
            if pixels[width - 1 - d, i][3] > 200 and all(c <= color_threshold for c in pixels[width - 1 - d, i][:3]): border_black_pixels +=1
            border_total_pixels_checked +=2
    
    if border_total_pixels_checked == 0: return image

    if (border_black_pixels / border_total_pixels_checked) > percentage_threshold:
        print(f"ℹ️ Detected potential black background ({(border_black_pixels / border_total_pixels_checked)*100:.1f}% of border is blackish). Attempting removal.")
        new_data = []
        for item in image.getdata():
            r, g, b, a = item
            if a > 200 and all(c <= color_threshold for c in item[:3]): # Opaque and blackish
                new_data.append((r, g, b, 0))  # Make transparent
            else:
                new_data.append(item)
        image.putdata(new_data)
    else:
        print(f"ℹ️ No dominant black border detected ({(border_black_pixels / border_total_pixels_checked)*100:.1f}% of border is blackish). Skipping heuristic black background removal.")
    return image


# --- Image Downloading and Processing (from URL) ---
def download_and_save_image(image_url, company_name_hint):
    def try_download(url_to_try):
        # ... (using the corrected try_download from our previous discussion) ...
        try:
            print(f"Attempting to download: {url_to_try}")
            response = requests.get(url_to_try, timeout=15, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'})
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            print(f"Response from {url_to_try}: Status {response.status_code}, Content-Type: {content_type}")
            if content_type.startswith("image"):
                print(f"✅ Content-Type is an image type ('{content_type}').")
                return response
            generic_types = ["application/octet-stream", "binary/octet-stream", "application/unknown"]
            parsed_url_to_try = urlparse(url_to_try)
            path_basename_to_try = os.path.basename(parsed_url_to_try.path)
            looks_like_image_url = any(path_basename_to_try.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico'])
            if content_type in generic_types and looks_like_image_url:
                print(f"⚠️ Content-Type is generic ('{content_type}'), but URL ('{url_to_try}') suggests an image. Proceeding.")
                return response
            print(f"❌ Content-Type ('{content_type}') not a recognized image type for URL ('{url_to_try}').")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Download failed for {url_to_try}: {e}")
            return None

    response = try_download(image_url)
    download_attempted_url = image_url

    if response is None: # Add more sophisticated fallback if needed, current one is basic
        print(f"ℹ️ Initial download of '{image_url}' failed. No extensive fallbacks implemented in this version.")
    if response is None:
        print(f"❌ All download attempts failed for the image URL: {image_url}")
        return None

    try:
        print(f"⚙️ Processing image from {download_attempted_url}")
        return process_image_content(response.content, download_attempted_url, company_name_hint)
    except Exception as e:
        print(f"❌ Failed to process downloaded image content from {download_attempted_url}: {e}")
        traceback.print_exc()
        return None


# --- NEW: Generic Image Content Processing ---
# This function will be used by both download_and_save_image and the new reformat tool endpoint
def process_image_content(image_bytes, source_identifier, name_hint_prefix):
    """
    Processes raw image bytes (from download or upload).
    source_identifier: original URL or filename, used for SVG type hint.
    name_hint_prefix: e.g., company name or "reformatted".
    """
    try:
        is_svg_hint = source_identifier.lower().endswith(".svg")
        image = None

        if is_svg_hint:
            try:
                from cairosvg import svg2png
                print(f"Attempting to convert SVG content from '{source_identifier}' to PNG.")
                # Ensure output_width/height are reasonable for SVGs that might lack intrinsic size
                png_bytes = svg2png(bytestring=image_bytes, output_width=560, output_height=280, background_color="rgba(0,0,0,0)") # Double canvas size before resize
                image = Image.open(BytesIO(png_bytes)).convert("RGBA")
                print("✅ SVG content successfully converted to PNG.")
            except ImportError:
                print("❌ cairosvg not installed. Cannot convert SVG content to PNG.")
                return None # Or save the .svg directly if desired
            except Exception as svg_error:
                print(f"❌ SVG conversion error for content from '{source_identifier}': {svg_error}")
                return None # Or save the .svg directly
        
        if image is None: # If not SVG or SVG conversion failed but we want to try Pillow
            try:
                image = Image.open(BytesIO(image_bytes)).convert("RGBA")
            except Exception as pillow_open_error:
                print(f"❌ Pillow could not open image content from '{source_identifier}': {pillow_open_error}")
                # Could be an unsupported format or corrupted data
                return None
        
        print(f"🖼️ Image loaded for processing. Original mode: {image.mode}, size: {image.size}")
        
        # Apply existing post-processing functions
        image = trim_whitespace(image)
        print(f"  After trim_whitespace: {image.size}")
        image = resize_to_canvas(image) # Uses default 280x140 canvas
        print(f"  After resize_to_canvas: {image.size}")
        image = remove_black_background_heuristic(image) # Your chosen heuristic
        print(f"  After remove_black_background_heuristic: {image.size}")


        timestamp = int(time.time())
        # Create a filename using the name_hint_prefix (e.g., company name or "reformatted")
        # and part of the source_identifier if it's a filename.
        base_source_name = "logo" # Default
        if isinstance(source_identifier, str):
            base_source_name, _ = os.path.splitext(os.path.basename(source_identifier))
        
        safe_base_name = "".join(c if c.isalnum() else "_" for c in base_source_name[:20])
        
        filename = f"{name_hint_prefix}_{safe_base_name}_{timestamp}.png"
        
        # Ensure 'static' directory exists
        static_dir = "static"
        if not os.path.exists(static_dir):
            os.makedirs(static_dir)
            print(f"Created directory: {static_dir}")

        filepath = os.path.join(static_dir, filename)
        
        image.save(filepath, "PNG")
        print(f"✅ Processed image saved as {filepath}")
        return filename

    except Exception as e:
        print(f"❌ Failed during image content processing (source: '{source_identifier}'): {e}")
        traceback.print_exc()
        return None

# --- NEW: Function for app.py to call for the reformat tool ---
def process_uploaded_image_data(image_bytes, original_filename, name_hint_for_file):
    """
    Wrapper for process_image_content specifically for uploaded data.
    original_filename is used as the source_identifier for SVG hint.
    name_hint_for_file is used as the prefix for the saved filename.
    """
    print(f"⚙️ Processing uploaded file: '{original_filename}', with name hint: '{name_hint_for_file}'")
    return process_image_content(image_bytes, original_filename, name_hint_for_file)


# --- Main function for standalone testing (optional) ---
def main():
    test_url = input("Enter company website URL for standalone test (or type 'skip' for no Selenium test): ").strip()
    if test_url.lower() != 'skip':
        if not test_url.startswith("http"):
            test_url = "https://" + test_url
        company_name = extract_domain(test_url).split('.')[0]
        logo_url_from_selenium = search_logo_with_selenium(test_url)

        if isinstance(logo_url_from_selenium, str) and logo_url_from_selenium.startswith("http"):
            print(f"\n--- Standalone Test: Downloading from URL: {logo_url_from_selenium} ---")
            download_and_save_image(logo_url_from_selenium, company_name)
        elif logo_url_from_selenium is None:
            print("\n--- Standalone Test: Selenium search returned None (check static folder for internal saves) ---")
        else:
            print(f"\n--- Standalone Test: Selenium search returned: {logo_url_from_selenium} (not a downloadable URL) ---")
    
    # Example test for process_uploaded_image_data (requires a sample image file)
    sample_image_path = "test_logo.png" # Create a dummy test_logo.png for this
    if os.path.exists(sample_image_path):
        print(f"\n--- Standalone Test: Processing local file: {sample_image_path} ---")
        with open(sample_image_path, "rb") as f:
            img_bytes = f.read()
        process_uploaded_image_data(img_bytes, sample_image_path, "test_upload")
    else:
        print(f"\nℹ️ Standalone Test: Sample image '{sample_image_path}' not found, skipping local file processing test.")


if __name__ == "__main__":
    main()