# bulk_test_scraper.py
import os
import time
import csv
from urllib.parse import urlparse, unquote
import traceback

# Assuming scraper.py is in the same directory or accessible in Python's path
try:
    # Import all necessary functions from your scraper.py
    from scraper import (
        search_logo_with_selenium,
        download_and_save_image, # Used if Selenium returns a direct URL
        extract_domain,
        process_image_content # This is the core processing function
        # Add other functions if your scraper.py's internal save logic
        # relies on them directly being called here (e.g., for SVG to PNG conversion if not in process_image_content)
    )
except ImportError as e:
    print(f"Error importing from scraper.py: {e}")
    print("Make sure scraper.py is in the same directory, has no syntax errors,")
    print("and all necessary functions (search_logo_with_selenium, download_and_save_image, extract_domain, process_image_content) are defined.")
    exit()

# --- Configuration ---
URL_LIST_FILE = "urls_to_test.txt"
OUTPUT_CSV_FILE = "scraping_results.csv"
STATIC_DIR = "static"  # Directory where logos are saved
DELAY_BETWEEN_REQUESTS = 5  # Seconds. BE RESPECTFUL TO SERVERS! Increase if needed.

def normalize_url(url_str):
    """Ensure URL has a scheme."""
    if not url_str.strip(): # Handle empty strings
        return ""
    if not url_str.startswith(('http://', 'https://')):
        return 'https://' + url_str
    return url_str

def get_company_name_from_url(url_str):
    """Extracts a company name hint from the URL using scraper's extract_domain."""
    try:
        if not url_str: return "unknown_company"
        domain = extract_domain(url_str) # Uses your existing function
        parts = domain.split('.')
        if len(parts) > 1 and parts[0].lower() == 'www':
            return parts[1] if len(parts) > 2 else parts[0] # Handles www.example.com and www.example
        return parts[0]
    except Exception as e:
        print(f"  Error getting company name from URL '{url_str}': {e}")
        # Fallback for URLs that might not parse well
        try:
            parsed = urlparse(url_str)
            if parsed.hostname:
                hostname_parts = parsed.hostname.split('.')
                if len(hostname_parts) > 1 and hostname_parts[0].lower() == 'www':
                    return hostname_parts[1] if len(hostname_parts) > 2 else hostname_parts[0]
                return hostname_parts[0]
            return "unknown_company_fallback"
        except Exception:
            return "unknown_company_error"


def test_single_url(url_to_test):
    """
    Tests scraping for a single URL and returns a dictionary of results.
    """
    print(f"\n--- Processing: {url_to_test} ---")
    result = {
        "original_url": url_to_test,
        "processed_url": "",
        "company_name_guess": "",
        "status": "INIT",
        "selenium_result_url": "", # URL or 'None' string from search_logo_with_selenium
        "final_image_source_for_processing": "", # What was actually fed to process_image_content
        "saved_filename": "", # Basename of the saved file in STATIC_DIR
        "error_message": ""
    }

    try:
        result["processed_url"] = normalize_url(url_to_test)
        if not result["processed_url"]:
            result["status"] = "FAIL_INVALID_URL_INPUT"
            result["error_message"] = "Input URL was empty or invalid."
            print(f"  [FAIL] {result['error_message']}")
            return result

        result["company_name_guess"] = get_company_name_from_url(result["processed_url"])

        if not os.path.exists(STATIC_DIR):
            os.makedirs(STATIC_DIR)
            print(f"  Created directory: {STATIC_DIR}")

        print(f"  Calling search_logo_with_selenium for {result['processed_url']}...")
        scraper_selenium_output = search_logo_with_selenium(result["processed_url"])
        result["selenium_result_url"] = str(scraper_selenium_output) if scraper_selenium_output is not None else "None"
        print(f"  search_logo_with_selenium returned: {scraper_selenium_output}")

        saved_file_basename = None

        # Case 1: Selenium found a direct URL
        if isinstance(scraper_selenium_output, str) and scraper_selenium_output.startswith("http"):
            result["final_image_source_for_processing"] = scraper_selenium_output
            print(f"  Attempting to download and process from URL: {scraper_selenium_output}")
            # download_and_save_image now calls process_image_content internally
            saved_file_basename = download_and_save_image(scraper_selenium_output, result["company_name_guess"])
            if saved_file_basename:
                result["status"] = "SUCCESS_DOWNLOADED_AND_PROCESSED"
            else:
                result["status"] = "FAIL_DOWNLOAD_OR_PROCESS_FROM_URL"
                result["error_message"] = "download_and_save_image (or internal process_image_content) failed."

        # Case 2: Selenium returned None (might be internal save, e.g., screenshot or processed SVG)
        elif scraper_selenium_output is None:
            result["final_image_source_for_processing"] = "Internal save by Selenium (e.g., screenshot/SVG)"
            print(f"  search_logo_with_selenium returned None. Checking for internally saved files in '{STATIC_DIR}'...")
            potential_files = []
            # Pattern for files saved internally by search_logo_with_selenium
            # e.g., "{company_name}_logo_screenshot.png" or "{company_name}_logo_from_svg.png"
            for f_name in os.listdir(STATIC_DIR):
                if f_name.startswith(f"{result['company_name_guess']}_logo") and f_name.endswith(".png"):
                    potential_files.append(os.path.join(STATIC_DIR, f_name))
            
            if potential_files:
                most_recent_filepath = max(potential_files, key=lambda p: os.path.getmtime(p))
                saved_file_basename = os.path.basename(most_recent_filepath)
                result["status"] = "SUCCESS_INTERNAL_SELENIUM_SAVE_FOUND"
                # Note: This file was saved by search_logo_with_selenium, so it might not have
                # undergone the full process_image_content reformatting (trim, canvas, bg remove).
                # If consistency is key, you might want to load this file and re-process it.
                # For now, we just acknowledge it was found.
            else:
                result["status"] = "FAIL_NO_LOGO_SELENIUM_NONE_NO_FILE"
                result["error_message"] = "search_logo_with_selenium returned None, and no matching internally saved file found."
        else:
            result["status"] = "FAIL_SELENIUM_UNEXPECTED_RESULT"
            result["error_message"] = f"search_logo_with_selenium returned an unexpected value: {scraper_selenium_output}"

        if saved_file_basename:
            result["saved_filename"] = saved_file_basename # Just the basename
            full_path_check = os.path.join(STATIC_DIR, saved_file_basename)
            if os.path.exists(full_path_check):
                print(f"  [SUCCESS] Logo file confirmed: {full_path_check}")
            else:
                # This would be an issue if a filename was returned but file doesn't exist
                result["status"] = result["status"].replace("SUCCESS", "WARN_FILE_MISSING_POST_SAVE")
                result["error_message"] += " Saved filename reported, but file not found at path."
                print(f"  [WARNING] File '{full_path_check}' not found, though a filename was reported.")
        elif result["status"].startswith("INIT") or "FAIL" not in result["status"]: # If status wasn't set to a failure yet
             if not result["status"].startswith("SUCCESS"): # and not already a success
                result["status"] = "FAIL_UNKNOWN_NO_FILE_SAVED"
                result["error_message"] = "Processing finished but no identifiable logo file was saved or confirmed."


    except Exception as e:
        result["status"] = "FAIL_SCRIPT_ERROR"
        result["error_message"] = f"Major exception: {str(e)}"
        print(f"  [CRITICAL ERROR] during processing for {url_to_test}: {e}")
        traceback.print_exc()
        
    print(f"  Result Status: {result['status']}")
    return result

