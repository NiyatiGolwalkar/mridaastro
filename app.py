
import importlib
from datetime import time, date
from io import BytesIO

import streamlit as st

try:
    # Optional: python-docx is commonly available in the user's app already
    from docx import Document
    from docx.shared import Pt
    HAVE_DOCX = True
except Exception:
    HAVE_DOCX = False

# ---------------- Page / layout ----------------
st.set_page_config(page_title="MRIDAASTRO", page_icon="🕉️", layout="wide")

BG_IMAGE_URL = "https://raw.githubusercontent.com/NiyatiGolwalkar/kundali-streamlit/main/assets/ganesha_bg.png"

# Layout knobs
SAFE_TOP     = "10px"         # keep small top padding
MAX_WIDTH    = "980px"        # overall content width
INPUT_FONT   = "1rem"         # input font size
LABEL_FONT   = "1.1rem"       # label font size
INPUT_PAD_V  = "8px"          # input vertical padding
INPUT_PAD_H  = "12px"         # input horizontal padding

# ---------------- CSS ----------------
st.markdown(f'''
<style>
/* Make everything translucent so bg shows through */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
[data-testid="stToolbar"], .main, .block-container {{ background: transparent !important; }}

/* Fixed background */
body::before, .stApp::before {{
  content: ""; position: fixed; inset: 0; z-index: -1;
  background-image: url("{BG_IMAGE_URL}");
  background-repeat: no-repeat; background-position: top center;
  background-size: cover; background-attachment: fixed;
  pointer-events: none;
}}

/* Avoid page scroll; keep content compact and centered */
html, body {{ height: 100%; overflow: hidden; }}
.stApp {{ height: 100vh; overflow: hidden; }}
[data-testid="stAppViewContainer"] {{ overflow: hidden; }}

.block-container {{
  margin-top: {SAFE_TOP} !important;
  height: calc(100vh - {SAFE_TOP});
  overflow: hidden;
  display: flex; flex-direction: column;
  gap: .6rem;
  padding: .5rem 1rem 0 1rem !important;
  max-width: {MAX_WIDTH};
  margin-left: auto !important; margin-right: auto !important;
}}

/* Fonts for brand */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Crimson+Text:ital,wght@1,700&display=swap');
.app-brand {{ text-align:center; line-height: 1.05; }}
.app-brand h1 {{
  font-family: "Playfair Display", serif;
  font-weight: 800; font-size: 2.4rem; margin: .1rem 0 .1rem 0;
  letter-spacing:.4px; text-transform: uppercase;
}}
.app-brand h2 {{
  font-family: "Crimson Text", serif;
  font-weight: 700; font-style: italic; font-size: 1.06rem;
  margin: 0 0 .45rem 0;     /* tighter gap below title */
}}

/* Labels: bold + larger */
:root {{ --label-font: {LABEL_FONT}; }}
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"],
label {{ font-weight: 800 !important; margin-bottom: .28rem !important;
         font-size: var(--label-font) !important; }}

/* Inputs with solid white so values are always readable */
.stTextInput input,
.stDateInput input,
.stTimeInput input {{
  padding: {INPUT_PAD_V} {INPUT_PAD_H} !important;
  font-size: {INPUT_FONT} !important;
  color: #111 !important; background-color: rgba(255,255,255,0.95) !important;
  border: 1px solid rgba(0,0,0,.10) !important; border-radius: 10px !important;
}}
/* Placeholder color */
.stTextInput input::placeholder, .stDateInput input::placeholder, .stTimeInput input::placeholder {{ color:#666 !important; }}

/* Select (BaseWeb) */
[data-baseweb="select"] > div {{
  min-height: calc(2*{INPUT_PAD_V} + 1.2rem) !important;
  padding-top:{INPUT_PAD_V} !important; padding-bottom:{INPUT_PAD_V} !important;
  font-size: {INPUT_FONT} !important; color:#111 !important;
  background-color: rgba(255,255,255,0.95) !important;
  border: 1px solid rgba(0,0,0,.10) !important; border-radius: 10px !important;
}}
[data-baseweb="select"] span {{ font-size: {INPUT_FONT} !important; }}

/* Reduce vertical gaps */
.stTextInput, .stDateInput, .stTimeInput, .stSelectbox {{ margin-bottom: .5rem !important; }}

/* Center the submit button row */
.center-btn-row {{ display:flex; justify-content:center; }}
</style>
''', unsafe_allow_html=True)

