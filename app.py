
import streamlit as st
from datetime import time, date

st.set_page_config(page_title="MRIDAASTRO", page_icon="🕉️", layout="wide")

# ======= HARD NO-PAGE-SCROLL, COMPACT HEADER VERSION =======
# Background (change URL if you switch images)
BG_IMAGE_URL = "https://raw.githubusercontent.com/NiyatiGolwalkar/kundali-streamlit/main/assets/ganesha_bg.png"

# We keep the top safe area *minimal* so everything fits without scrolling
SAFE_TOP = "0px"

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

/* Kill browser/page scrolling */
html, body {{ height: 100%; overflow: hidden; }}
.stApp {{ height: 100vh; overflow: hidden; }}
[data-testid="stAppViewContainer"] {{ overflow: hidden; }}

/* Single, compact viewport for all content */
:root {{ --safe-top: {SAFE_TOP}; }}
.block-container {{
  margin-top: var(--safe-top) !important;
  height: calc(100vh - var(--safe-top));
  overflow: hidden;                 /* no visible scrollbar */
  display: flex;
  flex-direction: column;
  gap: .75rem;
  padding: .5rem 1rem .5rem 1rem !important;
}}

/* Compact brand */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Crimson+Text:wght@700&display=swap');
.app-brand {{ text-align:center; line-height: 1.1; }}
.app-brand h1 {{
  font-family: "Playfair Display", serif;
  font-weight: 800; font-size: 2.1rem; margin: .2rem 0 .3rem 0; letter-spacing:.4px;
  text-transform: uppercase;
}}
.app-brand h2 {{
  font-family: "Crimson Text", serif;
  font-weight: 700; font-size: 1.05rem; margin: .1rem 0 .6rem 0;
}}

/* Bold field labels + tighten vertical rhythm */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"],
label {{ font-weight: 700 !important; margin-bottom: .25rem !important; }}

.css-1kyxreq, .css-1fcdlhz, .css-1jicfl2, .stTextInput, .stSelectbox, .stDateInput, .stTimeInput {{
  margin-bottom: .5rem !important;
}}

/* Make inputs a touch shorter */
input, textarea {{ padding-top: .5rem !important; padding-bottom: .5rem !important; }}

</style>
""", unsafe_allow_html=True)

# Brand
st.markdown("""
<div class="app-brand">
  <h1>MRIDAASTRO</h1>
  <h2>In the light of the divine, let your soul journey shine.</h2>
</div>
""", unsafe_allow_html=True)

# -------- Compact layout (fits in one screen) --------
row1_c1, row1_c2 = st.columns([1,1])
with row1_c1:
    name = st.text_input("Name", "")
with row1_c2:
    dob = st.text_input("Date of Birth", date.today().isoformat())

row2_c1, row2_c2 = st.columns([1,1])
with row2_c1:
    tob = st.time_input("Time of Birth", value=time(10, 30), step=60)
with row2_c2:
    pob = st.text_input("Place of Birth (City, State, Country)", "")

utc = st.text_input("UTC offset override (optional, e.g., 5.5)", "")

st.button("Generate DOCX")
