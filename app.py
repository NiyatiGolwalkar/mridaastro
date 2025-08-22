
import streamlit as st
import swisseph as swe
import pandas as pd
import datetime
import requests
from docx import Document
from io import BytesIO
from math import floor

# ---------------- Settings ----------------
# Lahiri ayanamsa for sidereal
def set_sidereal():
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

# Hindi planet names
PLANET_NAMES_HINDI = {
    'Su': 'सूर्य','Mo': 'चंद्र','Ma': 'मंगल','Me': 'बुध','Ju': 'गुरु',
    'Ve': 'शुक्र','Sa': 'शनि','Ra': 'राहु','Ke': 'केतु'
}

# Vimshottari / Nakshatra order
ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
NAKSHATRA_LEN = 360.0/27.0

# Helpers
def dms(deg):
    d = floor(deg); m = floor((deg-d)*60); s = round((deg-d-m/60)*3600); return d,m,s

def fmt_deg(lon):
    d,m,s = dms(lon); return f"{d:02d}°{m:02d}'{s:02d}\""

def kp_sublord(lon_sid):
    part = lon_sid % 360.0
    nak_idx = int(part // NAKSHATRA_LEN)  # 0..26
    pos_in = part - nak_idx*NAKSHATRA_LEN
    nak_lord = ORDER[nak_idx % 9]
    # Build sublord cycle starting from nak_lord
    start = ORDER.index(nak_lord)
    seq = [ORDER[(start+i)%9] for i in range(9)]
    # segment lengths proportional to YEARS/120 of nakshatra length
    cum = 0.0
    for lord in seq:
        seg = NAKSHATRA_LEN * (YEARS[lord] / 120.0)
        if pos_in <= cum + seg + 1e-9:
            return nak_lord, lord
        cum += seg
    return nak_lord, seq[-1]

def get_lat_lon(place, api_key):
    url = "https://api.geoapify.com/v1/geocode/search"
    r = requests.get(url, params={"text":place, "apiKey":api_key, "limit":1}, timeout=10)
    j = r.json()
    # support both Geoapify response shapes
    if isinstance(j, dict) and "features" in j and j["features"]:
        lon, lat = j["features"][0]["geometry"]["coordinates"]
        return float(lat), float(lon)
    if isinstance(j, dict) and "results" in j and j["results"]:
        res = j["results"][0]; return float(res["lat"]), float(res["lon"])
    return None, None

def planetary_positions(jd):
    set_sidereal()
    ayan = swe.get_ayanamsa_ut(jd)
    # Planet codes for Swiss Ephemeris
    plist = [
        ('Su', swe.SUN), ('Mo', swe.MOON), ('Ma', swe.MARS), ('Me', swe.MERCURY),
        ('Ju', swe.JUPITER), ('Ve', swe.VENUS), ('Sa', swe.SATURN),
        ('Ra', swe.TRUE_NODE),  # True Rahu
    ]
    rows = []
    for code, p in plist:
        xx, _ = swe.calc_ut(jd, p, swe.FLG_MOSEPH)  # xx[0] = ecliptic longitude (tropical)
        lon_sid = (xx[0] - ayan) % 360
        sign = int(lon_sid // 30) + 1
        lord, sub = kp_sublord(lon_sid)
        rows.append([PLANET_NAMES_HINDI[code], fmt_deg(lon_sid % 30), sign, PLANET_NAMES_HINDI[lord], PLANET_NAMES_HINDI[sub]])
    # Ketu opposite Rahu
    xx, _ = swe.calc_ut(jd, swe.TRUE_NODE, swe.FLG_MOSEPH)
    ketu_sid = ((xx[0] + 180.0) - ayan) % 360
    sign = int(ketu_sid // 30) + 1
    lord, sub = kp_sublord(ketu_sid)
    rows.append([PLANET_NAMES_HINDI['Ke'], fmt_deg(ketu_sid % 30), sign, PLANET_NAMES_HINDI[lord], PLANET_NAMES_HINDI[sub]])
    return pd.DataFrame(rows, columns=['Planet','Degree','Sign','Lord','Sub-Lord'])

def mahadasha_table(dob):
    # Simple full-cycle starting at birth nakshatra lord start; for demo keep sequential with ages
    rows = []
    age = 0
    for lord in ORDER:
        start_date = dob + datetime.timedelta(days=int(age*365.2425))
        rows.append([PLANET_NAMES_HINDI[lord], start_date.strftime("%Y-%m-%d"), age])
        age += YEARS[lord]
    return pd.DataFrame(rows, columns=['Planet','Start Date','Age (start)'])

def antar_pratyantar_table():
    # Placeholder rows (start-only) for next 2 years; detailed KP timing can be plugged later
    rows = []
    today = datetime.date.today()
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
    t = doc.add_table(rows=1, cols=len(df1.columns)); hdr = t.rows[0].cells
    for i,c in enumerate(df1.columns): hdr[i].text = c
    for _, row in df1.iterrows():
        r = t.add_row().cells
        for i, c in enumerate(row): r[i].text = str(c)

    doc.add_heading('Vimshottari Mahadasha (Start + Age)', level=2)
    t = doc.add_table(rows=1, cols=len(df2.columns)); hdr = t.rows[0].cells
    for i,c in enumerate(df2.columns): hdr[i].text = c
    for _, row in df2.iterrows():
        r = t.add_row().cells
        for i, c in enumerate(row): r[i].text = str(c)

    doc.add_heading('Antar / Pratyantar – Next 2 years (Start only)', level=2)
    t = doc.add_table(rows=1, cols=len(df3.columns)); hdr = t.rows[0].cells
    for i,c in enumerate(df3.columns): hdr[i].text = c
    for _, row in df3.iterrows():
        r = t.add_row().cells
        for i, c in enumerate(row): r[i].text = str(c)

    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def main():
    st.title("Horoscope Generator (Hindi KP version)")

    name = st.text_input("Name")
    dob = st.date_input("Date of Birth", value=datetime.date(1987,9,15),
                        min_value=datetime.date(1900,1,1), max_value=datetime.date.today())
    tob = st.time_input("Time of Birth", value=datetime.time(10,53), step=datetime.timedelta(minutes=1))
    pob = st.text_input("Place of Birth (City, Country)")

    st.caption("Tip: Calendar supports 1900..today; time supports any minute like 10:53.")

    api_key = st.secrets.get("GEOAPIFY_API_KEY","")

    if st.button("Generate Horoscope"):
        lat, lon = get_lat_lon(pob, api_key)
        if lat is None:
            st.error("Could not resolve place (check Geoapify key or try another city)."); return

        # Use date+time to compute Julian day
        jd = swe.julday(dob.year, dob.month, dob.day, tob.hour + tob.minute/60.0)

        df1 = planetary_positions(jd)
        df2 = mahadasha_table(dob)
        df3 = antar_pratyantar_table()

        st.subheader("Planetary Positions (Lord & Sub-Lord)"); st.table(df1)
        st.subheader("Vimshottari Mahadasha (Start + Age)"); st.table(df2)
        st.subheader("Antar / Pratyantar – Next 2 years (Start only)"); st.table(df3)

        details = {"name":name, "dob":dob, "tob":tob, "pob":pob}
        docx_bytes = export_docx(details, df1, df2, df3)
        st.download_button("Download DOCX", docx_bytes, "horoscope.docx")

if __name__ == "__main__":
    main()
