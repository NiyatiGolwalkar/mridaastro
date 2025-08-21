import streamlit as st
import datetime
import io
import tempfile
from math import floor
import matplotlib.pyplot as plt
import swisseph as swe
from docx import Document
from docx.shared import Inches

# New deps
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz

st.set_page_config(page_title="Kundali Generator (Streamlit)", page_icon="🪔", layout="wide")

# -----------------------------
# Helpers
# -----------------------------
SIGNS = ['Mesha (1)', 'Vrishabha (2)', 'Mithuna (3)', 'Karka (4)',
         'Simha (5)', 'Kanya (6)', 'Tula (7)', 'Vrischika (8)',
         'Dhanu (9)', 'Makara (10)', 'Kumbha (11)', 'Meena (12)']
SIGN_SHORT = ['1','2','3','4','5','6','7','8','9','10','11','12']
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

def fmt_lon(lon):
    sign, deg = lon_to_sign_deg(lon)
    d, m, s = dms(deg)
    return f"{SIGNS[sign]} {d:02d}°{m:02d}'{s:02d}\""

def jd_from_dt(dt_utc):
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                      dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600)

def geocode_place(place_text, dt_local_naive):
    '''Return (lat, lon, tz_name, tz_offset_hours). Raises ValueError on failure.'''
    geolocator = Nominatim(user_agent='kundali_streamlit_app')
    loc = geolocator.geocode(place_text, language='en', addressdetails=True, timeout=10)
    if loc is None:
        raise ValueError('Could not find that place. Try "City, State, Country" (e.g., "Jabalpur, MP, India").')
    lat, lon = float(loc.latitude), float(loc.longitude)

    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon)
    if tz_name is None:
        # Fallback for India
        tz_name = 'Asia/Kolkata'
    tz = pytz.timezone(tz_name)
    # Localize the naive local time to get proper UTC offset (handles DST if any)
    dt_aware = tz.localize(dt_local_naive)
    offset_hours = dt_aware.utcoffset().total_seconds()/3600.0
    return lat, lon, tz_name, offset_hours

def compute_chart(dt_local, tz_hours, lat, lon, use_moshier=True):
    # Convert to UTC
    dt_utc = dt_local - datetime.timedelta(hours=tz_hours)
    jd = jd_from_dt(dt_utc)

    # Choose flags: prefer built-in Moshier to avoid ephemeris files
    flags = swe.FLG_MOSEPH if use_moshier else swe.FLG_SWIEPH

    # Set Lahiri sidereal mode, then get ayanamsa for this JD.
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    # Houses (Placidus) then convert to Lahiri sidereal
    try:
        cusps, ascmc = swe.houses_ex(jd, flags, lat, lon, b'H')
    except Exception:
        cusps, ascmc = swe.houses(jd, lat, lon, b'H')
    ayan = swe.get_ayanamsa_ut(jd)

    asc_sidereal = (ascmc[0] - ayan) % 360
    houses_sidereal = [(c - ayan) % 360 for c in cusps[1:13]]

    # Planets sidereal longitudes
    planet_list = [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS,
                   swe.JUPITER, swe.SATURN, swe.MEAN_NODE]
    plon = {}
    for p in planet_list:
        x, _ = swe.calc_ut(jd, p, flags)   # x = [lon, lat, dist, speedlon, speedlat, speeddist]
        lon_trop = x[0]
        lon_sid = (lon_trop - ayan) % 360
        plon[p] = lon_sid

    # Ketu opposite Rahu
    plon[-1] = (plon[swe.MEAN_NODE] + 180) % 360
    return {'jd': jd, 'ayanamsa': ayan, 'asc': asc_sidereal, 'houses': houses_sidereal, 'planets': plon}