def main():
    if not os.path.exists(URL_LIST_FILE):
        print(f"Error: URL list file '{URL_LIST_FILE}' not found.")
        print(f"Please create it in the current directory ({os.getcwd()}) with one URL per line.")
        return

    with open(URL_LIST_FILE, 'r', encoding='utf-8') as f:
        urls_to_process = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    if not urls_to_process:
        print(f"No processable URLs found in '{URL_LIST_FILE}'.")
        return

    print(f"Starting bulk scrape for {len(urls_to_process)} URLs...")
    all_results = []
    successful_scrapes = 0

    csv_fieldnames = ["original_url", "processed_url", "company_name_guess", "status", 
                      "selenium_result_url", "final_image_source_for_processing", 
                      "saved_filename", "error_message"]
    
    # Ensure static directory exists before loop, though test_single_url also checks
    if not os.path.exists(STATIC_DIR):
        os.makedirs(STATIC_DIR)
        print(f"Created main static directory: {STATIC_DIR}")

    try:
        with open(OUTPUT_CSV_FILE, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_fieldnames)
            writer.writeheader()

            for i, url in enumerate(urls_to_process):
                if not url: # Skip empty lines that might have been read
                    print(f"Skipping empty URL at line {i+1}")
                    continue
                result_data = test_single_url(url)
                all_results.append(result_data)
                writer.writerow(result_data)
                csvfile.flush() 

                if result_data["status"].startswith("SUCCESS"):
                    successful_scrapes += 1
                
                if i < len(urls_to_process) - 1:
                    print(f"--- Waiting for {DELAY_BETWEEN_REQUESTS} seconds before next URL ({i+2}/{len(urls_to_process)}) ---")
                    time.sleep(DELAY_BETWEEN_REQUESTS)
    except IOError as e:
        print(f"Error writing to CSV file '{OUTPUT_CSV_FILE}': {e}")
        print("Please ensure you have write permissions and the file is not locked.")
        return
    except Exception as e:
        print(f"An unexpected error occurred during the bulk test main loop: {e}")
        traceback.print_exc()
        return


    print("\n--- Bulk Scraping Complete ---")
    print(f"Processed {len(all_results)} URLs.")
    print(f"Successful scrapes (logo file confirmed or internal save found): {successful_scrapes}")
    print(f"Results logged to: {OUTPUT_CSV_FILE}")
    print(f"Saved logos (if any) are in the '{os.path.abspath(STATIC_DIR)}' directory.")

if __name__ == "__main__":
    main()