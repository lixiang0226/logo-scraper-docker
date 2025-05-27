# scraper.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from PIL import Image, ImageOps
from io import BytesIO
import requests
import time
import os
import re
import traceback

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR_PATH = os.path.join(PROJECT_ROOT, "static")

def ensure_static_dir_exists():
    if not os.path.exists(STATIC_DIR_PATH):
        print(f"Attempting to create static directory at: {STATIC_DIR_PATH}")
        try:
            os.makedirs(STATIC_DIR_PATH)
            print(f"✅ Created directory: {STATIC_DIR_PATH}")
        except OSError as e:
            print(f"❌ Error creating static directory {STATIC_DIR_PATH}: {e}")
            raise

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36")
    print("ℹ️ setup_driver (Docker/Chromium): Attempting system chromedriver via Service() (PATH search).")
    try:
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        print("✅ setup_driver (Docker/Chromium): Successfully initialized driver.")
        return driver
    except Exception as e:
        print(f"❌ setup_driver (Docker/Chromium): Failed to initialize driver: {e}")
        print(f"   Full traceback: {traceback.format_exc()}")
        raise

def extract_domain(url):
    try:
        parsed = urlparse(url)
        if not parsed.netloc and not parsed.path:
            if not url.startswith(('http://', 'https://')) and '.' in url:
                temp_parsed = urlparse(f"https://{url}")
                if temp_parsed.netloc:
                    return temp_parsed.netloc
            return "unknown_domain"
        return parsed.netloc
    except Exception:
        return "unknown_domain"

# scraper.py

# (Keep existing imports and other functions like setup_driver, extract_domain, etc., as they are)
# from selenium import webdriver
# ... etc.

# scraper.py

# (Keep existing imports and other functions like setup_driver, extract_domain, etc., as they are)
# from selenium import webdriver
# ... etc.

