import streamlit as st
import fitz  # PyMuPDF
import zipfile
import io
from PIL import Image
from pyzbar.pyzbar import decode

# Barcode scan karke Docket ID nikalne ka function
def get_docket_id_from_image(page):
    # PDF page ko high-resolution image (PixMap) mein convert karein
    pix = page.get_pixmap(dpi=200)
    img = Image.frombytes("RGB",[pix.width, pix.height], pix.samples)
    
    # Image mein Barcode ya QR code scan karein
    decoded_objects = decode(img)
    
    if decoded_objects:
        # Agar barcode milta hai, toh uska data return karein
        docket_id = decoded_objects[0].data.decode('utf-8').strip()
        # Agar id mein kuch ajeeb characters aa jayein, toh unko clean karein
        valid_filename = "".join(x for x in docket_id if x.isalnum() or x in "._-")
        return valid_filename
    return None

def process_pdf(uploaded_file):
    # Main PDF file open karein
    pdf_document = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            
            # 1. Barcode/QR scan karne ki koshish
            docket_id = get_docket_id_from_image(page)
            
            # 2. File ka naam set karna
            if docket_id:
                file_name = f"{docket_id}.pdf"
            else:
                # Agar us page pe QR read nahi hua, toh backup name
                file_name = f"Unscanned_Page_{page_num + 1}.pdf"
                
            # 3. Single page alag karna
            new_pdf = fitz.open()
            new_pdf.insert_pdf(pdf_document, from_page=page_num, to_page=page_num)
            pdf_bytes = new_pdf.write()
            new_pdf.close()
            
            # 4. Zip file mein save karna
            zip_file.writestr(file_name, pdf_bytes)
            
    return zip_buffer

# --- UI Setup ---
st.set_page_config(page_title="Auto PDF Splitter & Renamer", page_icon="📦")
st.title("📦 Smart PDF Splitter (QR/Barcode Scanner)")
st.write("Apna courier PDF upload karein. Ye app QR/Barcode scan karke auto-rename karega aur Zip banayega.")

uploaded_file = st.file_uploader("Upload Main PDF File", type=["pdf"])

if uploaded_file is not None:
    if st.button("Magic Start 🪄 (Process & ZIP)"):
        with st.spinner("Scannig Barcodes aur PDF split ho raha hai..."):
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