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
    
    # 2. PEHLA TRY: Normal Barcode Scan
    decoded_objects = decode(img)
    if decoded_objects:
        docket_id = decoded_objects[0].data.decode('utf-8').strip()
        return "".join(x for x in docket_id if x.isalnum() or x in "._-")
        
    # 3. DUSRA TRY: Image ko Black & White aur Sharp karke Barcode Scan (Dhundhle QR/Barcode ke liye)
    gray_img = ImageOps.grayscale(img)
    enhancer = ImageEnhance.Contrast(gray_img)
    sharp_img = enhancer.enhance(2.0)
    
    decoded_objects_2 = decode(sharp_img)
    if decoded_objects_2:
        docket_id = decoded_objects_2[0].data.decode('utf-8').strip()
        return "".join(x for x in docket_id if x.isalnum() or x in "._-")
        
    # 4. TISRA TRY (SMART OCR): Sirf AWB/Docket number padhna, Mobile/Ph number nahi
    try:
        extracted_text = pytesseract.image_to_string(sharp_img)
        
        # Condition A: Agar text mein AWB, Waybill ya Docket likha ho (Sabse Accurate)
        keyword_match = re.search(r'(?:AWB|Waybill|Docket|Tracking)[\s\:\-\#]*(?:No\.?)?[\s\:\-\#]*([A-Za-z0-9]{8,18})', extracted_text, re.IGNORECASE)
        if keyword_match:
            return keyword_match.group(1)
            
        # Condition B: Safexpress format jisme space hota hai (Jaise: 1000 3524 5962)
        safe_match = re.search(r'\b(\d{4}\s\d{4}\s\d{4})\b', extracted_text)
        if safe_match:
            return safe_match.group(1).replace(" ", "")

        # Condition C: Agar upar kuch na mile, toh sirf wo number uthayein jo Mobile ya Phone na ho
        lines = extracted_text.split('\n')
        for line in lines:
            # Agar line mein Mobile, Phone, Ph, Pincode ya GST likha hai, toh usko ignore karein
            if re.search(r'mob|ph\s|phone|contact|pincode|gst', line, re.IGNORECASE):
                continue
                
            # Baki bachi line mein 9 se 18 digit ka number dhoondein (Kyunki barcode number bada hota hai)
            nums = re.findall(r'\b\d{9,18}\b', line)
            for n in nums:
                # Agar 9999999999 jaisa koi fake ek jaisa number hai toh usko ignore karein
                if n == n[0] * len(n):
                    continue
                return n
    except Exception as e:
        pass # Agar OCR fail ho jaye toh code crash na ho
        
    return None

def process_pdf(uploaded_file):
    pdf_document = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            
            # Smart Scanner Function Call
            docket_id = get_docket_from_image(page)
            
            # File ka naam tay karein
            if docket_id:
                file_name = f"{docket_id}.pdf"
            else:
                file_name = f"Unscanned_Page_{page_num + 1}.pdf"
                
            # --- SUPER COMPRESSION LOGIC (Size kam karne ke liye - 100-150KB) ---
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
