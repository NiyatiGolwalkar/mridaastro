import streamlit as st
from datetime import time, date

st.set_page_config(page_title="MRIDAASTRO", page_icon="🕉️", layout="wide")

# ---- Styling & Brand (no-body-scroll version) ----
# You can swap to a different RAW URL if you want another background.
BG_IMAGE_URL = "https://raw.githubusercontent.com/NiyatiGolwalkar/kundali-streamlit/main/assets/ganesha_bg.png"

# Reserved area under Ganapati + shloka (adjust if needed)
SAFE_TOP = "clamp(420px, 52vw, 760px)"

st.markdown(f"""
<style>
/* Transparent app surface */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
[data-testid="stToolbar"], .main, .block-container {{ background: transparent !important; }}

/* Fixed, non-scrolling background */
body::before, .stApp::before {{
  content: ""; position: fixed; inset: 0; z-index: -1;
  background-image: url('{BG_IMAGE_URL}');
  background-repeat: no-repeat; background-position: top center;
  background-size: cover; background-attachment: fixed;
  pointer-events: none; opacity: 1;
}}

/* Prevent browser scroll bar */
html, body {{ height: 100%; overflow: hidden; }}
.stApp {{ height: 100vh; overflow: hidden; }}
[data-testid="stAppViewContainer"] {{ overflow: hidden; }}

/* Use an inner scroll area for content (keeps it below Ganapati).
   Scrollbar is hidden visually (wheel/trackpad still works). */
:root {{ --safe-top: {SAFE_TOP}; }}
.block-container {{
  margin-top: var(--safe-top) !important;
  height: calc(100vh - var(--safe-top));
  overflow: auto;
  padding-bottom: 0 !important;
  margin-bottom: 0 !important;
  -ms-overflow-style: none;       /* IE/Edge */
  scrollbar-width: none;          /* Firefox */
}}
.block-container::-webkit-scrollbar {{ display: none; }}   /* Chrome/Safari */

/* Center brand and make tagline bold */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Crimson+Text:wght@700&display=swap');
.app-brand {{ text-align:center; }}
.app-brand h1 {{
  font-family: "Playfair Display", serif; font-weight: 800; font-size: 2.6rem;
  margin: 0 0 .35rem 0; letter-spacing:.5px; text-transform: uppercase;
}}
.app-brand h2 {{
  font-family: "Crimson Text", serif; font-weight: 700; font-style: normal;
  font-size: 1.35rem; margin:.25rem 0 1.25rem 0;
}}

/* Bold labels for all inputs */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"],
label,
.stSelectbox label, .stTextInput label, .stDateInput label, .stTimeInput label {{ font-weight: 700 !important; }}

</style>
""", unsafe_allow_html=True)

# ---- Brand ----
st.markdown("""
<div class="app-brand">
  <h1>MRIDAASTRO</h1>
  <h2>In the light of the divine, let your soul journey shine.</h2>
</div>
""", unsafe_allow_html=True)

# ---- Minimal demo form (replace with your full logic if needed) ----
left, right = st.columns(2)
with left:
    name = st.text_input("Name", "")
with right:
    dob = st.text_input("Date of Birth", date.today().isoformat())

left2, right2 = st.columns(2)
with left2:
    tob = st.time_input("Time of Birth", value=time(10, 30), step=60)
with right2:
    pob = st.text_input("Place of Birth (City, State, Country)", "")

st.text_input("UTC offset override (optional, e.g., 5.5)", "")

st.button("Generate DOCX")
