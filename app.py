
import os, re, io, zipfile, datetime, json, urllib.parse, urllib.request
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

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

st.set_page_config(page_title="AstroDesk — Kundali (Auto Hindi PDF + Stacked Charts DOCX)", layout="wide", page_icon="🪔")

HN = {'Su':'सूर्य','Mo':'चंद्र','Ma':'मंगल','Me':'बुध','Ju':'गुरु','Ve':'शुक्र','Sa':'शनि','Ra':'राहु','Ke':'केतु'}
SYMB = {'Su':'☉','Mo':'☾','Ma':'♂','Me':'☿','Ju':'♃','Ve':'♀','Sa':'♄','Ra':'☊','Ke':'☋'}

def set_sidereal(): swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

def dms(deg):
    d=int(deg); m=int((deg-d)*60); s=int(round((deg-d-m/60)*3600))
    if s==60: s=0; m+=1
    if m==60: m=0; d+=1
    return d,m,s

def fmt_deg_sign(lon_sid):
    sign=int(lon_sid//30) + 1
    deg_in_sign = lon_sid % 30.0
    d,m,s=dms(deg_in_sign)
    return sign, f"{d:02d}°{m:02d}'{s:02d}\""

def kp_sublord(lon_sid):
    NAK=360.0/27.0
    ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
    YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
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

def positions_table(sidelons):
    rows=[]
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        lon=sidelons[code]
        sign, deg_str = fmt_deg_sign(lon)
        nak_lord, sub_lord = kp_sublord(lon)
        rows.append([SYMB[code], HN[code], sign, deg_str, HN[nak_lord], HN[sub_lord]])
    cols = ["Symbol","Planet","Sign","Degree","Nakshatra","Sub‑Nakshatra"]
    return pd.DataFrame(rows, columns=cols)

def moon_balance(moon_sid):
    NAK=360.0/27.0
    ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
    YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
    part = moon_sid % 360.0
    ni = int(part // NAK)
    pos = part - ni*NAK
    md_lord = ORDER[ni % 9]
    frac = pos/NAK
    remaining_years = YEARS[md_lord]*(1 - frac)
    return md_lord, remaining_years

def add_years(dt, y): return dt + datetime.timedelta(days=y*365.2425)

def build_mahadashas_from_birth(birth_local_dt, moon_sid):
    ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
    YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
    md_lord, rem = moon_balance(moon_sid)
    end_limit = add_years(birth_local_dt, 100.0)
    segments = []
    birth_md_start = birth_local_dt
    birth_md_end = min(add_years(birth_md_start, rem), end_limit)
    segments.append({"planet": md_lord, "start": birth_md_start, "end": birth_md_end, "years_used": (birth_md_end - birth_md_start).days / 365.2425})
    idx = (ORDER.index(md_lord) + 1) % 9
    t = birth_md_end
    while t < end_limit:
        L = ORDER[idx]; end = add_years(t, YEARS[L])
        if end > end_limit: end = end_limit
        segments.append({"planet": L, "start": t, "end": end, "years_used": (end - t).days / 365.2425})
        t = end; idx = (idx + 1) % 9
    return segments, md_lord, rem

def antars_in_md(md_lord, md_start, md_years):
    ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
    YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
    res=[]; t=md_start; start_idx=ORDER.index(md_lord)
    for i in range(9):
        L=ORDER[(start_idx+i)%9]
        yrs = YEARS[L]*(md_years/120.0)
        days = yrs*365.2425
        start = t; end = t + datetime.timedelta(days=days)
        res.append((L, start, end, yrs)); t = end
    return res

def pratyantars_in_antar(antar_lord, antar_start, antar_years):
    ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
    YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
    res=[]; t=antar_start; start_idx=ORDER.index(antar_lord)
    for i in range(9):
        L=ORDER[(start_idx+i)%9]
        yrs = YEARS[L]*(antar_years/120.0)
        days = yrs*365.2425
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

def render_north_diamond(size_px=900, stroke=3):
    fig = plt.figure(figsize=(size_px/100, size_px/100), dpi=100)
    ax = fig.add_axes([0,0,1,1]); ax.axis('off')
    ax.plot([0.02,0.98,0.98,0.02,0.02],[0.02,0.02,0.98,0.98,0.02], linewidth=stroke, color='black')
    L,R,B,T = 0.02,0.98,0.02,0.98
    cx, cy = 0.5, 0.5
    ax.plot([L,R],[T,B], linewidth=stroke, color='black')
    ax.plot([L,R],[B,T], linewidth=stroke, color='black')
    midL=(L,cy); midR=(R,cy); midT=(cx,T); midB=(cx,B)
    ax.plot([midL[0], midT[0]],[midL[1], midT[1]], linewidth=stroke, color='black')
    ax.plot([midT[0], midR[0]],[midT[1], midR[1]], linewidth=stroke, color='black')
    ax.plot([midR[0], midB[0]],[midR[1], midB[1]], linewidth=stroke, color='black')
    ax.plot([midB[0], midL[0]],[midB[1], midL[1]], linewidth=stroke, color='black')
    buf = BytesIO(); fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.02)
    plt.close(fig); buf.seek(0); return buf

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

def add_footer(section, brand="Generated by AstroDesk"):
    footer = section.footer
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.text = brand + " • Page "
    r = p.add_run()
    fldChar1 = OxmlElement('w:fldChar'); fldChar1.set(qn('w:fldCharType'),'begin')
    instrText = OxmlElement('w:instrText'); instrText.set(qn('xml:space'),'preserve'); instrText.text = " PAGE "
    fldChar2 = OxmlElement('w:fldChar'); fldChar2.set(qn('w:fldCharType'),'separate')
    fldChar3 = OxmlElement('w:fldChar'); fldChar3.set(qn('w:fldCharType'),'end')
    r._r.append(fldChar1); r._r.append(instrText); r._r.append(fldChar2); r._r.append(fldChar3)

def sanitize_filename(name: str) -> str:
    """Safe, cross‑platform filename base without regex range bugs."""
    if not name: return "Horoscope"
    # Allow letters, digits, underscore, hyphen, and space
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in "_- ")
    cleaned = cleaned.strip().replace(" ", "_")
    return cleaned or "Horoscope"

