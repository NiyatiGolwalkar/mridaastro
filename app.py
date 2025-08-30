# app.py
import io
import streamlit as st
from docx import Document

# import the library we just created
from kundali_markers_lib import render_kundalis_into_doc

st.set_page_config(page_title="DevoAstroBhav Kundali", layout="centered")

st.title("DevoAstroBhav Kundali (Editable DOCX)")

# --- Simple inputs (wire these to your existing pipeline) ---
col1, col2 = st.columns(2)
name = col1.text_input("Name", "Demo User")
pob  = col2.text_input("Place of Birth (City, State, Country)", "Jabalpur, Madhya Pradesh, India")

dob = st.date_input("Date of Birth")
tob = st.time_input("Time of Birth")

utc_off = st.text_input("UTC offset override (e.g., 5.5)", "5.5")

# --- IMPORTANT ---
# Replace this function with your real Swiss Ephemeris / API code.
def compute_demo_sidereal_positions_and_lagna():
    # sidelons: sidereal longitudes in degrees 0..360
    # lagna_sign: 1..12 for D1 (Rāśi) Ascendant
    # nav_lagna_sign: 1..12 for D9 (Navāṁśa) Ascendant
    sidelons = {
        "Su":  20.0,  # Aries
        "Mo":  85.0,  # Gemini
        "Ma": 140.0,  # Leo
        "Me": 182.0,  # Libra
        "Ju": 240.0,  # Sagittarius
        "Ve":  62.0,  # Gemini
        "Sa": 305.0,  # Aquarius
        "Ra":  15.0,  # Aries (mean)
        "Ke": 195.0,  # Libra (opposite)
    }
    lagna_sign = 2   # Taurus
    nav_lagna_sign = 4  # Cancer
    return sidelons, lagna_sign, nav_lagna_sign

st.write("Fill the details and click Generate.")

if st.button("Generate DOCX"):
    # TODO: swap this line with your real computation
    sidelons, lagna_sign, nav_lagna_sign = compute_demo_sidereal_positions_and_lagna()

    # Build the docx in-memory
    doc = Document()
    # You likely already add personal details + tables here...
    doc.add_heading(f"{name} — Horoscope", level=1)
    p = doc.add_paragraph()
    p.add_run(f"Place: {pob}\n").bold = True

    # render both kundalis (Lag/ Nav) with markers
    render_kundalis_into_doc(
        doc,
        sidelons=sidelons,
        lagna_sign=lagna_sign,
        nav_lagna_sign=nav_lagna_sign,
        size_pt=230,   # tweak if you want larger/smaller charts
    )

    # Return file as a download without touching disk
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    st.download_button(
        "Download DOCX",
        data=buf,
        file_name=f"{name.replace(' ', '_')}_Horoscope.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
