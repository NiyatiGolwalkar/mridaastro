# login_branding_helper.py (hardened)
# Renders a branded login screen and builds Google OAuth URL.
# Handles missing secrets gracefully (shows a clear message instead of crashing).

import base64, os, time
from urllib.parse import urlencode
from pathlib import Path
import streamlit as st

def _read_google_oauth_from_secrets():
    """Return (client_id, redirect_uri); None if missing."""
    try:
        # Read secrets the same way as main.py
        _cfg = st.secrets.get("google_oauth", st.secrets)
        client_id = _cfg["client_id"]
        redirect_uri = _cfg["redirect_uri"]
        return client_id, redirect_uri
    except Exception:
        # Also try environment variables as fallback
        client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI")
        return client_id, redirect_uri

def build_auth_url(state: str) -> str:
    client_id, redirect_uri = _read_google_oauth_from_secrets()
    if not client_id or not redirect_uri:
        # Show an inline configuration error and stop building URL
        st.error(
            "Google OAuth is not configured. Please add `google_oauth.client_id` and "
            "`google_oauth.redirect_uri` in **Secrets** (or set env vars "
            "`GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_REDIRECT_URI`)."
        )
        st.info(
            "Example secrets:\n\n"
            "[google_oauth]\n"
            "client_id = \"YOUR_CLIENT_ID.apps.googleusercontent.com\"\n"
            "redirect_uri = \"https://mridaastro.streamlit.app/~/+/oauth2callback\""
        )
        return ""

    AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
    SCOPES = "openid email profile"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "online",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"

def show_login_screen():
    """Render the branded login page. Requires google_oauth secrets/env to be set."""
    st.session_state["oauth_state"] = str(time.time())
    login_url = build_auth_url(st.session_state["oauth_state"])

    # If config missing, we already showed an error; avoid rendering a broken button
    if not login_url:
        return

    # Background image
    bg_path = Path("assets/login_bg.png")
    bg_data_url = ""
    if bg_path.exists():
        try:
            b64 = base64.b64encode(bg_path.read_bytes()).decode("utf-8")
            bg_data_url = f"data:image/png;base64,{b64}"
        except Exception:
            bg_data_url = ""

    st.markdown(f"""
<link href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&display=swap" rel="stylesheet">
<style>
  [data-testid="stAppViewContainer"] {{
    {"background-image: url('" + bg_data_url + "');" if bg_data_url else "background: #0b0b0b;"}
    background-size: cover; background-position: center; background-repeat: no-repeat;
  }}
  [data-testid="stHeader"] {{ background: transparent; }}
  .login-card {{  position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);  /* centers both vertically and horizontally */
    width: min(92vw, 640px);
    padding: 32px;
    border-radius: 16px;
    background: rgba(255,255,255,0.95);
    box-shadow: 0 12px 30px rgba(0,0,0,0.28);
    text-align: center;
    backdrop-filter: blur(4px); }}
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
