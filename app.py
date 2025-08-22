import streamlit as st
import swisseph as swe
import pandas as pd
import math
from datetime import datetime, timedelta

# Geoapify key from secrets
import requests, os
API_KEY = os.environ.get("GEOAPIFY_API_KEY", "")

# Planet mapping
PLANETS = [
    (swe.SUN, "सूर्य"),
    (swe.MOON, "चंद्र"),
    (swe.MARS, "मंगल"),
    (swe.MERCURY, "बुध"),
    (swe.JUPITER, "गुरु"),
    (swe.VENUS, "शुक्र"),
    (swe.SATURN, "शनि"),
    (swe.TRUE_NODE, "राहु"),
    (swe.KETU, "केतु"),
]

DASHA_YEARS = {
    "केतु": 7, "शुक्र": 20, "सूर्य": 6, "चंद्र": 10,
    "मंगल": 7, "राहु": 18, "गुरु": 16, "शनि": 19, "बुध": 17
}

ORDER = ["केतु","शुक्र","सूर्य","चंद्र","मंगल","राहु","गुरु","शनि","बुध"]
YEAR_DAYS = 365.2425

def planetary_positions(jd):
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    data = []
    for pid, name in PLANETS:
        lon, lat, dist = swe.calc_ut(jd, pid)[0:3]
        sign = int(lon // 30) + 1
        data.append([name, lon, sign])
    return pd.DataFrame(data, columns=["Planet","Degree","Sign"])

def vimshottari_md(moon_long, birth_dt):
    # Nakshatra fraction
    nak = (moon_long % 360) / (360/27)
    nak_frac = nak - int(nak)
    lord = ORDER[int(nak)%9]
    elapsed = nak_frac * DASHA_YEARS[lord]
    rem = DASHA_YEARS[lord] - elapsed

    # Start of birth MD = birth_dt - elapsed*YEAR_DAYS
    md_start = birth_dt - timedelta(days=elapsed*YEAR_DAYS)

    # Build sequence until 100 yrs age
    out = []
    age_limit = birth_dt + timedelta(days=100*YEAR_DAYS)
    idx = ORDER.index(lord)
    cur_start = md_start
    for i in range(9*12): # enough cycles
        lord = ORDER[(idx+i)%9]
        dur = DASHA_YEARS[lord]*YEAR_DAYS
        if cur_start >= birth_dt and cur_start <= age_limit:
            age = (cur_start - birth_dt).days/365.2425
            out.append([lord, cur_start.date(), round(age,1)])
        cur_start += timedelta(days=dur)
        if cur_start > age_limit:
            break
    return pd.DataFrame(out, columns=["Mahadasha Lord","Start Date","Age"])

def antar_pratyantar(md_table, birth_dt):
    # Next 2 yrs from now
    now = datetime.utcnow()
    horizon = now + timedelta(days=2*YEAR_DAYS)
    out = []
    for _,row in md_table.iterrows():
        md_lord, md_start = row["Mahadasha Lord"], row["Start Date"]
        md_start = datetime.strptime(str(md_start), "%Y-%m-%d")
        md_dur = DASHA_YEARS[md_lord]*YEAR_DAYS
        for ad_lord in ORDER:
            ad_dur = md_dur*DASHA_YEARS[ad_lord]/120.0
            ad_start = md_start
            md_start += timedelta(days=ad_dur)
            if ad_start>=now and ad_start<=horizon:
                out.append(["Antar", md_lord+"/"+ad_lord, ad_start.date()])
            # Pratyantar
            for pd_lord in ORDER:
                pd_dur = ad_dur*DASHA_YEARS[pd_lord]/120.0
                pd_start = ad_start
                ad_start += timedelta(days=pd_dur)
                if pd_start>=now and pd_start<=horizon:
                    out.append(["Pratyantar", md_lord+"/"+ad_lord+"/"+pd_lord, pd_start.date()])
    return pd.DataFrame(out, columns=["Level","Lord","Start Date"])

def main():
    st.title("Horoscope Generator (Hindi KP version)")

    name = st.text_input("Name")
    dob = st.date_input("Date of Birth", datetime(1990,1,1), min_value=datetime(1900,1,1), max_value=datetime(2100,12,31))
    tob = st.time_input("Time of Birth", datetime.now().time())
    place = st.text_input("Place of Birth (City, Country)", "Jabalpur, India")

    # Resolve coords
    coords = None
    if API_KEY and place:
        url = f"https://api.geoapify.com/v1/geocode/search?text={place}&apiKey={API_KEY}"
        r = requests.get(url).json()
        if r.get("features"):
            coords = r["features"][0]["geometry"]["coordinates"]
    if coords:
        lon, lat = coords
    else:
        lon, lat = 79.95, 23.17

    birth_dt = datetime.combine(dob, tob)
    jd = swe.julday(birth_dt.year, birth_dt.month, birth_dt.day, birth_dt.hour+birth_dt.minute/60.0)

    pos = planetary_positions(jd)
    st.subheader("Planetary Positions")
    st.dataframe(pos)

    moon_long = pos.loc[pos["Planet"]=="चंद्र","Degree"].values[0]
    md_table = vimshottari_md(moon_long, birth_dt)
    st.subheader("Vimshottari Mahadasha (till 100 years)")
    st.dataframe(md_table)

    antar = antar_pratyantar(md_table, birth_dt)
    st.subheader("Antar / Pratyantar (Next 2 years)")
    st.dataframe(antar)

if __name__ == "__main__":
    main()
