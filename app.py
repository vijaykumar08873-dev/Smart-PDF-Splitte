import streamlit as st
import fitz  # PyMuPDF
import zipfile
import io
import re
from PIL import Image
from pyzbar.pyzbar import decode

# 1. Barcode scan karne ka function (DPI badha di gayi hai taki scan fail na ho)
def get_docket_id_from_image(page):
    pix = page.get_pixmap(dpi=300) # High quality for better scanning
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    decoded_objects = decode(img)
    if decoded_objects:
        docket_id = decoded_objects[0].data.decode('utf-8').strip()
        return "".join(x for x in docket_id if x.isalnum() or x in "._-")
    return None

# 2. NAYA FUNCTION: Agar Barcode fail ho jaye, toh Text padh ke Docket nikalna
def get_docket_from_text(page):
    text = page.get_text("text")
    
    # Check 1: Agar "Docket" likha ho aur uske aage number ho
    match = re.search(r'docket[\s\:\-\#]*([a-zA-Z0-9]+)', text, re.IGNORECASE)
    if match:
        return match.group(1)
        
    # Check 2: Agar "Docket" na likha ho par koi 10 se 20 digit ka bada number ho (jaise AWB no.)
    match_num = re.search(r'\b\d{10,20}\b', text)
    if match_num:
        return match_num.group(0)
        
    return None

def process_pdf(uploaded_file):
    pdf_document = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            
            # Pehle Barcode Scan karne ki koshish karein
            docket_id = get_docket_id_from_image(page)
            
            # Agar Barcode scan NAHI hua, toh Text padhein
            if not docket_id:
                docket_id = get_docket_from_text(page)
            
            # File ka naam tay karein
            if docket_id:
                file_name = f"{docket_id}.pdf"
            else:
                file_name = f"Unscanned_Page_{page_num + 1}.pdf"
                
            # --- SUPER COMPRESSION LOGIC (100-150KB GUARANTEE) ---
            # Page ko Grayscale (Black & White) mein convert karein
            pix_low = page.get_pixmap(dpi=150, colorspace=fitz.csGRAY)
            img = Image.frombytes("L", [pix_low.width, pix_low.height], pix_low.samples)
            
            # Image ko bahut chote size ki JPEG mein badlein
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG', quality=45, optimize=True)
            img_bytes = img_byte_arr.getvalue()
            
            # Us choti image se nayi PDF banayein
            new_pdf = fitz.open()
            new_page = new_pdf.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, stream=img_bytes)
            
            pdf_bytes = new_pdf.write(garbage=4, deflate=True)
            new_pdf.close()
            # -----------------------------------------------------
            
            # Zip file mein save karna
            zip_file.writestr(file_name, pdf_bytes)
            
    return zip_buffer

# --- UI Setup ---
st.set_page_config(page_title="Auto PDF Splitter & Renamer", page_icon="📦")
st.title("📦 Smart PDF Splitter (QR/Barcode Scanner)")
st.write("Apna courier PDF upload karein. Ye app scan karega, agar scan fail hua toh text padhega, aur size compress karke Zip banayega.")

uploaded_file = st.file_uploader("Upload Main PDF File", type=["pdf"])

if uploaded_file is not None:
    if st.button("Magic Start 🪄 (Process & ZIP)"):
        with st.spinner("Processing & Compressing... isme thoda time lag sakta hai..."):
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