# ---------------- Brand ----------------
st.markdown('''
<div class="app-brand">
  <h1>MRIDAASTRO</h1>
  <h2><em>In the light of the divine, let your soul journey shine.</em></h2>
</div>
''', unsafe_allow_html=True)

# ---------------- Form ----------------
with st.form("kundali-form", clear_on_submit=False):
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Name", "")
    with c2:
        # Bring back the calendar date picker
        dob = st.date_input("Date of Birth", value=date(2025, 9, 3), format="YYYY-MM-DD")

    c3, c4 = st.columns(2)
    with c3:
        tob = st.time_input("Time of Birth", value=time(10, 30), step=60)  # visible and precise to minutes
    with c4:
        pob = st.text_input("Place of Birth (City, State, Country)", "")

    # UTC — half width (left column only)
    u1, _ = st.columns([1,1])
    with u1:
        utc = st.text_input("UTC offset override (optional, e.g., 5.5)", "")

    submitted = st.form_submit_button("Generate DOCX")

def _fallback_docx(name, dob, tob, pob, utc):
    \"\"\"Very small, safe DOCX fallback so the button always works.
    Real kundali generation will be used if we can find user's generator.
    \"\"\"
    if not HAVE_DOCX:
        return None
    doc = Document()
    p = doc.add_paragraph()
    run = p.add_run("MRIDAASTRO")
    run.bold = True
    run.font.size = Pt(20)

    doc.add_paragraph("In the light of the divine, let your soul journey shine.").italic = True
    doc.add_paragraph("")
    doc.add_paragraph(f"Name: {name}")
    doc.add_paragraph(f"Date of Birth: {dob}")
    doc.add_paragraph(f"Time of Birth: {tob}")
    doc.add_paragraph(f"Place of Birth: {pob}")
    if utc:
        doc.add_paragraph(f"UTC offset override: {utc}")

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

def _try_call_user_generator(name, dob, tob, pob, utc):
    \"\"\"Try several likely module/function names from the user's earlier app.
    Return BytesIO or None.
    \"\"\"
    candidates = [
        # (module, function)
        ("app_kundali_rect_exact_fix_v6",    "generate_docx"),
        ("app_kundali_rect_exact_fix_v6",    "build_kundali_docx"),
        ("app_kundali_rect_exact_fix_v6",    "create_kundali_docx"),
        ("app",                               "generate_docx"),
        ("kundali_markers_lib",               "generate_docx"),
    ]
    for mod_name, fn_name in candidates:
        try:
            mod = importlib.import_module(mod_name)
            fn  = getattr(mod, fn_name, None)
            if callable(fn):
                out = fn(name=name, dob=dob, tob=tob, pob=pob, utc_override=utc)  # common signature guess
                if isinstance(out, BytesIO):
                    return out
        except Exception:
            continue
    return None

# ---------------- Generate / Download ----------------
if submitted:
    # First, try to call user's real generator (if present).
    buf = _try_call_user_generator(name, dob, tob, pob, utc)

    # Fallback simple DOCX so the button is never a no-op
    if buf is None:
        buf = _fallback_docx(name, dob, tob, pob, utc)

    if buf is None:
        st.error("Generate failed: couldn't find your kundali generator and 'python-docx' is not available.")
    else:
        st.success("Kundali ready ✓")
        st.download_button("Download DOCX", buf, file_name="kundali.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