def search_logo_with_selenium(company_url):
    print(f"🚀 Starting Selenium search for: {company_url}")
    driver = None
    try:
        driver = setup_driver()
        driver.get(company_url)
        print(f"Page loaded: {company_url}")

        # Attempt 1: Specific element screenshot (example placeholder)
        try:
            logo_elem = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.CLASS_NAME, "otto2-logo")) # Example class
            )
            domain_name_part = extract_domain(company_url)
            company_name_for_screenshot = domain_name_part.split('.')[0] if domain_name_part and '.' in domain_name_part else domain_name_part if domain_name_part else "unknown"

            ensure_static_dir_exists() # Make sure this function is defined globally or imported
            output_path = os.path.join(STATIC_DIR_PATH, f"{company_name_for_screenshot}_logo_screenshot.png")
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
        domain_for_name = extract_domain(company_url)
        current_company_name_main_part = domain_for_name.split('.')[0].lower() if domain_for_name != "unknown_domain" else "unknown_domain"


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
                        company_name_for_svg = current_company_name_main_part if current_company_name_main_part != "unknown_domain" else "unknown_svg_logo"
                        ensure_static_dir_exists()
                        try:
                            from cairosvg import svg2png
                            png_filename = f"{company_name_for_svg}_logo_from_svg.png"
                            png_output_path = os.path.join(STATIC_DIR_PATH, png_filename)
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
            img_id = img_tag.get("id", "").lower()
            img_class = " ".join(img_tag.get("class", [])).lower()
            img_alt = img_tag.get("alt", "").lower()
            img_title = img_tag.get("title", "").lower()
            parent = img_tag.find_parent()
            parent_classes = " ".join(parent.get("class", [])).lower() if parent else ""
            parent_id = parent.get("id", "").lower() if parent else ""

            raw_src_options = [s_url for s_url in [src, data_src] if s_url and not s_url.startswith("data:image")]
            if srcset:
                sources = [s.strip().split()[0] for s in srcset.split(',') if s.strip() and not s.strip().startswith("data:image")]
                raw_src_options.extend(sources)

            is_likely_logo = False
            is_explicit_logo_signal = False
            logo_keywords = ["logo", "brand", "logotype", "header-logo", "site-logo", "navbar-logo", "identity", "logoหลัก", "โลโก้"]
            skip_keywords_strict = ["icon", "avatar", "profile", "placeholder", "spinner", "loader", "close", "menu", "hamburger", "banner", "pixel", "tracker", "badge", "seal", "card", "payment", "captcha", "flag", "star", "rating", "thumbnail", "arrow", "caret", "example", "sample", "pattern", "bg", "background", "footer-logo"]
            skip_keywords_substring = ["/ad/", "_ad", "ad.", "ad_", "?ad=", "/ads/", "_ads", "ads.", "ads_", "?ads="]
            skip_keywords_lower_priority = ["widget", "user", "social", "feed", "promo", "slide", "map", "chart", "graph", "mini", "small", "tiny", "shield"]

            current_img_src_lower = (src.lower().split('?')[0] if src and not src.startswith("data:image") else "")
            strong_logo_fields = {"id": img_id, "class": img_class, "alt": img_alt, "title": img_title, "src": current_img_src_lower}

            if current_company_name_main_part != "unknown_domain" and current_img_src_lower and current_company_name_main_part in current_img_src_lower:
                is_explicit_logo_signal = True
                is_likely_logo = True
                print(f"  👍 Strong logo signal (company name in src): '{current_company_name_main_part}' in '{current_img_src_lower}' for src='{src}'")

            if not is_explicit_logo_signal:
                for field_name, field_value in strong_logo_fields.items():
                    if field_value and any(logo_kw in str(field_value) for logo_kw in logo_keywords):
                        is_explicit_logo_signal = True
                        is_likely_logo = True 
                        print(f"  👍 Strong logo signal (keyword): kw found in '{field_name}' ('{field_value}') for src='{src}'")
                        break
            
            if not is_explicit_logo_signal:
                img_fields_for_skip_check = {"id": img_id, "class": img_class, "alt": img_alt, "title": img_title, "parent_class": parent_classes, "parent_id": parent_id, "src": current_img_src_lower}
                skipped_due_to_keyword = False

                for field_name, field_value in img_fields_for_skip_check.items():
                    if not field_value: continue
                    for skip_kw in skip_keywords_strict:
                        if skip_kw in str(field_value):
                            if "logo" in strong_logo_fields["src"] and field_name != "src":
                                print(f"  🤔 Field '{field_name}' ('{field_value}') has strict_skip_kw='{skip_kw}', but 'logo' in src. Prioritizing src.")
                            else:
                                print(f"  ⚠️ DEBUG SKIP (Strict): Matched skip_kw='{skip_kw}' in field='{field_name}' with value='{field_value}' for src='{src}'")
                                skipped_due_to_keyword = True; break
                    if skipped_due_to_keyword: break
                if skipped_due_to_keyword: continue

                if current_img_src_lower:
                    for skip_sub_kw in skip_keywords_substring:
                        if skip_sub_kw in current_img_src_lower:
                            print(f"  ⚠️ DEBUG SKIP (Substring): Matched skip_kw='{skip_sub_kw}' in src='{src}'"); skipped_due_to_keyword = True; break
                if skipped_due_to_keyword: continue
                
                found_lower_priority_skip = False; offending_lower_skip_field_name = ""; offending_lower_skip_value = ""; offending_lower_skip_kw = ""
                for field_name, field_value in img_fields_for_skip_check.items():
                    if not field_value: continue
                    for skip_kw in skip_keywords_lower_priority:
                        if skip_kw in str(field_value):
                            found_lower_priority_skip = True
                            offending_lower_skip_field_name = field_name
                            offending_lower_skip_value = field_value
                            offending_lower_skip_kw = skip_kw
                            print(f"  ℹ️ Lower prio skip candidate: kw='{skip_kw}' in field='{field_name}' ('{field_value}') for src='{src}'")
                            break
                    if found_lower_priority_skip: break
                
                if found_lower_priority_skip:
                    override_lower_priority_skip = False
                    for f_name_strong, f_val_strong in strong_logo_fields.items():
                        if f_val_strong and any(logo_kw in str(f_val_strong) for logo_kw in logo_keywords):
                            override_lower_priority_skip = True
                            print(f"  👍 Override lower_prio_skip '{offending_lower_skip_kw}': Direct logo_kw in img attribute '{f_name_strong}' for src='{src}'.")
                            break
                    
                    if not override_lower_priority_skip and \
                       current_company_name_main_part != "unknown_domain" and \
                       current_img_src_lower and \
                       current_company_name_main_part in current_img_src_lower:
                        override_lower_priority_skip = True
                        print(f"  👍 Override lower_prio_skip '{offending_lower_skip_kw}': Company name in src for src='{src}'.")

                    if not override_lower_priority_skip:
                        parent_attributes_contain_logo_kw = False
                        if parent_classes and any(logo_kw in parent_classes for logo_kw in logo_keywords):
                            parent_attributes_contain_logo_kw = True
                            print(f"  👍 Override lower_prio_skip '{offending_lower_skip_kw}': Logo keyword in parent_class='{parent_classes}' for src='{src}'.")
                        if not parent_attributes_contain_logo_kw and parent_id and any(logo_kw in parent_id for logo_kw in logo_keywords):
                            parent_attributes_contain_logo_kw = True
                            print(f"  👍 Override lower_prio_skip '{offending_lower_skip_kw}': Logo keyword in parent_id='{parent_id}' for src='{src}'.")
                        
                        if parent_attributes_contain_logo_kw:
                            override_lower_priority_skip = True
                            
                    if not override_lower_priority_skip:
                        print(f"  ⚠️ DEBUG SKIP (Lower Prio): Matched skip_kw='{offending_lower_skip_kw}' in field='{offending_lower_skip_field_name}' ('{offending_lower_skip_value}') for src='{src}' and no overriding signal found.")
                        skipped_due_to_keyword = True
                if skipped_due_to_keyword: continue
            
            if not is_likely_logo: # is_likely_logo could be True from explicit signal checks above
                all_relevant_fields_for_logo_check = [img_id, img_class, img_alt, img_title, parent_classes, parent_id, current_img_src_lower]
                if current_company_name_main_part != "unknown_domain" and current_img_src_lower and current_company_name_main_part in current_img_src_lower:
                    is_likely_logo = True # Set it here if not already set by strong signal check
                    print(f"  👍 General logo signal (company name in src): '{current_company_name_main_part}' in '{current_img_src_lower}'")
                
                if not is_likely_logo and any(logo_kw in str(s_field) for s_field in all_relevant_fields_for_logo_check if s_field for logo_kw in logo_keywords):
                    is_likely_logo = True
                    print(f"  👍 General logo signal (keyword): Found logo keyword in attributes/src for src='{src}'")

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
                    print(f"  ℹ️ Skipping img (not deemed likely logo by heuristics AFTER ALL CHECKS): src='{src}', alt='{img_alt}', class='{img_class}'")
                continue
            
            if not raw_src_options:
                print(f"  ℹ️ Skipping likely logo (no valid src found after filtering data URIs): alt='{img_alt}', class='{img_class}'")
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

