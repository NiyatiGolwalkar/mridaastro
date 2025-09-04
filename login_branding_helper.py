# login_branding_helper.py (full-screen cover bg + fixed login card)
import base64, os, time
from urllib.parse import urlencode
from pathlib import Path
import streamlit as st

def _read_google_oauth_from_secrets():
    cfg = {}
    try:
        cfg = st.secrets.get("google_oauth", {})
    except Exception:
        cfg = {}
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", cfg.get("client_id", "").strip())
    redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", cfg.get("redirect_uri", "").strip())
    return client_id, redirect_uri

def build_auth_url(state: str) -> str:
    client_id, redirect_uri = _read_google_oauth_from_secrets()
    if not client_id or not redirect_uri:
        st.error(
            "Google OAuth is not configured. Please add `google_oauth.client_id` and "
            "`google_oauth.redirect_uri` in Secrets (or set env vars)."
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
    st.session_state["oauth_state"] = str(time.time())
    login_url = build_auth_url(st.session_state["oauth_state"])

    # Background image
    bg_path = Path("assets/login_bg.png")
    bg_data_url = ""
    if bg_path.exists():
        try:
            b64 = base64.b64encode(bg_path.read_bytes()).decode("utf-8")
            bg_data_url = f"data:image/png;base64,{b64}"
        except Exception:
            bg_data_url = ""

    # client id tail for quick verification
    client_id_tail = ""
    cid, _ = _read_google_oauth_from_secrets()
    if cid:
        client_id_tail = cid[-12:]

    st.markdown(f"""
<link href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&display=swap" rel="stylesheet">
<style>
  html, body, [data-testid="stAppViewContainer"] {{
    height: 100%;
    min-height: 100vh;
  }}
  /* Full-screen background */
  [data-testid="stAppViewContainer"] {{
    {"background-image: url('" + bg_data_url + "');" if bg_data_url else "background: #f6ede6;"}
    background-size: cover;
    background-position: top center;
    background-repeat: no-repeat;
    background-attachment: fixed; /* keeps bg static while card stays fixed */
    background-color: #f6ede6;
  }}
  [data-testid="stHeader"] {{ background: transparent; }}

  /* Fixed login card positioned just below the stotram area */
  .login-card {{
    position: fixed;
    left: 50%;
    transform: translateX(-50%);
    /* Adjust this top value to sit just under the stotram in the image */
    top: 56vh;
    width: min(92vw, 640px);
    padding: 32px;
    border-radius: 16px;
    background: rgba(255,255,255,0.95);
    box-shadow: 0 12px 30px rgba(0,0,0,0.28);
    text-align: center;
    backdrop-filter: blur(4px);
  }}
  .brand {{
    font-family: 'Cinzel Decorative', cursive;
    font-size: clamp(40px, 6vw, 64px);
    font-weight: 700;
    color: #000;
    margin-bottom: 8px;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.18);
  }}
  .tagline {{
    font-family: Georgia, serif;
    font-style: italic;
    font-size: clamp(18px, 2.4vw, 24px);
    color: #000;
    margin-bottom: 18px;
  }}
  .divider {{
    height: 3px; width: 180px; margin: 0 auto 20px auto;
    background: #000; border-radius: 2px;
  }}
  .login-btn {{
    display: inline-block;
    padding: 14px 28px;
    border-radius: 10px;
    font-weight: 700;
    font-size: 20px;
    border: none;
    background: #FFD700;
    color: black !important;
    transition: all .2s ease-in-out;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    text-decoration: none !important;
  }}
  .login-btn:hover {{ background: #e6c200; transform: translateY(-2px); }}
  .fineprint {{ margin-top: 12px; font-size: 13px; color: #333; }}
  .cidtail {{ margin-top: 6px; font-size: 11px; color: #666; }}

  /* Small screens: bring card up a bit */
  @media (max-width: 640px) {{
    .login-card {{ top: 52vh; padding: 24px; }}
  }}
</style>
<div class="login-card">
  <div class="brand">MRIDAASTRO</div>
  <div class="tagline">In the light of divine, let your soul journey shine</div>
  <div class="divider"></div>
  {"<a class='login-btn' href=\"" + login_url + "\">Sign in with Google</a>" if login_url else ""}
  <div class="fineprint">Access restricted to authorised users.</div>
  <div class="cidtail">Client ID ends with: {client_id_tail}</div>
</div>
""", unsafe_allow_html=True)
