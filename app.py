# kundali-streamlit/app.py
# ---------------------------------
# Streamlit Kundali (Sidereal Lahiri) using Swiss Ephemeris
# Fix: pyswisseph has no swe.KETU. We compute Ketu = Rahu + 180°.
# Also supports Mean/True node toggle and fallback geocoding.

import os
import math
from datetime import datetime, timedelta
import requests
import pytz
import pandas as pd
import streamlit as st
import swisseph as swe

APP_TITLE = "🕉️ Vedic Horoscope (Sidereal Lahiri)"
USE_TRUE_NODE = False  # False = Mean Rahu; True = True Rahu
SIDEREAL_FLAG = swe.FLG_SIDEREAL

# Optional: Geoapify API key for better geocoding (else fallback to Nominatim)
GEOAPIFY_API_KEY = os.environ.get("GEOAPIFY_API_KEY", "")

DASHA_YEARS = {
    "केतु": 7, "शुक्र": 20, "सूर्य": 6, "चंद्र": 10,
    "मंगल": 7, "राहु": 18, "गुरु": 16, "शनि": 19, "बुध": 17
}
DASHA_ORDER = ["केतु", "शुक्र", "सूर्य", "चंद्र", "मंगल", "राहु", "गुरु", "शनि", "बुध"]
YEAR_DAYS = 365.2425

PLANETS = [
    (swe.SUN, "सूर्य"),
    (swe.MOON, "चंद्र"),
    (swe.MARS, "मंगल"),
    (swe.MERCURY, "बुध"),
    (swe.JUPITER, "गुरु"),
    (swe.VENUS, "शुक्र"),
    (swe.SATURN, "शनि"),
    ((swe.TRUE_NODE if USE_TRUE_NODE else swe.MEAN_NODE), "राहु"),
]
# NOTE: No swe.KETU in pyswisseph; we compute it as Rahu + 180°.

def deg_to_dms(deg):
    d = int(deg)
    m = int((deg - d) * 60)
    s = round((deg - d - m/60) * 3600, 2)
    return f"{d:02d}° {m:02d}' {s:04.1f}\""

def geocode(place):
    if not place:
        return None
    try:
        if GEOAPIFY_API_KEY:
            r = requests.get(
                "https://api.geoapify.com/v1/geocode/search",
                params={"text": place, "format": "json", "apiKey": GEOAPIFY_API_KEY},
                timeout=10,
            )
            r.raise_for_status()
            js = r.json()
            if js.get("results"):
                it = js["results"][0]
                return float(it["lat"]), float(it["lon"]), it.get("timezone", {}).get("name", "UTC")
        # Fallback to free Nominatim
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": place, "format": "json", "limit": 1},
            headers={"User-Agent": "kundali-streamlit"},
            timeout=10,
        )
        r.raise_for_status()
        arr = r.json()
        if arr:
            it = arr[0]
            # no tz in response; guess using TimezoneFinder would need extra dep.
            return float(it["lat"]), float(it["lon"]), "UTC"
    except Exception:
        return None
    return None

def to_julian_ut(dt_local: datetime, tz_name: str):
    try:
        tz = pytz.timezone(tz_name)
    except Exception:
        tz = pytz.UTC
    aware_local = tz.localize(dt_local)
    utc_dt = aware_local.astimezone(pytz.UTC)
    hour_decimal = utc_dt.hour + utc_dt.minute/60 + utc_dt.second/3600
    return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, hour_decimal)

