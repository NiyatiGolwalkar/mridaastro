import streamlit as st
from io import BytesIO

# ------------------ Branding ------------------
st.markdown(
    """
    <div style="text-align:center; margin-bottom:20px;">
        <h1 style="margin-bottom:0;">MRIDAASTRO</h1>
        <p style="font-size:18px; font-style:italic; margin-top:0;">
            In the light of divine, let your soul journey shine
        </p>
        <hr style="border: 1px solid gold; width:50%; margin:auto;" />
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

def build_kundali_docx(name, dob, tob, place, tz_override):
    # pick your actual generator function here if defined elsewhere
    for fn_name in ("generate_kundali_docx_full", "generate_kundali_docx", "create_docx"):
        fn = globals().get(fn_name)
        if callable(fn):
            return fn(name, dob, tob, place, tz_override)
    return None

# ------------------ Action ------------------
if st.button("Generate DOCX"):
    try:
        built = build_kundali_docx(name, dob, tob, place, tz_override)
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
