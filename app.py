
import os, datetime, requests, pytz
import streamlit as st
import pandas as pd
import swisseph as swe
from timezonefinder import TimezoneFinder
from math import floor
from docx import Document
from io import BytesIO

st.set_page_config(page_title="Kundali – Hindi KP (Mahadasha + Antar/Pratyantar)", layout="wide", page_icon="🪔")

HN = {'Su':'सूर्य','Mo':'चंद्र','Ma':'मंगल','Me':'बुध','Ju':'गुरु','Ve':'शुक्र','Sa':'शनि','Ra':'राहु','Ke':'केतु'}
ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
NAK = 360.0/27.0

def set_sidereal(): swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

def dms(deg): d=int(deg); m=int((deg-d)*60); s=int(round((deg-d-m/60)*3600)); return d,m,s
def fmt_deg_sign(lon_sid):
    sign=int(lon_sid//30); deg=lon_sid - sign*30; d,m,s=dms(deg); return f"{d:02d}°{m:02d}'{s:02d}\"", (sign+1)

def kp_sublord(lon_sid):
    part = lon_sid % 360.0
    ni = int(part // NAK); pos = part - ni*NAK
    lord = ORDER[ni % 9]
    start = ORDER.index(lord)
    seq = [ORDER[(start+i)%9] for i in range(9)]
    acc = 0.0
    for L in seq:
        seg = NAK * (YEARS[L]/120.0)
        if pos <= acc + seg + 1e-9: return lord, L
        acc += seg
    return lord, seq[-1]

def geocode(place, api_key):
    if not api_key: raise RuntimeError("Geoapify key missing. Add GEOAPIFY_API_KEY in Secrets.")
    url="https://api.geoapify.com/v1/geocode/search"
    r=requests.get(url, params={"text":place, "format":"json", "limit":1, "apiKey":api_key}, timeout=12)
    j=r.json()
    if r.status_code!=200: raise RuntimeError(f"Geoapify {r.status_code}: {j.get('message', str(j)[:150])}")
    if j.get("results"):
        res=j["results"][0]; return float(res["lat"]), float(res["lon"]), res.get("formatted", place)
    if j.get("features"):
        lon,lat=j["features"][0]["geometry"]["coordinates"]; return float(lat), float(lon), place
    raise RuntimeError("Place not found.")

def tz_from_latlon(lat, lon, dt_local):
    tf = TimezoneFinder(); tzname = tf.timezone_at(lat=lat, lng=lon) or "Etc/UTC"
    tz = pytz.timezone(tzname); dt_local_aware = tz.localize(dt_local)
    dt_utc_naive = dt_local_aware.astimezone(pytz.utc).replace(tzinfo=None)
    offset_hours = tz.utcoffset(dt_local_aware).total_seconds()/3600.0
    return tzname, offset_hours, dt_utc_naive

def sidereal_positions(dt_utc):
    jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600)
    set_sidereal(); ay = swe.get_ayanamsa_ut(jd); flags=swe.FLG_MOSEPH
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
        lon=sidelons[code]; deg,sign=fmt_deg_sign(lon); lord,sub=kp_sublord(lon)
        rows.append([HN[code], deg, sign, HN[lord], HN[sub]])
    return pd.DataFrame(rows, columns=["Planet","Degree","Sign","Lord","Sub-Lord"])

# ---- Vimshottari ----
def moon_balance(moon_sid):
    part = moon_sid % 360.0
    ni = int(part // NAK)
    pos = part - ni*NAK
    md_lord = ORDER[ni % 9]
    frac = pos/NAK
    remaining_years = YEARS[md_lord]*(1 - frac)
    return md_lord, remaining_years

def add_years(dt, y): return dt + datetime.timedelta(days=y*365.2425)

def build_mahadashas(birth_local_dt, moon_sid):
    md_lord, rem = moon_balance(moon_sid)
    first_change = add_years(birth_local_dt, rem)
    seq=[]; idx=(ORDER.index(md_lord)+1)%9; t=first_change
    while len(seq) < 27:
        L=ORDER[idx]; yrs=YEARS[L]; end=add_years(t, yrs); age=int((t-birth_local_dt).days/365.2425 + 0.5)
        seq.append({"planet":L,"start":t,"end":end,"age":age})
        t=end; idx=(idx+1)%9
    return seq, md_lord, rem

def antars_in_md(md_lord, md_start, md_years):
    res=[]; t=md_start; start_idx=ORDER.index(md_lord)
    for i in range(9):
        L=ORDER[(start_idx+i)%9]
        yrs = YEARS[L]*(md_years/120.0)
        days = yrs*365.2425
        res.append((L, t, yrs))
        t = t + datetime.timedelta(days=days)
    return res

def pratyantars_in_antar(antar_lord, antar_start, antar_years):
    res=[]; t=antar_start; start_idx=ORDER.index(antar_lord)
    for i in range(9):
        L=ORDER[(start_idx+i)%9]
        yrs = YEARS[L]*(antar_years/120.0)
        days = yrs*365.2425
        res.append((L, t))
        t = t + datetime.timedelta(days=days)
    return res

def next_2y_ant_praty(now_local, birth_local_dt, moon_sid, md_list, birth_md_lord, birth_md_rem):
    rows=[]; horizon=now_local + datetime.timedelta(days=730)
    birth_end=add_years(birth_local_dt, birth_md_rem)
    sched=[(birth_md_lord, birth_local_dt, birth_end)] + [(m['planet'], m['start'], m['end']) for m in md_list]
    for MD, ms, me in sched:
        if me < now_local or ms > horizon: continue
        md_years = YEARS[MD]
        for AL, as_, ay in antars_in_md(MD, ms, md_years):
            if as_ > horizon: break
            for PL, ps in pratyantars_in_antar(AL, as_, ay):
                if ps > horizon: break
                if ps >= now_local:
                    rows.append({"major":MD,"antar":AL,"pratyantar":PL,"start":ps})
    rows.sort(key=lambda r:r["start"])
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

            # Planets
            _, _, sidelons = sidereal_positions(dt_utc)
            df_pos = positions_table(sidelons)
            st.subheader("Planetary Positions (Lord & Sub-Lord)"); st.dataframe(df_pos)

            # Vimshottari MD from Moon balance
            md_list, birth_md_lord, birth_md_rem = build_mahadashas(dt_local, sidelons['Mo'])
            df_md = pd.DataFrame([{"Planet":HN[m["planet"]],"Start":m["start"].strftime("%d-%m-%Y"),"Age (start)":m["age"]} for m in md_list])
            st.subheader("Vimshottari Mahadasha (Start + Age)"); st.dataframe(df_md)

            # Antar/Pratyantar next 2 years (start only)
            now_local = datetime.datetime.now()
            ant_rows = next_2y_ant_praty(now_local, dt_local, sidelons['Mo'], md_list, birth_md_lord, birth_md_rem)
            df_ant = pd.DataFrame([{"Major":HN[r["major"]],"Antar":HN[r["antar"]],"Pratyantar":HN[r["pratyantar"]],"Start":r["start"].strftime("%d-%m-%Y")} for r in ant_rows])
            st.subheader("Antar / Pratyantar — Next 2 years (Start only)"); st.dataframe(df_ant)

            # DOCX export
            doc = Document(); doc.add_heading(f"Kundali — {name}", 0)
            doc.add_paragraph(f"DOB: {dob}, TOB: {tob}, Place: {disp} (UTC{tz_hours:+.2f})")
            doc.add_heading("Planetary Positions", level=2)
            t = doc.add_table(rows=1, cols=len(df_pos.columns)); hdr=t.rows[0].cells
            for i,c in enumerate(df_pos.columns): hdr[i].text=c
            for _,row in df_pos.iterrows():
                r=t.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)

            doc.add_heading("Vimshottari Mahadasha (Start + Age)", level=2)
            t2 = doc.add_table(rows=1, cols=len(df_md.columns)); h2=t2.rows[0].cells
            for i,c in enumerate(df_md.columns): h2[i].text=c
            for _,row in df_md.iterrows():
                r=t2.add_row().cells
                for i,c in enumerate(row): r[i].text=str(c)

            doc.add_heading("Antar / Pratyantar — Next 2 years (Start only)", level=2)
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
