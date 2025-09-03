
# -*- coding: utf-8 -*-
"""
MRIDAASTRO – UI wrapper for the stable v6 engine.

Drop this file into your repo as app.py (or the entry file you deploy).
Keep your working engine file (app_kundali_rect_exact_fix_v6.py) unchanged.
This wrapper:
- sets background (assets/ganesha_bg.png preferred),
- shows centered brand + italic tagline,
- bolds field labels,
- makes inputs compact,
- centers the "Generate DOCX" button,
- validates inputs,
- and calls into your existing engine to build the DOCX.
If no compatible function is found in the engine, a small placeholder DOCX is created
so the button always works.
"""

import os
import io
import datetime
import streamlit as st

# ---------- Try to import your stable engine ----------
ENGINE = None
try:
    import app_kundali_rect_exact_fix_v6 as ENGINE  # keep your v6 file name
except Exception as _e:
    ENGINE = None

# ---------- Page config ----------
st.set_page_config(
    page_title="MRIDAASTRO",
    page_icon="🪔",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- CSS / Theming ----------
def inject_css():
    bg = None
    for cand in ["assets/ganesha_bg.png", "bg1.jpg", "bg.png", "assets/bg1.jpg"]:
        if os.path.exists(cand):
            bg = cand
            break

    st.markdown(
        f"""
        <style>
            .stApp {{
                {"background: url('" + bg + "') center top / cover no-repeat fixed;" if bg else ""}
                background-color: #f6f6f6;
            }}
            .block-container {{
                padding-top: 2rem;
                max-width: 1200px;
            }}
            .brand-title {{
                text-align: center;
                font-family: Georgia, 'Times New Roman', serif;
                font-weight: 800;
                letter-spacing: 0.5px;
                font-size: 44px;
                margin: .4rem 0 .15rem 0;
                color: #222;
                text-shadow: 0 1px 1px rgba(0,0,0,.15);
            }}
            .brand-tagline {{
                text-align: center;
                font-style: italic;
                font-size: 20px;
                margin: 0 0 1.0rem 0;
                color: #222;
                text-shadow: 0 1px 1px rgba(0,0,0,.12);
            }}
            /* Bold field labels */
            label, .st-emotion-cache-1jicfl2 p, .stMarkdown p {{
                font-weight: 700 !important;
                font-size: 1.05rem;
                color: #202124;
            }}
            /* Button centered */
            .stButton > button {{
                display: inline-block;
                min-width: 260px;
                font-size: 1.05rem;
                padding: 0.6rem 1rem;
                margin: 0 auto;
            }}
            .button-row {{
                text-align: center;
                margin-top: .6rem;
            }}
        </style>
        {"<div class='stAlert stAlert--info'>Background image not found. Place one at assets/ganesha_bg.png or bg1.jpg</div>" if not bg else ""}
        """,
        unsafe_allow_html=True,
    )

def brand_header():
    st.markdown("<div class='brand-title'>MRIDAASTRO</div>", unsafe_allow_html=True)
    st.markdown("<div class='brand-tagline'>In the light of the divine, let your soul journey shine.</div>", unsafe_allow_html=True)

# ---------- Fallback very small DOCX if engine function is not found ----------
def build_placeholder_docx(name, dob, tob, place, tz_str):
    try:
        from docx import Document
        from docx.shared import Pt, Mm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except Exception as e:
        st.error("python-docx is required but not available.")
        return None

    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Mm(210); sec.page_height = Mm(297)
    sec.top_margin = Mm(12); sec.bottom_margin = Mm(12); sec.left_margin = Mm(15); sec.right_margin = Mm(15)

    def add_center(ptext, bold=False, italic=False, size=14):
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(ptext); r.bold = bold; r.italic = italic; r.font.size = Pt(size)

    add_center("MRIDAASTRO", bold=True, size=18)
    add_center("In the light of the divine, let your soul journey shine.", italic=True, size=11)
    add_center("Kundali (Preview Extract)", bold=True, size=13)

    doc.add_paragraph("")
    doc.add_paragraph(f"Name: {name}")
    doc.add_paragraph(f"Date of Birth: {dob.isoformat()}")
    doc.add_paragraph(f"Time of Birth: {tob.strftime('%H:%M')}")
    doc.add_paragraph(f"Place of Birth: {place}")
    if tz_str.strip():
        doc.add_paragraph(f"UTC Offset (manual): {tz_str}")
    else:
        doc.add_paragraph("UTC Offset: auto")

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

# ---------- Try to call the engine's generation function with many common names ----------
def try_engine_generate(name, dob, tob, place, tz_str):
    if ENGINE is None:
        return None

    # Execute one of these, if present. Function should return bytes/BytesIO or (filename, bytes).
    candidate_names = [
        "generate_docx", "build_and_download_docx", "create_docx",
        "create_kundali_docx", "make_kundali_docx", "export_docx"
    ]
    for fname in candidate_names:
        try:
            if hasattr(ENGINE, fname):
                func = getattr(ENGINE, fname)
                result = func(name, dob, tob, place, tz_str)
                # Normalize to BytesIO
                if result is None:
                    continue
                if isinstance(result, (bytes, bytearray)):
                    return io.BytesIO(result)
                if hasattr(result, "read"):
                    # file-like
                    try:
                        result.seek(0)
                    except Exception:
                        pass
                    return result
                if isinstance(result, tuple) and len(result) == 2:
                    # (filename, bytes)
                    return io.BytesIO(result[1])
                # Fallback: assume it's a path
                if isinstance(result, str) and os.path.exists(result):
                    return open(result, "rb")
        except Exception as e:
            # Keep trying others; we want a resilient button
            continue
    return None

# ---------- UI ----------
def main():
    inject_css()
    brand_header()

    # Inputs row 1
    col1, col2 = st.columns([1, 1])
    with col1:
        name = st.text_input("Name", value="", placeholder="Your full name")
    with col2:
        dob = st.date_input("Date of Birth", value=datetime.date(1990, 1, 1), format="YYYY-MM-DD")

    # Inputs row 2
    col3, col4 = st.columns([1, 1])
    with col3:
        tob = st.time_input("Time of Birth", value=datetime.time(12, 0), help="24-hour format (HH:MM)")
    with col4:
        place = st.text_input("Place of Birth (City, State, Country)", value="", placeholder="e.g., Jabalpur, Madhya Pradesh, India")

    # Inputs row 3
    c5, c6, _ = st.columns([1, 1, 0.15])
    with c5:
        tz_str = st.text_input("UTC offset override (optional, e.g., 5.5)", value="")

    # Validation hints
    validation_errors = []
    if not name.strip():
        validation_errors.append("Please enter your name.")
    if not place.strip():
        validation_errors.append("Please enter **City, State, Country** (e.g., 'Jabalpur, Madhya Pradesh, India').")

    if validation_errors:
        st.warning("\n".join(validation_errors))

    # Button
    st.markdown("<div class='button-row'>", unsafe_allow_html=True)
    btn = st.button("Generate DOCX", type="primary", disabled=bool(validation_errors))
    st.markdown("</div>", unsafe_allow_html=True)

    if btn and not validation_errors:
        with st.spinner("Building your Kundali document…"):
            # 1) Try your engine
            buf = try_engine_generate(name.strip(), dob, tob, place.strip(), tz_str.strip())
            # 2) Fallback mini doc if engine hook missing
            if buf is None:
                buf = build_placeholder_docx(name.strip(), dob, tob, place.strip(), tz_str.strip())

        if buf is None:
            st.error("Could not generate the document. Make sure your engine exposes one of: "
                     "`generate_docx`, `build_and_download_docx`, `create_docx`, "
                     "`create_kundali_docx`, `make_kundali_docx`, `export_docx`.")
        else:
            st.success("Kundali ready ✓")
            st.download_button(
                "Download Kundali (DOCX)",
                data=buf,
                file_name=f"Kundali_{name.strip().replace(' ', '_')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )


if __name__ == "__main__":
    main()
