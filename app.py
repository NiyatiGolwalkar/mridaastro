import os, datetime, requests, pytz
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

st.set_page_config(page_title="Kundali – North Indian (Diamond)", layout="wide", page_icon="🪔")

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
    sign=int(lon_sid//30) + 1
    deg_in_sign = lon_sid % 30.0
    d,m,s=dms(deg_in_sign)
    return sign, f"{d:02d}°{m:02d}'{s:02d}\\\""

def kp_sublord(lon_sid):
    ORDER_LOCAL = ORDER
    part = lon_sid % 360.0
    ni = int(part // NAK); pos = part - ni*NAK
    lord = ORDER_LOCAL[ni % 9]
    start = ORDER_LOCAL.index(lord)
    seq = [ORDER_LOCAL[(start+i)%9] for i in range(9)]
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
    import json, urllib.parse, urllib.request
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
    rows=[]
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        lon=sidelons[code]
        sign, deg_str = fmt_deg_sign(lon)
        nak_lord, sub_lord = kp_sublord(lon)
        rows.append([HN[code], sign, deg_str, HN[nak_lord], HN[sub_lord]])
    return pd.DataFrame(rows, columns=["Planet","Sign number","Degree","Nakshatra Lord","Sub Nakshatra Lord"])

# ---- Vimshottari ----
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
    segments.append({"planet": md_lord, "start": birth_md_start, "end": birth_md_end, "years_used": (birth_md_end - birth_md_start).days / YEAR_DAYS})
    idx = (ORDER.index(md_lord) + 1) % 9
    t = birth_md_end
    while t < end_limit:
        L = ORDER[idx]; end = add_years(t, YEARS[L]); 
        if end > end_limit: end = end_limit
        segments.append({"planet": L, "start": t, "end": end, "years_used": (end - t).days / YEAR_DAYS})
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

# ---- North Indian (Diamond) Chart ----
def ascendant_lon(jd_ut, lat, lon):
    set_sidereal()
    cusps, ascmc = swe.houses_ex(jd_ut, lat, lon, b'P')
    ay = swe.get_ayanamsa_ut(jd_ut)
    asc = (ascmc[0] - ay) % 360.0
    return asc

def house_sign_numbers(asc_sid):
    start = int(asc_sid//30) + 1
    return [((start-1+i)%12)+1 for i in range(12)]

def render_north_diamond(house_numbers, size_px=900, font_pts=18, stroke=3):
    """
    Strict North-Indian diamond grid (like your reference):
    - Outer rectangle
    - Both diagonals
    - Midpoint-connector lines to form 12 rhombi/triangles
    - Clean black lines only
    """
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(size_px/100, size_px/100), dpi=100)
    ax = fig.add_axes([0,0,1,1]); ax.axis('off')

    # Outer rectangle
    ax.plot([0.02,0.98,0.98,0.02,0.02],[0.02,0.02,0.98,0.98,0.02], linewidth=stroke, color='black')

    # Key points
    L,R,B,T = 0.02,0.98,0.02,0.98
    cx, cy = 0.5, 0.5
    # Diagonals
    ax.plot([L,R],[T,B], linewidth=stroke, color='black')
    ax.plot([L,R],[B,T], linewidth=stroke, color='black')

    # Mid points
    midL=(L,cy); midR=(R,cy); midT=(cx,T); midB=(cx,B)

    # Connect midpoints to form inner diamond edges
    ax.plot([midL[0], midT[0]],[midL[1], midT[1]], linewidth=stroke, color='black')
    ax.plot([midT[0], midR[0]],[midT[1], midR[1]], linewidth=stroke, color='black')
    ax.plot([midR[0], midB[0]],[midR[1], midB[1]], linewidth=stroke, color='black')
    ax.plot([midB[0], midL[0]],[midB[1], midL[1]], linewidth=stroke, color='black')

    # Place numbers in standard North-Indian reading order (starting from top diamond = 1st house if Asc there)
    # Our 'house_numbers' already encodes sign numbers in houses 1..12 order.
    # Coordinates for 12 house text placements (tuned visually)
    pos = [
        (cx, T-0.06),        # House 1 (top)
        (L+0.18, T-0.18),    # 2 (top-left)
        (L+0.08, cy),        # 3 (left mid)
        (L+0.18, B+0.18),    # 4 (bottom-left)
        (cx, B+0.06),        # 5 (bottom)
        (R-0.18, B+0.18),    # 6 (bottom-right)
        (R-0.08, cy),        # 7 (right mid)
        (R-0.18, T-0.18),    # 8 (top-right)
        (cx, cy),            # 9 (center diamond)
        (cx+0.12, cy+0.12),  # 10 (upper-right inner)
        (cx-0.12, cy+0.12),  # 11 (upper-left inner)
        (cx-0.12, cy-0.12),  # 12 (lower-left inner)
    ]
    for i,(x,y) in enumerate(pos):
        ax.text(x, y, str(house_numbers[i]), ha='center', va='center', fontsize=font_pts, fontweight='bold', color='black')

    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.02)
    plt.close(fig); buf.seek(0)
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
                for r in p.runs: r.font.size = Pt(pt)

def main():
    st.title("Lagna Kundali (North Indian – Diamond)")

    c1,c2 = st.columns([1,1])
    with c1:
        name = st.text_input("Name")
        dob = st.date_input("Date of Birth")
        tob = st.time_input("Time of Birth")
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

            # Positions
            jd_ut, _, sidelons = sidereal_positions(dt_utc)
            df_positions = positions_table(sidelons)

            # Ascendant and house numbers (sign numbers rotated by Lagna)
            asc = ascendant_lon(jd_ut, lat, lon)
            house_nums = house_sign_numbers(asc)

            # Render precise North diamond (Option A: house/sign numbers only)
            img_lagna = render_north_diamond(house_nums, size_px=1000, font_pts=22, stroke=3)

            left, right = st.columns([1.2, 0.9])
            with left:
                st.subheader("Personal Details")
                st.markdown(f"**Name:** {name or '—'}  \n**Date of Birth:** {dob}  \n**Time of Birth:** {tob}  \n**Place of Birth:** {disp}  \n**Time Zone:** {tzname} (UTC{tz_hours:+.2f})")

                st.subheader("Planetary Positions")
                st.dataframe(df_positions, use_container_width=True)

            with right:
                st.subheader("Lagna Kundali (North)")
                st.image(img_lagna, use_container_width=True)

            # DOCX export
            doc = Document()
            doc.add_heading("Kundali — North Indian (Diamond)", 0)

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

            doc.add_heading("Lagna Kundali (North)", level=2)
            img_lagna.seek(0); doc.add_picture(img_lagna, width=Inches(6.0))

            bio = BytesIO(); doc.save(bio); bio.seek(0)
            st.download_button("⬇️ Download DOCX", bio.getvalue(), file_name="kundali_north.docx")

        except Exception as e:
            st.error(str(e))

if __name__=='__main__':
    main()
