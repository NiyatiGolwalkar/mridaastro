
import streamlit as st
import datetime
from io import BytesIO

APP_TITLE = "MRIDAASTRO"
APP_TAGLINE = "In the light of divine, let your soul journey shine"

st.set_page_config(page_title=APP_TITLE, layout="wide")

# ------------- Brand Header -------------
st.markdown(
    f"""
    <div style="text-align:center; margin-top:8px;">
      <div style="font-size:58px; font-weight:800; letter-spacing:2px; color:#1c2430;">
        {APP_TITLE}
      </div>
      <div style="margin-top:-8px;">
        <span style="
          display:inline-block;
          font-style:italic;
          font-size:26px;
          color:#223;
          padding-bottom:4px;
          border-bottom:3px solid #D4AF37;
        ">
          {APP_TAGLINE}
        </span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------- Inputs (two per row, stacked labels) -------------
row1c1, row1c2 = st.columns(2)
with row1c1:
    st.markdown("<div style='font-weight:700; font-size:18px;'>Name</div>", unsafe_allow_html=True)
    name = st.text_input("", key="name_input", label_visibility="collapsed")

with row1c2:
    st.markdown("<div style='font-weight:700; font-size:18px;'>Date of Birth</div>", unsafe_allow_html=True)
    dob = st.date_input("", key="dob_input", label_visibility="collapsed")

row2c1, row2c2 = st.columns(2)
with row2c1:
    st.markdown("<div style='font-weight:700; font-size:18px;'>Time of Birth</div>", unsafe_allow_html=True)
    tob = st.time_input("", key="tob_input", label_visibility="collapsed", step=datetime.timedelta(minutes=1))

with row2c2:
    st.markdown("<div style='font-weight:700; font-size:18px;'>Place of Birth (City, State, Country)</div>", unsafe_allow_html=True)
    place = st.text_input("", key="place_input", label_visibility="collapsed")

row3c1, row3c2 = st.columns(2)
with row3c1:
    st.markdown("<div style='font-weight:700; font-size:18px;'>UTC offset override (optional, e.g., 5.5)</div>", unsafe_allow_html=True)
    tz_override = st.text_input("", key="tz_input", label_visibility="collapsed", value="")

with row3c2:
    # small spacer to align button baseline with the textbox
    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
    generate_clicked = st.button("Generate Kundali", key="generate_btn")

# ------------- Helper to validate inputs -------------
def _safe_text(x):
    try:
        return (x or "").strip()
    except Exception:
        return ""

def _validate_inputs(name_v, place_v):
    if not name_v:
        st.error("Please enter a Name.")
        return False
    if not place_v:
        st.error("Please enter a Place of Birth.")
        return False
    return True

# ------------- GENERATION SECTION (plug your generator here) -------------
# Expect a function that returns bytes of a .docx file (application/vnd.openxmlformats-officedocument.wordprocessingml.document)
# Common function names you might already have in your working code:
#   - generate_kundali_docx_full(...)
#   - generate_kundali_docx(...)
#   - create_docx(...)
#   - build_kundali_docx(...)
# If one of these exists, we'll call it automatically.
def _call_user_generator(name_v, dob, tob, place_v, tz_override_v):
    # Try to import or use any of the common functions if they exist in this namespace.
    for fn_name in [
        "generate_kundali_docx_full",
        "generate_kundali_docx",
        "create_docx",
        "build_kundali_docx",
        "main_build_doc",
    ]:
        fn = globals().get(fn_name)
        if callable(fn):
            return fn(name_v, dob, tob, place_v, tz_override_v)
    raise RuntimeError("No kundali generator function found. Please paste your working generator functions into this file under the GENERATION SECTION.")

# ------------- Click handler -------------
if generate_clicked:
    name_v = _safe_text(name)
    place_v = _safe_text(place)
    tz_v = _safe_text(tz_override)
    if _validate_inputs(name_v, place_v):
        try:
            doc_bytes = _call_user_generator(name_v, dob, tob, place_v, tz_v)
            if isinstance(doc_bytes, bytes):
                st.download_button(
                    "Download Kundali (DOCX)",
                    data=doc_bytes,
                    file_name="kundali.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            else:
                st.error("Generator did not return bytes. Please ensure your function returns the DOCX file bytes.")
        except Exception as e:
            st.error(f"Could not generate the document. {type(e).__name__}: {e}")
