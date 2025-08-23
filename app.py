
import os, re, io, csv, zipfile, datetime, json, urllib.parse, urllib.request
import streamlit as st
import pandas as pd
import swisseph as swe
from timezonefinder import TimezoneFinder
from docx import Document
from docx.shared import Inches, Pt, Mm
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from io import BytesIO
import pytz
import matplotlib.pyplot as plt

# PDF generation
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

st.set_page_config(page_title="AstroDesk — Refined Kundali Suite", layout="wide", page_icon="🪔")

# ----------------- Constants -----------------
HN = {'Su':'सूर्य','Mo':'चंद्र','Ma':'मंगल','Me':'बुध','Ju':'गुरु','Ve':'शुक्र','Sa':'शनि','Ra':'राहु','Ke':'केतु'}
SYMB = {'Su':'☉','Mo':'☾','Ma':'♂','Me':'☿','Ju':'♃','Ve':'♀','Sa':'♄','Ra':'☊','Ke':'☋'}
ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
NAK = 360.0/27.0
YEAR_DAYS = 365.2425
DEVANAGARI_DIGITS = {str(i):"०१२३४५६७८९"[i] for i in range(10)}

# ----------------- Helpers -----------------
def set_sidereal():
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

def dms(deg):
    d=int(deg); m=int((deg-d)*60); s=int(round((deg-d-m/60)*3600))
    if s==60: s=0; m+=1
    if m==60: m=0; d+=1
    return d,m,s

