
import streamlit as st
import swisseph as swe
import pandas as pd
import datetime
import requests
from docx import Document
from io import BytesIO

# Hindi planet names
PLANET_NAMES_HINDI = {
    'Sun': 'सूर्य',
    'Moon': 'चंद्र',
    'Mars': 'मंगल',
    'Mercury': 'बुध',
    'Jupiter': 'गुरु',
    'Venus': 'शुक्र',
    'Saturn': 'शनि',
    'Rahu': 'राहु',
    'Ketu': 'केतु'
}

# Nakshatra lords (Vimshottari order)
NAKSHATRA_LORDS = [
    'Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury'
]
NAKSHATRA_PORTIONS = [7, 20, 6, 10, 7, 18, 16, 19, 17]  # years

def get_lat_lon(place, api_key):
    url = f"https://api.geoapify.com/v1/geocode/search?text={place}&apiKey={api_key}"
    resp = requests.get(url).json()
    if 'features' in resp and len(resp['features']) > 0:
        coords = resp['features'][0]['geometry']['coordinates']
        return coords[1], coords[0]
    return None, None

def planetary_positions(jd):
    planets = ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']
    rows = []
    for p in planets:
        if p == 'Rahu':
            lon = swe.calc_ut(jd, swe.TRUE_NODE)[0]
        elif p == 'Ketu':
            lon = (swe.calc_ut(jd, swe.TRUE_NODE)[0] + 180) % 360
        else:
            lon = swe.calc_ut(jd, getattr(swe, p.upper()))[0]
        sign = int(lon/30)+1
        # Nakshatra calc
        nak = int(lon/13.3333)
        lord = NAKSHATRA_LORDS[nak % 9]
        # Sub-lord calc (simplified KP style)
        sub_lord = NAKSHATRA_LORDS[(nak+1) % 9]
        rows.append([PLANET_NAMES_HINDI[p], f"{lon:.2f}", sign, PLANET_NAMES_HINDI[lord], PLANET_NAMES_HINDI[sub_lord]])
    return pd.DataFrame(rows, columns=['Planet','Degree','Sign','Lord','Sub-Lord'])

def mahadasha_table(dob):
    # Very simplified placeholder for demo
    start_year = dob.year
    rows = []
    age = 0
    for lord, years in zip(NAKSHATRA_LORDS, NAKSHATRA_PORTIONS):
        start_date = dob + datetime.timedelta(days=int(age*365.25))
        rows.append([PLANET_NAMES_HINDI[lord], start_date.strftime("%Y-%m-%d"), age])
        age += years
    return pd.DataFrame(rows, columns=['Planet','Start Date','Age'])

def antar_pratyantar_table(start_date):
    rows = []
    today = datetime.date.today()
    end_date = today + datetime.timedelta(days=730)
    # simplified structure
    for lord in NAKSHATRA_LORDS:
        rows.append([PLANET_NAMES_HINDI[lord], PLANET_NAMES_HINDI[lord], PLANET_NAMES_HINDI[lord], today.strftime("%Y-%m-%d")])
    return pd.DataFrame(rows, columns=['Major Dasha','Antar Dasha','Pratyantar Dasha','Start Date'])

def export_docx(details, df1, df2, df3):
    doc = Document()
    doc.add_heading('Horoscope Report', level=1)
    doc.add_paragraph(f"Name: {details['name']}")
    doc.add_paragraph(f"DOB: {details['dob']}")
    doc.add_paragraph(f"Time: {details['tob']}")
    doc.add_paragraph(f"Place: {details['pob']}")

    doc.add_heading('Planetary Positions', level=2)
    t = doc.add_table(rows=1, cols=len(df1.columns))
    hdr = t.rows[0].cells
    for i, c in enumerate(df1.columns):
        hdr[i].text = c
    for _, row in df1.iterrows():
        r = t.add_row().cells
        for i, c in enumerate(row):
            r[i].text = str(c)

    doc.add_heading('Mahadasha', level=2)
    t = doc.add_table(rows=1, cols=len(df2.columns))
    hdr = t.rows[0].cells
    for i, c in enumerate(df2.columns):
        hdr[i].text = c
    for _, row in df2.iterrows():
        r = t.add_row().cells
        for i, c in enumerate(row):
            r[i].text = str(c)

    doc.add_heading('Antar/Pratyantar (2 years)', level=2)
    t = doc.add_table(rows=1, cols=len(df3.columns))
    hdr = t.rows[0].cells
    for i, c in enumerate(df3.columns):
        hdr[i].text = c
    for _, row in df3.iterrows():
        r = t.add_row().cells
        for i, c in enumerate(row):
            r[i].text = str(c)

    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

def main():
    st.title("Horoscope Generator (Hindi KP version)")

    name = st.text_input("Name")
    dob = st.date_input("Date of Birth")
    tob = st.time_input("Time of Birth")
    pob = st.text_input("Place of Birth (City, Country)")

    api_key = st.secrets["GEOAPIFY_API_KEY"] if "GEOAPIFY_API_KEY" in st.secrets else ""

    if st.button("Generate Horoscope"):
        lat, lon = get_lat_lon(pob, api_key)
        if lat is None:
            st.error("Could not resolve place")
            return
        jd = swe.julday(dob.year, dob.month, dob.day, tob.hour + tob.minute/60.0)

        df1 = planetary_positions(jd)
        df2 = mahadasha_table(dob)
        df3 = antar_pratyantar_table(dob)

        st.subheader("Planetary Positions")
        st.table(df1)

        st.subheader("Mahadasha Periods")
        st.table(df2)

        st.subheader("Antar/Pratyantar (2 years)")
        st.table(df3)

        details = {"name": name, "dob": dob, "tob": tob, "pob": pob}
        docx_bytes = export_docx(details, df1, df2, df3)
        st.download_button("Download DOCX", docx_bytes, "horoscope.docx")

if __name__ == "__main__":
    main()
