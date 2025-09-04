# app.py — MRIDAASTRO
# - Shiva favicon (assets/shiva_fevicon.png)
# - Centered brand header
# - Black underline beneath tagline
# - Background image (tries several common filenames)
# - Validations on all inputs
# - Minimal fallback DOCX builder (replace with your full generator when ready)

import datetime
from io import BytesIO
from pathlib import Path
import base64
import streamlit as st


# ------------------------------------------------------------
# Page config (uses your Shiva favicon)
# ------------------------------------------------------------
st.set_page_config(
    page_title="MRIDAASTRO",
    layout="wide",
    page_icon="assets/shiva_fevicon.png",
)


# ------------------------------------------------------------
# Background image helper
# ------------------------------------------------------------
def _apply_bg():
    try:
        candidates = [
            "assets/mrida_bg.png",
            "assets/bg.png",
            "assets/bg.jpg",
            "assets/background.png",
        ]
        img_path = next((Path(p) for p in candidates if Path(p).exists()), None)
        if not img_path:
            return
        b64 = base64.b64encode(img_path.read_bytes()).decode()
        st.markdown(
            f"""
            <style>
              [data-testid="stAppViewContainer"] {{
                background: url('data:image/png;base64,{b64}') no-repeat center top fixed;
                background-size: cover;
              }}
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass


_apply_bg()


# ------------------------------------------------------------
# Header (centered + black underline)
# ------------------------------------------------------------
st.markdown(
    """
    <div style='text-align:center; padding: 18px 0 6px 0;'>
      <div style='font-size:46px; font-weight:800; letter-spacing:1px; color:#2C3E50; text-shadow:1px 1px 2px #ccc;'>
        MRIDAASTRO
      </div>
      <div style='font-family:Georgia,serif; font-style:italic; font-size:20px; color:#34495E; margin:6px 0 12px;'>
        In the light of divine, let your soul journey shine
      </div>
      <div style='height:4px; width:200px; margin:0 auto; background:#000; border-radius:2px;'></div>
    </div>
    """,
    unsafe_allow_html=True
)
st.write("")


# ------------------------------------------------------------
# Validated inputs
# ------------------------------------------------------------
def _validated_inputs():
    errors = []

    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Name", key="name_input", placeholder="Enter full name")
    with c2:
        dob = st.date_input(
            "Date of Birth",
            key="dob_input",
            min_value=datetime.date(1800, 1, 1),
            max_value=datetime.date(2100, 12, 31),
        )

    c3, c4 = st.columns(2)
    with c3:
        tob = st.time_input(
            "Time of Birth",
            key="tob_input",
            step=datetime.timedelta(minutes=1),
        )
    with c4:
        place = st.text_input(
            "Place of Birth (City, State, Country)",
            key="place_input",
            placeholder="City, State, Country",
        )

    c5, c6 = st.columns([2, 1])
    with c5:
        tz_override = st.text_input(
            "UTC offset override (optional, e.g., 5.5)",
            key="tz_input",
            placeholder="e.g., 5.5 or -4",
        )
    with c6:
        generate_clicked = st.button("Generate Kundali")

    # ---------- validations ----------
    if not name or not name.strip():
        errors.append("Please enter your name.")
    elif len(name.strip()) < 2:
        errors.append("Name looks too short.")

    if not isinstance(tob, datetime.time):
        errors.append("Please choose a valid time of birth (HH:mm).")

    if not place or not place.strip():
        errors.append("Please enter a valid place (City, State, Country).")

    if tz_override.strip():
        try:
            float(tz_override)
        except ValueError:
            errors.append("UTC override must be a number, e.g., 5.5 or -4.")

    if errors:
        st.error("• " + "\n• ".join(errors))

    return (
        generate_clicked and not errors,
        errors,
        name.strip() if name else "",
        dob,
        tob,
        place.strip() if place else "",
        tz_override.strip(),
    )


can_generate, errors, name, dob, tob, place, tz_override = _validated_inputs()


# ------------------------------------------------------------
# Minimal fallback DOCX builder
# ------------------------------------------------------------
def _simple_docx(name, dob, tob, place, tz_override) -> bytes:
    try:
        from docx import Document
        from docx.shared import Pt
    except Exception as e:
        raise RuntimeError(
            "python-docx is required for the fallback document. "
            "Install with 'pip install python-docx' or plug in your real generator."
        ) from e

    doc = Document()
    doc.add_heading("MRIDAASTRO — Kundali", level=1)

    p = doc.add_paragraph()
    run = p.add_run(f"Name: {name}\n")
    run.font.size = Pt(12)
    p.add_run(f"Date of Birth: {dob.isoformat()}\n")
    p.add_run(f"Time of Birth: {tob.strftime('%H:%M')}\n")
    p.add_run(f"Place of Birth: {place}\n")
    if tz_override:
        p.add_run(f"UTC override: {tz_override}\n")

    p.add_run(
        "\nThis is a placeholder document so the app runs.\n"
        "Hook your full kundali generator where indicated in the code."
    )

    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio.read()


# ------------------------------------------------------------
# Generate & Download
# ------------------------------------------------------------
if can_generate:
    try:
        # Replace this with your full kundali generator call if available:
        # bytes_data = generate_kundali_docx_full(name, dob, tob, place, tz_override)
        bytes_data = _simple_docx(name, dob, tob, place, tz_override)

        file_name = f"Kundali_{name.replace(' ', '_')}.docx"
        st.download_button(
            label="Download Kundali (DOCX)",
            data=bytes_data,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as ex:
        st.error(f"Could not generate the document. {type(ex).__name__}: {ex}")