def planetary_positions(jd_ut):
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    rows = []
    rahu_lon = None
    for pid, name in PLANETS:
        lon, lat, dist, *_ = swe.calc_ut(jd_ut, pid, SIDEREAL_FLAG)
        lon = lon % 360.0
        sign = int(lon // 30) + 1
        rows.append([name, lon, deg_to_dms(lon), sign])
        if name == "राहु":
            rahu_lon = lon
    if rahu_lon is not None:
        ketu_lon = (rahu_lon + 180.0) % 360.0
        ketu_sign = int(ketu_lon // 30) + 1
        rows.append(["केतु", ketu_lon, deg_to_dms(ketu_lon), ketu_sign])
    df = pd.DataFrame(rows, columns=["ग्रह", "अंश (°)", "DMS", "राशि (1-12)"])
    return df.sort_values("अंश (°)").reset_index(drop=True)

def vimshottari_mahadasha(moon_long: float, birth_dt: datetime):
    # Determine nakshatra index and fraction completed
    nak_index = int((moon_long % 360.0) // (360.0/27.0))
    nak_frac = ((moon_long % 360.0) / (360.0/27.0)) - nak_index
    # Starting lord is cyclic through 9
    lord = DASHA_ORDER[nak_index % 9]
    elapsed = nak_frac * DASHA_YEARS[lord]

    md_start = birth_dt - timedelta(days=elapsed * YEAR_DAYS)
    end_at = birth_dt + timedelta(days=120 * YEAR_DAYS)

    out, idx = [], DASHA_ORDER.index(lord)
    cur_start = md_start
    # Build full 120 years
    for i in range(60):  # 60 entries are enough
        l = DASHA_ORDER[(idx + i) % 9]
        dur_days = DASHA_YEARS[l] * YEAR_DAYS
        out.append([l, cur_start.date(), (cur_start + timedelta(days=dur_days)).date()])
        cur_start += timedelta(days=dur_days)
        if cur_start > end_at:
            break
    return pd.DataFrame(out, columns=["महादशा", "आरंभ", "समाप्त"])

def main():
    st.set_page_config(page_title=APP_TITLE, layout="centered")
    st.title(APP_TITLE)
    st.caption("Lahiri ayanāṁśa • Sidereal positions • Swiss Ephemeris")

    with st.sidebar:
        st.header("जन्म विवरण")
        name = st.text_input("नाम", value="")
        place = st.text_input("जन्म स्थान (City, Country)", value="Mumbai, India")
        date = st.date_input("जन्म दिनांक", value=datetime(1990, 1, 1).date())
        time = st.time_input("जन्म समय", value=datetime(1990, 1, 1, 6, 0).time())
        tz_name = st.text_input("समय क्षेत्र (IANA TZ)", value="Asia/Kolkata")
        st.write("उदा: Asia/Kolkata, Europe/London, America/New_York")
        node_choice = st.selectbox("राहु नोड प्रकार", ["Mean (डिफ़ॉल्ट)", "True"])
        global USE_TRUE_NODE
        USE_TRUE_NODE = (node_choice == "True")

    # Update planets list with current Rahu type
    global PLANETS
    PLANETS = [
        (swe.SUN, "सूर्य"),
        (swe.MOON, "चंद्र"),
        (swe.MARS, "मंगल"),
        (swe.MERCURY, "बुध"),
        (swe.JUPITER, "गुरु"),
        (swe.VENUS, "शुक्र"),
        (swe.SATURN, "शनि"),
        ((swe.TRUE_NODE if USE_TRUE_NODE else swe.MEAN_NODE), "राहु"),
    ]

    if st.button("🔎 Calculate"):
        # Geocode (optional – only to show on the page)
        latlon = geocode(place)
        if latlon:
            lat, lon, tz_guess = latlon
            st.success(f"स्थान मिला: lat={lat:.4f}, lon={lon:.4f}, tz≈{tz_guess}")
        else:
            st.info("स्थान लोकेट नहीं कर पाए; दिए हुए timezone के साथ आगे बढ़ रहे हैं।")

        dt_local = datetime.combine(date, time)
        jd_ut = to_julian_ut(dt_local, tz_name)

        # Positions
        df = planetary_positions(jd_ut)
        st.subheader("ग्रह स्थिति (साइडरेल)")
        st.dataframe(df, use_container_width=True)

        # Vimshottari (from Moon longitude)
        moon_row = df[df["ग्रह"] == "चंद्र"]
        if not moon_row.empty:
            moon_long = float(moon_row.iloc[0]["अंश (°)"])
            md = vimshottari_mahadasha(moon_long, dt_local)
            st.subheader("विंशोत्तरी महादशा (120 वर्ष)")
            st.dataframe(md, use_container_width=True)
        else:
            st.warning("चंद्र स्थिति नहीं मिली, महादशा नहीं निकाल पाए।")

    st.markdown("---")
    st.caption("Note: This app computes **Ketu = Rahu + 180°** because pyswisseph does not define `swe.KETU`.")

if __name__ == "__main__":
    main()
