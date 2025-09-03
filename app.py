
import streamlit as st
from datetime import time, date

st.set_page_config(page_title="MRIDAASTRO", page_icon="🕉️", layout="wide")

# ======= Slim inputs, centered button, italic tagline, no page scroll =======
BG_IMAGE_URL = "https://raw.githubusercontent.com/NiyatiGolwalkar/kundali-streamlit/main/assets/ganesha_bg.png"

# Layout knobs
SAFE_TOP     = "0px"          # keep 0 to avoid page scroll
MAX_WIDTH    = "940px"        # total content width (~about half screen on large displays)
INPUT_FONT   = "0.95rem"      # input font size
LABEL_FONT   = "1.08rem"      # field label font size (bolder + larger)
INPUT_PAD_V  = "6px"          # input vertical padding (height)
INPUT_PAD_H  = "10px"         # input horizontal padding

st.markdown(f"""
<style>
/* Transparent surfaces so background is visible */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
[data-testid="stToolbar"], .main, .block-container {{ background: transparent !important; }}

/* Fixed background image */
body::before, .stApp::before {{
  content: ""; position: fixed; inset: 0; z-index: -1;
  background-image: url('{BG_IMAGE_URL}');
  background-repeat: no-repeat; background-position: top center;
  background-size: cover; background-attachment: fixed;
  pointer-events: none;
}}

/* No page scroll */
html, body {{ height: 100%; overflow: hidden; }}
.stApp {{ height: 100vh; overflow: hidden; }}
[data-testid="stAppViewContainer"] {{ overflow: hidden; }}

/* Content container: fixed top + centered with max width (reduces textbox width) */
:root {{
  --safe-top: {SAFE_TOP};
  --label-font: {LABEL_FONT};
}}
.block-container {{
  margin-top: var(--safe-top) !important;
  height: calc(100vh - var(--safe-top));
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: .65rem;
  padding: .5rem 1rem .5rem 1rem !important;

  max-width: {MAX_WIDTH};                     /* << controls overall width */
  margin-left: auto !important;
  margin-right: auto !important;
}}

/* Brand (title + italic tagline directly below) */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Crimson+Text:ital,wght@1,700&display=swap');
.app-brand {{ text-align:center; line-height: 1.1; }}
.app-brand h1 {{
  font-family: "Playfair Display", serif;
  font-weight: 800; font-size: 2.2rem; margin: .15rem 0 .05rem 0; letter-spacing:.4px;
  text-transform: uppercase;
}}
.app-brand h2 {{
  font-family: "Crimson Text", serif;
  font-weight: 700; font-style: italic; font-size: 1.05rem; margin: 0 0 .35rem 0;
}}

/* Bold labels & bigger size */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"],
label {{ font-weight: 700 !important; margin-bottom: .25rem !important; font-size: var(--label-font) !important; }}

/* Make inputs readable on bg (value not visible issue) */
.stTextInput input,
.stDateInput input,
.stTimeInput input {{
  padding-top: {INPUT_PAD_V} !important;
  padding-bottom: {INPUT_PAD_V} !important;
  padding-left: {INPUT_PAD_H} !important;
  padding-right: {INPUT_PAD_H} !important;
  font-size: {INPUT_FONT} !important;
  color: #111 !important;
  background-color: rgba(255,255,255,0.95) !important;
  border: 1px solid rgba(0,0,0,.08) !important;
  border-radius: 10px !important;
}}
/* Placeholder color */
.stTextInput input::placeholder,
.stDateInput input::placeholder,
.stTimeInput input::placeholder {{ color: #666 !important; }}

/* Select box control (BaseWeb) */
[data-baseweb="select"] > div {{
  min-height: calc(2*{INPUT_PAD_V} + 1.2rem) !important;
  padding-top: {INPUT_PAD_V} !important;
  padding-bottom: {INPUT_PAD_V} !important;
  font-size: {INPUT_FONT} !important;
  color: #111 !important;
  background-color: rgba(255,255,255,0.95) !important;
  border: 1px solid rgba(0,0,0,.08) !important;
  border-radius: 10px !important;
}}
[data-baseweb="select"] span {{ font-size: {INPUT_FONT} !important; }}

/* Inputs spacing */
.stTextInput, .stDateInput, .stTimeInput, .stSelectbox {{ margin-bottom: .55rem !important; }}
</style>
""", unsafe_allow_html=True)

# ---- Brand ----
st.markdown("""
<div class="app-brand">
  <h1>MRIDAASTRO</h1>
  <h2><em>In the light of the divine, let your soul journey shine.</em></h2>
</div>
""", unsafe_allow_html=True)

# ---- Form (two columns) ----
c1, c2 = st.columns(2)
with c1:
    name = st.text_input("Name", "")
with c2:
    dob = st.text_input("Date of Birth", date.today().isoformat())

c3, c4 = st.columns(2)
with c3:
    tob = st.time_input("Time of Birth", value=time(10, 30), step=60)
with c4:
    pob = st.text_input("Place of Birth (City, State, Country)", "")

# UTC — half width (left column only)
u1, u2 = st.columns(2)
with u1:
    utc = st.text_input("UTC offset override (optional, e.g., 5.5)", "")

# ---- Centered Generate button ----
left, mid, right = st.columns([1,1,1])
with mid:
    st.button("Generate DOCX", use_container_width=True)
