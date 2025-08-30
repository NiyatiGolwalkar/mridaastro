# app.py
import io
import streamlit as st

st.set_page_config(page_title="DevoAstroBhav Kundali", layout="centered")
st.title("DevoAstroBhav Kundali (Editable DOCX)")

# Try importing the kundali library and show a helpful error instead of a blank page.
try:
    from kundali_markers_lib import render_kundalis_into_doc
    ok_lib = True
except Exception as e:
    ok_lib = False
    st.error("Failed to import kundali_markers_lib. See details below:")
    st.exception(e)

# Simple inputs (wire these into your existing logic later)
name = st.text_input("Name", "Demo User")
pob  = st.text_input("Place of Birth (City, State, Country)", "Jabalpur, Madhya Pradesh, India")

col1, col2 = st.columns(2)
dob = col1.date_input("Date of Birth")
tob = col2.time_input("Time of Birth")
utc_off = st.text_input("UTC offset override (e.g., 5.5)", "5.5")

st.divider()

def compute_demo_sidereal_positions_and_lagna():
    # Dummy values—replace with your Swiss-Ephemeris results
    sidelons = {
        "Su":  20.0,  # Aries
        "Mo":  85.0,  # Gemini
        "Ma": 140.0,  # Leo
        "Me": 182.0,  # Libra
        "Ju": 240.0,  # Sagittarius
        "Ve":  62.0,  # Gemini
        "Sa": 305.0,  # Aquarius
        "Ra":  15.0,
        "Ke": 195.0,
    }
    lagna_sign = 2        # Taurus
    nav_lagna_sign = 4    # Cancer
    return sidelons, lagna_sign, nav_lagna_sign

if st.button("Generate DOCX"):
    if not ok_lib:
        st.stop()

    try:
        from docx import Document
    except Exception as e:
        st.error("python-docx is not installed or failed to import. Add it to requirements.txt.")
        st.exception(e)
        st.stop()

    try:
        sidelons, lagna_sign, nav_lagna_sign = compute_demo_sidereal_positions_and_lagna()

        doc = Document()
        doc.add_heading(f"{name} — Horoscope", level=1)
        p = doc.add_paragraph(); p.add_run(f"Place: {pob}\n")

        # Build both charts with markers/overlays
        render_kundalis_into_doc(
            doc,
            sidelons=sidelons,
            lagna_sign=lagna_sign,
            nav_lagna_sign=nav_lagna_sign,
            size_pt=230
        )

        # Offer as download (no filesystem writes)
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        st.success("DOCX generated.")
        st.download_button(
            "Download DOCX",
            data=buf,
            file_name=f"{name.replace(' ', '_')}_Horoscope.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as e:
        st.error("An error occurred while generating the document:")
        st.exception(e)