def ensure_hindi_font():
    candidates = ["Mangal.ttf","Nirmala.ttf","Nirmala UI.ttf","NotoSansDevanagari-Regular.ttf"]
    for c in candidates:
        for base in [".","/usr/share/fonts/truetype","/usr/share/fonts","/usr/local/share/fonts","/mnt/data"]:
            p = os.path.join(base, c)
            if os.path.exists(p):
                try:
                    pdfmetrics.registerFont(TTFont("HindiAuto", p))
                    return "HindiAuto"
                except Exception:
                    pass
    url = "https://github.com/google/fonts/raw/main/ofl/notosansdevanagari/NotoSansDevanagari-Regular.ttf"
    try:
        data = urllib.request.urlopen(url, timeout=15).read()
        path = "/mnt/data/NotoSansDevanagari-Regular.ttf"
        with open(path,"wb") as f: f.write(data)
        pdfmetrics.registerFont(TTFont("HindiAuto", path))
        return "HindiAuto"
    except Exception:
        return None

def build_pdf_single_page(title, details_lines, df_positions, df_md, df_ap, img_lagna_bytes, img_nav_bytes, brand="Generated by AstroDesk", hindi_font_name=None):
    from reportlab.lib.pagesizes import A4
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    x_margin, y_margin = 28, 36
    y = height - y_margin
    c.setFont("Times-Bold", 14); c.drawString(x_margin, y, title); y -= 18
    font_text = hindi_font_name or "Times-Roman"
    c.setFont(font_text, 10)
    for line in details_lines:
        c.drawString(x_margin, y, line); y -= 12
    lagna = ImageReader(BytesIO(img_lagna_bytes))
    nav   = ImageReader(BytesIO(img_nav_bytes))
    img_w = 200; img_h = 200
    right_x = width - x_margin - img_w
    top_y = height - y_margin - img_h
    c.drawImage(lagna, right_x, top_y, img_w, img_h, preserveAspectRatio=True, mask='auto')
    c.drawImage(nav,   right_x, top_y - img_h - 12, img_w, img_h, preserveAspectRatio=True, mask='auto')
    y -= 8; c.setFont("Times-Bold", 11); c.drawString(x_margin, y, "Planetary Positions"); y -= 12
    c.setFont(font_text, 9)
    for _, row in df_positions.iterrows():
        sym = str(row["Symbol"]); planet = str(row["Planet"])
        line1 = f"{sym}  "; c.setFont("Times-Roman", 9); c.drawString(x_margin, y, line1)
        x2 = x_margin + pdfmetrics.stringWidth(line1, "Times-Roman", 9)
        c.setFont(font_text, 9)
        c.drawString(x2, y, f"{planet}  Sign:{row['Sign']}  Deg:{row['Degree']}  Nak:{row['Nakshatra']}  Sub:{row['Sub‑Nakshatra']}"); y -= 11
        if y < 140: break
    y -= 6; c.setFont("Times-Bold", 11); c.drawString(x_margin, y, "Vimshottari Mahadasha"); y -= 12
    c.setFont(font_text, 9)
    for _, row in df_md.iterrows():
        c.drawString(x_margin, y, f"{row['Planet']}  End:{row['End Date']}  Age:{row['Age (at end)']}"); y -= 11
        if y < 100: break
    y -= 4; c.setFont("Times-Bold", 11); c.drawString(x_margin, y, "Antar / Pratyantar (Next 2 years)"); y -= 12
    c.setFont(font_text, 9)
    for _, row in df_ap.iterrows():
        c.drawString(x_margin, y, f"{row['Major Dasha']} > {row['Antar Dasha']} > {row['Pratyantar Dasha']}  End:{row['End Date']}"); y -= 11
        if y < 60: break
    c.setFont("Times-Italic", 8); c.drawString(x_margin, 20, brand)
    c.showPage(); c.save(); buf.seek(0); return buf.getvalue()