def draw_north_indian(house_lons, planet_lons, title='Lagna (D-1)'):
    asc_sign, _ = lon_to_sign_deg(house_lons[0])
    house_signs = [(asc_sign + i) % 12 for i in range(12)]
    placements = {i+1: [] for i in range(12)}
    for p, lon in planet_lons.items():
        rel = (lon - house_lons[0]) % 360
        house = int(rel // 30) + 1
        placements[house].append(PLANET_LABELS[p])

    fig = plt.figure(figsize=(6,6), facecolor='white')
    ax = fig.add_axes([0,0,1,1])
    ax.set_xlim(0,100); ax.set_ylim(0,100); ax.axis('off')
    # Use single-color lines for all shapes
    ax.plot([0,100,100,0,0],[0,0,100,100,0], color='black', linewidth=1.2)
    ax.plot([0,50,100,50,0],[50,0,50,100,50], color='black', linewidth=1.2)
    ax.plot([0,50,100,50,0],[0,50,100,50,0], color='black', linewidth=1.2)

    coords = {1:(50,6), 2:(78,14), 3:(92,38), 4:(85,62),
              5:(78,86), 6:(50,94), 7:(22,86), 8:(8,62),
              9:(14,38), 10:(20,14), 11:(50,50), 12:(80,50)}
    for h in range(1,13):
        x,y = coords[h]
        ax.text(x,y, SIGN_SHORT[house_signs[h-1]], ha='center', va='center', fontsize=12, fontweight='bold')
        if placements[h]:
            ax.text(x, y+6, ' '.join(placements[h]), ha='center', va='center', fontsize=12)
    ax.set_title(title, fontsize=14)
    return fig

def navamsa_sign_index(lon):
    sign_index, deg_in_sign = lon_to_sign_deg(lon)
    part = int((deg_in_sign) // (30/9))
    if sign_index % 2 == 0:
        nav_sign = (sign_index + part) % 12
    else:
        nav_sign = (sign_index + (8 - part)) % 12
    return nav_sign

def draw_navamsa(planet_lons, title='Navamsa (D-9)'):
    place = {i+1: [] for i in range(12)}
    for p, lon in planet_lons.items():
        nav_sign = navamsa_sign_index(lon)
        place[nav_sign+1].append(PLANET_LABELS[p])

    fig = plt.figure(figsize=(6,6), facecolor='white')
    ax = fig.add_axes([0,0,1,1])
    ax.set_xlim(0,100); ax.set_ylim(0,100); ax.axis('off')
    ax.plot([0,100,100,0,0],[0,0,100,100,0], color='black', linewidth=1.2)
    ax.plot([0,50,100,50,0],[50,0,50,100,50], color='black', linewidth=1.2)
    ax.plot([0,50,100,50,0],[0,50,100,50,0], color='black', linewidth=1.2)

    coords = {1:(50,6), 2:(78,14), 3:(92,38), 4:(85,62),
              5:(78,86), 6:(50,94), 7:(22,86), 8:(8,62),
              9:(14,38), 10:(20,14), 11:(50,50), 12:(80,50)}
    for s in range(1,13):
        x,y = coords[s]
        ax.text(x,y, SIGN_SHORT[s-1], ha='center', va='center', fontsize=12, fontweight='bold')
        if place[s]:
            ax.text(x, y+6, ' '.join(place[s]), ha='center', va='center', fontsize=12)
    ax.set_title(title, fontsize=14)
    return fig

def build_docx(person_name, dt_local, tz_hours, place_name, lat, lon, positions_table, lagna_fig, nav_fig):
    # Save figs to temp PNG files to embed reliably
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f1:
        lagna_path = f1.name
        lagna_fig.savefig(lagna_path, format='png', dpi=200, bbox_inches='tight')
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f2:
        nav_path = f2.name
        nav_fig.savefig(nav_path, format='png', dpi=200, bbox_inches='tight')

    doc = Document()
    doc.add_heading('Janam Kundali (Vedic) – ' + person_name, 0)
    p = doc.add_paragraph()
    p.add_run('Birth Details: ').bold = True
    p.add_run(f"{dt_local.strftime('%d-%m-%Y %H:%M')} (UTC{tz_hours:+}), {place_name} ")
    p.add_run(f"(Lat {lat:.6f}, Lon {lon:.6f})")
    doc.add_heading('Planetary Positions (Sidereal – Lahiri)', level=1)
    for row in positions_table:
        doc.add_paragraph(row)
    doc.add_heading('Charts', level=1)
    doc.add_paragraph('Lagna (D-1):')
    doc.add_picture(lagna_path, width=Inches(4.8))
    doc.add_paragraph('Navamsa (D-9):')
    doc.add_picture(nav_path, width=Inches(4.8))
    doc.add_paragraph('Note: Rahu = Mean Node, Ketu = 180° from Rahu.')

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# -----------------------------
# UI
# -----------------------------
st.title('🪔 Kundali Generator (North-Indian)')
st.caption('Enter Name / DOB / Time / Place (City, State, Country). We will auto-detect latitude, longitude and timezone.')

colA, colB = st.columns([1,1])

with colA:
    name = st.text_input('Name', 'Sample Name')
    dob = st.date_input('Date of Birth', datetime.date(1987,9,15))
    tob = st.time_input('Time of Birth', datetime.time(22,53), step=datetime.timedelta(minutes=1))
with colB:
    place = st.text_input('Place of Birth (City, State, Country)', 'Bengaluru, Karnataka, India')
    tz_override = st.text_input('Timezone override (optional, e.g., 5.5)', '')

run = st.button('Generate Kundali')

if run:
    try:
        # Step 1: geocode
        with st.spinner('Resolving place to latitude/longitude and timezone...'):
            dt_local_naive = datetime.datetime.combine(dob, tob)
            lat, lon, tz_name, tz_hours = geocode_place(place, dt_local_naive)
            if tz_override.strip():
                try:
                    tz_hours = float(tz_override.strip())
                except:
                    st.warning('Could not parse timezone override; using detected timezone.')

        st.success(f'Place resolved: lat={lat:.6f}, lon={lon:.6f}, timezone={tz_name} (UTC{tz_hours:+.2f})')

        # Step 2: compute chart
        data = compute_chart(dt_local_naive, tz_hours, lat, lon, use_moshier=True)

        # Step 3: Planetary positions
        plist = [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS,
                 swe.JUPITER, swe.SATURN, swe.MEAN_NODE, -1]
        pos_lines = [f"{PLANET_LABELS[p]:>2}: {fmt_lon(data['planets'][p])}" for p in plist]

        st.subheader('Planetary Positions (Sidereal – Lahiri)')
        st.code('\\n'.join(pos_lines))

        # Step 4: Charts
        st.subheader('Charts')
        lagna_fig = draw_north_indian(data['houses'], data['planets'], 'Lagna (D-1)')
        nav_fig = draw_navamsa(data['planets'], 'Navamsa (D-9)')
        la_col, na_col = st.columns(2)
        with la_col:
            st.pyplot(lagna_fig, clear_figure=True)
        with na_col:
            st.pyplot(nav_fig, clear_figure=True)

        # Step 5: Download DOCX
        st.subheader('Download Report')
        docx_buf = build_docx(name, dt_local_naive, tz_hours, place, lat, lon, pos_lines, lagna_fig, nav_fig)
        st.download_button('⬇️ Download Word (.docx)', data=docx_buf, file_name=f'Kundali_{name.replace(" ", "_")}.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    except Exception as e:
        st.error(f'Something went wrong: {e}')
        st.stop()

st.markdown('---')
st.caption('Next up: Hindi labels, Vimshottari Dasha, Whole-sign houses, PDF export.')
