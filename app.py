
import os
import io
import json
import time
import datetime
import requests
import pytz
import streamlit as st
import matplotlib.pyplot as plt
import swisseph as swe
from math import floor
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from timezonefinder import TimezoneFinder

st.set_page_config(page_title="Kundali Generator – v4.3 (Geoapify)", page_icon="🪔", layout="wide")

# ---------------- Basics ----------------
SIGNS = ['Aries (1)','Taurus (2)','Gemini (3)','Cancer (4)','Leo (5)','Virgo (6)',
         'Libra (7)','Scorpio (8)','Sagittarius (9)','Capricorn (10)','Aquarius (11)','Pisces (12)']
NAKSHATRAS = ['Ashwini','Bharani','Krittika','Rohini','Mrigashira','Ardra','Punarvasu','Pushya','Ashlesha',
              'Magha','Purva Phalguni','Uttara Phalguni','Hasta','Chitra','Swati','Vishakha','Anuradha','Jyeshtha',
              'Mula','Purva Ashadha','Uttara Ashadha','Shravana','Dhanishta','Shatabhisha','Purva Bhadrapada','Uttara Bhadrapada','Revati']
DASHA_ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
DASHA_YEARS  = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
NAK_LORD    = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me'] * 3
PLANET_LABELS = {swe.SUN:'Su',swe.MOON:'Mo',swe.MERCURY:'Me',swe.VENUS:'Ve',swe.MARS:'Ma',swe.JUPITER:'Ju',swe.SATURN:'Sa',swe.MEAN_NODE:'Ra',-1:'Ke'}
NAME_MAP = {'Su':'Sun','Mo':'Moon','Me':'Mercury','Ve':'Venus','Ma':'Mars','Ju':'Jupiter','Sa':'Saturn','Ra':'Rahu','Ke':'Ketu'}

# --------------- Utilities ---------------
def dms(deg):
    d = floor(deg); m = floor((deg-d)*60); s = round((deg-d-m/60)*3600); return d,m,s

