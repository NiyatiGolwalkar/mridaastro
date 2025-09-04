# login_branding_helper.py
# Drop-in helper to show a branded Google OAuth login screen in Streamlit.
# Usage in app.py:
#   from login_branding_helper import show_login_screen
#   if "user" not in st.session_state:
#       show_login_screen(); st.stop()

import base64, time
from pathlib import Path
from urllib.parse import urlencode
import streamlit as st

def build_auth_url(state: str) -> str:
    CLIENT_ID     = st.secrets['google_oauth']['client_id']
    REDIRECT_URI  = st.secrets['google_oauth']['redirect_uri']
    AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
    SCOPES = "openid email profile"
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "online",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"

def show_login_screen():
    st.session_state["oauth_state"] = str(time.time())
    login_url = build_auth_url(st.session_state["oauth_state"])

    # Background image
    bg_path = Path("assets/login_bg.png")
    bg_data_url = ""
    if bg_path.exists():
        b64 = base64.b64encode(bg_path.read_bytes()).decode("utf-8")
        bg_data_url = f"data:image/png;base64,{b64}"

    st.markdown(f"""
<link href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&display=swap" rel="stylesheet">
<style>
  [data-testid="stAppViewContainer"] {{
    {"background-image: url('" + bg_data_url + "');" if bg_data_url else "background: #0b0b0b;"}
    background-size: cover; background-position: center; background-repeat: no-repeat;
  }}
  [data-testid="stHeader"] {{ background: transparent; }}
  .login-card {{ max-width:560px; margin:12vh auto; padding:32px; border-radius:16px;
                 background:rgba(255,255,255,0.85); box-shadow:0 12px 30px rgba(0,0,0,0.3);
                 text-align:center; backdrop-filter:blur(4px); }}
  .brand {{ font-family:'Cinzel Decorative', cursive; font-size:58px; font-weight:700;
            color:#000; margin-bottom:8px; text-shadow:2px 2px 4px rgba(0,0,0,0.2); }}
  .tagline {{ font-family:Georgia, serif; font-style:italic; font-size:24px; color:#000; margin-bottom:18px; }}
  .divider {{ height:3px; width:180px; margin:0 auto 20px auto; background:#000; border-radius:2px; }}
  .login-btn {{ display:inline-block; padding:14px 28px; border-radius:10px; font-weight:700; font-size:20px;
                border:none; background:#FFD700; color:black !important; transition:all .2s ease-in-out;
                box-shadow:0 4px 12px rgba(0,0,0,0.3); text-decoration:none !important; }}
  .login-btn:hover {{ background:#e6c200; transform:translateY(-2px); }}
  .fineprint {{ margin-top:12px; font-size:13px; color:#333; }}
</style>
<div class="login-card">
  <div class="brand">MRIDAASTRO</div>
  <div class="tagline">In the light of divine, let your soul journey shine</div>
  <div class="divider"></div>
  <a class="login-btn" href="{login_url}">Sign in with Google</a>
  <div class="fineprint">Access restricted to authorised users.</div>
</div>
""", unsafe_allow_html=True)
