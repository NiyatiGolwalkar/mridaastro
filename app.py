
import streamlit as st
import swisseph as swe
import pandas as pd
import datetime
import requests
from docx import Document
from io import BytesIO
from math import floor

# ---------------- Settings ----------------
def set_sidereal():
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

PLANET_NAMES_HINDI = {'Su':'सूर्य','Mo':'चंद्र','Ma':'मंगल','Me':'बुध','Ju':'गुरु','Ve':'शुक्र','Sa':'शनि','Ra':'राहु','Ke':'केतु'}
ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
NAKSHATRA_LEN = 360.0/27.0

def dms(deg):
    d = int(deg); m = int((deg-d)*60); s = int(round((deg-d-m/60)*3600)); return d,m,s
def fmt_deg(lon): d,m,s = dms(lon); return f"{d:02d}°{m:02d}'{s:02d}\""

def kp_sublord(lon_sid):
    part = lon_sid % 360.0
    nak_idx = int(part // NAKSHATRA_LEN)
    pos_in = part - nak_idx*NAKSHATRA_LEN
    nak_lord = ORDER[nak_idx % 9]
    start = ORDER.index(nak_lord)
    seq = [ORDER[(start+i)%9] for i in range(9)]
    cum = 0.0
    for lord in seq:
        seg = NAKSHATRA_LEN * (YEARS[lord] / 120.0)
        if pos_in <= cum + seg + 1e-9:
            return nak_lord, lord
        cum += seg
    return nak_lord, seq[-1]

def geocode_geoapify(place, api_key):
    if not api_key:
        raise RuntimeError("Geoapify API key missing. Add GEOAPIFY_API_KEY in Streamlit Secrets.")
    url = "https://api.geoapify.com/v1/geocode/search"
    params = {"text": place, "apiKey": api_key, "limit": 1, "format": "json"}
    r = requests.get(url, params=params, timeout=12)
    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"Geoapify HTTP {r.status_code}: {r.text[:200]}")

    if r.status_code != 200:
        msg = j.get("message") if isinstance(j, dict) else r.text[:200]
        raise RuntimeError(f"Geoapify error {r.status_code}: {msg}")

    if isinstance(j, dict) and j.get("results"):
        res = j["results"][0]
        return float(res["lat"]), float(res["lon"]), res.get("formatted", place)

    if isinstance(j, dict) and j.get("features"):
        lon, lat = j["features"][0]["geometry"]["coordinates"]
        return float(lat), float(lon), j["features"][0].get("properties", {}).get("formatted", place)

    raise RuntimeError(f"Place not found. Response: {str(j)[:200]}")