def lon_to_sign_deg(lon):
    sign = int(lon // 30); deg_in_sign = lon - sign*30; return sign, deg_in_sign

def fmt_deg_sign(lon):
    sign, deg = lon_to_sign_deg(lon); d,m,s = dms(deg); return f"{d:02d}°{m:02d}'{s:02d}\"", SIGNS[sign]

def nakshatra_pada(lon_sid):
    part = lon_sid % 360.0; nak_len = 360.0/27.0; pada_len = nak_len/4.0
    idx = int(part // nak_len); rem = part - idx*nak_len; pada = int(rem // pada_len) + 1
    return NAKSHATRAS[idx], pada, idx

def jd_from_dt(dt_utc):
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600)

def compute_chart(dt_local, tz_hours, lat, lon):
    dt_utc = dt_local - datetime.timedelta(hours=tz_hours)
    jd = jd_from_dt(dt_utc)
    flags = swe.FLG_MOSEPH
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    try:
        cusps, ascmc = swe.houses_ex(jd, flags, lat, lon, b'H')
    except Exception:
        cusps, ascmc = swe.houses(jd, lat, lon, b'H')
    ayan = swe.get_ayanamsa_ut(jd)
    plon = {}
    for p in [swe.SUN,swe.MOON,swe.MERCURY,swe.VENUS,swe.MARS,swe.JUPITER,swe.SATURN,swe.MEAN_NODE]:
        x,_ = swe.calc_ut(jd, p, flags); plon[p] = (x[0]-ayan)%360
    plon[-1] = (plon[swe.MEAN_NODE] + 180) % 360
    return {'jd': jd, 'ayanamsa': ayan, 'planets': plon}

def add_years(dt, years): return dt + datetime.timedelta(days=years*365.2425)

def moon_nakshatra_and_balance(moon_lon_sid):
    nak, _, idx = nakshatra_pada(moon_lon_sid)
    lord = NAK_LORD[idx]
    nak_len = 360.0/27.0
    pos_in_nak = (moon_lon_sid % nak_len)
    frac_elapsed = pos_in_nak / nak_len
    return lord, DASHA_YEARS[lord] * (1 - frac_elapsed)

def build_mahadasha_table(birth_dt_local, moon_lon_sid, horizon_years=120):
    start = birth_dt_local
    lord, rem_years = moon_nakshatra_and_balance(moon_lon_sid)
    first_change = add_years(start, rem_years)
    out = []; idx = (DASHA_ORDER.index(lord)+1)%9; t = first_change
    while (t-start).days/365.2425 <= horizon_years:
        L = DASHA_ORDER[idx]; yrs = DASHA_YEARS[L]; end = add_years(t, yrs)
        age = int((t-start).days/365.2425 + 0.5)
        out.append({'planet':L,'start':t,'end':end,'age':age,'years':yrs})
        t = end; idx = (idx+1)%9
    return out, first_change, lord, rem_years

def build_antar_within_md(md_start, md_years, md_lord):
    seq=DASHA_ORDER; md_days=md_years*365.2425; t=md_start; start_idx=seq.index(md_lord); res=[]
    for i in range(9):
        L = seq[(start_idx+i)%9]; factor=DASHA_YEARS[L]/120.0; d=md_days*factor; s=t; e=t+datetime.timedelta(days=d); res.append((L,s,e,d/365.2425)); t=e
    return res

def build_pratyantar_within_antar(antar_start, antar_years, antar_lord):
    seq=DASHA_ORDER; a_days=antar_years*365.2425; t=antar_start; start_idx=seq.index(antar_lord); res=[]
    for i in range(9):
        L=seq[(start_idx+i)%9]; factor=DASHA_YEARS[L]/120.0; d=a_days*factor; s=t; e=t+datetime.timedelta(days=d); res.append((L,s,e)); t=e
    return res

def antar_pratyantar_next_year(now_dt_local, md_table, birth_dt_local, moon_lon_sid, first_change, birth_md_lord, birth_md_remaining):
    schedule=[]; birth_end = add_years(birth_dt_local, birth_md_remaining); schedule.append((birth_md_lord,birth_dt_local,birth_end))
    for md in md_table: schedule.append((md['planet'],md['start'],md['end']))
    horizon_end = now_dt_local + datetime.timedelta(days=366); rows=[]
    for MD,ms,me in schedule:
        if me<now_dt_local or ms>horizon_end: continue
        antars = build_antar_within_md(ms, DASHA_YEARS[MD], MD)
        for AL,as_,ae,ay in antars:
            if ae<now_dt_local or as_>horizon_end: continue
            pr = build_pratyantar_within_antar(as_, ay, AL)
            for PL,ps,pe in pr:
                if pe<now_dt_local or ps>horizon_end: continue
                rows.append({'major':MD,'antar':AL,'pratyantar':PL,'start':max(ps,now_dt_local),'end':min(pe,horizon_end)})
    rows.sort(key=lambda r:r['start']); return rows

def draw_blank_north_indian():
    fig = plt.figure(figsize=(6,6), facecolor='white'); ax = fig.add_axes([0,0,1,1])
    ax.set_xlim(0,100); ax.set_ylim(0,100); ax.axis('off')
    ax.plot([0,100,100,0,0],[0,0,100,100,0],color='black',linewidth=1.2)
    ax.plot([0,50,100,50,0],[50,0,50,100,50],color='black',linewidth=1.2)
    ax.plot([0,50,100,50,0],[0,50,100,50,0],color='black',linewidth=1.2)
    return fig

def build_docx(name, dob, tob, place, tz_hours, positions, md_table, antar_rows, lagna_blank, nav_blank):
    doc = Document(); title = doc.add_heading('Janam Kundali (Vedic)', 0); title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    table = doc.add_table(rows=1, cols=2); left,right = table.rows[0].cells
    p=left.paragraphs[0]; r=p.add_run('Personal Details\n'); r.bold=True
    left.add_paragraph(f"Name: {name}"); left.add_paragraph(f"Date of Birth: {dob.strftime('%d-%m-%Y')}")
    left.add_paragraph(f"Time of Birth: {tob.strftime('%H:%M')} (UTC{tz_hours:+.2f})"); left.add_paragraph(f"Place of Birth: {place}")
    left.add_paragraph('\\nPlanetary Positions').runs[0].bold=True
    pos_tbl = doc.add_table(rows=1, cols=5); h=pos_tbl.rows[0].cells; h[0].text='Planet'; h[1].text='Degree'; h[2].text='Sign'; h[3].text='Nakshatra'; h[4].text='Pada'
    for row in positions:
        c=pos_tbl.add_row().cells
        for i,v in enumerate(row): c[i].text=str(v)
    left.add_paragraph('\\nVimshottari Mahadasha').runs[0].bold=True
    md_tbl = doc.add_table(rows=1, cols=4); h=md_tbl.rows[0].cells; h[0].text='Planet'; h[1].text='Start Date'; h[2].text='End Date'; h[3].text='Age (start)'
    for md in md_table:
        c=md_tbl.add_row().cells; c[0].text=md['planet']; c[1].text=md['start'].strftime('%d-%m-%Y'); c[2].text=md['end'].strftime('%d-%m-%Y'); c[3].text=str(md['age'])
    left.add_paragraph('\\nCurrent Antar/Pratyantar (Next 1 year)').runs[0].bold=True
    ap_tbl = doc.add_table(rows=1, cols=5); h=ap_tbl.rows[0].cells; h[0].text='Major Dasha'; h[1].text='Antar'; h[2].text='Pratyantar'; h[3].text='Start'; h[4].text='End'
    for r in antar_rows:
        c=ap_tbl.add_row().cells; c[0].text=r['major']; c[1].text=r['antar']; c[2].text=r['pratyantar']; c[3].text=r['start'].strftime('%d-%m-%Y'); c[4].text=r['end'].strftime('%d-%m-%Y')
    import tempfile
    right.add_paragraph('Lagna (D-1)').runs[0].bold=True
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f1:
        lagna_blank.savefig(f1.name, dpi=200, bbox_inches='tight'); right.add_paragraph().add_run().add_picture(f1.name, width=Inches(3.5))
    right.add_paragraph('Navamsa (D-9)').runs[0].bold=True
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f2:
        nav_blank.savefig(f2.name, dpi=200, bbox_inches='tight'); right.add_paragraph().add_run().add_picture(f2.name, width=Inches(3.5))
    return doc

# -------------- Geoapify --------------
def get_geoapify_key():
    if "GEOAPIFY_API_KEY" in st.secrets: return st.secrets["GEOAPIFY_API_KEY"]
    return os.environ.get("GEOAPIFY_API_KEY","")

def geocode_geoapify(query):
    api_key = get_geoapify_key()
    if not api_key: raise RuntimeError("Geoapify API key missing. Add GEOAPIFY_API_KEY to Streamlit secrets.")
    url = "https://api.geoapify.com/v1/geocode/search"
    params = {"text": query, "format":"json", "apiKey": api_key, "limit": 1}
    r = requests.get(url, params=params, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"Geoapify HTTP {r.status_code}: {r.text[:120]}")
    data = r.json()
    if not data.get("results"):
        raise RuntimeError("Place not found.")
    res = data["results"][0]
    lat, lon = float(res["lat"]), float(res["lon"])
    display_name = res.get("formatted","")
    return lat, lon, display_name

def tz_from_latlon(lat, lon, dt_local):
    tf = TimezoneFinder()
    tzname = tf.timezone_at(lat=lat, lng=lon) or "Etc/UTC"
    tz = pytz.timezone(tzname)
    offset_hours = tz.utcoffset(dt_local.replace(tzinfo=None)).total_seconds()/3600.0
    return tzname, offset_hours

# -------------- UI --------------
st.title("🪔 Kundali Generator – v4.3 (Geoapify)")
st.caption("Global place search via Geoapify (set API key), automatic timezone from coordinates, and your custom DOCX layout.")

c1, c2 = st.columns([1,1])
with c1:
    name = st.text_input("Name", "Sample Name")
    dob  = st.date_input("Date of Birth", datetime.date(1987,9,15))
    tob  = st.time_input("Time of Birth", datetime.time(22,53), step=datetime.timedelta(minutes=1))
with c2:
    place_query = st.text_input("Place of Birth (city, state, country)", "Paris, France")
    manual_mode = st.checkbox("Manual lat/lon/timezone (fallback)", value=False)
    if manual_mode:
        lat = st.number_input("Latitude", value=48.8566, format="%.6f")
        lon = st.number_input("Longitude", value=2.3522, format="%.6f")
        tz_hours = st.number_input("UTC offset (e.g., IST=5.5)", value=2.0, step=0.25)

go = st.button("Generate Horoscope")

if go:
    try:
        dt_local = datetime.datetime.combine(dob, tob)
        if manual_mode:
            display_place = "Manual"
        else:
            lat, lon, display_place = geocode_geoapify(place_query)
            tzname, tz_hours_calc = tz_from_latlon(lat, lon, dt_local)
            tz_hours = tz_hours_calc
            st.info(f"Resolved: {display_place} → lat {lat:.6f}, lon {lon:.6f}, tz {tzname} (UTC{tz_hours:+.2f})")

        data = compute_chart(dt_local, tz_hours, lat, lon)

        plist = [swe.SUN,swe.MOON,swe.MERCURY,swe.VENUS,swe.MARS,swe.JUPITER,swe.SATURN,swe.MEAN_NODE,-1]
        pos_rows = []
        for p in plist:
            lonp = data['planets'][p]
            deg, sign = fmt_deg_sign(lonp)
            nak, pada, _ = nakshatra_pada(lonp)
            pos_rows.append([NAME_MAP[PLANET_LABELS[p]], deg, sign, nak, str(pada)])

        md_list, first_change, birth_md_lord, birth_md_rem = build_mahadasha_table(dt_local, data['planets'][swe.MOON])
        now_local = datetime.datetime.now()
        antar_rows = antar_pratyantar_next_year(now_local, md_list, dt_local, data['planets'][swe.MOON], first_change, birth_md_lord, birth_md_rem)

        st.subheader("Planetary Positions")
        st.dataframe({'Planet':[r[0] for r in pos_rows],'Degree':[r[1] for r in pos_rows],'Sign':[r[2] for r in pos_rows],'Nakshatra':[r[3] for r in pos_rows],'Pada':[r[4] for r in pos_rows]})
        st.subheader("Vimshottari Mahadasha")
        st.dataframe({'Planet':[md['planet'] for md in md_list],'Start':[md['start'].strftime('%d-%m-%Y') for md in md_list],'End':[md['end'].strftime('%d-%m-%Y') for md in md_list],'Age (start)':[md['age'] for md in md_list]})
        st.subheader("Antar / Pratyantar – Next 1 year")
        st.dataframe({'Major':[r['major'] for r in antar_rows],'Antar':[r['antar'] for r in antar_rows],'Pratyantar':[r['pratyantar'] for r in antar_rows],'Start':[r['start'].strftime('%d-%m-%Y') for r in antar_rows],'End':[r['end'].strftime('%d-%m-%Y') for r in antar_rows]})
        lagna_blank, nav_blank = draw_blank_north_indian(), draw_blank_north_indian()
        doc = build_docx(name, dob, tob, display_place, tz_hours, pos_rows, md_list, antar_rows, lagna_blank, nav_blank)
        buf = io.BytesIO(); doc.save(buf); buf.seek(0)
        st.download_button("⬇️ Download Word (.docx)", data=buf, file_name=f"Kundali_{name.replace(' ','_')}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    except Exception as e:
        st.error(f"Error: {e}")