def fmt_deg_sign(lon_sid):
    sign=int(lon_sid//30) + 1  # 1..12
    deg_in_sign = lon_sid % 30.0
    d,m,s=dms(deg_in_sign)
    return sign, f"{d:02d}°{m:02d}'{s:02d}\""

def kp_sublord(lon_sid):
    part = lon_sid % 360.0
    ni = int(part // NAK); pos = part - ni*NAK
    lord = ORDER[ni % 9]
    start = ORDER.index(lord)
    seq = [ORDER[(start+i)%9] for i in range(9)]
    acc = 0.0
    for L in seq:
        seg = NAK * (YEARS[L]/120.0)
        if pos <= acc + seg + 1e-9:
            return lord, L
        acc += seg
    return lord, seq[-1]

def geocode(place, api_key):
    if not api_key:
        raise RuntimeError("Geoapify key missing. Add GEOAPIFY_API_KEY in Streamlit Secrets.")
    base="https://api.geoapify.com/v1/geocode/search?"
    q = urllib.parse.urlencode({"text":place, "format":"json", "limit":1, "apiKey":api_key})
    with urllib.request.urlopen(base+q, timeout=15) as r:
        j = json.loads(r.read().decode())
    if j.get("results"):
        res=j["results"][0]
        return float(res["lat"]), float(res["lon"]), res.get("formatted", place)
    raise RuntimeError("Place not found.")

def tz_from_latlon(lat, lon, dt_local):
    tf = TimezoneFinder()
    tzname = tf.timezone_at(lat=lat, lng=lon) or "Etc/UTC"
    tz = pytz.timezone(tzname)
    dt_local_aware = tz.localize(dt_local)
    dt_utc_naive = dt_local_aware.astimezone(pytz.utc).replace(tzinfo=None)
    offset_hours = tz.utcoffset(dt_local_aware).total_seconds()/3600.0
    return tzname, offset_hours, dt_utc_naive

def sidereal_positions(dt_utc):
    jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                    dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600)
    set_sidereal()
    ay = swe.get_ayanamsa_ut(jd)
    flags=swe.FLG_MOSEPH
    out = {}
    for code, p in [('Su',swe.SUN),('Mo',swe.MOON),('Ma',swe.MARS),
                    ('Me',swe.MERCURY),('Ju',swe.JUPITER),('Ve',swe.VENUS),
                    ('Sa',swe.SATURN),('Ra',swe.MEAN_NODE)]:
        xx,_ = swe.calc_ut(jd, p, flags)
        out[code] = (xx[0] - ay) % 360.0
    out['Ke'] = (out['Ra'] + 180.0) % 360.0
    return jd, ay, out

def positions_table(sidelons, include_symbols=True):
    rows=[]
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        lon=sidelons[code]
        sign, deg_str = fmt_deg_sign(lon)
        nak_lord, sub_lord = kp_sublord(lon)
        if include_symbols:
            rows.append([SYMB[code], HN[code], sign, deg_str, HN[nak_lord], HN[sub_lord]])
        else:
            rows.append([HN[code], sign, deg_str, HN[nak_lord], HN[sub_lord]])
    if include_symbols:
        cols = ["Symbol","Planet","Sign","Degree","Nakshatra","Sub-Nakshatra"]
    else:
        cols = ["Planet","Sign","Degree","Nakshatra","Sub-Nakshatra"]
    return pd.DataFrame(rows, columns=cols)

# ----------------- Vimshottari -----------------
def moon_balance(moon_sid):
    part = moon_sid % 360.0
    ni = int(part // NAK)
    pos = part - ni*NAK
    md_lord = ORDER[ni % 9]
    frac = pos/NAK
    remaining_years = YEARS[md_lord]*(1 - frac)
    return md_lord, remaining_years

def add_years(dt, y): return dt + datetime.timedelta(days=y*YEAR_DAYS)

def build_mahadashas_from_birth(birth_local_dt, moon_sid):
    md_lord, rem = moon_balance(moon_sid)
    end_limit = add_years(birth_local_dt, 100.0)
    segments = []
    birth_md_start = birth_local_dt
    birth_md_end = min(add_years(birth_md_start, rem), end_limit)
    segments.append({"planet": md_lord, "start": birth_md_start,
                     "end": birth_md_end,
                     "years_used": (birth_md_end - birth_md_start).days / YEAR_DAYS})
    idx = (ORDER.index(md_lord) + 1) % 9
    t = birth_md_end
    while t < end_limit:
        L = ORDER[idx]; end = add_years(t, YEARS[L])
        if end > end_limit: end = end_limit
        segments.append({"planet": L, "start": t, "end": end,
                         "years_used": (end - t).days / YEAR_DAYS})
        t = end; idx = (idx + 1) % 9
    return segments, md_lord, rem

def antars_in_md(md_lord, md_start, md_years):
    res=[]; t=md_start; start_idx=ORDER.index(md_lord)
    for i in range(9):
        L=ORDER[(start_idx+i)%9]
        yrs = YEARS[L]*(md_years/120.0)
        days = yrs*YEAR_DAYS
        start = t; end = t + datetime.timedelta(days=days)
        res.append((L, start, end, yrs)); t = end
    return res

def pratyantars_in_antar(antar_lord, antar_start, antar_years):
    res=[]; t=antar_start; start_idx=ORDER.index(antar_lord)
    for i in range(9):
        L=ORDER[(start_idx+i)%9]
        yrs = YEARS[L]*(antar_years/120.0)
        days = yrs*YEAR_DAYS
        start = t; end = t + datetime.timedelta(days=days)
        res.append((L, start, end)); t = end
    return res

def next_ant_praty_in_days(now_local, md_segments, days_window):
    rows=[]; horizon=now_local + datetime.timedelta(days=days_window)
    for seg in md_segments:
        MD = seg["planet"]; ms = seg["start"]; me = seg["end"]
        md_years_effective = seg["years_used"]
        for AL, as_, ae, ay in antars_in_md(MD, ms, md_years_effective):
            if ae < now_local or as_ > horizon: continue
            for PL, ps, pe in pratyantars_in_antar(AL, as_, ay):
                if pe < now_local or ps > horizon: continue
                rows.append({"major":MD,"antar":AL,"pratyantar":PL,"end":pe})
    rows.sort(key=lambda r:r["end"])
    return rows

# ----------------- Ascendant & Charts -----------------
def ascendant_lon(jd_ut, lat, lon):
    set_sidereal()
    cusps, ascmc = swe.houses_ex(jd_ut, lat, lon, b'P')
    ay = swe.get_ayanamsa_ut(jd_ut)
    asc = (ascmc[0] - ay) % 360.0
    return asc

def house_sign_numbers_from_sign(start_sign):
    return [((start_sign-1+i)%12)+1 for i in range(12)]

def house_sign_numbers_from_asc(asc_sid):
    start_sign = int(asc_sid//30) + 1
    return house_sign_numbers_from_sign(start_sign)

def navamsa_sign_of_lon(lon_sid):
    sign = int(lon_sid//30) + 1
    deg_in = lon_sid % 30.0
    part = int(deg_in // (30.0/9.0))
    if sign in (1,4,7,10): start = sign
    elif sign in (2,5,8,11): start = ((sign + 8 - 1) % 12) + 1
    else: start = ((sign + 4 - 1) % 12) + 1
    return ((start - 1 + part) % 12) + 1

def to_devanagari(num):
    s = str(num)
    return ''.join(DEVANAGARI_DIGITS.get(ch, ch) for ch in s)

def render_north_diamond(house_numbers=None, show_numbers=False, numerals='English', size_px=900, font_pts=18, stroke=3):
    fig = plt.figure(figsize=(size_px/100, size_px/100), dpi=100)
    ax = fig.add_axes([0,0,1,1]); ax.axis('off')
    # Outer rectangle
    ax.plot([0.02,0.98,0.98,0.02,0.02],[0.02,0.02,0.98,0.98,0.02], linewidth=stroke, color='black')
    # Diagonals
    L,R,B,T = 0.02,0.98,0.02,0.98
    cx, cy = 0.5, 0.5
    ax.plot([L,R],[T,B], linewidth=stroke, color='black')
    ax.plot([L,R],[B,T], linewidth=stroke, color='black')
    # Mid connectors
    midL=(L,cy); midR=(R,cy); midT=(cx,T); midB=(cx,B)
    ax.plot([midL[0], midT[0]],[midL[1], midT[1]], linewidth=stroke, color='black')
    ax.plot([midT[0], midR[0]],[midT[1], midR[1]], linewidth=stroke, color='black')
    ax.plot([midR[0], midB[0]],[midR[1], midB[1]], linewidth=stroke, color='black')
    ax.plot([midB[0], midL[0]],[midB[1], midL[1]], linewidth=stroke, color='black')
    # Numbers optional
    if show_numbers and house_numbers is not None:
        pos = [
            (cx, T-0.06),(L+0.18, T-0.18),(L+0.08, cy),(L+0.18, B+0.18),
            (cx, B+0.06),(R-0.18, B+0.18),(R-0.08, cy),(R-0.18, T-0.18),
            (cx, cy),(cx+0.12, cy+0.12),(cx-0.12, cy+0.12),(cx-0.12, cy-0.12)
        ]
        for i,(x,y) in enumerate(pos):
            val = house_numbers[i]
            label = to_devanagari(val) if numerals=='Hindi' else str(val)
            ax.text(x,y,label, ha='center', va='center', fontsize=font_pts, fontweight='bold', color='black')
    buf = BytesIO(); fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.02)
    plt.close(fig); buf.seek(0); return buf

# ---- DOCX helpers ----
def add_table_borders(table, size=6):
    for row in table.rows:
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            tcBorders = OxmlElement('w:tcBorders')
            for edge in ('top','left','bottom','right'):
                el = OxmlElement(f'w:{edge}')
                el.set(qn('w:val'), 'single'); el.set(qn('w:sz'), str(size))
                tcBorders.append(el)
            tcPr.append(tcBorders)

def set_table_font(table, pt=9):
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for r in p.runs: r.font.size = Pt(pt)

def center_header_row(table):
    for p in table.rows[0].cells:
        for par in p.paragraphs:
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if par.runs: par.runs[0].bold = True

def set_col_widths(table, widths_inch):
    for row in table.rows:
        for i, w in enumerate(widths_inch):
            row.cells[i].width = Inches(w)
    table.autofit = False

def add_divider(doc, thickness=4):
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'),'single')
    bottom.set(qn('w:sz'), str(thickness))
    bottom.set(qn('w:space'),'1')
    bottom.set(qn('w:color'),'808080')
    pBdr.append(bottom)
    pPr.append(pBdr)

def add_footer(section, brand="Generated by AstroDesk"):
    footer = section.footer
    if not footer.paragraphs:
        p = footer.add_paragraph()
    else:
        p = footer.paragraphs[0]
    p.text = brand + " • Page "
    # Add page number field
    r = p.add_run()
    fldChar1 = OxmlElement('w:fldChar'); fldChar1.set(qn('w:fldCharType'),'begin')
    instrText = OxmlElement('w:instrText'); instrText.set(qn('xml:space'),'preserve'); instrText.text = " PAGE "
    fldChar2 = OxmlElement('w:fldChar'); fldChar2.set(qn('w:fldCharType'),'separate')
    fldChar3 = OxmlElement('w:fldChar'); fldChar3.set(qn('w:fldCharType'),'end')
    r._r.append(fldChar1); r._r.append(instrText); r._r.append(fldChar2); r._r.append(fldChar3)

def apply_normal_style(doc, latin="Georgia", cjk="Mangal", size_pt=9):
    style = doc.styles['Normal']
    style.font.name = latin
    style.font.size = Pt(size_pt)
    # Set complex script font for Hindi/Devanagari
    rFonts = style._element.rPr.rFonts
    rFonts.set(qn('w:eastAsia'), cjk)
    rFonts.set(qn('w:cs'), cjk)

def sanitize_filename(name):
    if not name: return "Horoscope"
    return re.sub(r'[^A-Za-z0-9_\- ]+', '', name).strip().replace(' ', '_') + "_Horoscope"

# ----------------- PDF builder (simple) -----------------
def build_pdf_single_page(title, details_lines, df_positions, df_md, df_ap, img_lagna_bytes, img_nav_bytes, brand="Generated by AstroDesk"):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    x_margin, y_margin = 28, 36  # points
    y = height - y_margin

    # Title
    c.setFont("Times-Bold", 14); c.drawString(x_margin, y, title); y -= 18

    # Details
    c.setFont("Times-Roman", 9)
    for line in details_lines:
        c.drawString(x_margin, y, line); y -= 12

    # Grid images side-by-side
    lagna = ImageReader(BytesIO(img_lagna_bytes))
    nav   = ImageReader(BytesIO(img_nav_bytes))
    img_w = 180; img_h = 180
    c.drawImage(lagna, width - x_margin - img_w*2 - 12, height - y_margin - img_h, img_w, img_h, preserveAspectRatio=True, mask='auto')
    c.drawImage(nav,   width - x_margin - img_w,       height - y_margin - img_h, img_w, img_h, preserveAspectRatio=True, mask='auto')

    # Planetary positions (minimal table-like)
    y -= 8
    c.setFont("Times-Bold", 10); c.drawString(x_margin, y, "Planetary Positions"); y -= 12
    c.setFont("Times-Roman", 8)
    for _, row in df_positions.iterrows():
        c.drawString(x_margin, y, f"{row[0]} {row[1]}  Sign:{row[2]}  Deg:{row[3]}  Nak:{row[4]}  Sub:{row[5]}"); y -= 10
        if y < 100: break

    # Mahadasha
    y -= 6; c.setFont("Times-Bold", 10); c.drawString(x_margin, y, "Vimshottari Mahadasha"); y -= 12
    c.setFont("Times-Roman", 8)
    for _, row in df_md.iterrows():
        c.drawString(x_margin, y, f"{row[0]}  End:{row[1]}  Age:{row[2]}"); y -= 10
        if y < 80: break

    # Antar/Pratyantar
    y -= 6; c.setFont("Times-Bold", 10); c.drawString(x_margin, y, "Antar / Pratyantar (Next 2 years)"); y -= 12
    c.setFont("Times-Roman", 8)
    for _, row in df_ap.iterrows():
        c.drawString(x_margin, y, f"{row[0]} > {row[1]} > {row[2]}  End:{row[3]}"); y -= 10
        if y < 60: break

    # Footer
    c.setFont("Times-Italic", 8)
    c.drawString(x_margin, 20, brand)
    c.showPage(); c.save()
    buf.seek(0); return buf.getvalue()

# ----------------- App -----------------
def main():
    st.title("AstroDesk — Refined Kundali Suite (North‑Indian)")
    st.caption("Single‑page client‑ready report • DOCX + PDF • Batch mode • Brand watermark")

    # Sidebar options
    with st.sidebar:
        st.header("Layout & Style")
        base_font = st.select_slider("Base font size (pt)", options=[8,8.5,9,9.5,10], value=9)
        latin_font = st.selectbox("Latin font", ["Georgia","Times New Roman","Calibri"], index=0)
        hindi_font = st.selectbox("Hindi/Devanagari font", ["Mangal","Nirmala UI","Kokila"], index=0)

        st.divider()
        st.header("Chart Options")
        show_numbers = st.checkbox("Show sign numbers inside charts", value=False)
        numeral_style = st.radio("Numeral style", ["English","Hindi"], index=0, horizontal=True)

        st.divider()
        st.header("Astrology Options")
        include_transit = st.checkbox("Include current transit positions", value=False)

        st.divider()
        st.header("Branding / Export")
        brand_text = st.text_input("Footer brand text", "Generated by AstroDesk")
        add_watermark = st.checkbox("Add header watermark text", value=False)
        logo = st.file_uploader("Optional logo (PNG/JPG) for header", type=["png","jpg","jpeg"])
        generate_pdf = st.checkbox("Also generate PDF", value=True)

        st.divider()
        st.header("Batch Mode")
        batch = st.checkbox("Process a CSV of multiple births", value=False)
        csv_file = None
        if batch:
            csv_file = st.file_uploader("Upload CSV (name,dob(YYYY-MM-DD),tob(HH:MM),place)", type=["csv"])

    # Main inputs
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Name")
        dob = st.date_input("Date of Birth", min_value=datetime.date(1800,1,1), max_value=datetime.date(2100,12,31))
        tob = st.time_input("Time of Birth", step=datetime.timedelta(minutes=1))
    with col2:
        place = st.text_input("Place of Birth (City, State, Country)")
        tz_override = st.text_input("UTC offset override (optional, e.g., 5.5)", "")
    api_key = st.secrets.get("GEOAPIFY_API_KEY","")

    # Action
    if st.button("Generate Report(s)"):
        try:
            if batch and csv_file is not None:
                # Batch generation: ZIP
                zbuf = BytesIO()
                zf = zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED)

                df_csv = pd.read_csv(csv_file)
                for idx, row in df_csv.iterrows():
                    n = str(row.get("name",""))
                    d = datetime.datetime.strptime(str(row.get("dob","")), "%Y-%m-%d").date()
                    t = datetime.datetime.strptime(str(row.get("tob","")), "%H:%M").time()
                    p = str(row.get("place",""))
                    lat, lon, disp = geocode(p, api_key)

                    dt_local = datetime.datetime.combine(d, t)
                    tzname, tz_hours, dt_utc = tz_from_latlon(lat, lon, dt_local)

                    # Compute
                    jd_ut, _, sidelons = sidereal_positions(dt_utc)
                    df_positions = positions_table(sidelons, include_symbols=True)

                    md_segments, _, _ = build_mahadashas_from_birth(dt_local, sidelons['Mo'])
                    df_md = pd.DataFrame([{"Planet": HN[s["planet"]], "End Date": s["end"].strftime("%d-%m-%Y"), "Age (at end)": round(((s["end"] - dt_local).days / YEAR_DAYS), 1)} for s in md_segments])
                    now_local = datetime.datetime.now()
                    rows_ap = next_ant_praty_in_days(now_local, md_segments, days_window=2*365)
                    df_ap = pd.DataFrame([{"Major Dasha": HN[r["major"]], "Antar Dasha": HN[r["antar"]], "Pratyantar Dasha": HN[r["pratyantar"]], "End Date": r["end"].strftime("%d-%m-%Y")} for r in rows_ap])

                    asc = ascendant_lon(jd_ut, lat, lon)
                    house_nums_d1 = house_sign_numbers_from_asc(asc)
                    asc_nav_sign = navamsa_sign_of_lon(asc)
                    house_nums_d9 = house_sign_numbers_from_sign(asc_nav_sign)

                    img_lagna = render_north_diamond(house_nums_d1, show_numbers=show_numbers, numerals=numeral_style, size_px=900, font_pts=18, stroke=3)
                    img_nav   = render_north_diamond(house_nums_d9, show_numbers=show_numbers, numerals=numeral_style, size_px=900, font_pts=18, stroke=3)

                    # DOCX
                    fname = sanitize_filename(n) + ".docx"
                    doc_bytes = build_docx(n, d, t, disp, tzname, tz_hours, df_positions, df_md, df_ap, img_lagna, img_nav,
                                           base_font, latin_font, hindi_font, brand_text, add_watermark, logo, include_transit, dudt=dt_utc)
                    zf.writestr(fname, doc_bytes)

                    # PDF (optional)
                    if generate_pdf:
                        pdf_bytes = build_pdf_single_page(f"{n} — Horoscope",
                                                          [f"DOB: {d}  |  TOB: {t}", f"Place: {disp}", f"Time Zone: {tzname} (UTC{tz_hours:+.2f})"],
                                                          df_positions, df_md, df_ap,
                                                          img_lagna.getvalue(), img_nav.getvalue(), brand=brand_text)
                        zf.writestr(sanitize_filename(n) + ".pdf", pdf_bytes)

                zf.close(); zbuf.seek(0)
                st.download_button("⬇️ Download ZIP of Reports", zbuf.getvalue(), file_name="AstroDesk_Reports.zip")
            else:
                # Single
                lat, lon, disp = geocode(place, api_key)
                dt_local = datetime.datetime.combine(dob, tob)
                if tz_override.strip():
                    tz_hours = float(tz_override); dt_utc = dt_local - datetime.timedelta(hours=tz_hours); tzname=f"UTC{tz_hours:+.2f} (manual)"
                else:
                    tzname, tz_hours, dt_utc = tz_from_latlon(lat, lon, dt_local)

                jd_ut, _, sidelons = sidereal_positions(dt_utc)
                df_positions = positions_table(sidelons, include_symbols=True)

                md_segments, _, _ = build_mahadashas_from_birth(dt_local, sidelons['Mo'])
                df_md = pd.DataFrame([{"Planet": HN[s["planet"]], "End Date": s["end"].strftime("%d-%m-%Y"), "Age (at end)": round(((s["end"] - dt_local).days / YEAR_DAYS), 1)} for s in md_segments])
                now_local = datetime.datetime.now()
                rows_ap = next_ant_praty_in_days(now_local, md_segments, days_window=2*365)
                df_ap = pd.DataFrame([{"Major Dasha": HN[r["major"]], "Antar Dasha": HN[r["antar"]], "Pratyantar Dasha": HN[r["pratyantar"]], "End Date": r["end"].strftime("%d-%m-%Y")} for r in rows_ap])

                if include_transit:
                    now_utc = datetime.datetime.utcnow().replace(microsecond=0)
                    _, _, transit = sidereal_positions(now_utc)
                    df_transit = positions_table(transit, include_symbols=True)
                else:
                    df_transit = None

                asc = ascendant_lon(jd_ut, lat, lon)
                house_nums_d1 = house_sign_numbers_from_asc(asc)
                asc_nav_sign = navamsa_sign_of_lon(asc)
                house_nums_d9 = house_sign_numbers_from_sign(asc_nav_sign)

                img_lagna = render_north_diamond(house_nums_d1, show_numbers=show_numbers, numerals=numeral_style, size_px=900, font_pts=18, stroke=3)
                img_nav   = render_north_diamond(house_nums_d9, show_numbers=show_numbers, numerals=numeral_style, size_px=900, font_pts=18, stroke=3)

                # DOCX
                doc_bytes = build_docx(name, dob, tob, disp, tzname, tz_hours, df_positions, df_md, df_ap, img_lagna, img_nav,
                                       base_font, latin_font, hindi_font, brand_text, add_watermark, logo, include_transit, df_transit, dt_utc)
                st.download_button("⬇️ Download DOCX", doc_bytes, file_name=sanitize_filename(name)+".docx")

                # PDF
                if generate_pdf:
                    pdf_bytes = build_pdf_single_page(f"{name} — Horoscope",
                                                      [f"DOB: {dob}  |  TOB: {tob}", f"Place: {disp}", f"Time Zone: {tzname} (UTC{tz_hours:+.2f})"],
                                                      df_positions, df_md, df_ap,
                                                      img_lagna.getvalue(), img_nav.getvalue(), brand=brand_text)
                    st.download_button("⬇️ Download PDF", pdf_bytes, file_name=sanitize_filename(name)+".pdf")

                # On-screen previews
                lc, rc = st.columns([1.15,0.85])
                with lc:
                    st.subheader("Planetary Positions"); st.dataframe(df_positions, use_container_width=True)
                    st.subheader("Vimshottari Mahadasha"); st.dataframe(df_md, use_container_width=True)
                    st.subheader("Antar / Pratyantar (Next 2 years)"); st.dataframe(df_ap, use_container_width=True)
                    if include_transit and df_transit is not None:
                        st.subheader("Current Transit"); st.dataframe(df_transit, use_container_width=True)
                with rc:
                    st.subheader("Lagna Kundali"); st.image(img_lagna, use_container_width=True)
                    st.subheader("Navamsa Kundali"); st.image(img_nav, use_container_width=True)

        except Exception as e:
            st.error(str(e))

def build_docx(name, dob, tob, disp, tzname, tz_hours, df_positions, df_md, df_ap, img_lagna, img_nav,
               base_font, latin_font, hindi_font, brand_text, add_watermark, logo_file, include_transit, df_transit=None, dudt=None):
    doc = Document()
    # A4 & margins
    sec = doc.sections[0]
    sec.page_width = Mm(210); sec.page_height = Mm(297)
    margin = Mm(10); sec.left_margin = sec.right_margin = margin
    sec.top_margin = Mm(8); sec.bottom_margin = Mm(8)

    apply_normal_style(doc, latin=latin_font, cjk=hindi_font, size_pt=base_font)

    # Header watermark / logo
    if add_watermark:
        header = sec.header
        p = header.paragraphs[0]
        run = p.add_run(brand_text); run.font.size = Pt(12); run.font.color.rgb = None
    if logo_file is not None:
        header = sec.header
        rp = header.paragraphs[0].add_run()
        rp.add_picture(logo_file, width=Inches(0.6))

    # Footer with brand and page number
    add_footer(sec, brand=brand_text)

    # Title
    title = doc.add_paragraph(f"{name or '—'} — Horoscope")
    title.runs[0].font.size = Pt(base_font+4); title.runs[0].bold = True

    # 2-column layout
    layout = doc.add_table(rows=1, cols=2); layout.autofit = True
    layout.columns[0].width = Inches(3.9); layout.columns[1].width = Inches(3.9)

    # LEFT: Details + Tables
    left = layout.rows[0].cells[0]

    p = left.add_paragraph("Personal Details"); r = p.add_run(); r.bold = True
    left.add_paragraph(f"Name: {name}")
    left.add_paragraph(f"DOB: {dob}  |  TOB: {tob}")
    left.add_paragraph(f"Place: {disp}")
    left.add_paragraph(f"Time Zone: {tzname} (UTC{tz_hours:+.2f})")

    add_divider(doc)

    left.add_paragraph("Planetary Positions").runs[0].bold = True
    t1 = left.add_table(rows=1, cols=len(df_positions.columns))
    for i,c in enumerate(df_positions.columns): cell=t1.rows[0].cells[i]; cell.text=c
    for _,row in df_positions.iterrows():
        r=t1.add_row().cells
        for i,c in enumerate(row): r[i].text=str(c)
    add_table_borders(t1, size=6); set_table_font(t1, pt=base_font); center_header_row(t1)
    set_col_widths(t1, [0.5,1.0,0.6,0.9,1.0,1.0] if len(df_positions.columns)==6 else [1,0.6,0.9,1.0,1.0])

    add_divider(doc)

    left.add_paragraph("Vimshottari Mahadasha").runs[0].bold = True
    t2 = left.add_table(rows=1, cols=len(df_md.columns))
    for i,c in enumerate(df_md.columns): t2.rows[0].cells[i].text = c
    for _,row in df_md.iterrows():
        r=t2.add_row().cells
        for i,c in enumerate(row): r[i].text=str(c)
    add_table_borders(t2, size=6); set_table_font(t2, pt=base_font); center_header_row(t2)
    set_col_widths(t2, [1.0,1.0,0.8])

    add_divider(doc)

    left.add_paragraph("Current Antar / Pratyantar (Next 2 years)").runs[0].bold = True
    t3 = left.add_table(rows=1, cols=len(df_ap.columns))
    for i,c in enumerate(df_ap.columns): t3.rows[0].cells[i].text = c
    for _,row in df_ap.iterrows():
        r=t3.add_row().cells
        for i,c in enumerate(row): r[i].text=str(c)
    add_table_borders(t3, size=6); set_table_font(t3, pt=base_font); center_header_row(t3)
    set_col_widths(t3, [1.0,1.0,1.1,0.9])

    if include_transit and df_transit is not None:
        add_divider(doc)
        left.add_paragraph("Current Transit Positions").runs[0].bold = True
        t4 = left.add_table(rows=1, cols=len(df_transit.columns))
        for i,c in enumerate(df_transit.columns): t4.rows[0].cells[i].text = c
        for _,row in df_transit.iterrows():
            r=t4.add_row().cells
            for i,c in enumerate(row): r[i].text=str(c)
        add_table_borders(t4, size=6); set_table_font(t4, pt=base_font); center_header_row(t4)
        set_col_widths(t4, [0.5,1.0,0.6,0.9,1.0,1.0])

    # RIGHT: Charts side-by-side
    right = layout.rows[0].cells[1]
    # a table with one row, two columns to place charts side by side
    chart_tbl = right.add_table(rows=1, cols=2)
    c1, c2 = chart_tbl.rows[0].cells
    img_lagna.seek(0); c1.paragraphs[0].add_run().add_picture(img_lagna, width=Inches(3.2))
    img_nav.seek(0);   c2.paragraphs[0].add_run().add_picture(img_nav,   width=Inches(3.2))

    # Save
    out = BytesIO(); doc.save(out); out.seek(0); return out.getvalue()

if __name__=='__main__':
    main()
