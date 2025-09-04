
# app_with_favicon_blackline_validations_fix.py
# -------------------------------------------------
# MRIDAASTRO — header underline black; validations; robust favicon loading
# -------------------------------------------------

import os
import io
import datetime as dt
from PIL import Image

import streamlit as st

APP_TITLE = "MRIDAASTRO"

def _load_favicon():
    """
    Try several common paths/filenames for the Shiva favicon.
    Falls back to an Om emoji if not found.
    Returns an image object or a string (emoji).
    """
    candidates = [
        "assets/shiva_fevicon.png",
        "assets/Shiva Fevicon.png",
        "assets/shiva_favicon.png",
        "assets/ShivaFavicon.png",
        "shiva_fevicon.png",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return Image.open(p)
            except Exception:
                pass
    # last resort
    return "🕉️"

# Set page config FIRST (no Streamlit calls before this)
st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    page_icon=_load_favicon(),
)

# --- simple style: underline to black (length kept as-is) ---
st.markdown(
    """
    <style>
      .header-wrap {text-align:center; margin-top: 10px; margin-bottom: 18px;}
      .header-title {font-size: 46px; font-weight: 800; letter-spacing: 1px;}
      .header-tagline {font-size: 22px; font-style: italic; color: rgba(0,0,0,0.75);}
      .header-underline{width: 200px; height: 4px; background:#000; border-radius:3px;
                        margin: 8px auto 0 auto;}
      /* make field labels larger & bold */
      .stForm label, .stMarkdown h5 {font-weight: 800 !important; font-size: 1.05rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Header ---
st.markdown('<div class="header-wrap">', unsafe_allow_html=True)
st.markdown(f'<div class="header-title">{APP_TITLE}</div>', unsafe_allow_html=True)
st.markdown('<div class="header-tagline">In the light of divine, let your soul journey shine</div>', unsafe_allow_html=True)
st.markdown('<div class="header-underline"></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# --- Helpers ---
def _is_blank(x) -> bool:
    if x is None:
        return True
    if isinstance(x, str):
        return x.strip() == ""
    return False

def _parse_utc_offset(raw):
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip() == "":
        return None
    try:
        val = float(raw)
    except Exception:
        st.error("UTC offset must be a number like 5.5 or -4.")
        st.stop()
    if not (-14.0 <= val <= 14.0):
        st.error("UTC offset must be between -14 and +14 hours.")
        st.stop()
    return val

# --- Layout ---
col1, col2 = st.columns(2)

with col1:
    st.markdown("**Name**")
    name = st.text_input("", key="name_input", placeholder="Enter full name")

with col2:
    st.markdown("**Date of Birth**")
    dob = st.date_input("", key="dob_input")

with col1:
    st.markdown("**Time of Birth**")
    # Use time_input; defaults to None by setting a placeholder
    tob = st.time_input("", key="tob_input")

with col2:
    st.markdown("**Place of Birth (City, State, Country)**")
    pob = st.text_input("", key="pob_input", placeholder="City, State, Country")

with col1:
    st.markdown("**UTC offset override (optional, e.g., 5.5)**")
    utc_offset_raw = st.text_input("", key="utc_input", placeholder="e.g., 5.5 or -4")
    utc_offset = _parse_utc_offset(utc_offset_raw)

with col2:
    generate = st.button("Generate Kundali", use_container_width=False)

# --- Validations on click ---
if generate:
    # Name checks
    if _is_blank(name):
        st.error("Please enter your name.")
        st.stop()
    # simple alphabetic validation with spaces and dots
    import re
    if not re.fullmatch(r"[A-Za-z .'-]+", name.strip()):
        st.error("Name can include only letters, spaces, dots, hyphens and apostrophes.")
        st.stop()

    # DOB required
    if dob is None:
        st.error("Please select your date of birth.")
        st.stop()

    # Time required (for time_input, a dt.time is returned; treat None if not set)
    if tob is None or (isinstance(tob, str) and tob.strip() == ""):
        st.error("Please select your time of birth.")
        st.stop()
    if isinstance(tob, str):
        # try to parse HH:MM
        try:
            hh, mm = [int(p.strip()) for p in tob.split(":")[:2]]
            tob = dt.time(hour=hh, minute=mm)
        except Exception:
            st.error("Time of Birth must be in HH:MM format.")
            st.stop()

    # Place required
    if _is_blank(pob):
        st.error("Please enter the Place of Birth (City, State, Country).")
        st.stop()

    # All good -> continue with your existing generate routine
    st.success("Inputs look good. Proceeding to generate the Kundali document…")

    # >>>> CALL YOUR EXISTING GENERATION FUNCTION HERE <<<<
    # For example:
    # file_bytes = build_kundali_docx(name, dob, tob, pob, utc_offset)
    # st.download_button("Download Kundali (DOCX)", data=file_bytes, file_name="kundali.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

