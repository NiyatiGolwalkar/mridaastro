
# Kundali Generator (Streamlit)

This is a minimal **Streamlit** app that generates a Vedic horoscope in **North-Indian** style:
- **Lagna (D-1)** chart
- **Navamsa (D-9)** chart
- **Planetary positions (sidereal, Lahiri)**
- **Downloadable Word (.docx)** with charts + positions

## Run Locally (Windows/Mac/Linux)

1. Install Python 3.10+
2. Open terminal in this folder and run:
   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```
3. Your browser opens at `http://localhost:8501`

## Deploy on Streamlit Community Cloud (free)

1. Create a GitHub repo and upload **app.py** and **requirements.txt**
2. Go to https://share.streamlit.io/
3. Click **New app** → select your repo → branch → `app.py` as main file → **Deploy**
4. Share the URL with anyone

## Notes

- The app uses Swiss Ephemeris via **pyswisseph** with **Moshier** computation mode (no ephemeris files required).
- Timezone: enter `5.5` for IST (UTC+05:30), negative values for west of UTC.
- City list includes common Indian cities; you can also type custom lat/lon.
- Extendable: Hindi labels, Chalit overlay, Dasha timeline, PDF export, custom template.
