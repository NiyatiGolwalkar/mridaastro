import os, re, datetime, requests, pytz, math
import streamlit as st
import pandas as pd
import swisseph as swe
from timezonefinder import TimezoneFinder
from docx import Document
from io import BytesIO

st.set_page_config(page_title="Kundali – Vimshottari & Positions", layout="wide", page_icon="🪔")

# Hindi names & initials
HN = {'Su':'सूर्य','Mo':'चंद्र','Ma':'मंगल','Me':'बुध','Ju':'गुरु','Ve':'शुक्र','Sa':'शनि','Ra':'राहु','Ke':'केतु'}
HINIT = {'Su':'सू','Mo':'चं','Ma':'मं','Me':'बु','Ju':'गु','Ve':'शु','Sa':'श','Ra':'रा','Ke':'के'}
ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
NAK = 360.0/27.0
YEAR_DAYS = 365.2425

def set_sidereal():
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

def dms(deg):
    d=int(deg); m=int((deg-d)*60); s=int(round((deg-d-m/60)*3600))
    return d,m,s

def fmt_deg_sign(lon_sid):
    sign=int(lon_sid//30) + 1  # 1..12
    deg_in_sign = lon_sid % 30.0
    d,m,s=dms(deg_in_sign)
    return sign, f"{d:02d}°{m:02d}'{s:02d}\""

def kp_sublord(lon_sid):
    """Return (nakshatra_lord, sub_lord) — KP style."""
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

def ascendant_sign(jd_ut, lat, lon):
    set_sidereal()
    # Use Placidus houses; ascendant is ascmc[0]. Sidereal mode already set.
    cusps, ascmc = swe.houses_ex(jd_ut, lat, lon, b'P', swe.FLG_SIDEREAL)
    asc_lon = ascmc[0] % 360.0
    return int(asc_lon // 30) + 1  # 1..12

def positions_table(sidelons):
    rows=[]
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        lon=sidelons[code]
        sign, deg_str = fmt_deg_sign(lon)
        nak_lord, sub_lord = kp_sublord(lon)
        rows.append([HN[code], sign, deg_str, HN[nak_lord], HN[sub_lord]])
    df = pd.DataFrame(rows, columns=["Planet","Sign number","Degree","Nakshatra Lord","Sub Nakshatra Lord"])
    return df

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
    end_limit = add_years(birth_local_dt, 100.0)

    segments = []
    birth_md_start = birth_local_dt
    birth_md_end = min(add_years(birth_local_dt, rem), end_limit)
    segments.append({
        "planet": md_lord,
        "start": birth_md_start,
        "end": birth_md_end,
        "years_used": (birth_md_end - birth_md_start).days / YEAR_DAYS
    })
    idx = (ORDER.index(md_lord) + 1) % 9
    t = birth_md_end
    while t < end_limit:
        L = ORDER[idx]
        end = add_years(t, YEARS[L])
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
    return segments

def antars_in_md(md_lord, md_start, md_years):
    res=[]; t=md_start; start_idx=ORDER.index(md_lord)
    for i in range(9):
        L=ORDER[(start_idx+i)%9]
        yrs = YEARS[L]*(md_years/120.0)
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

# ---- Navamsa (D-9) ----
def navamsa_sign_for_lon(lon):
    sign_index = int(lon // 30)  # 0..11
    deg_in_sign = lon % 30.0
    pada = int((deg_in_sign * 9.0) // 30.0)  # 0..8
    sign_group = (sign_index % 12) + 1
    if sign_group in (1,5,9):
        base = 1
    elif sign_group in (2,6,10):
        base = 10
    elif sign_group in (3,7,11):
        base = 7
    else:
        base = 4
    nav_sign = ((base - 1) + pada) % 12 + 1  # 1..12
    return nav_sign

def build_navamsa_map(sidelons):
    m = {i:[] for i in range(1,13)}
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        lon = sidelons[code]
        nav_sign = navamsa_sign_for_lon(lon)
        m[nav_sign].append(HINIT[code])
    return m

# ---- North-Indian Diamond Chart (SVG) ----
def chart_mapping_D1(sidelons, asc_sign):
    """Return dict house(1..12) -> list of planet initials (Hindi) and sign numbers in each house (whole-sign from Lagna)."""
    planets_by_house = {i:[] for i in range(1,13)}
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        p_sign = int(sidelons[code] // 30) + 1
        house = ((p_sign - asc_sign) % 12) + 1
        planets_by_house[house].append(HINIT[code])
    sign_by_house = {h: ((asc_sign + h - 2) % 12) + 1 for h in range(1,13)}
    return sign_by_house, planets_by_house

def chart_mapping_D9(nav_map, asc_sign_d9):
    """nav_map is dict sign->list of planet initials. Convert to houses from D9 Lagna (whole sign)."""
    planets_by_house = {i:[] for i in range(1,13)}
    for sign in range(1,13):
        house = ((sign - asc_sign_d9) % 12) + 1
        planets_by_house[house].extend(nav_map[sign])
    sign_by_house = {h: ((asc_sign_d9 + h - 2) % 12) + 1 for h in range(1,13)}
    return sign_by_house, planets_by_house

def render_north_svg(sign_by_house, planets_by_house, title):
    # 12 fixed house centers (x,y); house 1 at top middle; then anti-clockwise
    # Coordinates tuned for 420x420 canvas
    centers = {
        1:(210,60), 2:(300,95), 3:(345,165), 4:(300,245),
        5:(345,315), 6:(300,385), 7:(210,420-60), 8:(120,385),
        9:(75,315), 10:(120,245), 11:(75,165), 12:(120,95)
    }
    # Draw frame (simple diamond + corners/edges)
    svg = [f"<svg width='420' height='420' viewBox='0 0 420 420' xmlns='http://www.w3.org/2000/svg'>"]
    svg.append("<rect x='0' y='0' width='420' height='420' fill='white'/>")
    # Outline (approx North-Indian look with lines)
    lines = [
        (210,10, 10,210),(210,10, 410,210),(10,210,210,410),(410,210,210,410), # main diamond
        (110,110,310,110),(110,310,310,310),(110,110,110,310),(310,110,310,310), # inner square
        (210,10,110,110),(210,10,310,110),(210,410,110,310),(210,410,310,310),  # connectors
        (10,210,110,110),(10,210,110,310),(410,210,310,110),(410,210,310,310)   # outer to inner
    ]
    for x1,y1,x2,y2 in lines:
        svg.append(f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='#333' stroke-width='2'/>")
    # Title
    svg.append(f"<text x='210' y='24' text-anchor='middle' font-size='16' font-weight='bold'>{title}</text>")
    # House contents
    for h in range(1,13):
        x,y = centers[h]
        sign = sign_by_house[h]
        planets = ", ".join(planets_by_house[h]) if planets_by_house[h] else ""
        svg.append(f"<text x='{x}' y='{y}' text-anchor='middle' font-size='18'>{sign}</text>")
        svg.append(f"<text x='{x}' y='{y+18}' text-anchor='middle' font-size='14'>{planets}</text>")
    svg.append("</svg>")
    return "".join(svg)

def sanitize_filename(name):
    name = (name or "").strip() or "Horoscope"
    safe = re.sub(r'[^A-Za-z0-9._ -]', '_', name)
    return f"{safe}_Horoscope.docx"

def main():
    st.title("Kundali — Report (North-Indian Charts)")

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

            # Positions + JD
            jd_ut, _, sidelons = sidereal_positions(dt_utc)

            # Ascendants
            asc_sign_d1 = ascendant_sign(jd_ut, lat, lon)

            # Planetary Positions table
            df_positions = positions_table(sidelons)

            # Vimshottari from birth
            md_segments = build_mahadashas_from_birth(dt_local, sidelons['Mo'])
            df_md = pd.DataFrame([
                {"Planet": HN[s["planet"]], "End Date": s["end"].strftime("%d-%m-%Y"),
                 "Age (at end)": round(((s["end"] - dt_local).days / YEAR_DAYS), 1)}
                for s in md_segments
            ])

            # Antar/Pratyantar next 2 years
            now_local = datetime.datetime.now()
            rows_ap = next_ant_praty_in_days(now_local, md_segments, days_window=2*365)
            df_ap = pd.DataFrame([
                {"Major Dasha": HN[r["major"]], "Antar Dasha": HN[r["antar"]],
                 "Pratyantar Dasha": HN[r["pratyantar"]], "End Date": r["end"].strftime("%d-%m-%Y")}
                for r in rows_ap
            ])

            # Navamsa sign mapping & D9 ascendant (use Moon's navamsa sign as proxy for D9 Lagna if birth time unknown.
            # Here we compute true D9 asc from D1 asc sign's navamsa? Standard practice varies; for display,
            # we will set D9 asc = navamsa of D1 asc longitude.
            asc_lon_dummy = (asc_sign_d1-1)*30.0 + 15.0  # mid of asc sign
            asc_sign_d9 = navamsa_sign_for_lon(asc_lon_dummy)
            nav_map = build_navamsa_map(sidelons)

            # Build chart mappings
            sign_by_house_d1, planets_by_house_d1 = chart_mapping_D1(sidelons, asc_sign_d1)
            sign_by_house_d9, planets_by_house_d9 = chart_mapping_D9(nav_map, asc_sign_d9)

            # Two-column app layout
            left, right = st.columns([1.2, 0.95])
            with left:
                st.subheader("Personal Details")
                st.markdown(f"**Name:** {name or '—'}  \n**Date of Birth:** {dob}  \n**Time of Birth:** {tob}  \n**Place of Birth:** {disp}")

                st.subheader("Planetary Positions")
                st.dataframe(df_positions, use_container_width=True)

                st.subheader("Vimshottari Mahadasha")
                st.dataframe(df_md, use_container_width=True)

                st.subheader("Current Antar Dasha / Pratyantar Dasha (Next 2 year)")
                st.dataframe(df_ap, use_container_width=True)

            with right:
                st.markdown("**Lagna (D-1) — North Indian**")
                st.markdown(render_north_svg(sign_by_house_d1, planets_by_house_d1, "D-1 (Lagna)"), unsafe_allow_html=True)
                st.markdown("**Navamsa (D-9) — North Indian**")
                st.markdown(render_north_svg(sign_by_house_d9, planets_by_house_d9, "D-9 (Navamsa)"), unsafe_allow_html=True)

            # DOCX export (tables as before + note: charts not embedded as diamond due to docx SVG limits)
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

            doc.add_heading("Vimshottari Mahadasha", level=2)
            t2 = doc.add_table(rows=1, cols=len(df_md.columns)); h2=t2.rows[0].cells
            for i,c in enumerate(df_md.columns): h2[i].text=c
            for _,row in df_md.iterrows():
                r=t2.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)

            doc.add_heading("Current Antar Dasha / Pratyantar Dasha (Next 2 year)", level=2)
            t3 = doc.add_table(rows=1, cols=len(df_ap.columns)); h3=t3.rows[0].cells
            for i,c in enumerate(df_ap.columns): h3[i].text=c
            for _,row in df_ap.iterrows():
                r=t3.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)

            bio = BytesIO(); doc.save(bio)
            st.download_button("⬇️ Download DOCX", bio.getvalue(), file_name=sanitize_filename(name))

        except Exception as e:
            st.error(str(e))

if __name__=='__main__':
    main()
