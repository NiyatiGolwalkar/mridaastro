import os
import base64
from io import BytesIO
import streamlit as st

# ------------------ Page config ------------------
st.set_page_config(page_title="MRIDAASTRO", layout="wide", page_icon="🔮")

# ------------------ Background (base64, cloud-safe) ------------------
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
    """Return raw .docx bytes from a python-docx Document, bytes, or a file path."""
    try:
        from docx import Document as _Doc
    except Exception:
        _Doc = None

    # already bytes
    if isinstance(doc_or_bytes_or_path, (bytes, bytearray)):
        return bytes(doc_or_bytes_or_path)

    # file path string
    if isinstance(doc_or_bytes_or_path, str) and doc_or_bytes_or_path.lower().endswith(".docx"):
        try:
            with open(doc_or_bytes_or_path, "rb") as f:
                return f.read()
        except Exception:
            return None

    # python-docx Document
    if _Doc is not None and isinstance(doc_or_bytes_or_path, _Doc):
        bio = BytesIO()
        doc_or_bytes_or_path.save(bio)
        return bio.getvalue()

    return None

def _build_kundali_docx_entry(name, dob, tob, place, tz_override):
    """Call a user-provided generator if present; else return a valid, minimal docx."""
    # Try to call an existing generator you may already have in your codebase
    for fn_name in ("generate_kundali_docx_full", "generate_kundali_docx", "create_docx", "main_build_doc"):
        fn = globals().get(fn_name)
        if callable(fn):
            return fn(name, dob, tob, place, tz_override)

    # Fallback: build a *valid* docx using python-docx so the download never errors
    try:
        from docx import Document
        doc = Document()
        title = name or "Kundali"
        doc.add_heading(f"{title}", level=1)
        doc.add_paragraph("This is a placeholder document. Replace this fallback with your kundali generator output.")
        return doc
    except Exception:
        return None

# ------------------ Generate -> Download-only ------------------
if st.button("Generate DOCX"):
    try:
        built = _build_kundali_docx_entry(name, dob, tob, place, tz_override)
        doc_bytes = _to_docx_bytes(built) if built is not None else None
    except Exception:
        doc_bytes = None

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
