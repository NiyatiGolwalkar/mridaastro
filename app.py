
import streamlit as st
import os

# --- Keep background ---
def _apply_bg():
    bg_file = os.path.join("assets", "ganesha_bg.png")
    if os.path.exists(bg_file):
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url("file://{bg_file}");
                background-size: cover;
                background-attachment: fixed;
            }}
            </style>
            """, unsafe_allow_html=True
        )

# Apply background
_apply_bg()

# --- Branding header ---
st.markdown("<h1 style='text-align: center;'>MRIDAASTRO</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center; font-style: italic;'>In the light of divine, let your soul journey shine</h3>", unsafe_allow_html=True)
st.markdown("<hr style='height:2px;border:none;color:gold;background-color:gold;'/>", unsafe_allow_html=True)

# --- Input fields ---
col1, col2 = st.columns(2)
with col1:
    name = st.text_input("Name")
    tob = st.time_input("Time of Birth")
    utc_offset = st.text_input("UTC offset override (optional, e.g., 5.5)", "5.5")
with col2:
    dob = st.date_input("Date of Birth")
    pob = st.text_input("Place of Birth (City, State, Country)")

# --- Generate DOCX button ---
if st.button("Generate DOCX"):
    try:
        # Dummy generator - replace with your actual kundali generator function
        from pathlib import Path
        file_path = Path("kundali_output.docx")
        with open(file_path, "wb") as f:
            f.write(b"This is a placeholder DOCX. Replace with kundali generator output.")
        
        with open(file_path, "rb") as f:
            st.download_button(
                label="Download Kundali (DOCX)",
                data=f,
                file_name="kundali_output.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
    except Exception as e:
        st.error("Couldn't generate the DOCX. Please check the generator function.")
