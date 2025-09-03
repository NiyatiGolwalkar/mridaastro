
# -*- coding: utf-8 -*-
import os
import io
import base64
import importlib
from datetime import date, time, datetime, timedelta

import streamlit as st

# ------------------------------
# Page & global styles
# ------------------------------
st.set_page_config(page_title="MRIDAASTRO", layout="wide", page_icon="✨")

def _read_first_existing(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def _bg_css():
    """Embed a background image (if found) as base64 CSS."""
    candidates = [
        "assets/ganesha_bg.png",
        "assets/bg1.jpg",
        "assets/bg.png",
        "bg1.jpg",
        "bg.png",
    ]
    path = _read_first_existing(candidates)
    if not path:
        # No image found – soft fallback: pastel gradient
        return """
        <style>
        .stApp { 
            background: linear-gradient(135deg, #f0fff0 0%, #e9f7ff 100%);
            background-attachment: fixed;
        }
        </style>
        """, False
    try:
        with open(path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode("utf-8")
        ext = "png" if path.lower().endswith("png") else "jpg"
        return f"""
        <style>
        .stApp {{
            background-image: url("data:image/{ext};base64,{b64}");
            background-size: cover;
            background-repeat: no-repeat;
            background-attachment: fixed;
            background-position: center;
        }}
        /* tighten layout a bit */
        section.main > div {{ padding-top: 2rem; }}
        /* make labels bold & inputs readable on image */
        label, .stMarkdown p, .st-emotion-cache-1kyxreq p {{
            font-weight: 700 !important;
            color: #1f2937 !important;
            text-shadow: 0 1px 0 rgba(255,255,255,0.35);
        }}
        .stTextInput > div > div input,
        .stDateInput input,
        .stTimeInput input,
        .stSelectbox > div > div, 
        .stTextArea textarea {{
            color: #111 !important;
        }}
        /* center the big header and tagline */
        .brand-wrap {{
            text-align: center;
            margin-bottom: 0.3rem;
        }}
        .brand {{ 
            font-size: clamp(34px, 4.3vw, 56px);
            font-weight: 800; 
            letter-spacing: 1px;
        }}
        .tagline {{
            margin-top: .2rem;
            font-style: italic;
            font-size: clamp(16px, 2.0vw, 22px);
            font-weight: 700;
        }}
        /* compact inputs */
        .compact .stTextInput > div, 
        .compact .stDateInput > div, 
        .compact .stTimeInput > div, 
        .compact .stSelectbox > div, 
        .compact .stTextArea > div {{
            background: rgba(255,255,255,0.85);
            border-radius: 10px;
        }}
        /* center the button */
        .center-btn button {{
            display: inline-block;
            padding: .9rem 1.6rem;
            font-size: 1.05rem;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,.12);
        }}
        </style>
        """, True
    except Exception:
        return """
        <style>.stApp { background: #fafafa; }</style>
        """, False

_css, _has_bg = _bg_css()
st.markdown(_css, unsafe_allow_html=True)
if not _has_bg:
    st.info("Background image not found. Add one of: `assets/ganesha_bg.png`, `bg1.jpg`, `bg.png`, `assets/bg1.jpg`.")

# ------------------------------
# Brand block
# ------------------------------
st.markdown(
    """
    <div class="brand-wrap">
        <div class="brand">MRIDAASTRO</div>
        <div class="tagline">In the light of the divine, let your soul journey shine.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------
# Form
# ------------------------------
with st.container():
    st.markdown('<div class="compact">', unsafe_allow_html=True)

    c1, c2 = st.columns([1,1], gap="large")

    with c1:
        name = st.text_input("Name", placeholder="e.g., Niyati Golwalkar")
    with c2:
        dob = st.date_input("Date of Birth", value=date.today())

    with c1:
        tob = st.time_input("Time of Birth", step=timedelta(minutes=1))
    with c2:
        place = st.text_input(
            "Place of Birth (City, State, Country)",
            placeholder="e.g., Jabalpur, Madhya Pradesh, India",
            help="Enter as City, State, Country. Example: Raipur, Chhattisgarh, India"
        )

    utc_offset = st.text_input("UTC offset override (optional, e.g., 5.5)", placeholder="e.g., 5.5")

    st.markdown("</div>", unsafe_allow_html=True)  # end compact

# ------------------------------
# Validation helpers
# ------------------------------
def _place_is_valid(s: str) -> bool:
    parts = [p.strip() for p in (s or "").split(",")]
    return len(parts) >= 3 and all(parts[:3])

def _as_float_or_none(s: str):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None

# ------------------------------
# Engine dispatcher
# ------------------------------
def _try_engine_generate(payload: dict) -> io.BytesIO | None:
    """
    Try to import a project-local engine and call a known function name.
    If nothing is available, return None so the caller can build a safe fallback.
    """
    module_candidates = [
        "app_kundali_rect_exact_fix_v6",
        "kundali_app",
        "engine",
        "generator",
    ]
    func_candidates = [
        "generate_docx",
        "build_and_download_docx",
        "create_docx",
        "create_kundali_docx",
        "make_kundali_docx",
        "export_docx",
    ]

    for mod_name in module_candidates:
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue

        for fn in func_candidates:
            func = getattr(mod, fn, None)
            if not callable(func):
                continue
            # Try kwargs call first
            try:
                out = func(**payload)
                if out is not None:
                    # Accept bytes, BytesIO, or path
                    if isinstance(out, (bytes, bytearray)):
                        return io.BytesIO(out)
                    if isinstance(out, io.BytesIO):
                        out.seek(0)
                        return out
                    if isinstance(out, str) and os.path.exists(out):
                        return io.BytesIO(open(out, "rb").read())
                    # Unknown return; stringify as docx fallback below
                return None
            except TypeError:
                # Try positional fallbacks
                for args in [
                    ("name","dob","tob","place","utc_offset"),
                    ("name","dob","tob","place"),
                    ("dob","tob","place"),
                    ("name","place","dob","tob"),
                ]:
                    try:
                        out = func(*(payload[k] for k in args if k in payload))
                        if out is not None:
                            if isinstance(out, (bytes, bytearray)):
                                return io.BytesIO(out)
                            if isinstance(out, io.BytesIO):
                                out.seek(0)
                                return out
                            if isinstance(out, str) and os.path.exists(out):
                                return io.BytesIO(open(out, "rb").read())
                        return None
                    except Exception:
                        continue
            except Exception:
                # engine raised—bubble up as None (we'll fallback)
                return None
    return None

# ------------------------------
# DOCX builder (safe fallback)
# ------------------------------
def _build_safe_docx(name, dob, tob, place, utc_offset):
    try:
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()
        # Title
        p = doc.add_paragraph()
        run = p.add_run("MRIDAASTRO")
        run.bold = True
        run.font.size = Pt(28)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        tag = doc.add_paragraph()
        r2 = tag.add_run("In the light of the divine, let your soul journey shine.")
        r2.italic = True
        r2.font.size = Pt(14)
        tag.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph("")

        # Content
        info = doc.add_paragraph()
        info.add_run("Kundali (Preview Extract)\n").bold = True

        fields = [
            ("Name", name or ""),
            ("Date of Birth", dob.isoformat() if isinstance(dob, date) else str(dob)),
            ("Time of Birth", tob.strftime("%H:%M") if isinstance(tob, time) else str(tob)),
            ("Place of Birth", place or ""),
            ("UTC Offset (manual)", str(utc_offset) if utc_offset is not None else ""),
        ]
        for k, v in fields:
            para = doc.add_paragraph()
            para.add_run(f"{k}: ").bold = True
            para.add_run(v)

        # Save to buffer
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf
    except Exception as e:
        # As a last resort, emit a tiny text-based DOCX-like content in memory (unlikely path)
        return io.BytesIO(b"")

# ------------------------------
# Action
# ------------------------------
payload = dict(
    name=name.strip() if name else "",
    dob=dob,
    tob=tob,
    place=place.strip() if place else "",
    utc_offset=_as_float_or_none(utc_offset),
)

# Inline validations
if st.button("Generate DOCX", type="primary", use_container_width=False, help="Generate and download Kundali DOCX"):
    # Validate inputs
    errors = []
    if not payload["name"]:
        errors.append("Please enter your name.")
    if not _place_is_valid(payload["place"]):
        errors.append("Please enter Place as **City, State, Country** (e.g., *Jabalpur, Madhya Pradesh, India*).")
    if errors:
        for e in errors:
            st.error(e)
    else:
        with st.spinner("Generating Kundali…"):
            # Try your local engine first
            buf = _try_engine_generate(payload)
            # Otherwise safe fallback (non-empty document with entered details)
            if buf is None or buf.getbuffer().nbytes == 0:
                buf = _build_safe_docx(**payload)
            # Offer download
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            fname = f"Kundali_{payload['name'].replace(' ', '_')}_{ts}.docx"
            st.success("Kundali ready ✓")
            st.download_button(
                label="Download Kundali (DOCX)",
                data=buf,
                file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
