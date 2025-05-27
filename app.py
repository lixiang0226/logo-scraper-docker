# app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
# Modified import: Added process_uploaded_image_data
from scraper import search_logo_with_selenium, download_and_save_image, extract_domain, process_uploaded_image_data
import os
import traceback # For more detailed error logging if needed

# http://127.0.0.1:5001/

app = Flask(__name__)
CORS(app)  # ✅ Allow cross-origin requests
app.config['UPLOAD_FOLDER'] = 'static' # Define where static files (logos) are stored

@app.route('/')
def index():
    # Serves the main HTML page
    return open("index.html").read()

@app.route('/scrape', methods=['POST'])
def scrape_logo():
    try:
        data = request.get_json(force=True) # Ensure data is parsed as JSON
        url = data.get("url")
        print(f"🌐 Incoming scrape request for: {url}")

        if not url:
            print("❌ Error: No URL provided.")
            return jsonify({"error": "No URL provided"}), 400
        
        # Basic check for invalid characters in hostname part
        # This is a simple check; more sophisticated validation could be added
        temp_domain_check = url.split('/')[2] if '//' in url else url.split('/')[0]
        if any(char in temp_domain_check for char in [' ', '\t', '\n', '\r']):
            print(f"❌ Error: URL '{url}' contains invalid characters in hostname.")
            return jsonify({"error": f"Invalid URL format: '{url}' contains spaces or control characters in hostname."}), 400

        # Normalize URL to include scheme if missing
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
            print(f"🔁 Normalized URL to: {url}")

        company_name = extract_domain(url).split('.')[0]
        print(f"🏷️ Extracted company name: {company_name}")

        scraper_result = search_logo_with_selenium(url)
        print(f"🔍 search_logo_with_selenium returned: {scraper_result}")

        if isinstance(scraper_result, str) and scraper_result.startswith("http"):
            logo_image_url = scraper_result
            print(f"⬇️ Downloading image from: {logo_image_url}")
            saved_filename = download_and_save_image(logo_image_url, company_name)

            if saved_filename:
                print(f"✅ Image saved as: {saved_filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
                file_size = 0
                if os.path.exists(filepath):
                    file_size = os.path.getsize(filepath)
                else:
                    print(f"⚠️ CRITICAL WARNING: File '{saved_filename}' reported as saved, but not found at '{filepath}'.")
                    return jsonify({"error": "Logo processing failed; saved file is missing."}), 500
                return jsonify({
                    "message": f"Logo found and saved for {company_name}",
                    "logo_url": f"/{app.config['UPLOAD_FOLDER']}/{saved_filename}",
                    "filename": saved_filename,
                    "file_size": file_size
                })
            else:
                print("❌ Failed to download and save the image from the URL provided by scraper.")
                return jsonify({"error": "Failed to download or process the identified logo image."}), 500
        elif scraper_result is None:
            print("ℹ️ Scraper returned None. Checking for internally saved files.")
            potential_files = []
            for f_name in os.listdir(app.config['UPLOAD_FOLDER']):
                if f_name.startswith(f"{company_name}_logo") and f_name.endswith(".png"):
                    potential_files.append(os.path.join(app.config['UPLOAD_FOLDER'], f_name))
            print(f"📦 Potential matching .png files: {[os.path.basename(p) for p in potential_files]}")
            if potential_files:
                most_recent_filepath = max(potential_files, key=os.path.getmtime)
                final_saved_filename = os.path.basename(most_recent_filepath)
                print(f"📌 Most recent .png file selected: {final_saved_filename}")
                file_size = 0
                if os.path.exists(most_recent_filepath):
                    file_size = os.path.getsize(most_recent_filepath)
                else:
                    print(f"⚠️ CRITICAL WARNING: File '{final_saved_filename}' selected but not found.")
                    return jsonify({"error": "Error accessing internally saved logo file."}), 500
                return jsonify({
                    "message": "Logo processed (e.g. from screenshot or inline SVG) and found",
                    "logo_url": f"/{app.config['UPLOAD_FOLDER']}/{final_saved_filename}",
                    "filename": final_saved_filename,
                    "file_size": file_size
                })
            else:
                print("❌ Scraper returned None, and no matching .png file found. Concluding no logo found.")
                return jsonify({"error": "No logo found for the website."}), 404
        else:
            print(f"❌ Scraper returned an unexpected or unusable result: '{scraper_result}'. No valid logo found.")
            return jsonify({"error": "Scraper did not return a usable logo URL or indication of a saved file."}), 404
    except Exception as e:
        print(f"❗ An unexpected server error occurred in /scrape route: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": f"An unexpected server error occurred: {str(e)}"}), 500

@app.route('/static/<path:filename>')
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- NEW ROUTE for Logo Reformat Tool ---
@app.route('/reformat-logo', methods=['POST'])
def reformat_uploaded_logo():
    try:
        if 'logo_image_to_reformat' not in request.files:
            print("❌ Error [/reformat-logo]: No 'logo_image_to_reformat' file part in request.")
            return jsonify({"error": "No image file provided for reformatting."}), 400

        file = request.files['logo_image_to_reformat']

        if file.filename == '':
            print("❌ Error [/reformat-logo]: No file selected for reformatting.")
            return jsonify({"error": "No file selected for reformatting."}), 400

        if file: # Basic check, could add more validation (e.g., allowed extensions server-side)
            image_bytes = file.read() # Read file content into bytes
            original_filename = file.filename
            print(f"🖼️ [/reformat-logo]: Received file '{original_filename}' for reformatting.")

            # For the reformatted file, we'll use a generic name hint or one derived from original filename.
            # The actual processing function in scraper.py will handle timestamping.
            # We can extract the base of the original filename without extension as a hint.
            name_hint_base, _ = os.path.splitext(original_filename)
            # Sanitize and shorten the hint
            sanitized_name_hint = "".join(c if c.isalnum() else "_" for c in name_hint_base[:20])
            name_hint = f"reformatted_{sanitized_name_hint}" if sanitized_name_hint else "reformatted_logo"

            # Call the processing function from scraper.py
            # This function will handle saving to 'static' and return the new filename
            reformatted_filename = process_uploaded_image_data(image_bytes, original_filename, name_hint)

            if reformatted_filename:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], reformatted_filename)
                file_size = 0
                if os.path.exists(filepath):
                    file_size = os.path.getsize(filepath)
                else:
                    # This means process_uploaded_image_data reported success but the file is missing
                    print(f"⚠️ CRITICAL [/reformat-logo]: File '{reformatted_filename}' reported as saved but not found.")
                    return jsonify({"error": "Error saving reformatted image."}), 500
                
                print(f"✅ [/reformat-logo]: Reformatting successful. Saved as '{reformatted_filename}'.")
                return jsonify({
                    "message": "Logo reformatted successfully!",
                    "logo_url": f"/{app.config['UPLOAD_FOLDER']}/{reformatted_filename}",
                    "filename": reformatted_filename,
                    "file_size": file_size
                })
            else:
                print("❌ Error [/reformat-logo]: Failed to process/reformat the uploaded image in backend.")
                return jsonify({"error": "Failed to reformat the uploaded image."}), 500
        else:
            # This case should be caught by earlier checks, but as a fallback
            return jsonify({"error": "Invalid file provided for reformatting."}), 400

    except Exception as e:
        print(f"❗ Server error in /reformat-logo: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": f"An unexpected server error occurred during reformatting: {str(e)}"}), 500

if __name__ == "__main__":
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=False, host='0.0.0.0', port=5007) 