def planetary_positions(jd):
    set_sidereal()
    ayan = swe.get_ayanamsa_ut(jd)
    plist = [('Su',swe.SUN),('Mo',swe.MOON),('Ma',swe.MARS),('Me',swe.MERCURY),('Ju',swe.JUPITER),('Ve',swe.VENUS),('Sa',swe.SATURN),('Ra',swe.TRUE_NODE)]
    rows = []
    for code,p in plist:
        xx,_ = swe.calc_ut(jd, p, swe.FLG_MOSEPH); lon_sid = (xx[0] - ayan) % 360
        sign = int(lon_sid // 30) + 1
        lord, sub = kp_sublord(lon_sid)
        rows.append([PLANET_NAMES_HINDI[code], fmt_deg(lon_sid % 30), sign, PLANET_NAMES_HINDI[lord], PLANET_NAMES_HINDI[sub]])
    xx,_ = swe.calc_ut(jd, swe.TRUE_NODE, swe.FLG_MOSEPH); ketu_sid = ((xx[0]+180) - ayan) % 360
    sign = int(ketu_sid // 30) + 1; lord, sub = kp_sublord(ketu_sid)
    rows.append([PLANET_NAMES_HINDI['Ke'], fmt_deg(ketu_sid % 30), sign, PLANET_NAMES_HINDI[lord], PLANET_NAMES_HINDI[sub]])
    return pd.DataFrame(rows, columns=['Planet','Degree','Sign','Lord','Sub-Lord'])

def mahadasha_table(dob):
    rows=[]; age=0
    for lord in ORDER:
        start_date = dob + datetime.timedelta(days=int(age*365.2425))
        rows.append([PLANET_NAMES_HINDI[lord], start_date.strftime("%Y-%m-%d"), age])
        age += YEARS[lord]
    return pd.DataFrame(rows, columns=['Planet','Start Date','Age (start)'])

def antar_pratyantar_table():
    rows=[]; today=datetime.date.today()
    for lord in ORDER:
        rows.append([PLANET_NAMES_HINDI[lord], PLANET_NAMES_HINDI[lord], PLANET_NAMES_HINDI[lord], today.strftime("%Y-%m-%d")])
    return pd.DataFrame(rows, columns=['Major Dasha','Antar Dasha','Pratyantar Dasha','Start Date'])

def export_docx(details, df1, df2, df3):
    doc = Document()
    doc.add_heading('Janam Kundali (Vedic)', level=1)
    doc.add_paragraph(f"Name: {details['name']}")
    doc.add_paragraph(f"Date of Birth: {details['dob']}")
    doc.add_paragraph(f"Time of Birth: {details['tob']}")
    doc.add_paragraph(f"Place of Birth: {details['pob']}")

    doc.add_heading('Planetary Positions (Lord & Sub-Lord)', level=2)
    t = doc.add_table(rows=1, cols=len(df1.columns)); hdr=t.rows[0].cells
    for i,c in enumerate(df1.columns): hdr[i].text=c
    for _,row in df1.iterrows():
        r=t.add_row().cells
        for i,c in enumerate(row): r[i].text=str(c)

    doc.add_heading('Vimshottari Mahadasha (Start + Age)', level=2)
    t = doc.add_table(rows=1, cols=len(df2.columns)); hdr=t.rows[0].cells
    for i,c in enumerate(df2.columns): hdr[i].text=c
    for _,row in df2.iterrows():
        r=t.add_row().cells
        for i,c in enumerate(row): r[i].text=str(c)

    doc.add_heading('Antar / Pratyantar – Next 2 years (Start only)', level=2)
    t = doc.add_table(rows=1, cols=len(df3.columns)); hdr=t.rows[0].cells
    for i,c in enumerate(df3.columns): hdr[i].text=c
    for _,row in df3.iterrows():
        r=t.add_row().cells
        for i,c in enumerate(row): r[i].text=str(c)

    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def main():
    st.title("Horoscope Generator (Hindi KP version)")

    name = st.text_input("Name")
    dob = st.date_input("Date of Birth", value=datetime.date(1987,9,15),
                        min_value=datetime.date(1900,1,1), max_value=datetime.date.today())
    tob = st.time_input("Time of Birth", value=datetime.time(10,53), step=datetime.timedelta(minutes=1))
    pob = st.text_input("Place of Birth (City, Country)", "Jabalpur, Madhya Pradesh, India")

    manual = st.checkbox("Enter coordinates manually (fallback)")
    lat_manual = lon_manual = None
    if manual:
        lat_manual = st.number_input("Latitude (+N)", value=23.1815, format="%.6f")
        lon_manual = st.number_input("Longitude (+E)", value=79.9864, format="%.6f")

    st.caption("Tip: Calendar supports 1900..today; time supports any minute like 10:53.")

    api_key = st.secrets.get("GEOAPIFY_API_KEY","")

    if st.button("Generate Horoscope"):
        try:
            if manual:
                lat, lon, display_place = float(lat_manual), float(lon_manual), "Manual"
            else:
                lat, lon, display_place = geocode_geoapify(pob, api_key)
            jd = swe.julday(dob.year, dob.month, dob.day, tob.hour + tob.minute/60.0)
            df1 = planetary_positions(jd); df2 = mahadasha_table(dob); df3 = antar_pratyantar_table()
            st.subheader("Planetary Positions (Lord & Sub-Lord)"); st.table(df1)
            st.subheader("Vimshottari Mahadasha (Start + Age)"); st.table(df2)
            st.subheader("Antar / Pratyantar – Next 2 years (Start only)"); st.table(df3)
            details = {"name":name,"dob":dob,"tob":tob,"pob":display_place}
            st.download_button("Download DOCX", export_docx(details, df1, df2, df3), "horoscope.docx")
        except Exception as e:
            st.error(str(e))
            st.info("If the error mentions Geoapify, try Manual coordinates fallback above.")

if __name__ == "__main__":
    main()
