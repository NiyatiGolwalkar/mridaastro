import os, datetime, requests, pytz, math
import streamlit as st
import pandas as pd
import swisseph as swe
from timezonefinder import TimezoneFinder
from docx import Document
from docx.shared import Inches, Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from io import BytesIO
import matplotlib.pyplot as plt

st.set_page_config(page_title="Kundali – Vimshottari & Positions", layout="wide", page_icon="🪔")

HN = {'Su':'सूर्य','Mo':'चंद्र','Ma':'मंगल','Me':'बुध','Ju':'गुरु','Ve':'शुक्र','Sa':'शनि','Ra':'राहु','Ke':'केतु'}
ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
NAK = 360.0/27.0
YEAR_DAYS = 365.2425

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
    return sign, f"{d:02d}°{m:02d}'{s:02d}\\\""

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
        raise RuntimeError("Geoapify key missing. Add GEOAPIFY_API_KEY in Secrets.")
    url="https://api.geoapify.com/v1/geocode/search"
    r=requests.get(url, params={"text":place, "format":"json", "limit":1, "apiKey":api_key}, timeout=12)
    j=r.json()
    if r.status_code!=200:
        raise RuntimeError(f"Geoapify {r.status_code}: {j.get('message', str(j)[:150])}")
    if j.get("results"):
        res=j["results"][0]
        return float(res["lat"]), float(res["lon"]), res.get("formatted", place)
    if j.get("features"):
        lon,lat=j["features"][0]["geometry"]["coordinates"]; return float(lat), float(lon), place
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
    jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600)
    set_sidereal()
    ay = swe.get_ayanamsa_ut(jd)
    flags=swe.FLG_MOSEPH
    out = {}
    for code, p in [('Su',swe.SUN),('Mo',swe.MOON),('Ma',swe.MARS),('Me',swe.MERCURY),
                    ('Ju',swe.JUPITER),('Ve',swe.VENUS),('Sa',swe.SATURN),('Ra',swe.MEAN_NODE)]:
        xx,_ = swe.calc_ut(jd, p, flags)
        out[code] = (xx[0] - ay) % 360.0
    out['Ke'] = (out['Ra'] + 180.0) % 360.0
    return jd, ay, out

def positions_table(sidelons):
    rows_disp=[]; rows_kp=[]
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        lon=sidelons[code]
        sign, deg_str = fmt_deg_sign(lon)
        nak_lord, sub_lord = kp_sublord(lon)
        rows_disp.append([HN[code], sign, deg_str, HN[nak_lord], HN[sub_lord]])
        rows_kp.append([HN[code], sign, deg_str, HN[nak_lord], HN[sub_lord]])
    df_display = pd.DataFrame(rows_disp, columns=["Planet","Sign number","Degree","Nakshatra Lord","Sub Nakshatra Lord"])
    df_kp = pd.DataFrame(rows_kp, columns=["Planet","Sign","Degree","Lord","Sub-Lord"])
    return df_display, df_kp

