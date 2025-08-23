import os, datetime, json, urllib.parse, urllib.request
import streamlit as st
import pandas as pd
import swisseph as swe
from timezonefinder import TimezoneFinder
from docx import Document
from docx.shared import Inches, Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from io import BytesIO
import pytz
import matplotlib.pyplot as plt

st.set_page_config(page_title="Kundali — North Indian (Lagna & Navamsa) + Dashas",
                   layout="wide", page_icon="🪔")

# ----------------- Constants -----------------
HN = {'Su':'सूर्य','Mo':'चंद्र','Ma':'मंगल','Me':'बुध',
      'Ju':'गुरु','Ve':'शुक्र','Sa':'शनि','Ra':'राहु','Ke':'केतु'}
ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
NAK = 360.0/27.0
YEAR_DAYS = 365.2425

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

def positions_table(sidelons):
    rows=[]
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        lon=sidelons[code]
        sign, deg_str = fmt_deg_sign(lon)
        nak_lord, sub_lord = kp_sublord(lon)
        rows.append([HN[code], sign, deg_str, HN[nak_lord], HN[sub_lord]])
    return pd.DataFrame(rows, columns=["Planet","Sign number","Degree","Nakshatra Lord","Sub Nakshatra Lord"])

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
    sign = int(lon_sid//30) + 1  # 1..12
    deg_in = lon_sid % 30.0
    part = int(deg_in // (30.0/9.0))  # 0..8

    # Determine starting navamsa sign sequence by sign modality
    if sign in (1,4,7,10):       # Movable: start from same sign
        start = sign
    elif sign in (2,5,8,11):     # Fixed: start from 9th from sign
        start = ((sign + 8 - 1) % 12) + 1
    else:                        # Dual: start from 5th from sign
        start = ((sign + 4 - 1) % 12) + 1

    nav_sign = ((start - 1 + part) % 12) + 1
    return nav_sign

def render_north_diamond(house_numbers, size_px=900, font_pts=18, stroke=3):
    fig = plt.figure(figsize=(size_px/100, size_px/100), dpi=100)
    ax = fig.add_axes([0,0,1,1]); ax.axis('off')

    # Outer rectangle
    ax.plot([0.02,0.98,0.98,0.02,0.02],[0.02,0.02,0.98,0.98,0.02],
            linewidth=stroke, color='black')

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

    # House labels (sign numbers) — tuned positions
    pos = [
        (cx, T-0.06),(L+0.18, T-0.18),(L+0.08, cy),(L+0.18, B+0.18),
        (cx, B+0.06),(R-0.18, B+0.18),(R-0.08, cy),(R-0.18, T-0.18),
        (cx, cy),(cx+0.12, cy+0.12),(cx-0.12, cy+0.12),(cx-0.12, cy-0.12)
    ]
    for i,(x,y) in enumerate(pos):
        ax.text(x, y, str(house_numbers[i]), ha='center', va='center',
                fontsize=font_pts, fontweight='bold', color='black')

    buf = BytesIO(); fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.02)
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

# ----------------- App -----------------
def main():
    st.title("Kundali — North Indian (Diamond) with Navamsa + Dashas")

    c1,c2 = st.columns([1,1])
    with c1:
        name = st.text_input("Name")
        dob = st.date_input("Date of Birth",
                            min_value=datetime.date(1800,1,1),
                            max_value=datetime.date(2100,12,31))
        tob = st.time_input("Time of Birth", step=datetime.timedelta(minutes=1))
    with c2:
        place = st.text_input("Place of Birth (City, State, Country)")
        tz_override = st.text_input("UTC offset override (optional, e.g., 5.5)", "")
    api_key = st.secrets.get("GEOAPIFY_API_KEY","")

    if st.button("Generate"):
        try:
            # Geocode & time
            lat, lon, disp = geocode(place, api_key)
            dt_local = datetime.datetime.combine(dob, tob)
            if tz_override.strip():
                tz_hours = float(tz_override); dt_utc = dt_local - datetime.timedelta(hours=tz_hours); tzname=f"UTC{tz_hours:+.2f} (manual)"
            else:
                tzname, tz_hours, dt_utc = tz_from_latlon(lat, lon, dt_local)

            # Planetary positions (sidereal)
            jd_ut, _, sidelons = sidereal_positions(dt_utc)
            df_positions = positions_table(sidelons)

            # Vimshottari — full, with upcoming Antar/Pratyantar (2 yrs)
            md_segments, birth_md_lord, birth_md_rem = build_mahadashas_from_birth(dt_local, sidelons['Mo'])
            df_md = pd.DataFrame([
                {"Planet": HN[s["planet"]], "End Date": s["end"].strftime("%d-%m-%Y"),
                 "Age (at end)": round(((s["end"] - dt_local).days / YEAR_DAYS), 1)}
                for s in md_segments
            ])
            now_local = datetime.datetime.now()
            rows_ap = next_ant_praty_in_days(now_local, md_segments, days_window=2*365)
            df_ap = pd.DataFrame([
                {"Major Dasha": HN[r["major"]], "Antar Dasha": HN[r["antar"]],
                 "Pratyantar Dasha": HN[r["pratyantar"]], "End Date": r["end"].strftime("%d-%m-%Y")}
                for r in rows_ap
            ])

            # Lagna house numbers
            asc = ascendant_lon(jd_ut, lat, lon)
            house_nums_d1 = house_sign_numbers_from_asc(asc)

            # Navamsa ascendant sign and house numbers
            asc_nav_sign = navamsa_sign_of_lon(asc)
            house_nums_d9 = house_sign_numbers_from_sign(asc_nav_sign)

            # Render charts (Option A: sign/house numbers only)
            img_lagna = render_north_diamond(house_nums_d1, size_px=1000, font_pts=22, stroke=3)
            img_nav   = render_north_diamond(house_nums_d9, size_px=900, font_pts=20, stroke=3)

            # ---- Layout ----
            left, right = st.columns([1.25, 0.9])
            with left:
                st.subheader("Personal Details")
                st.markdown(f"**Name:** {name or '—'}  \n**Date of Birth:** {dob}  \n**Time of Birth:** {tob}  \n**Place of Birth:** {disp}  \n**Time Zone:** {tzname} (UTC{tz_hours:+.2f})")

                st.subheader("Planetary Positions")
                st.dataframe(df_positions, use_container_width=True)

                st.subheader("Vimshottari Mahadasha")
                st.dataframe(df_md, use_container_width=True)

                st.subheader("Current Antar / Pratyantar (Next 2 years)")
                st.dataframe(df_ap, use_container_width=True)

            with right:
                st.subheader("Lagna Kundali (D‑1) — North Indian")
                st.image(img_lagna, use_container_width=True)
                st.subheader("Navamsa Kundali (D‑9) — North Indian")
                st.image(img_nav, use_container_width=True)

            # ---- DOCX Export ----
            doc = Document()
            doc.add_heading("Kundali — North Indian (D‑1 & D‑9) with Dashas", 0)

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

            doc.add_heading("Current Antar / Pratyantar (Next 2 years)", level=2)
            t3 = doc.add_table(rows=1, cols=len(df_ap.columns)); h3=t3.rows[0].cells
            for i,c in enumerate(df_ap.columns): h3[i].text=c
            for _,row in df_ap.iterrows():
                r=t3.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)
            add_table_borders(t3, size=8); set_table_font(t3, pt=11)

            doc.add_heading("Lagna Kundali (D‑1) — North Indian", level=2)
            img_lagna.seek(0); doc.add_picture(img_lagna, width=Inches(6.0))
            doc.add_heading("Navamsa Kundali (D‑9) — North Indian", level=2)
            img_nav.seek(0); doc.add_picture(img_nav, width=Inches(6.0))

            bio = BytesIO(); doc.save(bio); bio.seek(0)
            st.download_button("⬇️ Download DOCX", bio.getvalue(), file_name="kundali_full.docx")

        except Exception as e:
            st.error(str(e))

if __name__=='__main__':
    main()
