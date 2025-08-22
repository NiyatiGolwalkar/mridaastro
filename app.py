
import streamlit as st
import swisseph as swe
import datetime
import pytz
import requests
import pandas as pd
from io import BytesIO
from docx import Document

# Load API key from Streamlit secrets if available
API_KEY = st.secrets.get("GEOAPIFY_API_KEY", None)

# Planet names in Hindi
PLANETS = ["सूर्य","चंद्र","मंगल","बुध","गुरु","शुक्र","शनि","राहु","केतु"]
PLANET_IDS = [swe.SUN, swe.MOON, swe.MARS, swe.MERCURY, swe.JUPITER, swe.VENUS, swe.SATURN, swe.MEAN_NODE, swe.TRUE_NODE]

def geocode_place(place):
    if not API_KEY:
        return None
    url = f"https://api.geoapify.com/v1/geocode/search?text={place}&apiKey={API_KEY}"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        if data['features']:
            coords = data['features'][0]['geometry']['coordinates']
            return coords[1], coords[0]
    return None

def planetary_positions(jd_ut):
    results = []
    for i, pid in enumerate(PLANET_IDS[:-1]):  # Exclude TRUE_NODE (dup of Rahu)
        lon, lat, dist = swe.calc_ut(jd_ut, pid)[0:3]
        sign = int(lon/30)+1
        lord = "TODO"
        sublord = "TODO"
        results.append([PLANETS[i], lon, sign, lord, sublord])
    return results

def main():
    st.title("Horoscope Generator (Hindi KP version)")

    name = st.text_input("Name")
    dob = st.date_input("Date of Birth", min_value=datetime.date(1900,1,1), max_value=datetime.date.today())
    tob = st.time_input("Time of Birth", datetime.time(12,0))
    place = st.text_input("Place of Birth (City, Country)", "Jabalpur, Madhya Pradesh, India")

    if st.button("Generate Horoscope"):
        coords = geocode_place(place)
        if not coords:
            st.error("Could not resolve place. Check API key or try manual coords.")
            return
        lat, lon = coords

        # Julian Day
        dt = datetime.datetime.combine(dob, tob)
        jd = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute/60.0)

        # Planetary positions
        pos = planetary_positions(jd)
        df = pd.DataFrame(pos, columns=["Planet","Longitude","Sign","Lord","Sub-Lord"])
        st.write("### Planetary Positions (Lord & Sub-Lord)")
        st.dataframe(df)

        # Export DOCX
        doc = Document()
        doc.add_heading(f"Kundali for {name}", level=1)
        doc.add_paragraph(f"Birth: {dob} {tob} at {place}")
        table = doc.add_table(rows=1, cols=len(df.columns))
        hdr = table.rows[0].cells
        for j, col in enumerate(df.columns):
            hdr[j].text = col
        for row in df.values.tolist():
            cells = table.add_row().cells
            for j, val in enumerate(row):
                cells[j].text = str(val)
        bio = BytesIO()
        doc.save(bio)
        st.download_button("Download Horoscope DOCX", bio.getvalue(), file_name="horoscope.docx")

if __name__ == "__main__":
    main()
