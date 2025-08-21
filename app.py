
import streamlit as st
import datetime
import io
import math
import tempfile
from math import floor
import matplotlib.pyplot as plt
import swisseph as swe
from docx import Document
from docx.shared import Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# New deps
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz

st.set_page_config(page_title="Kundali Generator (Streamlit)", page_icon="🪔", layout="wide")

# -----------------------------
# Helpers
# -----------------------------
SIGNS = ['Aries (1)', 'Taurus (2)', 'Gemini (3)', 'Cancer (4)',
         'Leo (5)', 'Virgo (6)', 'Libra (7)', 'Scorpio (8)',
         'Sagittarius (9)', 'Capricorn (10)', 'Aquarius (11)', 'Pisces (12)']
SIGN_SHORT = ['1','2','3','4','5','6','7','8','9','10','11','12']

NAKSHATRAS = [
    'Ashwini','Bharani','Krittika','Rohini','Mrigashira','Ardra','Punarvasu','Pushya','Ashlesha',
    'Magha','Purva Phalguni','Uttara Phalguni','Hasta','Chitra','Swati','Vishakha','Anuradha','Jyeshtha',
    'Mula','Purva Ashadha','Uttara Ashadha','Shravana','Dhanishta','Shatabhisha','Purva Bhadrapada','Uttara Bhadrapada','Revati'
]
# Vimshottari dasha order and years
DASHA_ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
DASHA_YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
# Nakshatra lords in order starting at Ashwini
NAK_LORD = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me'] * 3

PLANET_LABELS = {
    swe.SUN: 'Su', swe.MOON: 'Mo', swe.MERCURY: 'Me', swe.VENUS: 'Ve',
    swe.MARS: 'Ma', swe.JUPITER: 'Ju', swe.SATURN: 'Sa',
    swe.MEAN_NODE: 'Ra',  # Rahu (mean node)
    -1: 'Ke'              # Ketu placeholder (180° from Rahu)
}

def dms(deg):
    d = floor(deg)
    m = floor((deg - d)*60)
    s = round((deg - d - m/60)*3600)
    return d, m, s