# ---- Vimshottari ----
def moon_balance(moon_sid):
    part = moon_sid % 360.0
    ni = int(part // NAK)
    pos = part - ni*NAK
    md_lord = ORDER[ni % 9]
    frac = pos/NAK
    remaining_years = YEARS[md_lord]*(1 - frac)
    return md_lord, remaining_years

def add_years(dt, y):
    return dt + datetime.timedelta(days=y*YEAR_DAYS)

def build_mahadashas_from_birth(birth_local_dt, moon_sid):
    md_lord, rem = moon_balance(moon_sid)
    end_limit = add_years(birth_local_dt, 100.0)  # cap at 100 years

    segments = []

    # 1) Birth partial MD
    birth_md_start = birth_local_dt
    birth_md_end = min(add_years(birth_md_start, rem), end_limit)
    segments.append({
        "planet": md_lord,
        "start": birth_md_start,
        "end": birth_md_end,
        "years_used": (birth_md_end - birth_md_start).days / YEAR_DAYS
    })

    # 2) Subsequent full MDs (clamp last if needed)
    idx = (ORDER.index(md_lord) + 1) % 9
    t = birth_md_end
    while t < end_limit:
        L = ORDER[idx]
        full_years = YEARS[L]
        end = add_years(t, full_years)
        if end > end_limit:
            end = end_limit
        segments.append({
            "planet": L,
            "start": t,
            "end": end,
            "years_used": (end - t).days / YEAR_DAYS
        })
        t = end
        idx = (idx + 1) % 9

    return segments, md_lord, rem

def antars_in_md(md_lord, md_start, md_years):
    res=[]; t=md_start; start_idx=ORDER.index(md_lord)
    for i in range(9):
        L=ORDER[(start_idx+i)%9]
        yrs = YEARS[L]*(md_years/120.0)  # proportional share
        days = yrs*YEAR_DAYS
        start = t
        end = t + datetime.timedelta(days=days)
        res.append((L, start, end, yrs))
        t = end
    return res

def pratyantars_in_antar(antar_lord, antar_start, antar_years):
    res=[]; t=antar_start; start_idx=ORDER.index(antar_lord)
    for i in range(9):
        L=ORDER[(start_idx+i)%9]
        yrs = YEARS[L]*(antar_years/120.0)
        days = yrs*YEAR_DAYS
        start = t
        end = t + datetime.timedelta(days=days)
        res.append((L, start, end))
        t = end
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

# ---- Kundali (North) Chart ----
def ascendant_lon(jd_ut, lat, lon):
    set_sidereal()
    # houses_ex returns (cusps, ascmc); ascmc[0] is Ascendant (tropical).
    cusps, ascmc = swe.houses_ex(jd_ut, lat, lon, b'P')  # Placidus for Asc calc
    ay = swe.get_ayanamsa_ut(jd_ut)
    asc = (ascmc[0] - ay) % 360.0  # sidereal
    return asc

def house_sign_numbers(asc_sid):
    start = int(asc_sid//30) + 1
    return [( (start-1+i) % 12 ) + 1 for i in range(12)]

def render_north_chart(sign_numbers, title="Lagna Kundali", size_px=900, font_pts=18, stroke=6):
    # Diamond style using matplotlib
    fig = plt.figure(figsize=(size_px/100, size_px/100), dpi=100)
    ax = fig.add_axes([0,0,1,1])
    ax.axis('off')

    # Outer rounded rectangle
    from matplotlib.patches import FancyBboxPatch
    pad = 0.02
    rect = FancyBboxPatch((pad, pad), 1-2*pad, 1-2*pad,
                          boxstyle="round,pad=0.02,rounding_size=0.025",
                          linewidth=stroke/2, fill=False)
    ax.add_patch(rect)

    # Diamond grid
    # Coordinates of diamond corners
    cx, cy = 0.5, 0.5
    s = 0.9
    corners = [(cx, cy+s/2),(cx+s/2, cy),(cx, cy-s/2),(cx-s/2, cy)]
    # Diagonals
    ax.plot([corners[0][0], corners[2][0]],[corners[0][1], corners[2][1]],linewidth=stroke)
    ax.plot([corners[1][0], corners[3][0]],[corners[1][1], corners[3][1]],linewidth=stroke)
    # Inner diamonds
    def line(p,q): ax.plot([p[0],q[0]],[p[1],q[1]],linewidth=stroke/1.2)
    line(((corners[0][0]+corners[3][0])/2,(corners[0][1]+corners[3][1])/2),
         ((corners[0][0]+corners[1][0])/2,(corners[0][1]+corners[1][1])/2))
    line(((corners[1][0]+corners[0][0])/2,(corners[1][1]+corners[0][1])/2),
         ((corners[1][0]+corners[2][0])/2,(corners[1][1]+corners[2][1])/2))
    line(((corners[2][0]+corners[1][0])/2,(corners[2][1]+corners[1][1])/2),
         ((corners[2][0]+corners[3][0])/2,(corners[2][1]+corners[3][1])/2))
    line(((corners[3][0]+corners[2][0])/2,(corners[3][1]+corners[2][1])/2),
         ((corners[3][0]+corners[0][0])/2,(corners[3][1]+corners[0][1])/2))

    # House number placements (English numerals as requested earlier)
    positions = [
        (0.50,0.77),(0.66,0.66),(0.77,0.50),(0.66,0.34),
        (0.50,0.23),(0.34,0.34),(0.23,0.50),(0.34,0.66),
        (0.50,0.50),(0.58,0.58),(0.42,0.58),(0.42,0.42)
    ]
    for i, (x,y) in enumerate(positions[:12]):
        ax.text(x, y, str(sign_numbers[i]), ha='center', va='center', fontsize=font_pts, fontweight='bold')

    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.02)
    plt.close(fig)
    buf.seek(0)
    return buf

# ---- DOCX helpers ----
def add_table_borders(table, size=8):
    for row in table.rows:
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            tcBorders = OxmlElement('w:tcBorders')
            for edge in ('top','left','bottom','right'):
                el = OxmlElement(f'w:{edge}')
                el.set(qn('w:val'), 'single'); el.set(qn('w:sz'), str(size))
                tcBorders.append(el)
            tcPr.append(tcBorders)

def set_table_font(table, pt=11):
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(pt)

def draw_blank_box(doc, title):
    p = doc.add_paragraph(title)
    p.runs[0].bold = True
    t = doc.add_table(rows=8, cols=8)
    add_table_borders(t, size=8)
    doc.add_paragraph("")

def main():
    st.title("Kundali — Report Layout")

    # Inputs
    c1,c2 = st.columns([1,1])
    with c1:
        name = st.text_input("Name")
        dob = st.date_input("Date of Birth", min_value=datetime.date(1900,1,1), max_value=datetime.date.today())
        tob = st.time_input("Time of Birth", step=datetime.timedelta(minutes=1))
    with c2:
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

            # Compute positions
            jd_ut, _, sidelons = sidereal_positions(dt_utc)
            df_positions, _ = positions_table(sidelons)

            # Mahadashas from birth
            md_segments, birth_md_lord, birth_md_rem = build_mahadashas_from_birth(dt_local, sidelons['Mo'])

            # Vimshottari Mahadasha table
            df_md = pd.DataFrame([
                {
                    "Planet": HN[s["planet"]],
                    "End Date": s["end"].strftime("%d-%m-%Y"),
                    "Age (at end)": round(((s["end"] - dt_local).days / YEAR_DAYS), 1),
                }
                for s in md_segments
            ])

            # Antar/Pratyantar (next 2 years)
            now_local = datetime.datetime.now()
            rows_ap = next_ant_praty_in_days(now_local, md_segments, days_window=2*365)
            df_ap = pd.DataFrame([
                {
                    "Major Dasha": HN[r["major"]],
                    "Antar Dasha": HN[r["antar"]],
                    "Pratyantar Dasha": HN[r["pratyantar"]],
                    "End Date": r["end"].strftime("%d-%m-%Y"),
                }
                for r in rows_ap
            ])

            # House numbers for D-1 (sidereal asc)
            asc = ascendant_lon(jd_ut, lat, lon)
            house_nums = house_sign_numbers(asc)

            # Render high-visibility Lagna & Navamsa placeholders (same house numbers for demo here)
            img_lagna = render_north_chart(house_nums, title="Lagna Kundali", size_px=1000, font_pts=20, stroke=8)
            img_nav = render_north_chart(house_nums, title="Navamsa Kundali", size_px=800, font_pts=18, stroke=7)

            # Two-column display
            left, right = st.columns([1.2, 0.8])
            with left:
                st.subheader("Personal Details")
                st.markdown(f"**Name:** {name or '—'}  \n**Date of Birth:** {dob}  \n**Time of Birth:** {tob}  \n**Place of Birth:** {disp}  \n**Time Zone:** {tzname} (UTC{tz_hours:+.2f})")

                st.subheader("Planetary Positions")
                st.dataframe(df_positions, use_container_width=True)

                st.subheader("Vimshottari Mahadasha")
                st.dataframe(df_md, use_container_width=True)

                st.subheader("Current Antar Dasha / Pratyantar Dasha (Next 2 year)")
                st.dataframe(df_ap, use_container_width=True)

            with right:
                st.subheader("Lagna Kundali")
                st.image(img_lagna, use_container_width=True)
                st.subheader("Navamsa Kundali")
                st.image(img_nav, use_container_width=True)

            # DOCX export
            doc = Document()
            doc.add_heading("Kundali — Report", 0)

            doc.add_heading("Personal Details", level=2)
            doc.add_paragraph(f"Name: {name}")
            doc.add_paragraph(f"Date of Birth: {dob}")
            doc.add_paragraph(f"Time of Birth: {tob}")
            doc.add_paragraph(f"Place of Birth: {disp} (UTC{tz_hours:+.2f})")

            doc.add_heading("Planetary Positions", level=2)
            t1 = doc.add_table(rows=1, cols=len(df_positions.columns)); hdr=t1.rows[0].cells
            for i,c in enumerate(df_positions.columns): hdr[i].text=c
            for _,row in df_positions.iterrows():
                r=t1.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)
            add_table_borders(t1, size=8); set_table_font(t1, pt=11)

            doc.add_heading("Vimshottari Mahadasha", level=2)
            t2 = doc.add_table(rows=1, cols=len(df_md.columns)); h2=t2.rows[0].cells
            for i,c in enumerate(df_md.columns): h2[i].text=c
            for _,row in df_md.iterrows():
                r=t2.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)
            add_table_borders(t2, size=8); set_table_font(t2, pt=11)

            doc.add_heading("Current Antar Dasha / Pratyantar Dasha (Next 2 year)", level=2)
            t3 = doc.add_table(rows=1, cols=len(df_ap.columns)); h3=t3.rows[0].cells
            for i,c in enumerate(df_ap.columns): h3[i].text=c
            for _,row in df_ap.iterrows():
                r=t3.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)
            add_table_borders(t3, size=8); set_table_font(t3, pt=11)

            # Insert rendered Kundali images with complete borders
            doc.add_heading("Lagna Kundali (North)", level=2)
            img_lagna.seek(0); doc.add_picture(img_lagna, width=Inches(5.8))

            doc.add_heading("Navamsa Kundali (North)", level=2)
            img_nav.seek(0); doc.add_picture(img_nav, width=Inches(5.8))

            bio = BytesIO(); doc.save(bio); bio.seek(0)
            st.download_button("⬇️ Download DOCX", bio.getvalue(), file_name="kundali_report.docx")

        except Exception as e:
            st.error(str(e))

if __name__=='__main__':
    main()
