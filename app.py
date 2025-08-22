import os, datetime, requests, pytz
import streamlit as st
import pandas as pd
import swisseph as swe
from timezonefinder import TimezoneFinder
from docx import Document
from io import BytesIO

st.set_page_config(page_title="Kundali – Hindi KP (Mahadasha + Antar/Pratyantar)", layout="wide", page_icon="🪔")

HN = {'Su':'सूर्य','Mo':'चंद्र','Ma':'मंगल','Me':'बुध','Ju':'गुरु','Ve':'शुक्र','Sa':'शनि','Ra':'राहु','Ke':'केतु'}
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
    rows=[]
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        lon=sidelons[code]
        sign, deg_str = fmt_deg_sign(lon)
        lord, sub = kp_sublord(lon)
        rows.append([HN[code], sign, deg_str, HN[lord], HN[sub]])
    return pd.DataFrame(rows, columns=["Planet","Sign","Degree","Lord","Sub-Lord"])

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
    """Return MD segments starting at birth, capped to 100 years.
    Each segment dict: {'planet','start','end','years_used'}.
    First segment is the balance of birth MD (start=birth, end=birth+rem)."""
    md_lord, rem = moon_balance(moon_sid)
    end_limit = add_years(birth_local_dt, 100.0)  # cap at 100 years

    segments = []

    # 1) Birth partial MD
    birth_md_start = birth_local_dt
    birth_md_end = min(add_years(birth_local_dt, rem), end_limit)
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
    """Return list of (antar_lord, start, end, antar_years) for this specific MD segment duration (md_years)."""
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
    """Return list of (pratyantar_lord, start, end) within a given Antar, using proportional share of antar_years."""
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

def next_2y_ant_praty(now_local, birth_local_dt, md_segments):
    """Compute Antars & Pratyantars for all MD segments, return rows that end within next 2 years.
       Uses END dates only."""
    rows=[]; horizon=now_local + datetime.timedelta(days=2*365)
    for seg in md_segments:
        MD = seg["planet"]
        ms = seg["start"]; me = seg["end"]
        md_years_effective = seg["years_used"]  # balance/full/truncated
        for AL, as_, ae, ay in antars_in_md(MD, ms, md_years_effective):
            if ae < now_local or as_ > horizon: continue
            for PL, ps, pe in pratyantars_in_antar(AL, as_, ay):
                if pe < now_local or ps > horizon: continue
                rows.append({"major":MD,"antar":AL,"pratyantar":PL,"end":pe})
    rows.sort(key=lambda r:r["end"])
    return rows

def main():
    st.title("Kundali — Hindi KP (with Vimshottari)")

    c1,c2 = st.columns([1,1])
    with c1:
        name = st.text_input("Name")
        dob = st.date_input("Date of Birth", min_value=datetime.date(1900,1,1), max_value=datetime.date.today())
        tob = st.time_input("Time of Birth", step=datetime.timedelta(minutes=1))
    with c2:
        place = st.text_input("Place of Birth (City, State, Country)")
        tz_override = st.text_input("UTC offset override (optional, e.g., 5.5)", "")
    api_key = st.secrets.get("GEOAPIFY_API_KEY","")

    if st.button("Generate Horoscope"):
        try:
            lat, lon, disp = geocode(place, api_key)
            dt_local = datetime.datetime.combine(dob, tob)
            if tz_override.strip():
                tz_hours = float(tz_override); dt_utc = dt_local - datetime.timedelta(hours=tz_hours); tzname=f"UTC{tz_hours:+.2f} (manual)"
            else:
                tzname, tz_hours, dt_utc = tz_from_latlon(lat, lon, dt_local)
            st.info(f"Resolved {disp} → lat {lat:.6f}, lon {lon:.6f}, tz {tzname} (UTC{tz_hours:+.2f})")

            # Planetary Positions
            _, _, sidelons = sidereal_positions(dt_utc)
            df_pos = positions_table(sidelons)
            st.subheader("Planetary Positions")
            st.dataframe(df_pos, use_container_width=True)

            # Vimshottari Mahadasha — from birth, ≤100y, End Date only + Age (at start)
            md_segments, birth_md_lord, birth_md_rem = build_mahadashas_from_birth(dt_local, sidelons['Mo'])
            df_md = pd.DataFrame([
                {
                    "Planet": HN[s["planet"]],
                    "End Date": s["end"].strftime("%d-%m-%Y"),
                    "Age (at start)": round(((s["start"] - dt_local).days / YEAR_DAYS), 1),
                }
                for s in md_segments
            ])
            st.subheader("Vimshottari Mahadasha")
            st.dataframe(df_md, use_container_width=True)

            # Antar / Pratyantar for next 2 years — End Date only
            now_local = datetime.datetime.now()
            ant_rows = next_2y_ant_praty(now_local, dt_local, md_segments)
            df_ant = pd.DataFrame([
                {
                    "Major Dasha": HN[r["major"]],
                    "Antar Dasha": HN[r["antar"]],
                    "Pratyantar Dasha": HN[r["pratyantar"]],
                    "End Date": r["end"].strftime("%d-%m-%Y"),
                }
                for r in ant_rows
            ])
            st.subheader("Antar / Pratyantar for next 2 years")
            st.dataframe(df_ant, use_container_width=True)

            # DOCX export matching same titles + column orders
            doc = Document()
            doc.add_heading(f"Kundali — {name}", 0)
            doc.add_paragraph(f"Name: {name}")
            doc.add_paragraph(f"Date of Birth: {dob}")
            doc.add_paragraph(f"Time of Birth: {tob}")
            doc.add_paragraph(f"Place of Birth: {disp} (UTC{tz_hours:+.2f})")

            doc.add_heading("Planetary Positions", level=2)
            t1 = doc.add_table(rows=1, cols=len(df_pos.columns)); hdr=t1.rows[0].cells
            for i,c in enumerate(df_pos.columns): hdr[i].text=c
            for _,row in df_pos.iterrows():
                r=t1.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)

            doc.add_heading("Vimshottari Mahadasha", level=2)
            t2 = doc.add_table(rows=1, cols=len(df_md.columns)); h2=t2.rows[0].cells
            for i,c in enumerate(df_md.columns): h2[i].text=c
            for _,row in df_md.iterrows():
                r=t2.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)

            doc.add_heading("Antar / Pratyantar for next 2 years", level=2)
            t3 = doc.add_table(rows=1, cols=len(df_ant.columns)); h3=t3.rows[0].cells
            for i,c in enumerate(df_ant.columns): h3[i].text=c
            for _,row in df_ant.iterrows():
                r=t3.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)

            bio = BytesIO(); doc.save(bio)
            st.download_button("⬇️ Download DOCX", bio.getvalue(), file_name="kundali_vimshottari.docx")
        except Exception as e:
            st.error(str(e))

if __name__=='__main__':
    main()