# Ensure the rest of your scraper.py file (other functions like process_image_content, main, etc.) follows.
# Also ensure ensure_static_dir_exists and STATIC_DIR_PATH are defined at the top of scraper.py.
# The rest of scraper.py (trim_whitespace, resize_to_canvas, etc.) would follow here.
# Make sure ensure_static_dir_exists() and STATIC_DIR_PATH are defined correctly
# at the beginning of the scraper.py file.

def trim_whitespace(image, threshold=240, border_px=1):
    if image.mode != 'RGBA': image = image.convert('RGBA')
    alpha = image.split()[-1]
    bbox = alpha.getbbox()
    if not bbox: return image
    image_trimmed_alpha = image.crop(bbox)
    temp_pixels = image_trimmed_alpha.load()
    width, height = image_trimmed_alpha.size
    is_opaque_enough_for_color_trim = True
    if width > border_px*2 and height > border_px*2:
        opaque_count = 0; border_pixel_count = 0
        for x_coord in range(width):
            for y_offset in range(min(border_px, height // 2)):
                if temp_pixels[x_coord,y_offset][3] > 200: opaque_count+=1
                if temp_pixels[x_coord,height-1-y_offset][3] > 200: opaque_count+=1
                border_pixel_count +=2
        for y_coord in range(min(border_px, height // 2), height - min(border_px, height // 2)):
            for x_offset in range(min(border_px, width // 2)):
                if temp_pixels[x_offset,y_coord][3] > 200: opaque_count+=1
                if temp_pixels[width-1-x_offset,y_coord][3] > 200: opaque_count+=1
                border_pixel_count +=2
        if border_pixel_count > 0 and (opaque_count / border_pixel_count) < 0.8:
            is_opaque_enough_for_color_trim = False
    if not is_opaque_enough_for_color_trim:
        print("ℹ️ Skipping color-based trim (alpha-trimmed image has transparent borders).")
        return image_trimmed_alpha
    left, top, right, bottom, found_content = width, height, 0, 0, False
    for x in range(width):
        for y in range(height):
            r, g, b, a = temp_pixels[x, y]
            if a > 128 and (r < threshold or g < threshold or b < threshold):
                left = min(left, x); right = max(right, x); top = min(top, y); bottom = max(bottom, y)
                found_content = True
    return image_trimmed_alpha.crop((left, top, right + 1, bottom + 1)) if found_content else image_trimmed_alpha

def resize_to_canvas(image, canvas_width=280, canvas_height=140):
    if not image or image.width == 0 or image.height == 0:
        print(f"⚠️ Cannot resize_to_canvas: invalid image or zero dimension. Image: {image}")
        return Image.new("RGBA", (canvas_width, canvas_height), (0,0,0,0))
    image_ratio = image.width / image.height
    canvas_ratio = canvas_width / canvas_height
    if image_ratio > canvas_ratio: new_width = canvas_width; new_height = round(new_width / image_ratio)
    else: new_height = canvas_height; new_width = round(new_height * image_ratio)
    new_width = max(1, new_width); new_height = max(1, new_height)
    try:
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"Error during resize: {e}. Orig: {image.size}, Target:({new_width}x{new_height}). Returning original."); return image
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    paste_x = (canvas_width - new_width) // 2; paste_y = (canvas_height - new_height) // 2
    canvas.paste(resized, (paste_x, paste_y), mask=resized if resized.mode == "RGBA" else None)
    return canvas

def remove_black_background_heuristic(image, border_check_depth=3, color_threshold=20, percentage_threshold=0.60):
    if not image: return image
    if image.mode != 'RGBA': image = image.convert('RGBA')
    width, height = image.size
    if width < border_check_depth * 2 or height < border_check_depth * 2: print("ℹ️ Image too small for border-based black background removal."); return image
    pixels = image.load()
    border_black_pixels, border_total_pixels_checked = 0, 0
    for x in range(width):
        for d in range(min(border_check_depth, height // 2)):
            if pixels[x, d][3] > 200 and all(c <= color_threshold for c in pixels[x, d][:3]): border_black_pixels +=1
            if pixels[x, height - 1 - d][3] > 200 and all(c <= color_threshold for c in pixels[x, height - 1 - d][:3]): border_black_pixels +=1
            border_total_pixels_checked +=2
    for y in range(min(border_check_depth, height // 2), height - min(border_check_depth, height // 2)):
        for d in range(min(border_check_depth, width // 2)):
            if pixels[d, y][3] > 200 and all(c <= color_threshold for c in pixels[d, y][:3]): border_black_pixels +=1
            if pixels[width - 1 - d, y][3] > 200 and all(c <= color_threshold for c in pixels[width - 1 - d, y][:3]): border_black_pixels +=1
            border_total_pixels_checked +=2
    if border_total_pixels_checked == 0: return image
    if (border_black_pixels / border_total_pixels_checked) > percentage_threshold:
        print(f"ℹ️ Potential black bg detected ({(border_black_pixels / border_total_pixels_checked)*100:.1f}% border blackish). Removing.")
        new_data = [ (r,g,b,0) if a > 200 and all(c <= color_threshold for c in (r,g,b)) else (r,g,b,a) for r,g,b,a in image.getdata()]
        image.putdata(new_data)
    else:
        print(f"ℹ️ No dominant black border ({(border_black_pixels / border_total_pixels_checked)*100:.1f}% blackish). Skipping heuristic black removal.")
    return image

# MODIFIED to take content_type as a parameter
def process_image_content(image_bytes, source_identifier, name_hint_prefix, actual_content_type=None):
    try:
        image = None
        # Determine if it's SVG based on actual_content_type if provided, otherwise fallback to URL hint
        is_actually_svg = False
        if actual_content_type:
            is_actually_svg = "svg" in actual_content_type.lower()
        else: # Fallback for direct calls like process_uploaded_image_data
            parsed_source_url_for_hint = urlparse(source_identifier.lower())
            is_actually_svg = parsed_source_url_for_hint.path.endswith(".svg")

        if is_actually_svg:
            try:
                from cairosvg import svg2png
                print(f"Attempting to convert SVG content (type: {actual_content_type or 'hinted'}) from '{source_identifier}' to PNG using cairosvg.")
                png_bytes = svg2png(bytestring=image_bytes, output_width=560, output_height=280, background_color="rgba(0,0,0,0)")
                image = Image.open(BytesIO(png_bytes)).convert("RGBA")
                print("✅ SVG content successfully converted to PNG by cairosvg.")
            except ImportError:
                print("❌ cairosvg not installed. Cannot convert SVG content to PNG.")
                return None
            except Exception as svg_error:
                print(f"❌ cairosvg conversion error for content from '{source_identifier}': {svg_error}")
                return None
        
        if image is None and not is_actually_svg: # Only try Pillow if not SVG or SVG processing failed
            try:
                print(f"Attempting to open non-SVG image content (type: {actual_content_type or 'unknown/hinted'}) from '{source_identifier}' with Pillow.")
                image = Image.open(BytesIO(image_bytes)).convert("RGBA")
                print("✅ Non-SVG image content successfully opened by Pillow.")
            except Exception as pillow_open_error:
                print(f"❌ Pillow could not open image content from '{source_identifier}': {pillow_open_error}")
                return None
        elif image is None and is_actually_svg:
            print(f"❌ Failed to process SVG from '{source_identifier}' as cairosvg step did not yield an image, though it was identified as SVG.")
            return None

        if image is None:
            print(f"❌ Image object is None after attempting to load/convert from '{source_identifier}'.")
            return None
        
        print(f"🖼️ Image loaded for processing. Original mode: {image.mode}, size: {image.size}")
        if image.width == 0 or image.height == 0:
            print(f"❌ Image from '{source_identifier}' has zero dimension ({image.width}x{image.height}) after loading. Cannot process.")
            return None

        image = trim_whitespace(image); print(f"  After trim_whitespace: {image.size}")
        image = resize_to_canvas(image); print(f"  After resize_to_canvas: {image.size}")
        image = remove_black_background_heuristic(image); print(f"  After remove_black_background_heuristic: {image.size}")

        timestamp = int(time.time())
        parsed_source_url_for_filename = urlparse(source_identifier) # Use original case for filename part
        base_source_name_part, _ = os.path.splitext(os.path.basename(parsed_source_url_for_filename.path))
        safe_base_name = "".join(c if c.isalnum() else "_" for c in base_source_name_part[:20]) if base_source_name_part else "logo"
        filename = f"{name_hint_prefix}_{safe_base_name}_{timestamp}.png"
        ensure_static_dir_exists()
        filepath = os.path.join(STATIC_DIR_PATH, filename)
        image.save(filepath, "PNG")
        print(f"✅ Processed image saved as {filepath}")
        return filename
    except Exception as e:
        print(f"❌ Failed during image content processing (source: '{source_identifier}'): {e}")
        traceback.print_exc()
        return None

# scraper.py

# ... (other imports and functions like urlparse, os, requests, process_image_content) ...
# Ensure process_image_content is defined elsewhere in the file as before.

def download_and_save_image(image_url, company_name_hint):
    image_content_type = None # To store the determined content type from the response

    def try_download(url_to_try):
        nonlocal image_content_type # Allow modification of outer scope variable
        try:
            print(f"Attempting to download: {url_to_try}")
            
            parsed_uri = urlparse(url_to_try)
            referer_url = f"{parsed_uri.scheme}://{parsed_uri.netloc}/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
                'Referer': referer_url
            }

            response = requests.get(url_to_try, timeout=15, headers=headers)
            
            if response.status_code == 404:
                print(f"❌ Download failed for {url_to_try}: Server returned 404 Not Found.")
                image_content_type = "error/404" # Special marker
                return None 

            response.raise_for_status() # For other HTTP errors (5xx, 403, etc.)
            
            # Store the actual content type from the successful response
            image_content_type = response.headers.get("Content-Type", "").lower()
            print(f"Response from {url_to_try}: Status {response.status_code}, Content-Type: {image_content_type}")

            # 1. Ideal case: Explicit image content type
            if image_content_type.startswith("image/"):
                print(f"✅ Content-Type is an image type ('{image_content_type}').")
                return response
            
            # 2. Handle generic binary types
            generic_types = ["application/octet-stream", "binary/octet-stream"]
            path_basename_to_try = os.path.basename(parsed_uri.path)
            looks_like_image_url_by_extension = any(path_basename_to_try.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico'])

            if image_content_type in generic_types:
                if looks_like_image_url_by_extension:
                    print(f"⚠️ Content-Type is generic ('{image_content_type}'), and URL ('{url_to_try}') extension suggests an image. Proceeding.")
                    return response
                else:
                    # NEW: If Content-Type is octet-stream and URL has NO image extension,
                    # but our scraper heuristics picked it, try processing it.
                    # This is for cases like S3 URLs without extensions.
                    print(f"⚠️ Content-Type is generic ('{image_content_type}'), URL has no image extension, but heuristics identified it. Attempting to process.")
                    return response 
            
            # 3. Handle server mistakenly returning HTML for an image URL
            if image_content_type.startswith("text/html"):
                 print(f"❌ Content-Type is '{image_content_type}', but URL ('{url_to_try}') suggests an image. Server returned HTML. Skipping.")
                 image_content_type = "error/html_instead_of_image" # Special marker
                 return None

            # 4. If none of the above, content type is not recognized/permissible
            print(f"❌ Content-Type ('{image_content_type}') not a recognized/permissible type for URL ('{url_to_try}').")
            return None
            
        except requests.exceptions.HTTPError as http_err:
            print(f"❌ Download failed for {url_to_try} with HTTPError: {http_err}")
            if http_err.response.status_code == 404:
                 image_content_type = "error/404"
            # You could add more specific handling for other codes like 403 Forbidden here
            # For now, just ensure image_content_type reflects an error state or is None
            elif image_content_type and not image_content_type.startswith("error/"): # if it was set to something valid before error
                image_content_type = None
            return None
        except requests.exceptions.RequestException as e: # Catch other network errors (timeout, DNS, connection error)
            print(f"❌ Download failed for {url_to_try} with RequestException: {e}")
            image_content_type = None # Reset on failure
            return None

    # Call the inner try_download function
    response_object = try_download(image_url) 
    
    # Check for special error markers set by try_download
    if image_content_type == "error/404":
        print(f"❌ Specific Error: Identified logo URL {image_url} resulted in a 404 error from server.")
        return None 
    if image_content_type == "error/html_instead_of_image":
        print(f"❌ Specific Error: Identified logo URL {image_url} returned HTML instead of an image from server.")
        return None

    # If response_object is None for any other reason (e.g., unrecognized content type, other network error)
    if response_object is None:
        print(f"❌ Download or initial validation failed for the image URL: {image_url}")
        return None
        
    # If download was successful and content type seems okay, proceed to process
    try:
        # actual_content_type is passed to help process_image_content decide if it's SVG, etc.
        print(f"⚙️ Processing image from {image_url} with detected Content-Type: {image_content_type}")
        return process_image_content(response_object.content, image_url, company_name_hint, actual_content_type=image_content_type)
    except Exception as e:
        print(f"❌ Failed to process downloaded image content from {image_url}: {e}")
        traceback.print_exc()
        return None

# Remember to have process_image_content defined elsewhere in scraper.py:
# def process_image_content(image_bytes, source_identifier, name_hint_prefix, actual_content_type=None):
#    # ... its full implementation ...
def process_uploaded_image_data(image_bytes, original_filename, name_hint_for_file):
    print(f"⚙️ Processing uploaded file: '{original_filename}', with name hint: '{name_hint_for_file}'")
    # For uploaded files, we don't have a server-sent Content-Type,
    # so process_image_content will rely on the original_filename hint (e.g. if it's .svg)
    # or Pillow's detection.
    return process_image_content(image_bytes, original_filename, name_hint_for_file, actual_content_type=None)

def main():
    test_url = input("Enter company website URL for standalone test (or type 'skip' for no Selenium test): ").strip()
    if test_url.lower() != 'skip':
        if not test_url.startswith("http"): test_url = "https://" + test_url
        domain_name = extract_domain(test_url)
        company_name = "unknown"
        if domain_name != "unknown_domain":
            domain_parts = domain_name.split('.')
            company_name = domain_parts[0] if len(domain_parts) == 1 else (domain_parts[1] if domain_parts[0].lower() == 'www' and len(domain_parts) > 1 else domain_parts[0])
        
        logo_url_from_selenium = search_logo_with_selenium(test_url)
        if isinstance(logo_url_from_selenium, str) and logo_url_from_selenium.startswith("http"):
            print(f"\n--- Standalone Test: Downloading from URL: {logo_url_from_selenium} ---")
            download_and_save_image(logo_url_from_selenium, company_name)
        elif logo_url_from_selenium is None: print("\n--- Standalone Test: Selenium search returned None (check static folder for internal saves) ---")
        else: print(f"\n--- Standalone Test: Selenium search returned: {logo_url_from_selenium} (not a downloadable URL) ---")
    
    sample_image_path = "test_logo.png" 
    if os.path.exists(sample_image_path):
        print(f"\n--- Standalone Test: Processing local file: {sample_image_path} ---")
        with open(sample_image_path, "rb") as f: img_bytes = f.read()
        process_uploaded_image_data(img_bytes, sample_image_path, "test_upload")
    else: print(f"\nℹ️ Standalone Test: Sample image '{sample_image_path}' not found.")

if __name__ == "__main__":
    main()