def main():
    st.title("AstroDesk — Auto-Hindi PDF + Stacked Charts (DOCX)")
    with st.sidebar:
        base_font = st.select_slider("DOCX base font (pt)", options=[8,8.5,9,9.5,10], value=9)
        latin_font = st.selectbox("DOCX Latin font", ["Georgia","Times New Roman","Calibri"], index=0)
        hindi_font = st.selectbox("DOCX Hindi font", ["Mangal","Nirmala UI","Kokila"], index=0)
        brand_text = st.text_input("Footer brand", "Generated by AstroDesk")
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Name")
        dob = st.date_input("Date of Birth", min_value=datetime.date(1800,1,1), max_value=datetime.date(2100,12,31))
        tob = st.time_input("Time of Birth", step=datetime.timedelta(minutes=1))
    with col2:
        place = st.text_input("Place of Birth (City, State, Country)")
        tz_override = st.text_input("UTC offset override (optional, e.g., 5.5)", "")
    api_key = st.secrets.get("GEOAPIFY_API_KEY","")
    if st.button("Generate"):
        try:
            lat, lon, disp = geocode(place, api_key)
            dt_local = datetime.datetime.combine(dob, tob)
            if tz_override.strip():
                tz_hours = float(tz_override); dt_utc = dt_local - datetime.timedelta(hours=tz_hours); tzname=f"UTC{tz_hours:+.2f} (manual)"
            else:
                tzname, tz_hours, dt_utc = tz_from_latlon(lat, lon, dt_local)
            jd_ut, _, sidelons = sidereal_positions(dt_utc)
            df_positions = positions_table(sidelons)
            md_segments, _, _ = build_mahadashas_from_birth(dt_local, sidelons['Mo'])
            df_md = pd.DataFrame([{"Planet": HN[s["planet"]], "End Date": s["end"].strftime("%d-%m-%Y"), "Age (at end)": round(((s["end"] - dt_local).days / 365.2425), 1)} for s in md_segments])
            now_local = datetime.datetime.now()
            rows_ap = next_ant_praty_in_days(now_local, md_segments, days_window=2*365)
            df_ap = pd.DataFrame([{"Major Dasha": HN[r["major"]], "Antar Dasha": HN[r["antar"]], "Pratyantar Dasha": HN[r["pratyantar"]], "End Date": r["end"].strftime("%d-%m-%Y")} for r in rows_ap])
            img_lagna = render_north_diamond(size_px=900, stroke=3)
            img_nav   = render_north_diamond(size_px=900, stroke=3)
            # DOCX stacked charts
            doc = Document()
            sec = doc.sections[0]; sec.page_width = Mm(210); sec.page_height = Mm(297)
            margin = Mm(10); sec.left_margin = sec.right_margin = margin; sec.top_margin = Mm(8); sec.bottom_margin = Mm(8)
            style = doc.styles['Normal']; style.font.name = latin_font; style.font.size = Pt(base_font)
            style._element.rPr.rFonts.set(qn('w:eastAsia'), hindi_font); style._element.rPr.rFonts.set(qn('w:cs'), hindi_font)
            add_footer(sec, brand=brand_text)
            title = doc.add_paragraph(f"{name or '—'} — Horoscope"); title.runs[0].font.size = Pt(base_font+4); title.runs[0].bold = True
            layout = doc.add_table(rows=1, cols=2); layout.autofit=False
            layout.columns[0].width = Inches(3.9); layout.columns[1].width = Inches(3.9)
            left = layout.rows[0].cells[0]
            p = left.add_paragraph("Personal Details"); p.runs[0].bold=True
            left.add_paragraph(f"Name: {name}")
            left.add_paragraph(f"DOB: {dob}  |  TOB: {tob}")
            left.add_paragraph(f"Place: {disp}")
            left.add_paragraph(f"Time Zone: {tzname} (UTC{tz_hours:+.2f})")
            left.add_paragraph("Planetary Positions").runs[0].bold=True
            t1 = left.add_table(rows=1, cols=len(df_positions.columns)); t1.autofit=False
            for i,c in enumerate(df_positions.columns): t1.rows[0].cells[i].text=c
            for _,row in df_positions.iterrows():
                r=t1.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)
            add_table_borders(t1, size=6); set_table_font(t1, pt=base_font); center_header_row(t1)
            set_col_widths(t1, [0.5,1.0,0.6,0.9,1.0,1.0])
            left.add_paragraph("Vimshottari Mahadasha").runs[0].bold=True
            t2 = left.add_table(rows=1, cols=len(df_md.columns)); t2.autofit=False
            for i,c in enumerate(df_md.columns): t2.rows[0].cells[i].text=c
            for _,row in df_md.iterrows():
                r=t2.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)
            add_table_borders(t2, size=6); set_table_font(t2, pt=base_font); center_header_row(t2)
            set_col_widths(t2, [1.0,1.0,0.8])
            left.add_paragraph("Antar / Pratyantar (Next 2 years)").runs[0].bold=True
            t3 = left.add_table(rows=1, cols=len(df_ap.columns)); t3.autofit=False
            for i,c in enumerate(df_ap.columns): t3.rows[0].cells[i].text=c
            for _,row in df_ap.iterrows():
                r=t3.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)
            add_table_borders(t3, size=6); set_table_font(t3, pt=base_font); center_header_row(t3)
            set_col_widths(t3, [1.0,1.0,1.1,0.9])
            right = layout.rows[0].cells[1]
            img_lagna.seek(0); p1 = right.paragraphs[0]; p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p1.add_run().add_picture(img_lagna, width=Inches(3.2))
            right.add_paragraph("")
            img_nav.seek(0); p2 = right.add_paragraph(); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p2.add_run().add_picture(img_nav, width=Inches(3.2))
            doc_bytes = BytesIO(); doc.save(doc_bytes); doc_bytes.seek(0)
            fname_base = sanitize_filename(name)
            st.download_button("⬇️ Download DOCX", doc_bytes.getvalue(), file_name=f"{fname_base}_Horoscope.docx")
            # PDF
            hindi_font_name = ensure_hindi_font()
            pdf_bytes = build_pdf_single_page(f"{name} — Horoscope",
                                              [f"DOB: {dob}  |  TOB: {tob}", f"Place: {disp}", f"Time Zone: {tzname} (UTC{tz_hours:+.2f})"],
                                              df_positions, df_md, df_ap,
                                              img_lagna.getvalue(), img_nav.getvalue(),
                                              brand=brand_text, hindi_font_name=hindi_font_name)
            st.download_button("⬇️ Download PDF", pdf_bytes, file_name=f"{fname_base}_Horoscope.pdf")
            # Previews
            lc, rc = st.columns([1.2,0.8])
            with lc:
                st.subheader("Planetary Positions"); st.dataframe(df_positions, use_container_width=True)
                st.subheader("Vimshottari Mahadasha"); st.dataframe(df_md, use_container_width=True)
                st.subheader("Antar / Pratyantar (Next 2 years)"); st.dataframe(df_ap, use_container_width=True)
            with rc:
                st.subheader("Lagna Kundali"); st.image(img_lagna, use_container_width=True)
                st.subheader("Navamsa Kundali"); st.image(img_nav, use_container_width=True)
        except Exception as e:
            st.error(str(e))

if __name__=='__main__':
    main()
