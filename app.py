import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="MRIDAASTRO",
    page_icon="Shiva Fevicon.png",
    layout="wide"
)

st.markdown(
    """
    <style>
        .title-container {text-align: center; margin-top: -40px;}
        .title-container h1 {font-size: 3em; font-weight: 800;}
        .title-container h3 {font-size: 1.2em; font-style: italic; margin-top: -15px;}
        .black-line {border: none; height: 3px; background-color: black; width: 90%; margin: 10px auto;}
        label {font-weight: bold !important; font-size: 1.1em !important;}
    </style>
    """, unsafe_allow_html=True
)

st.markdown(
    """
    <div class="title-container">
        <h1>MRIDAASTRO</h1>
        <h3>In the light of divine, let your soul journey shine</h3>
        <hr class="black-line">
    </div>
    """, unsafe_allow_html=True
)

with st.form("kundali_form"):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Name")
        time_of_birth = st.time_input("Time of Birth", value=None)
    with col2:
        dob = st.date_input("Date of Birth")
        place = st.text_input("Place of Birth (City, State, Country)")
    col3, col4 = st.columns([2, 1])
    with col3:
        utc_offset = st.text_input("UTC offset override (optional, e.g., 5.5)")
    with col4:
        submit = st.form_submit_button("Generate Kundali")

if submit:
    errors = []
    if not name.strip():
        errors.append("⚠️ Name cannot be empty.")
    elif not name.replace(" ", "").replace(".", "").replace("'", "").replace("-", "").isalpha():
        errors.append("⚠️ Name must contain only letters, spaces, periods, apostrophes, or hyphens.")
    if not dob:
        errors.append("⚠️ Date of Birth cannot be empty.")
    if not time_of_birth:
        errors.append("⚠️ Time of Birth cannot be empty.")
    if not place.strip():
        errors.append("⚠️ Place of Birth cannot be empty.")
    if utc_offset.strip():
        try:
            val = float(utc_offset)
            if val < -14 or val > 14:
                errors.append("⚠️ UTC offset must be between -14 and +14.")
        except ValueError:
            errors.append("⚠️ UTC offset must be a valid number.")
    if errors:
        for e in errors:
            st.error(e)
    else:
        st.success("✅ All inputs look good! Kundali generation logic will run here.")
