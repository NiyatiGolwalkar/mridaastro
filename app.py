import os
import base64
from io import BytesIO
import streamlit as st

st.set_page_config(page_title="MRIDAASTRO", layout="wide", page_icon="🔮")

# ------------------ Background (base64) ------------------
def _apply_bg():
    img_path = os.path.join("assets", "ganesha_bg.png")
    if os.path.exists(img_path):
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url("data:image/png;base64,{b64}");
                background-size: cover;
                background-attachment: fixed;
                background-position: center;
            }}
            </style>
            """, unsafe_allow_html=True
        )

_apply_bg()

# ------------------ Branding ------------------
st.markdown(
    """
    <div style="text-align:center; margin-bottom:24px;">
        <h1 style="margin-bottom:0; letter-spacing:1px;">MRIDAASTRO</h1>
        <p style="font-size:18px; font-style:italic; margin-top:6px;">
            In the light of divine, let your soul journey shine
        </p>
        <hr style="border: 2px solid gold; width:320px; margin:auto;" />
    </div>
    """, unsafe_allow_html=True
)

# ------------------ Inputs ------------------
col1, col2 = st.columns(2)
with col1:
    name = st.text_input("Name")
with col2:
    dob = st.date_input("Date of Birth")

col3, col4 = st.columns(2)
with col3:
    tob = st.time_input("Time of Birth")
with col4:
    place = st.text_input("Place of Birth (City, State, Country)")

tz_override = st.text_input("UTC offset override (optional, e.g., 5.5)")

# ------------------ Helpers ------------------
def _to_docx_bytes(doc_or_bytes_or_path):
    try:
        from docx import Document as _Doc
    except Exception:
        _Doc = None

    if isinstance(doc_or_bytes_or_path, (bytes, bytearray)):
        return bytes(doc_or_bytes_or_path)

    if isinstance(doc_or_bytes_or_path, str) and doc_or_bytes_or_path.lower().endswith(".docx"):
        try:
            with open(doc_or_bytes_or_path, "rb") as f:
                return f.read()
        except Exception:
            return None

    if _Doc is not None and isinstance(doc_or_bytes_or_path, _Doc):
        bio = BytesIO()
        doc_or_bytes_or_path.save(bio)
        return bio.getvalue()

    return None

def _build_fallback_doc(name, dob, tob, place, tz_override):
    """Always produces a valid .docx using python-docx."""
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    doc.add_heading("MRIDAASTRO", level=1)
    p = doc.add_paragraph("In the light of divine, let your soul journey shine")
    p.runs[0].italic = True
    doc.add_paragraph("This placeholder DOCX is generated because the kundali generator wasn't found or failed.")
    doc.add_paragraph(f"Name: {name or ''}")
    doc.add_paragraph(f"Date of Birth: {dob}")
    doc.add_paragraph(f"Time of Birth: {tob}")
    doc.add_paragraph(f"Place of Birth: {place or ''}")
    if tz_override:
        doc.add_paragraph(f"UTC override: {tz_override}")
    return doc

def _try_call(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return None

def _build_kundali_docx_entry(name, dob, tob, place, tz_override):
    # Try a set of likely generator names; if any exist and succeed, use it.
    for fn_name in ("generate_kundali_docx_full", "generate_kundali_docx", "create_docx", "main_build_doc"):
        fn = globals().get(fn_name)
        if callable(fn):
            built = _try_call(fn, name, dob, tob, place, tz_override)
            if built is not None:
                return built
    # Fallback if none worked
    return _build_fallback_doc(name, dob, tob, place, tz_override)

# ------------------ Generate -> Download-only ------------------
if st.button("Generate DOCX"):
    built = _build_kundali_docx_entry(name, dob, tob, place, tz_override)
    doc_bytes = _to_docx_bytes(built)
    if doc_bytes:
        safe = (name or "Kundali").strip().replace(" ", "_")
        st.download_button(
            "Download Kundali (DOCX)",
            data=doc_bytes,
            file_name=f"{safe}_kundali.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    else:
        st.error("Couldn't generate the DOCX. Please check the generator function.")
