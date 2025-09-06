
# brand_component.py
# Lightweight header component for MRIDAASTRO with tilak replacing the letter "I"
# Usage:
#   from brand_component import render_brand
#   render_brand()  # call where you want the header
#
# Requirements:
#   - Place your image at "assets/tilak_mark.png" OR at repo root "tilak_mark.png".

from __future__ import annotations
import os, base64
import streamlit as st

def _load_tilak_data_uri() -> str:
    """Return a data: URI for tilak_mark.png from ./assets or repo root."""
    for p in ("assets/tilak_mark.png", "tilak_mark.png"):
        if os.path.exists(p):
            with open(p, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            return "data:image/png;base64," + b64
    # transparent 1x1 GIF fallback (prevents broken <img> icon)
    return "data:image/gif;base64,R0lGODlhAQABAAAAACw="

def render_brand(title_font_px: int = 50, tilak_px: int = 32, tagline_px: int = 22) -> None:
    """Render MRIDAASTRO header with Cinzel Decorative and tilak image as 'I'."""
    data_uri = _load_tilak_data_uri()

    # Double all CSS braces for .format()
    html = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&display=swap');
    .mrida-brand {{ text-align:center; padding:16px 0 8px; }}
    .mrida-title {{
      font-family:'Cinzel Decorative',serif; font-weight:700; letter-spacing:1px; color:#000;
      display:flex; align-items:center; justify-content:center; gap:6px; font-size:{TITLE_PX}px;
      text-shadow:1px 1px 2px rgba(0,0,0,0.2);
    }}
    .mrida-tilak {{ width:{TILAK_PX}px; height:{TILAK_PX}px; display:inline-block; vertical-align:middle; }}
    .mrida-tagline {{ font-family:'Cinzel Decorative',serif; font-style:italic; color:#000; font-size:{TAGLINE_PX}px; margin-top:6px; }}
    @media (max-width: 480px) {{ .mrida-title{{font-size:{MOBILE_TITLE_PX}px}} .mrida-tilak{{width:{MOBILE_TILAK_PX}px;height:{MOBILE_TILAK_PX}px}} .mrida-tagline{{font-size:{MOBILE_TAGLINE_PX}px}} }}
    </style>
    <div class="mrida-brand">
      <div class="mrida-title">
        <span>MR</span>
        <img src="{IMG}" alt="I" class="mrida-tilak" />
        <span>DAASTRO</span>
      </div>
      <div class="mrida-tagline">In the light of divine, let your soul journey shine</div>
      <div style="height:3px; width:160px; margin:6px auto 0; background:black; border-radius:2px;"></div>
    </div>
    """.format(
        IMG=data_uri,
        TITLE_PX=title_font_px,
        TILAK_PX=tilak_px,
        TAGLINE_PX=tagline_px,
        MOBILE_TITLE_PX=max(22, int(title_font_px*0.76)),
        MOBILE_TILAK_PX=max(16, int(tilak_px*0.8)),
        MOBILE_TAGLINE_PX=max(14, int(tagline_px*0.82)),
    )

    st.markdown(html, unsafe_allow_html=True)
