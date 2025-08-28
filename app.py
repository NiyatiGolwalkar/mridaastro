
import os, io, datetime, json, urllib.parse, urllib.request
import streamlit as st
import pandas as pd
import swisseph as swe
from timezonefinder import TimezoneFinder
from docx import Document
from docx.shared import Inches, Pt, Mm
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ROW_HEIGHT_RULE
from io import BytesIO
import pytz
import matplotlib.pyplot as plt

APP_TITLE = "DevoAstroBhav Kundali (Editable Kundali in DOCX)"
st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon="🪔")

BASE_FONT_PT = 8.5
LATIN_FONT = "Georgia"
HINDI_FONT = "Mangal"

HN = {'Su':'सूर्य','Mo':'चंद्र','Ma':'मंगल','Me':'बुध','Ju':'गुरु','Ve':'शुक्र','Sa':'शनि','Ra':'राहु','Ke':'केतु'}

def set_sidereal():
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

def dms(deg):
    d=int(deg); m=int((deg-d)*60); s=int(round((deg-d-m/60)*3600))
    if s==60: s=0; m+=1
    if m==60: m=0; d+=1
    return d,m,s

def fmt_deg_sign(lon_sid):
    sign=int(lon_sid//30) + 1
    deg_in_sign = lon_sid % 30.0
    d,m,s=dms(deg_in_sign)
    return sign, f\"{d:02d}°{m:02d}'{s:02d}\\\"\"

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
        raise RuntimeError(\"Geoapify key missing. Add GEOAPIFY_API_KEY in Streamlit Secrets.\")
    base=\"https://api.geoapify.com/v1/geocode/search?\"
    q = urllib.parse.urlencode({\"text\":place, \"format\":\"json\", \"limit\":1, \"apiKey\":api_key})
    with urllib.request.urlopen(base+q, timeout=15) as r:
        j = json.loads(r.read().decode())
    if j.get(\"results\"):
        res=j[\"results\"][0]
        return float(res[\"lat\"]), float(res[\"lon\"]), res.get(\"formatted\", place)
    raise RuntimeError(\"Place not found.\")

def tz_from_latlon(lat, lon, dt_local):
    tf = TimezoneFinder()
    tzname = tf.timezone_at(lat=lat, lng=lon) or \"Etc/UTC\"
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

def ascendant_sign(jd, lat, lon, ay):
    # tropical ascendant from houses_ex, then convert to sidereal
    _, ascmc, _ = swe.houses_ex(jd, lat, lon, b'P')
    asc_trop = ascmc[0]
    asc_sid = (asc_trop - ay) % 360.0
    return int(asc_sid // 30) + 1, asc_sid

def navamsa_sign_from_lon_sid(lon_sid):
    sign = int(lon_sid // 30) + 1
    deg_in_sign = lon_sid % 30.0
    pada = int(deg_in_sign // (30.0/9.0))  # 0..8
    if sign % 2 == 1:  # odd sign
        nav = (sign + pada - 1) % 12 + 1
    else:
        start = (sign + 8 - 1) % 12 + 1  # starts from 9th sign for even signs
        nav = (start + pada - 1) % 12 + 1
    return nav

def positions_table_no_symbol(sidelons):
    rows=[]
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        lon=sidelons[code]
        sign, deg_str = fmt_deg_sign(lon)
        nak_lord, sub_lord = kp_sublord(lon)
        rows.append([HN[code], sign, deg_str, HN[nak_lord], HN[sub_lord]])
    cols = [\"Planet\",\"Sign\",\"Degree\",\"Nakshatra\",\"Sub‑Nakshatra\"]
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
    segments.append({\"planet\": md_lord, \"start\": birth_md_start, \"end\": birth_md_end, \"years_used\": (birth_md_end - birth_md_start).days / 365.2425})
    idx = (ORDER.index(md_lord) + 1) % 9
    t = birth_md_end
    while t < end_limit:
        L = ORDER[idx]; end = add_years(t, YEARS[L])
        if end > end_limit: end = end_limit
        segments.append({\"planet\": L, \"start\": t, \"end\": end, \"years_used\": (end - t).days / 365.2425})
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
        MD = seg[\"planet\"]; ms = seg[\"start\"]; me = seg[\"end\"]
        md_years_effective = seg[\"years_used\"]
        for AL, as_, ae, ay in antars_in_md(MD, ms, md_years_effective):
            if ae < now_local or as_ > horizon: continue
            for PL, ps, pe in pratyantars_in_antar(AL, as_, ay):
                if pe < now_local or ps > horizon: continue
                rows.append({\"major\":MD,\"antar\":AL,\"pratyantar\":PL,\"end\":pe})
    rows.sort(key=lambda r:r[\"end\"])
    return rows

def render_north_diamond(size_px=900, stroke=3):
    fig = plt.figure(figsize=(size_px/100, size_px/100), dpi=100)
    ax = fig.add_axes([0,0,1,1]); ax.axis('off')
    ax.plot([0.02,0.98,0.98,0.02,0.02],[0.02,0.02,0.98,0.98,0.02], linewidth=3, color='black')
    L,R,B,T = 0.02,0.98,0.02,0.98
    cx, cy = 0.5, 0.5
    ax.plot([L,R],[T,B], linewidth=3, color='black')
    ax.plot([L,R],[B,T], linewidth=3, color='black')
    midL=(L,cy); midR=(R,cy); midT=(cx,T); midB=(cx,B)
    ax.plot([midL[0], midT[0]],[midL[1], midT[1]], linewidth=3, color='black')
    ax.plot([midT[0], midR[0]],[midT[1], midR[1]], linewidth=3, color='black')
    ax.plot([midR[0], midB[0]],[midR[1], midB[1]], linewidth=3, color='black')
    ax.plot([midB[0], midL[0]],[midB[1], midL[1]], linewidth=3, color='black')
    buf = BytesIO(); fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.02)
    plt.close(fig); buf.seek(0); return buf

def rotated_house_labels(lagna_sign):
    order = [str(((lagna_sign - 1 + i) % 12) + 1) for i in range(12)]
    mapping = {
        \"1\": order[0],  \"2\": order[1],  \"3\": order[2],  \"4\": order[3],
        \"5\": order[4],  \"6\": order[5],  \"7\": order[6],  \"8\": order[7],
        \"9\": order[8], \"10\": order[9], \"11\": order[10], \"12\": order[11],
    }
    return mapping

def kundali_w_p_with_centroid_labels(size_pt=220, lagna_sign=1):
    # Size kept at 220pt so it fits in ~3.3in column without clipping
    S=size_pt; L,T,R,B=0,0,S,S
    TM=(S/2,0); RM=(S,S/2); BM=(S/2,S); LM=(0,S/2)
    P_lt=(S/4,S/4); P_rt=(3*S/4,S/4); P_rb=(3*S/4,3*S/4); P_lb=(S/4,3*S/4); O=(S/2,S/2)

    labels = rotated_house_labels(lagna_sign)

    houses = {
        \"1\":  [TM, P_rt, O, P_lt],
        \"2\":  [(0,0), TM, P_lt],
        \"3\":  [(0,0), LM, P_lt],
        \"4\":  [LM, O, P_lt, P_lb],
        \"5\":  [LM, (0,S), P_lb],
        \"6\":  [(0,S), BM, P_lb],
        \"7\":  [BM, P_rb, O, P_lb],
        \"8\":  [BM, (S,S), P_rb],
        \"9\":  [RM, (S,S), P_rb],
        \"10\": [RM, O, P_rt, P_rb],
        \"11\": [(S,0), RM, P_rt],
        \"12\": [TM, (S,0), P_rt],
    }

    def centroid(poly):
        A=Cx=Cy=0.0; n=len(poly)
        for i in range(n):
            x1,y1=poly[i]; x2,y2=poly[(i+1)%n]
            cross=x1*y2 - x2*y1
            A += cross; Cx += (x1+x2)*cross; Cy += (y1+y2)*cross
        A*=0.5
        if abs(A)<1e-9:
            xs,ys=zip(*poly); return (sum(xs)/n, sum(ys)/n)
        return (Cx/(6*A), Cy/(6*A))

    w=h=20; boxes=[]
    for k,poly in houses.items():
        x,y = centroid(poly); left = x - w/2; top = y - h/2
        txt = labels[k]
        boxes.append(f'''
        <v:rect style=\"position:absolute;left:{left}pt;top:{top}pt;width:{w}pt;height:{h}pt;z-index:5\" strokecolor=\"none\">
          <v:textbox inset=\"0,0,0,0\">
            <w:txbxContent xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">
              <w:p><w:pPr><w:jc w:val=\"center\"/></w:pPr><w:r><w:t>{txt}</w:t></w:r></w:p>
            </w:txbxContent>
          </v:textbox>
        </v:rect>
        ''')
    boxes_xml = "\\n".join(boxes)

    xml = f'''
    <w:p xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">
      <w:r>
        <w:pict xmlns:v=\"urn:schemas-microsoft-com:vml\" xmlns:o=\"urn:schemas-microsoft-com:office:office\" xmlns:w10=\"urn:schemas-microsoft-com:office:word\">
          <v:group style=\"position:relative;margin-left:0;margin-top:0;width:{S}pt;height:{S}pt\" coordorigin=\"0,0\" coordsize=\"{S},{S}\">
            <v:rect style=\"position:absolute;left:0;top:0;width:{S}pt;height:{S}pt;z-index:1\" strokecolor=\"black\" strokeweight=\"1.5pt\" fillcolor=\"#fff2cc\"/>
            <v:line style=\"position:absolute;z-index:2\" from=\"{L},{T}\" to=\"{R},{B}\" strokecolor=\"black\" strokeweight=\"1.5pt\"/>
            <v:line style=\"position:absolute;z-index:2\" from=\"{R},{T}\" to=\"{L},{B}\" strokecolor=\"black\" strokeweight=\"1.5pt\"/>
            <v:line style=\"position:absolute;z-index:2\" from=\"{S/2},{T}\" to=\"{R},{S/2}\" strokecolor=\"black\" strokeweight=\"1.5pt\"/>
            <v:line style=\"position:absolute;z-index:2\" from=\"{R},{S/2}\" to=\"{S/2},{B}\" strokecolor=\"black\" strokeweight=\"1.5pt\"/>
            <v:line style=\"position:absolute;z-index:2\" from=\"{S/2},{B}\" to=\"{L},{S/2}\" strokecolor=\"black\" strokeweight=\"1.5pt\"/>
            <v:line style=\"position:absolute;z-index:2\" from=\"{L},{S/2}\" to=\"{S/2},{T}\" strokecolor=\"black\" strokeweight=\"1.5pt\"/>
            {boxes_xml}
          </v:group>
        </w:pict>
      </w:r>
    </w:p>
    '''
    return parse_xml(xml)

def add_table_borders(table, size=6):
    tbl = table._tbl
    tblPr = tbl.tblPr
    tblBorders = OxmlElement('w:tblBorders')
    for edge in ('top','left','bottom','right','insideH','insideV'):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), str(size))
        tblBorders.append(el)
    tblPr.append(tblBorders)

def set_table_font(table, pt=8.5):
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for r in p.runs: r.font.size = Pt(pt)

def center_header_row(table):
    for cell in table.rows[0].cells:
        for par in cell.paragraphs:
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if par.runs: par.runs[0].bold = True

def set_col_widths(table, widths_inch):
    table.autofit = False
    for row in table.rows:
        for i, w in enumerate(widths_inch):
            row.cells[i].width = Inches(w)

def sanitize_filename(name: str) -> str:
    if not name: return \"Horoscope\"
    cleaned = \"\".join(ch for ch in name if ch.isalnum() or ch in \"_- \")
    cleaned = cleaned.strip().replace(\" \", \"_\")
    return cleaned or \"Horoscope\"

def main():
    st.title(APP_TITLE)

    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input(\"Name\")
        dob = st.date_input(\"Date of Birth\", min_value=datetime.date(1800,1,1), max_value=datetime.date(2100,12,31))
        tob = st.time_input(\"Time of Birth\", step=datetime.timedelta(minutes=1))
    with col2:
        place = st.text_input(\"Place of Birth (City, State, Country)\")
        tz_override = st.text_input(\"UTC offset override (optional, e.g., 5.5)\", \"\")
    api_key = st.secrets.get(\"GEOAPIFY_API_KEY\",\"\")

    if st.button(\"Generate DOCX\"):
        try:
            lat, lon, disp = geocode(place, api_key)
            dt_local = datetime.datetime.combine(dob, tob)
            if tz_override.strip():
                tz_hours = float(tz_override); dt_utc = dt_local - datetime.timedelta(hours=tz_hours); tzname=f\"UTC{tz_hours:+.2f} (manual)\"
            else:
                tzname, tz_hours, dt_utc = tz_from_latlon(lat, lon, dt_local)

            jd, ay, sidelons = sidereal_positions(dt_utc)

            # Ascendant sign (Rāśi) and Navāṁśa Lagna
            lagna_sign, asc_sid = ascendant_sign(jd, lat, lon, ay)
            nav_lagna_sign = navamsa_sign_from_lon_sid(asc_sid)

            df_positions = positions_table_no_symbol(sidelons)

            md_segments, _, _ = build_mahadashas_from_birth(dt_local, sidelons['Mo'])
            df_md = pd.DataFrame([
                {\"Planet\": HN[s[\"planet\"]], \"End Date\": s[\"end\"].strftime(\"%d-%m-%Y\"),
                 \"Age (at end)\": int(((s[\"end\"] - dt_local).days / 365.2425))}
                for s in md_segments
            ])

            now_local = datetime.datetime.now()
            rows_ap = next_ant_praty_in_days(now_local, md_segments, days_window=2*365)
            df_ap = pd.DataFrame([
                {\"Major Dasha\": HN[r[\"major\"]], \"Antar Dasha\": HN[r[\"antar\"]],
                 \"Pratyantar Dasha\": HN[r[\"pratyantar\"]], \"End Date\": r[\"end\"].strftime(\"%d-%m-%Y\")}
                for r in rows_ap
            ])

            # Web preview images
            img_lagna = render_north_diamond(size_px=900, stroke=3)
            img_nav   = render_north_diamond(size_px=900, stroke=3)

            # Build DOCX
            doc = Document()
            sec = doc.sections[0]
            sec.page_width = Mm(210); sec.page_height = Mm(297)
            margin = Mm(12)
            sec.left_margin = sec.right_margin = margin
            sec.top_margin = Mm(10); sec.bottom_margin = Mm(10)

            style = doc.styles['Normal']
            style.font.name = LATIN_FONT; style.font.size = Pt(BASE_FONT_PT)
            style._element.rPr.rFonts.set(qn('w:eastAsia'), HINDI_FONT)
            style._element.rPr.rFonts.set(qn('w:cs'), HINDI_FONT)

            title = doc.add_paragraph(f\"{name or '—'} — Horoscope\")
            title.runs[0].font.size = Pt(BASE_FONT_PT+3); title.runs[0].bold = True

            outer = doc.add_table(rows=1, cols=2); outer.autofit=False
            right_width_in = 3.3
            outer.columns[0].width = Inches(3.3)
            outer.columns[1].width = Inches(right_width_in)
            add_table_borders(outer, size=6)

            left = outer.rows[0].cells[0]
            p = left.add_paragraph(\"Personal Details\"); p.runs[0].bold=True
            left.add_paragraph(f\"Name: {name}\")
            left.add_paragraph(f\"DOB: {dob}  |  TOB: {tob}\")
            left.add_paragraph(f\"Place: {disp}\")
            left.add_paragraph(f\"Time Zone: {tzname} (UTC{tz_hours:+.2f})\")

            left.add_paragraph(\"Planetary Positions\").runs[0].bold=True
            t1 = left.add_table(rows=1, cols=len(df_positions.columns)); t1.autofit=False
            for i,c in enumerate(df_positions.columns): t1.rows[0].cells[i].text=c
            for _,row in df_positions.iterrows():
                r=t1.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)
            center_header_row(t1); set_table_font(t1, pt=BASE_FONT_PT); add_table_borders(t1, size=6)
            set_col_widths(t1, [0.8,0.4,0.7,0.7,0.7])

            left.add_paragraph(\"Vimshottari Mahadasha\").runs[0].bold=True
            t2 = left.add_table(rows=1, cols=len(df_md.columns)); t2.autofit=False
            for i,c in enumerate(df_md.columns): t2.rows[0].cells[i].text=c
            for _,row in df_md.iterrows():
                r=t2.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)
            center_header_row(t2); set_table_font(t2, pt=BASE_FONT_PT); add_table_borders(t2, size=6)
            set_col_widths(t2, [1.1,1.0,1.0])

            left.add_paragraph(\"Antar / Pratyantar (Next 2 years)\").runs[0].bold=True
            t3 = left.add_table(rows=1, cols=len(df_ap.columns)); t3.autofit=False
            for i,c in enumerate(df_ap.columns): t3.rows[0].cells[i].text=c
            for _,row in df_ap.iterrows():
                r=t3.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)
            center_header_row(t3); set_table_font(t3, pt=BASE_FONT_PT); add_table_borders(t3, size=6)
            set_col_widths(t3, [0.9,0.9,0.9,0.6])

            right = outer.rows[0].cells[1]

            # Stack kundalis in a 2-row table; row height and spacers to avoid overlap
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            kt = right.add_table(rows=2, cols=1); kt.autofit=False
            kt.columns[0].width = Inches(right_width_in)
            for row in kt.rows:
                row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
                row.height = Pt(280)

            # Row 1: Lagna chart with dynamic numbering
            cell1 = kt.rows[0].cells[0]
            cell1.add_paragraph()  # spacer
            p1 = cell1.add_paragraph()
            p1._p.addnext(kundali_w_p_with_centroid_labels(size_pt=220, lagna_sign=lagna_sign))
            cap1 = cell1.add_paragraph(\"लग्न कुंडली\")
            cap1.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if cap1.runs: cap1.runs[0].bold = True
            cell1.add_paragraph()  # spacer

            # Row 2: Navamsa chart with dynamic numbering
            cell2 = kt.rows[1].cells[0]
            cell2.add_paragraph()  # spacer
            p2 = cell2.add_paragraph()
            p2._p.addnext(kundali_w_p_with_centroid_labels(size_pt=220, lagna_sign=nav_lagna_sign))
            cap2 = cell2.add_paragraph(\"नवांश कुंडली\")
            cap2.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if cap2.runs: cap2.runs[0].bold = True
            cell2.add_paragraph()  # spacer

            out = BytesIO(); doc.save(out); out.seek(0)
            st.download_button(\"⬇️ Download DOCX\", out.getvalue(), file_name=f\"{sanitize_filename(name)}_Horoscope.docx\")

            # Web preview
            lc, rc = st.columns([1.2, 0.8])
            with lc:
                st.subheader(\"Planetary Positions\")
                st.dataframe(df_positions.reset_index(drop=True), use_container_width=True, hide_index=True)
                st.subheader(\"Vimshottari Mahadasha\")
                st.dataframe(df_md.reset_index(drop=True), use_container_width=True, hide_index=True)
                st.subheader(\"Antar / Pratyantar (Next 2 years)\")
                st.dataframe(df_ap.reset_index(drop=True), use_container_width=True, hide_index=True)
            with rc:
                st.subheader(\"Lagna Kundali (Preview)\")
                st.image(img_lagna, use_container_width=True)
                st.subheader(\"Navamsa Kundali (Preview)\")
                st.image(img_nav, use_container_width=True)

        except Exception as e:
            st.error(str(e))

if __name__=='__main__':
    main()