def lon_to_sign_deg(lon):
    sign = int(lon // 30)
    deg_in_sign = lon - sign*30
    return sign, deg_in_sign

def fmt_deg_sign(lon):
    sign, deg = lon_to_sign_deg(lon)
    d, m, s = dms(deg)
    return f"{d:02d}°{m:02d}'{s:02d}\"", SIGNS[sign]

def nakshatra_pada(lon_sid):
    # 27 * 13°20' = 360; one nakshatra = 13.333333..., one pada = 3°20' = 3.333333...
    part = lon_sid % 360.0
    nak_len = 360.0 / 27.0
    pada_len = nak_len / 4.0
    idx = int(part // nak_len)  # 0..26
    rem = part - idx * nak_len
    pada = int(rem // pada_len) + 1  # 1..4
    return NAKSHATRAS[idx], pada, idx

def jd_from_dt(dt_utc):
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                      dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600)

def geocode_place(place_text, dt_local_naive):
    geolocator = Nominatim(user_agent='kundali_streamlit_app')
    loc = geolocator.geocode(place_text, language='en', addressdetails=True, timeout=10)
    if loc is None:
        raise ValueError('Could not find that place. Try "City, State, Country" (e.g., "Jabalpur, MP, India").')
    lat, lon = float(loc.latitude), float(loc.longitude)
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon) or 'Asia/Kolkata'
    tz = pytz.timezone(tz_name)
    dt_aware = tz.localize(dt_local_naive)
    offset_hours = dt_aware.utcoffset().total_seconds()/3600.0
    return lat, lon, tz_name, offset_hours

def compute_chart(dt_local, tz_hours, lat, lon, use_moshier=True):
    dt_utc = dt_local - datetime.timedelta(hours=tz_hours)
    jd = jd_from_dt(dt_utc)
    flags = swe.FLG_MOSEPH if use_moshier else swe.FLG_SWIEPH
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    try:
        cusps, ascmc = swe.houses_ex(jd, flags, lat, lon, b'H')
    except Exception:
        cusps, ascmc = swe.houses(jd, lat, lon, b'H')
    ayan = swe.get_ayanamsa_ut(jd)
    asc_sidereal = (ascmc[0] - ayan) % 360
    houses_sidereal = [(c - ayan) % 360 for c in cusps[1:13]]
    planet_list = [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS,
                   swe.JUPITER, swe.SATURN, swe.MEAN_NODE]
    plon = {}
    for p in planet_list:
        x, _ = swe.calc_ut(jd, p, flags)
        lon_trop = x[0]
        lon_sid = (lon_trop - ayan) % 360
        plon[p] = lon_sid
    plon[-1] = (plon[swe.MEAN_NODE] + 180) % 360  # Ketu
    return {'jd': jd, 'ayanamsa': ayan, 'asc': asc_sidereal, 'houses': houses_sidereal, 'planets': plon}

def draw_blank_north_indian(title=''):
    fig = plt.figure(figsize=(6,6), facecolor='white')
    ax = fig.add_axes([0,0,1,1])
    ax.set_xlim(0,100); ax.set_ylim(0,100); ax.axis('off')
    ax.plot([0,100,100,0,0],[0,0,100,100,0], color='black', linewidth=1.2)
    ax.plot([0,50,100,50,0],[50,0,50,100,50], color='black', linewidth=1.2)
    ax.plot([0,50,100,50,0],[0,50,100,50,0], color='black', linewidth=1.2)
    if title:
        ax.set_title(title, fontsize=14)
    return fig

# -----------------------------
# Vimshottari Dasha Calculations
# -----------------------------
def moon_nakshatra_and_balance(moon_lon_sid):
    nak, _, idx = nakshatra_pada(moon_lon_sid)
    lord = NAK_LORD[idx]
    nak_len = 360.0/27.0
    pos_in_nak = (moon_lon_sid % nak_len)
    frac_elapsed = pos_in_nak / nak_len
    md_years = DASHA_YEARS[lord]
    remaining_years = md_years * (1 - frac_elapsed)
    return lord, remaining_years

def add_years(dt, years):
    days = years * 365.2425
    return dt + datetime.timedelta(days=days)

def build_mahadasha_table(birth_dt_local, moon_lon_sid, horizon_years=120):
    start_dt = birth_dt_local
    start_lord, rem_years = moon_nakshatra_and_balance(moon_lon_sid)
    # First change after birth:
    md_list = []
    # from birth to first change: remaining of birth MD
    first_change = add_years(start_dt, rem_years)
    next_index = (DASHA_ORDER.index(start_lord) + 1) % 9
    # Generate MDs from the first change for ~120 years from birth
    current_start = first_change
    while (current_start - start_dt).days/365.2425 <= horizon_years:
        lord = DASHA_ORDER[next_index]
        years = DASHA_YEARS[lord]
        end = add_years(current_start, years)
        age_at_start = int((current_start - start_dt).days/365.2425 + 0.5)  # nearest year
        md_list.append({'planet': lord, 'start': current_start, 'end': end, 'age': age_at_start, 'years': years})
        current_start = end
        next_index = (next_index + 1) % 9
    return md_list, first_change, start_lord, rem_years

def build_antar_within_md(md_start, md_years, md_lord):
    'Return list of (antar_lord, antar_start, antar_end, antar_years_equiv).'
    seq = DASHA_ORDER
    md_dur_days = md_years * 365.2425
    entries = []
    t = md_start
    # Antar order starts with MD lord
    start_idx = seq.index(md_lord)
    for i in range(9):
        lord = seq[(start_idx + i) % 9]
        years_factor = DASHA_YEARS[lord] / 120.0
        dur_days = md_dur_days * years_factor
        start = t
        end = t + datetime.timedelta(days=dur_days)
        entries.append((lord, start, end, dur_days/365.2425))
        t = end
    return entries

def build_pratyantar_within_antar(antar_start, antar_years, antar_lord):
    seq = DASHA_ORDER
    antar_dur_days = antar_years * 365.2425
    entries = []
    t = antar_start
    # Pratyantar order starts with Antar lord
    start_idx = seq.index(antar_lord)
    for i in range(9):
        lord = seq[(start_idx + i) % 9]
        years_factor = DASHA_YEARS[lord] / 120.0
        dur_days = antar_dur_days * years_factor
        start = t
        end = t + datetime.timedelta(days=dur_days)
        entries.append((lord, start, end))
        t = end
    return entries

def antar_pratyantar_next_year(now_dt_local, md_table, birth_dt_local, moon_lon_sid, first_change, birth_md_lord, birth_md_remaining):
    'Return rows for next 1 year from now_dt_local: Major, Antar, Pratyantar, start, end.'
    # Build a full MD schedule including the remainder of birth MD
    schedule = []
    # Birth running MD segment
    birth_end = add_years(birth_dt_local, birth_md_remaining)
    schedule.append((birth_md_lord, birth_dt_local, birth_end))
    for md in md_table:
        schedule.append((md['planet'], md['start'], md['end']))

    horizon_end = now_dt_local + datetime.timedelta(days=366)
    rows = []
    for md_lord, md_start, md_end in schedule:
        if md_end < now_dt_local or md_start > horizon_end:
            continue
        md_years = DASHA_YEARS[md_lord]
        antars = build_antar_within_md(md_start, md_years, md_lord)
        for antar_lord, a_start, a_end, a_years in antars:
            if a_end < now_dt_local or a_start > horizon_end:
                continue
            praty = build_pratyantar_within_antar(a_start, a_years, antar_lord)
            for pr_lord, p_start, p_end in praty:
                if p_end < now_dt_local or p_start > horizon_end:
                    continue
                s = max(p_start, now_dt_local)
                e = min(p_end, horizon_end)
                rows.append({
                    'major': md_lord, 'antar': antar_lord, 'pratyantar': pr_lord,
                    'start': s, 'end': e
                })
    # Sort by start time
    rows.sort(key=lambda r: r['start'])
    return rows

# -----------------------------
# DOCX Builder (two-column layout)
# -----------------------------
def build_docx(person_name, dob, tob, place_name, tz_hours,
               positions, md_table, antar_rows,
               lagna_blank_fig, nav_blank_fig):
    doc = Document()
    title = doc.add_heading('Janam Kundali (Vedic)', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    table = doc.add_table(rows=1, cols=2)
    left, right = table.rows[0].cells

    # Left column: Personal details
    p = left.paragraphs[0]
    run = p.add_run('Personal Details\n')
    run.bold = True
    left.add_paragraph(f"Name: {person_name}")
    left.add_paragraph(f"Date of Birth: {dob.strftime('%d-%m-%Y')}")
    left.add_paragraph(f"Time of Birth: {tob.strftime('%H:%M')} (UTC{tz_hours:+.2f})")
    left.add_paragraph(f"Place of Birth: {place_name}")

    # Planetary Positions
    left.add_paragraph('\nPlanetary Positions').runs[0].bold = True
    pos_tbl = doc.add_table(rows=1, cols=5)
    hdr = pos_tbl.rows[0].cells
    hdr[0].text = 'Planet'; hdr[1].text='Degree'; hdr[2].text='Sign'; hdr[3].text='Nakshatra'; hdr[4].text='Pada'
    for row in positions:
        cells = pos_tbl.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)

    # Mahadasha table
    left.add_paragraph('\nVimshottari Mahadasha').runs[0].bold = True
    md_tbl = doc.add_table(rows=1, cols=4)
    hdr = md_tbl.rows[0].cells
    hdr[0].text='Planet'; hdr[1].text='Start Date'; hdr[2].text='End Date'; hdr[3].text='Age (start)'
    for md in md_table:
        cells = md_tbl.add_row().cells
        cells[0].text = md['planet']
        cells[1].text = md['start'].strftime('%d-%m-%Y')
        cells[2].text = md['end'].strftime('%d-%m-%Y')
        cells[3].text = str(md['age'])

    # Antar/Pratyantar next year
    left.add_paragraph('\nCurrent Antar/Pratyantar (Next 1 year)').runs[0].bold = True
    ap_tbl = doc.add_table(rows=1, cols=5)
    hdr = ap_tbl.rows[0].cells
    hdr[0].text='Major Dasha'; hdr[1].text='Antar'; hdr[2].text='Pratyantar'; hdr[3].text='Start'; hdr[4].text='End'
    for r in antar_rows:
        cells = ap_tbl.add_row().cells
        cells[0].text = r['major']; cells[1].text=r['antar']; cells[2].text=r['pratyantar']
        cells[3].text = r['start'].strftime('%d-%m-%Y')
        cells[4].text = r['end'].strftime('%d-%m-%Y')

    # Right column: blank charts
    right.add_paragraph('Lagna (D-1)').runs[0].bold = True
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f1:
        lagna_blank_fig.savefig(f1.name, dpi=200, bbox_inches='tight')
        right.add_paragraph().add_run().add_picture(f1.name, width=Inches(3.5))

    right.add_paragraph('Navamsa (D-9)').runs[0].bold = True
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f2:
        nav_blank_fig.savefig(f2.name, dpi=200, bbox_inches='tight')
        right.add_paragraph().add_run().add_picture(f2.name, width=Inches(3.5))

    return doc

# -----------------------------
# UI
# -----------------------------
st.title('🪔 Kundali Generator – v4')
st.caption('Left: Personal details + tables (positions, mahadasha, antar/pratyantar next 1 year). Right: blank Lagna & Navamsa charts.')

colA, colB = st.columns([1,1])

with colA:
    name = st.text_input('Name', 'Sample Name')
    dob = st.date_input('Date of Birth', datetime.date(1987,9,15))
    tob = st.time_input('Time of Birth', datetime.time(22,53), step=datetime.timedelta(minutes=1))
with colB:
    place = st.text_input('Place of Birth (City, State, Country)', 'Bengaluru, Karnataka, India')
    tz_override = st.text_input('Timezone override (optional, e.g., 5.5)', '')

run = st.button('Generate Horoscope')

if run:
    try:
        with st.spinner('Resolving place to latitude/longitude and timezone...'):
            dt_local_naive = datetime.datetime.combine(dob, tob)
            lat, lon, tz_name, tz_hours = geocode_place(place, dt_local_naive)
            if tz_override.strip():
                try: tz_hours = float(tz_override.strip())
                except: st.warning('Could not parse timezone override; using detected timezone.')
        st.success(f'Resolved: lat={lat:.6f}, lon={lon:.6f}, tz={tz_name} (UTC{tz_hours:+.2f})')

        data = compute_chart(dt_local_naive, tz_hours, lat, lon, use_moshier=True)

        plist = [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS, swe.JUPITER, swe.SATURN, swe.MEAN_NODE, -1]
        pos_rows = []
        for p in plist:
            lonp = data['planets'][p]
            deg_str, sign_name = fmt_deg_sign(lonp)
            nak, pada, _ = nakshatra_pada(lonp)
            pos_rows.append([ {'Su':'Sun','Mo':'Moon','Me':'Mercury','Ve':'Venus','Ma':'Mars','Ju':'Jupiter','Sa':'Saturn','Ra':'Rahu','Ke':'Ketu'}[PLANET_LABELS[p]], deg_str, sign_name, nak, str(pada) ])

        md_list, first_change, birth_md_lord, birth_md_rem = build_mahadasha_table(dt_local_naive, data['planets'][swe.MOON])
        now_local = datetime.datetime.now()
        antar_rows = antar_pratyantar_next_year(now_local, md_list, dt_local_naive, data['planets'][swe.MOON], first_change, birth_md_lord, birth_md_rem)

        # Preview
        st.subheader('Planetary Positions')
        st.dataframe({ 'Planet':[r[0] for r in pos_rows], 'Degree':[r[1] for r in pos_rows], 'Sign':[r[2] for r in pos_rows], 'Nakshatra':[r[3] for r in pos_rows], 'Pada':[r[4] for r in pos_rows] })
        st.subheader('Vimshottari Mahadasha')
        st.dataframe({ 'Planet':[md['planet'] for md in md_list], 'Start':[md['start'].strftime('%d-%m-%Y') for md in md_list], 'End':[md['end'].strftime('%d-%m-%Y') for md in md_list], 'Age (start)':[md['age'] for md in md_list] })
        st.subheader('Antar / Pratyantar – Next 1 year')
        st.dataframe({ 'Major':[r['major'] for r in antar_rows], 'Antar':[r['antar'] for r in antar_rows], 'Pratyantar':[r['pratyantar'] for r in antar_rows], 'Start':[r['start'].strftime('%d-%m-%Y') for r in antar_rows], 'End':[r['end'].strftime('%d-%m-%Y') for r in antar_rows] })

        lagna_blank = draw_blank_north_indian('')
        nav_blank = draw_blank_north_indian('')

        st.subheader('Download Report (DOCX)')
        doc = build_docx(name, dob, tob, place, tz_hours, pos_rows, md_list, antar_rows, lagna_blank, nav_blank)
        buf = io.BytesIO(); doc.save(buf); buf.seek(0)
        st.download_button('⬇️ Download Word (.docx)', data=buf, file_name=f'Kundali_{name.replace(" ","_")}.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    except Exception as e:
        st.error(f'Error: {e}')
        st.stop()

st.markdown('---')
st.caption('v4: Auto geocode + timezone, positions with nakshatra/pada, Mahadasha with Age, Antar/Pratyantar next 1 year, blank charts on right.')
