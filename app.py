
import streamlit as st
import datetime

def render_label(text: str, show_required: bool = False):
    html = (
        "<div style='display:flex;justify-content:space-between;align-items:center;'>"
        f"<span style='font-weight:700; font-size:18px;'>{text}</span>"
        + ("<span style='color:#c1121f; font-size:14px; font-weight:700;'>Required</span>" if show_required else "")
        + "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)

# === MRIDAASTRO Brand Header (Top) with same font ===
st.markdown(
    """
    <div style='text-align:center; padding: 14px 0 4px 0; font-family:Poppins, sans-serif;'>
      <div style='font-size:46px; font-weight:800; letter-spacing:1px; color:#000000; margin-bottom:6px;'>
        MRIDAASTRO
      </div>
      <div style='font-size:20px; font-weight:500; color:#000000; margin-bottom:10px;'>
        In the light of divine, let your soul journey shine
      </div>
      <div style='height:3px; width:160px; margin:0 auto 6px auto; background:black; border-radius:2px;'></div>
    </div>
    """, unsafe_allow_html=True
)

# === Two fields per row layout (half-width) ===
row1c1, row1c2 = st.columns(2)
with row1c1:
    render_label('Name <span style="color:red">*</span>')
    name = st.text_input("", key="name_input", label_visibility="collapsed")
with row1c2:
    render_label('Date of Birth <span style="color:red">*</span>')
    dob = st.date_input("", key="dob_input", label_visibility="collapsed",
                        min_value=datetime.date(1800,1,1), max_value=datetime.date(2100,12,31))

row2c1, row2c2 = st.columns(2)
with row2c1:
    render_label('Time of Birth <span style="color:red">*</span>')
    tob = st.time_input("", key="tob_input", label_visibility="collapsed", step=datetime.timedelta(minutes=1))
with row2c2:
    render_label('Place of Birth (City, State, Country) <span style="color:red">*</span>')
    place = st.text_input("", key="place_input", label_visibility="collapsed")

# === Last row: UTC + Button side by side ===
row3c1, row3c2 = st.columns([2,1])
with row3c1:
    render_label('UTC offset override (e.g., 5.5) <span style="color:red">*</span>')
    tz_override = st.text_input("", key="tz_input", label_visibility="collapsed", value="")
with row3c2:
    st.write("")
    gen_clicked = st.button("Generate Kundali", key="gen_btn")

if gen_clicked:
    st.success("Kundali generation triggered! (Hook your generator here)")
