import streamlit as st
import fitz  # PyMuPDF
import zipfile
import io
import re
from PIL import Image, ImageEnhance, ImageOps
from pyzbar.pyzbar import decode
import pytesseract

# Barcode aur OCR Scan karne ka Super Function
def get_docket_from_image(page):
    # 1. Page ko high quality image mein badlein
    pix = page.get_pixmap(dpi=300)
    img = Image.frombytes("RGB",[pix.width, pix.height], pix.samples)
    
    # Helper Function: Check karne ke liye ki result mein SIRF NUMBER hai ya nahi
    def is_valid_docket(text):
        # User requirement: Sirf numbers hone chahiye (0-9), baaki sab hata do
        clean_text = "".join(x for x in text if x.isdigit())
        # Docket kam se kam 8 digits ka hona chahiye (jaisa screenshots mein hai)
        if len(clean_text) >= 8 and len(clean_text) <= 18:
            # 99999999 jaise fake numbers ko block karein
            if clean_text == clean_text[0] * len(clean_text):
                return False, ""
            return True, clean_text
        return False, ""

    # 2. PEHLA TRY: Normal Barcode Scan
    decoded_objects = decode(img)
    for obj in decoded_objects:
        valid, clean_data = is_valid_docket(obj.data.decode('utf-8').strip())
        if valid:
            return clean_data
        
    # 3. DUSRA TRY: Image ko Black & White aur Sharp karke Barcode Scan
    gray_img = ImageOps.grayscale(img)
    enhancer = ImageEnhance.Contrast(gray_img)
    sharp_img = enhancer.enhance(2.0)
    
    decoded_objects_2 = decode(sharp_img)
    for obj in decoded_objects_2:
        valid, clean_data = is_valid_docket(obj.data.decode('utf-8').strip())
        if valid:
            return clean_data
        
    # 4. TISRA TRY (SMART OCR): Sirf "Numbers" uthana, alphabets nahi
    try:
        extracted_text = pytesseract.image_to_string(sharp_img)
        
        # Condition A: Safexpress format jisme space hota hai (Jaise: 1000 3524 5962)
        safe_match = re.search(r'\b(\d{4}\s\d{4}\s\d{4})\b', extracted_text)
        if safe_match:
            return safe_match.group(1).replace(" ", "")

        # Condition B: Agar text mein AWB, Waybill ya Docket likha ho aur aage PURE NUMBER ho
        keyword_match = re.search(r'(?:AWB|Waybill|Docket|Tracking)[\s\:\-\#]*(?:No\.?)?[\s\:\-\#]*(\d{8,18})\b', extracted_text, re.IGNORECASE)
        if keyword_match:
            return keyword_match.group(1)

        # Condition C: Agar upar kuch na mile, toh sirf standalone number dhoondo (Jo Barcode ke niche bada sa likha hota hai)
        lines = extracted_text.split('\n')
        for line in lines:
            # In sab cheezon wale number ko dhokhe se bhi mat uthana
            if re.search(r'mob|ph[\s\:\.]|phone|contact|pincode|pin\s|gst|date|time|rs\.|amount|pkg|ref', line, re.IGNORECASE):
                continue
                
            # Line mein sirf aur sirf NUMBER dhoondo (8 se 18 digit ka)
            nums = re.findall(r'\b\d{8,18}\b', line)
            for n in nums:
                # Fake numbers jaise 999999999 ignore karo
                if n == n[0] * len(n):
                    continue
                return n
    except Exception as e:
        pass 
        
    return None

def process_pdf(uploaded_file):
    pdf_document = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            
            docket_id = get_docket_from_image(page)
            
            if docket_id:
                file_name = f"{docket_id}.pdf"
            else:
                file_name = f"Unscanned_Page_{page_num + 1}.pdf"
                
            # --- COMPRESSION LOGIC (100-150KB) ---
            pix_low = page.get_pixmap(dpi=150, colorspace=fitz.csGRAY)
            img = Image.frombytes("L",[pix_low.width, pix_low.height], pix_low.samples)
            
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG', quality=45, optimize=True)
            img_bytes = img_byte_arr.getvalue()
            
            new_pdf = fitz.open()
            new_page = new_pdf.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, stream=img_bytes)
            
            pdf_bytes = new_pdf.write(garbage=4, deflate=True)
            new_pdf.close()
            # -----------------------------------------------------
            
            zip_file.writestr(file_name, pdf_bytes)
            
    return zip_buffer

# --- UI Setup ---
st.set_page_config(page_title="Auto PDF Splitter & Renamer", page_icon="📦")
st.title("📦 Smart PDF Splitter")
st.write("Apna courier PDF upload karein. Agar Barcode dhundhla hua, toh App automatically Text padh kar rename karega!")

uploaded_file = st.file_uploader("Upload Main PDF File", type=["pdf"])

if uploaded_file is not None:
    if st.button("Magic Start 🪄 (Process & ZIP)"):
        with st.spinner("Scanning Barcodes & Reading Text (Isme thoda waqt lag sakta hai)..."):
            try:
                zip_data = process_pdf(uploaded_file)
                st.success("🎉 Process Complete! Aapki ZIP file taiyaar hai.")
                
                st.download_button(
                    label="📥 Download ZIP",
                    data=zip_data.getvalue(),
                    file_name="Renamed_Dockets.zip",
                    mime="application/zip"
                )
            except Exception as e:
                st.error(f"Kuch error aayi: {e}")
