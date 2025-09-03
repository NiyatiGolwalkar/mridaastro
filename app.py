
# ===== Background Template Helper (stable image) =====
import os
from io import BytesIO
from docx import Document as _WordDocument

TEMPLATE_DOCX = "bg_template.docx"

# UI: set to True to show on-screen tables/preview (dev only)
PREVIEW_MODE = False

def make_document():
    try:
        if os.path.exists(TEMPLATE_DOCX):
            return _WordDocument(TEMPLATE_DOCX)
    except Exception:
        pass
    return _WordDocument()
# ===== End Background Template Helper =====


# app_docx_borders_85pt_editable_v6_8_8_locked.py
# Changes from 6.8.7:
# - Rename & style headings:
#     * "Planetary Positions..." -> "ग्रह स्थिति" (bold + underline)
#     * "Vimshottari Mahadasha..." -> "विंशोत्तरी महादशा" (bold + underline)
# - Fix kundali preview image whitespace: compact square PNG with zero padding

import math
import datetime, json, urllib.parse, urllib.request
from io import BytesIO

# --- One-page layout switch ---
ONE_PAGE = True

# --- Appearance configuration ---
# Sizing (pt) — tuned smaller to reduce white space
NUM_W_PT = 10       # house number box width (was 12)
NUM_H_PT = 12       # house number box height (was 14)
PLANET_W_PT = 20    # planet label box width (was 16)
PLANET_H_PT = 16    # planet label box height (was 14)
GAP_X_PT = 3        # horizontal gap between planet boxes (was 4)
OFFSET_Y_PT = 10    # vertical offset below number box (was 12)

# Options: "plain", "bordered", "shaded", "bordered_shaded"
HOUSE_NUM_STYLE = "bordered"
HOUSE_NUM_BORDER_PT = 0.75
HOUSE_NUM_SHADE = "#FFFFFF"  # soft light-yellow




# --- Reliable cell shading (works in all Word views) ---
def shade_cell(cell, fill_hex="FFFFFF"):
    return

def shade_header_row(table, fill_hex="FFFFFF"):
    return

def set_page_background(doc, hex_color):
    try:
        bg = OxmlElement('w:background')
        bg.set(qn('w:color'), hex_color)
        doc.element.insert(0, bg)
    except Exception:
        pass


# --- Phalit ruled lines (25 rows) ---
from docx.enum.table import WD_ROW_HEIGHT_RULE
def add_phalit_section(container_cell, width_inches=3.60, rows=25):
    head = container_cell.add_paragraph("फलित")
    _apply_hindi_caption_style(head, size_pt=11, underline=True, bold=True)

    t = container_cell.add_table(rows=rows, cols=1); t.autofit = False
    # Clear table borders so only bottom rules show
    try:
        tbl = t._tbl; tblPr = tbl.tblPr
        tblBorders = OxmlElement('w:tblBorders')
        for edge in ('top','left','bottom','right','insideH','insideV'):
            el = OxmlElement(f'w:{edge}'); el.set(qn('w:val'),'nil'); tblBorders.append(el)
        tblPr.append(tblBorders)
    except Exception:
        pass
    set_col_widths(t, [Inches(width_inches)])
    for r in t.rows:
        r.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
        r.height = Pt(14)
        c = r.cells[0]
        p = c.paragraphs[0]; run = p.add_run("\u00A0"); run.font.size = Pt(1)
        tcPr = c._tc.get_or_add_tcPr()
        for el in list(tcPr):
            if el.tag.endswith('tcBorders'):
                tcPr.remove(el)
        tcBorders = OxmlElement('w:tcBorders')
        for edge in ('top','left','right'):
            el = OxmlElement(f'w:{edge}'); el.set(qn('w:val'),'nil'); tcBorders.append(el)
        el = OxmlElement('w:bottom')
        el.set(qn('w:val'),'single'); el.set(qn('w:sz'),'8'); el.set(qn('w:space'),'0'); el.set(qn('w:color'),'B6B6B6')
        tcBorders.append(el)
        tcPr.append(tcBorders)

def _rects_overlap(a, b):
    return not (a['right'] <= b['left'] or a['left'] >= b['right'] or a['bottom'] <= b['top'] or a['top'] >= b['bottom'])

def _nudge_number_box(base_left, base_top, w, h, S, occupied):
    cx = S/2.0; cy = S/2.0
    bx = base_left + w/2.0; by = base_top + h/2.0
    vx = (bx - cx); vy = (by - cy)
    n = (vx*vx + vy*vy) ** 0.5 or 1.0
    ux, uy = vx/n, vy/n  # unit vector outward
    pad = 2.0
    for step in range(0, 9):  # try nudges up to ~16pt
        dx = ux * (step * 2.0)
        dy = uy * (step * 2.0)
        l = max(pad, min(S - w - pad, base_left + dx))
        t = max(pad, min(S - h - pad, base_top + dy))
        r = {'left': l, 'top': t, 'right': l + w, 'bottom': t + h}
        hit = False
        for o in occupied:
            if _rects_overlap(r, o):
                hit = True; break
        if not hit:
            return l, t
    return base_left, base_top
import matplotlib.pyplot as plt
import pandas as pd
import pytz
import streamlit as st
import swisseph as swe
from timezonefinder import TimezoneFinder


def _bbox_of_poly(poly):
    xs, ys = zip(*poly)
    return {'left': min(xs), 'top': min(ys), 'right': max(xs), 'bottom': max(ys)}

def _clamp_in_bbox(left, top, w, h, bbox, pad):
    lmin = bbox['left'] + pad
    tmin = bbox['top'] + pad
    lmax = bbox['right'] - w - pad
    tmax = bbox['bottom'] - h - pad
    return max(lmin, min(left, lmax)), max(tmin, min(top, tmax))
from docx import Document
from docx.enum.table import WD_ROW_HEIGHT_RULE, WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt

# --- Table header shading helper (match kundali bg) ---
def shade_cell(cell, fill_hex="FFFFFF"):
    return

def shade_header_row(table, fill_hex="FFFFFF"):
    return

def set_page_background(doc, hex_color):
    try:
        bg = OxmlElement('w:background')
        bg.set(qn('w:color'), hex_color)
        doc.element.insert(0, bg)
    except Exception:
        pass



# ---- Dasha helpers (top-level; ORDER & YEARS must exist at call time) ----
def antar_segments_in_md_utc(md_lord, md_start_utc, md_days):
    res=[]; t=md_start_utc; start_idx=ORDER.index(md_lord)
    for i in range(9):
        L=ORDER[(start_idx+i)%9]; dur = YEARS[L]*(md_days/(120.0)); start = t; end = t + datetime.timedelta(days=dur)
        res.append((L, start, end, dur)); t = end
    return res

def pratyantars_in_antar_utc(antar_lord, antar_start_utc, antar_days):
    res=[]; t=antar_start_utc; start_idx=ORDER.index(antar_lord)
    for i in range(9):
        L=ORDER[(start_idx+i)%9]; dur = YEARS[L]*(antar_days/(120.0)); start = t; end = t + datetime.timedelta(days=dur)
        res.append((L, start, end)); t = end
    return res

def next_antar_in_days_utc(now_utc, md_segments, days_window):
    rows=[]; horizon=now_utc + datetime.timedelta(days=days_window)
    for seg in md_segments:
        MD = seg["planet"]; ms = seg["start"]; me = seg["end"]; md_days = seg["days"]
        for AL, as_, ae, adays in antar_segments_in_md_utc(MD, ms, md_days):
            if ae < now_utc or as_ > horizon: 
                continue
            end = min(ae, horizon)
            rows.append({"major": MD, "antar": AL, "end": end})
    rows.sort(key=lambda r:r["end"])
    return rows
# ---- End helpers ----


# ---- Dasha helpers (top-level; use ORDER & YEARS defined before calls) ----
# ---- End helpers ----


APP_TITLE = "Midraastro"
# --- Global place format validator ---
def _place_is_valid(s: str) -> bool:
    parts = [p.strip() for p in (s or '').split(',') if p.strip()]
    return len(parts) >= 3

AYANAMSHA_VAL = swe.SIDM_LAHIRI
YEAR_DAYS     = 365.2422

BASE_FONT_PT = 7.0
LATIN_FONT = "Georgia"
HINDI_FONT = "Mangal"

HN = {'Su':'सूर्य','Mo':'चंद्र','Ma':'मंगल','Me':'बुध','Ju':'गुरु','Ve':'शुक्र','Sa':'शनि','Ra':'राहु','Ke':'केतु'}

# Compact Hindi abbreviations for planet boxes
HN_ABBR = {'Su':'सू','Mo':'चं','Ma':'मं','Me':'बु','Ju':'गु','Ve':'शु','Sa':'श','Ra':'रा','Ke':'के'}

# ==== Status helpers (Rāśi vs Navāṁśa aware) ====
SIGN_LORD = {1:'Ma',2:'Ve',3:'Me',4:'Mo',5:'Su',6:'Me',7:'Ve',8:'Ma',9:'Ju',10:'Sa',11:'Sa',12:'Ju'}
EXALT_SIGN = {'Su':1,'Mo':2,'Ma':10,'Me':6,'Ju':4,'Ve':12,'Sa':7,'Ra':2,'Ke':8}
DEBIL_SIGN = {'Su':7,'Mo':8,'Ma':4,'Me':12,'Ju':10,'Ve':6,'Sa':1,'Ra':8,'Ke':2}
# --- Combustion settings ---
# Only the SUN causes combustion. Rahu/Ketu never combust. Moon CAN be combust (by Sun) if within orb.
# Set this to True if you want to mark combustion ONLY when the Sun and the planet are in the SAME rāśi sign.
REQUIRE_SAME_SIGN_FOR_COMBUST = False  # change to True if that matches your tradition

COMBUST_ORB = {'Mo':12.0,'Ma':17.0,'Me':12.0,'Ju':11.0,'Ve':10.0,'Sa':15.0}

def _min_circ_angle(a, b):
    d = abs((a - b) % 360.0)
    return d if d <= 180.0 else 360.0 - d

def _xml_text(s):
    return (str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"))

def planet_rasi_sign(lon_sid):
    return int(lon_sid // 30) + 1  # 1..12

def compute_statuses_all(sidelons):
    """Return per-planet dict containing both rasi-based and nav-based flags."""
    out = {}
    sun_lon = sidelons.get('Su', 0.0)
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        lon = sidelons[code]
        rasi = planet_rasi_sign(lon)
        nav  = navamsa_sign_from_lon_sid(lon)
        varg = (rasi == nav)
        # Combustion: Sun only, optional same-sign constraint
        combust = False
        if code in COMBUST_ORB and code != 'Su':
            sep = _min_circ_angle(lon, sun_lon)
            if not REQUIRE_SAME_SIGN_FOR_COMBUST or (planet_rasi_sign(lon) == planet_rasi_sign(sun_lon)):
                combust = (sep <= COMBUST_ORB[code])

        out[code] = {
            'rasi': rasi,
            'nav': nav,
            'vargottama': varg,
            'combust': combust,
            'self_rasi': (SIGN_LORD.get(rasi) == code),
            'self_nav':  (SIGN_LORD.get(nav)  == code),
            'exalt_rasi': (EXALT_SIGN.get(code) == rasi),
            'exalt_nav':  (EXALT_SIGN.get(code) == nav),
            'debil_rasi': (DEBIL_SIGN.get(code) == rasi),
            'debil_nav':  (DEBIL_SIGN.get(code) == nav),
        }
        # Nodes (Rahu/Ketu): do not mark exaltation/debilitation
        if code in ('Ra','Ke'):
            out[code]['exalt_rasi'] = False
            out[code]['exalt_nav'] = False
            out[code]['debil_rasi'] = False
            out[code]['debil_nav'] = False
    return out

def _make_flags(view, st):
    """Reduce the big dict to the fields used by the renderer for a given chart view."""
    if view == 'nav':
        return {
            'self': st['self_nav'],
            'exalted': st['exalt_nav'],
            'debilitated': st['debil_nav'],
            'vargottama': st['vargottama'],
            'combust': False,
        }
    # default: rasi
    return {
        'self': st['self_rasi'],
        'exalted': st['exalt_rasi'],
        'debilitated': st['debil_rasi'],
        'vargottama': st['vargottama'],
        'combust': st['combust'],
    }

def fmt_planet_label(code, flags):
    base = HN_ABBR.get(code, code)
    if flags.get('exalted'): base += '↑'
    if flags.get('debilitated'): base += '↓'
    if flags.get('combust'): base += '^'
    return base



def planet_navamsa_house(lon_sid, nav_lagna_sign):
    # Return 1..12 house index in Navamsa for a planet
    nav_sign = navamsa_sign_from_lon_sid(lon_sid)  # 1..12
    return ((nav_sign - nav_lagna_sign) % 12) + 1

def build_navamsa_house_planets(sidelons, nav_lagna_sign):
    # Map: house -> list of planet abbreviations in Navamsa
    house_map = {i: [] for i in range(1, 13)}
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        h = planet_navamsa_house(sidelons[code], nav_lagna_sign)
        house_map[h].append(HN_ABBR.get(code, code))
    return house_map


def build_rasi_house_planets_marked(sidelons, lagna_sign):
    house_map = {i: [] for i in range(1, 13)}
    stats = compute_statuses_all(sidelons)
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        sign = planet_rasi_sign(sidelons[code])
        h = ((sign - lagna_sign) % 12) + 1
        fl = _make_flags('rasi', stats[code])
        label = fmt_planet_label(code, fl)
        house_map[h].append({'txt': label, 'flags': fl})
    return house_map

def build_navamsa_house_planets_marked(sidelons, nav_lagna_sign):
    house_map = {i: [] for i in range(1, 13)}
    stats = compute_statuses_all(sidelons)
    sun_nav = stats['Su']['nav']  # Sun's Navāṁśa sign
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        nav_sign = navamsa_sign_from_lon_sid(sidelons[code])
        h = ((nav_sign - nav_lagna_sign) % 12) + 1
        fl = _make_flags('nav', stats[code])   # nav-based self/exalt/debil
        # Navāṁśa combust rule: planet combust iff shares Nav sign with Sun
        if code not in ('Su','Ra','Ke'):
            fl['combust'] = (nav_sign == sun_nav)
        else:
            fl['combust'] = False
        label = fmt_planet_label(code, fl)
        house_map[h].append({'txt': label, 'flags': fl})
    return house_map


def build_rasi_house_planets(sidelons, lagna_sign):
    # Map: house -> list of planet abbreviations in Rasi (Lagna) chart
    house_map = {i: [] for i in range(1, 13)}
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        sign = int(sidelons[code] // 30) + 1  # 1..12
        h = ((sign - lagna_sign) % 12) + 1
        house_map[h].append(HN_ABBR.get(code, code))
    return house_map

def _apply_hindi_caption_style(paragraph, size_pt=11, underline=True, bold=True):
    if not paragraph.runs:
        paragraph.add_run("")
    r = paragraph.runs[0]
    r.bold = bold; r.underline = underline; r.font.size = Pt(size_pt)
    rpr = r._element.rPr or OxmlElement('w:rPr')
    if r._element.rPr is None: r._element.append(rpr)
    rfonts = rpr.find(qn('w:rFonts')) or OxmlElement('w:rFonts')
    if rpr.find(qn('w:rFonts')) is None: rpr.append(rfonts)
    rfonts.set(qn('w:eastAsia'), HINDI_FONT)

def set_sidereal_locked():
    swe.set_sid_mode(AYANAMSHA_VAL, 0, 0)

def dms_exact(deg):
    d = int(deg); m_float = (deg - d) * 60.0; m = int(m_float); s = (m_float - m) * 60.0
    return d, m, s

def fmt_deg_sign(lon_sid):
    sign=int(lon_sid//30) + 1; deg_in_sign = lon_sid % 30.0
    d,m,s=dms_exact(deg_in_sign); s_rounded = int(round(s))
    if s_rounded == 60: s_rounded = 0; m += 1
    if m == 60: m = 0; d += 1; 
    if d == 30: d = 0
    return sign, f"{d:02d}°{m:02d}'{s_rounded:02d}\""

def kp_sublord(lon_sid):
    NAK=360.0/27.0
    ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
    YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
    part = lon_sid % 360.0; ni = int(part // NAK); pos = part - ni*NAK
    lord = ORDER[ni % 9]; start = ORDER.index(lord)
    seq = [ORDER[(start+i)%9] for i in range(9)]
    acc = 0.0
    for L in seq:
        seg = NAK * (YEARS[L]/120.0)
        if pos <= acc + seg + 1e-9: return lord, L
        acc += seg
    return lord, seq[-1]

def geocode(place, api_key):
    if not api_key: raise RuntimeError("Geoapify key missing. Add GEOAPIFY_API_KEY in Secrets.")
    base="https://api.geoapify.com/v1/geocode/search?"
    if not _place_is_valid(place):
        raise RuntimeError("Place format must be City, State, Country.")
    q = urllib.parse.urlencode({"text":place, "format":"json", "limit":1, "apiKey":api_key})
    with urllib.request.urlopen(base+q, timeout=15) as r: j = json.loads(r.read().decode())
    if j.get("results"):
        res=j["results"][0]; return float(res["lat"]), float(res["lon"]), res.get("formatted", place)
    raise RuntimeError("Place not found.")


def tz_from_latlon(lat, lon, dt_local):
    tf = TimezoneFinder(); tzname = tf.timezone_at(lat=lat, lng=lon) or "Etc/UTC"
    # Ensure naive before localize (pytz requires naive datetime)
    if getattr(dt_local, "tzinfo", None) is not None:
        dt_local = dt_local.replace(tzinfo=None)
    tz = pytz.timezone(tzname)
    try:
        dt_local_aware = tz.localize(dt_local)
    except Exception:
        dt_local_aware = tz.localize(dt_local.replace(tzinfo=None))
    dt_utc_naive = dt_local_aware.astimezone(pytz.utc).replace(tzinfo=None)
    offset_hours = tz.utcoffset(dt_local_aware).total_seconds()/3600.0
    return tzname, offset_hours, dt_utc_naive


def sidereal_positions(dt_utc):
    jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600)
    set_sidereal_locked(); flags = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
    out = {}
    for code, p in [('Su',swe.SUN),('Mo',swe.MOON),('Ma',swe.MARS),('Me',swe.MERCURY),('Ju',swe.JUPITER),('Ve',swe.VENUS),('Sa',swe.SATURN)]:
        xx,_ = swe.calc_ut(jd, p, flags); out[code] = xx[0] % 360.0
    xx,_ = swe.calc_ut(jd, swe.MEAN_NODE, flags)  # Mean node locked
    out['Ra'] = xx[0] % 360.0; out['Ke'] = (out['Ra'] + 180.0) % 360.0
    ay = swe.get_ayanamsa_ut(jd); return jd, ay, out

def ascendant_sign(jd, lat, lon, ay):
    cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P'); asc_trop = ascmc[0]; asc_sid = (asc_trop - ay) % 360.0
    return int(asc_sid // 30) + 1, asc_sid

def navamsa_sign_from_lon_sid(lon_sid):
    sign = int(lon_sid // 30) + 1; deg_in_sign = lon_sid % 30.0; pada = int(deg_in_sign // (30.0/9.0))
    if sign in (1,4,7,10): start = sign
    elif sign in (2,5,8,11): start = ((sign + 8 - 1) % 12) + 1
    else: start = ((sign + 4 - 1) % 12) + 1
    return ((start - 1 + pada) % 12) + 1

def positions_table_no_symbol(sidelons):
    rows=[]
    for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']:
        lon=sidelons[code]; sign, deg_str = fmt_deg_sign(lon); nak_lord, sub_lord = kp_sublord(lon)
        rows.append([HN[code], sign, deg_str, HN[nak_lord], HN[sub_lord]])
    return pd.DataFrame(rows, columns=["ग्रह","राशि","अंश","नक्षत्र","उप‑नक्षत्र"])

ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}

def moon_balance_days(moon_sid):
    NAK=360.0/27.0; part = moon_sid % 360.0; ni = int(part // NAK); pos = part - ni*NAK
    md_lord = ORDER[ni % 9]; frac = pos/NAK; remaining_days = YEARS[md_lord]*(1 - frac)*YEAR_DAYS
    return md_lord, remaining_days

def build_mahadashas_days_utc(birth_utc_dt, moon_sid):
    md_lord, rem_days = moon_balance_days(moon_sid); end_limit = birth_utc_dt + datetime.timedelta(days=100*YEAR_DAYS)
    segments=[]; birth_md_start = birth_utc_dt; birth_md_end = min(birth_md_start + datetime.timedelta(days=rem_days), end_limit)
    segments.append({"planet": md_lord, "start": birth_md_start, "end": birth_md_end, "days": rem_days})
    idx = (ORDER.index(md_lord) + 1) % 9; t = birth_md_end
    while t < end_limit:
        L = ORDER[idx]; dur_days = YEARS[L]*YEAR_DAYS; end = min(t + datetime.timedelta(days=dur_days), end_limit)
        segments.append({"planet": L, "start": t, "end": end, "days": dur_days}); t = end; idx = (idx + 1) % 9
    return segments
# --- FIXED: compact kundali rendering with zero padding ---
def render_north_diamond(size_px=800, stroke=3):
    fig, ax = plt.subplots(figsize=(size_px/200, size_px/200), dpi=200)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_aspect('equal')
    ax.axis('off')
    # Outer square
    ax.plot([0,1,1,0,0],[0,0,1,1,0], linewidth=stroke, color='black')
    # Diagonals
    ax.plot([0,1],[1,0], linewidth=stroke, color='black')
    ax.plot([0,1],[0,1], linewidth=stroke, color='black')
    # Midpoint diamond
    ax.plot([0,0.5],[0.5,1], linewidth=stroke, color='black')
    ax.plot([0.5,1],[1,0.5], linewidth=stroke, color='black')
    ax.plot([1,0.5],[0.5,0], linewidth=stroke, color='black')
    ax.plot([0.5,0],[0,0.5], linewidth=stroke, color='black')
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)  # zero padding
    plt.close(fig); buf.seek(0); return buf

def rotated_house_labels(lagna_sign):
    order = [str(((lagna_sign - 1 + i) % 12) + 1) for i in range(12)]
    return {"1":order[0],"2":order[1],"3":order[2],"4":order[3],"5":order[4],"6":order[5],"7":order[6],"8":order[7],"9":order[8],"10":order[9],"11":order[10],"12":order[11]}


def kundali_with_planets(size_pt=None, lagna_sign=1, house_planets=None):
    
    # robust default for size_pt so definition never depends on globals
    if size_pt is None:
        try:
            size_pt = CHART_W_PT
        except Exception:
            size_pt = 318  # safe fallback
# Like kundali_w_p_with_centroid_labels but adds small side-by-side planet boxes below the number
    if house_planets is None:
        house_planets = {i: [] for i in range(1, 13)}
    S=size_pt; L,T,R,B=0,0,S,S
    TM=(S/2,0); RM=(S,S/2); BM=(S/2,S); LM=(0,S/2)
    P_lt=(S/4,S/4); P_rt=(3*S/4,S/4); P_rb=(3*S/4,3*S/4); P_lb=(S/4,3*S/4); O=(S/2,S/2)
    labels = rotated_house_labels(lagna_sign)
    houses = {
        "1":[TM,P_rt,O,P_lt],
        "2":[(0,0),TM,P_lt],
        "3":[(0,0),LM,P_lt],
        "4":[LM,O,P_lt,P_lb],
        "5":[LM,(0,S),P_lb],
        "6":[(0,S),BM,P_lb],
        "7":[BM,P_rb,O,P_lb],
        "8":[BM,(S,S),P_rb],
        "9":[RM,(S,S),P_rb],
        "10":[RM,O,P_rt,P_rb],
        "11":[(S,0),RM,P_rt],
        "12":[TM,(S,0),P_rt],
    }
    def centroid(poly):
        A=Cx=Cy=0.0; n=len(poly)
        for i in range(n):
            x1,y1=poly[i]; x2,y2=poly[(i+1)%n]
            cross=x1*y2 - x2*y1
            A+=cross; Cx+=(x1+x2)*cross; Cy+=(y1+y2)*cross
        A*=0.5
        if abs(A)<1e-9:
            xs,ys=zip(*poly); return (sum(xs)/n, sum(ys)/n)
        return (Cx/(6*A), Cy/(6*A))
    # Style for house-number boxes
    style = HOUSE_NUM_STYLE.lower()
    if style == 'plain':
        NUM_FILL, NUM_STROKE, NUM_STROKE_W = '#ffffff', 'none', '0pt'
    elif style == 'bordered':
        NUM_FILL, NUM_STROKE, NUM_STROKE_W = '#ffffff', 'black', f'{HOUSE_NUM_BORDER_PT}pt'
    elif style == 'shaded':
        NUM_FILL, NUM_STROKE, NUM_STROKE_W = HOUSE_NUM_SHADE, 'none', '0pt'
    else:  # bordered_shaded
        NUM_FILL, NUM_STROKE, NUM_STROKE_W = HOUSE_NUM_SHADE, 'black', f'{HOUSE_NUM_BORDER_PT}pt'
    num_boxes=[]; planet_boxes=[]; occupied_rects=[]
    num_w=NUM_W_PT; num_h=NUM_H_PT; p_w,p_h=PLANET_W_PT,PLANET_H_PT; gap_x=GAP_X_PT; offset_y=OFFSET_Y_PT
    for k,poly in houses.items():
        bbox = _bbox_of_poly(poly)
        # house number box
        x,y = centroid(poly); left = x - num_w/2; top = y - num_h/2; txt = labels[k]
        left, top = _clamp_in_bbox(left, top, num_w, num_h, bbox, pad=2)

        nl, nt = _nudge_number_box(left, top, num_w, num_h, S, occupied_rects)
        left, top = nl, nt
        occupied_rects.append({'left': left, 'top': top, 'right': left + num_w, 'bottom': top + num_h});
        num_boxes.append(f'''
        <v:rect style="position:absolute;left:{left}pt;top:{top}pt;width:{num_w}pt;height:{num_h}pt;z-index:80" fillcolor="#ffffff" strokecolor="none" strokeweight="0pt">
          <v:textbox inset="0,0,0,0">
            <w:txbxContent xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:t>{txt}</w:t></w:r></w:p>
            </w:txbxContent>
          </v:textbox>
        </v:rect>
        ''')
        # planet row below number
        planets = house_planets.get(int(k), [])
        if planets:
            n = len(planets)
            max_cols = 2  # wrap after this many per row
            rows = (n + max_cols - 1) // max_cols
            gap_y = 2
            # compute total grid height and top start
            total_h = rows * p_h + (rows - 1) * gap_y
            # start rows just below the number box
            grid_top = y + (p_h/2 + 2) + offset_y
            for idx, pl in enumerate(planets):
                # normalize input item
                if isinstance(pl, dict):
                    label = str(pl.get('txt', '')).strip() or '?'
                    fl = pl.get('flags', {}) or {}
                else:
                    label = str(pl).strip() or '?'
                    fl = {}
                r = idx // max_cols
                c = idx % max_cols
                # columns in this row (last row can be shorter)
                cols_this = max_cols if r < rows - 1 else (n - max_cols * (rows - 1)) or max_cols
                row_w = cols_this * p_w + (cols_this - 1) * gap_x
                row_left = x - row_w / 2
                top_box = grid_top + r * (p_h + gap_y) - p_h / 2
                # keep within chart square bounds with margin and tiny shrink on edges
                M = 5
                row_left = max(M, min(row_left, S - row_w - M))
                top_box  = max(M, min(top_box,  S - p_h - M))
                edge_touch = (row_left <= M + 0.05) or (row_left >= S - row_w - M - 0.05) or (top_box <= M + 0.05) or (top_box >= S - p_h - M - 0.05)
                pw = p_w - (1 if edge_touch else 0)
                ph = p_h - (1 if edge_touch else 0)
                left_pl = row_left + c * (pw + gap_x)
                box_xml = (
                    f"<v:rect style=\"position:absolute;left:{left_pl}pt;top:{top_box}pt;width:{pw}pt;height:{ph}pt;z-index:6\" strokecolor=\"none\">"
                    + "<v:textbox inset=\"0,0,0,0\">"
                    + "<w:txbxContent xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
                    + f"<w:p><w:pPr><w:jc w:val=\"center\"/></w:pPr><w:r><w:t>{_xml_text(label)}</w:t></w:r></w:p>"
                    + "</w:txbxContent>"
                    + "</v:textbox>"
                    + "</v:rect>"
                )
                planet_boxes.append(box_xml)
                # overlays
                try:
                    selfr = bool(fl.get('self'))
                    varg  = bool(fl.get('vargottama'))
                except Exception:
                    selfr = varg = False
                if selfr:
                    circle_left = left_pl + 2
                    circle_top  = top_box + 1
                    circle_w    = pw - 4
                    circle_h    = ph - 2
                    oval_xml = (
                        f"<v:oval style=\"position:absolute;left:{circle_left}pt;top:{circle_top}pt;width:{circle_w}pt;height:{circle_h}pt;z-index:7\" fillcolor=\"none\" strokecolor=\"black\" strokeweight=\"0.75pt\"/>"
                    )
                    planet_boxes.append(oval_xml)
                if varg:
                    badge_w = 5; badge_h = 5
                    badge_left = left_pl + pw - badge_w + 0.5
                    badge_top  = top_box - 2
                    badge_xml = (
                        f"<v:rect style=\"position:absolute;left:{badge_left}pt;top:{badge_top}pt;width:{badge_w}pt;height:{badge_h}pt;z-index:8\" fillcolor=\"#ffffff\" strokecolor=\"black\" strokeweight=\"0.75pt\"/>"
                    )
                    planet_boxes.append(badge_xml)
    # Compose shapes after processing all houses
    boxes_xml = "\\n".join(num_boxes + planet_boxes)

    xml = f'''
    <w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:r>
      <w:pict xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w10="urn:schemas-microsoft-com:office:word"><w10:wrap type="topAndBottom"/>
        <v:group style="position:relative;margin-left:0;margin-top:0;width:{S}pt;height:{int(S*0.80)}pt" coordorigin="0,0" coordsize="{S},{S}">
          <v:rect style="position:absolute;left:0;top:0;width:{S}pt;height:{S}pt;z-index:1" strokecolor="black" strokeweight="1.25pt" fillcolor="#fff2cc"/>
          <v:line style="position:absolute;z-index:2" from="{L},{T}" to="{R},{B}" strokecolor="black" strokeweight="1.25pt"/>
          <v:line style="position:absolute;z-index:2" from="{R},{T}" to="{L},{B}" strokecolor="black" strokeweight="1.25pt"/>
          <v:line style="position:absolute;z-index:2" from="{S/2},{T}" to="{R},{S/2}" strokecolor="black" strokeweight="1.25pt"/>
          <v:line style="position:absolute;z-index:2" from="{R},{S/2}" to="{S/2},{B}" strokecolor="black" strokeweight="1.25pt"/>
          <v:line style="position:absolute;z-index:2" from="{S/2},{B}" to="{L},{S/2}" strokecolor="black" strokeweight="1.25pt"/>
          <v:line style="position:absolute;z-index:2" from="{L},{S/2}" to="{S/2},{T}" strokecolor="black" strokeweight="1.25pt"/>
          {boxes_xml}
        </v:group>
      </w:pict>
    </w:r></w:p>
    '''
    return parse_xml(xml)



def kundali_single_box(size_pt=220, lagna_sign=1, house_planets=None):
    # One text box per house: first row = house number, second row = planets (centered)
    if house_planets is None:
        house_planets = {i: [] for i in range(1, 13)}
    S=size_pt; L,T,R,B=0,0,S,S
    TM=(S/2,0); RM=(S,S/2); BM=(S/2,S); LM=(0,S/2)
    P_lt=(S/4,S/4); P_rt=(3*S/4,S/4); P_rb=(3*S/4,3*S/4); P_lb=(S/4,3*S/4); O=(S/2,S/2)
    labels = rotated_house_labels(lagna_sign)
    houses = {
        "1":[TM,P_rt,O,P_lt],
        "2":[(0,0),TM,P_lt],
        "3":[(0,0),LM,P_lt],
        "4":[LM,O,P_lt,P_lb],
        "5":[LM,(0,S),P_lb],
        "6":[(0,S),BM,P_lb],
        "7":[BM,P_rb,O,P_lb],
        "8":[BM,(S,S),P_rb],
        "9":[RM,(S,S),P_rb],
        "10":[RM,O,P_rt,P_rb],
        "11":[(S,0),RM,P_rt],
        "12":[TM,(S,0),P_rt],
    }
    def centroid(poly):
        A=Cx=Cy=0.0; n=len(poly)
        for i in range(n):
            x1,y1=poly[i]; x2,y2=poly[(i+1)%n]
            cross=x1*y2 - x2*y1
            A+=cross; Cx+=(x1+x2)*cross; Cy+=(y1+y2)*cross
        A*=0.5
        if abs(A)<1e-9:
            xs,ys=zip(*poly); return (sum(xs)/n, sum(ys)/n)
        return (Cx/(6*A), Cy/(6*A))
    box_w, box_h = 30, 26  # slightly taller to hold two lines cleanly
    text_boxes=[]
    for k,poly in houses.items():
        x,y = centroid(poly)
        left = x - box_w/2; top = y - box_h/2
        num = labels[k]
        pls = house_planets.get(int(k), [])
        if pls:
            planets_text = " ".join(pls)
            content = f'<w:r><w:t>{num}</w:t></w:r><w:r/><w:br/><w:r><w:t>{planets_text}</w:t></w:r>'
        else:
            content = f'<w:r><w:t>{num}</w:t></w:r>'
        text_boxes.append(f'''
        <v:rect style="position:absolute;left:{left}pt;top:{top}pt;width:{box_w}pt;height:{box_h}pt;z-index:5" strokecolor="none">
          <v:textbox inset="0,0,0,0">
            <w:txbxContent xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:p><w:pPr><w:jc w:val="center"/></w:pPr>{content}</w:p>
            </w:txbxContent>
          </v:textbox>
        </v:rect>
        ''')
    boxes_xml = "\\n".join(text_boxes)
    xml = f'''
    <w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:r>
      <w:pict xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w10="urn:schemas-microsoft-com:office:word"><w10:wrap type="topAndBottom"/>
        <v:group style="position:relative;margin-left:0;margin-top:0;width:{S}pt;height:{int(S*0.80)}pt" coordorigin="0,0" coordsize="{S},{S}">
          <v:rect style="position:absolute;left:0;top:0;width:{S}pt;height:{S}pt;z-index:1" strokecolor="black" strokeweight="1.25pt" fillcolor="#fff2cc"/>
          <v:line style="position:absolute;z-index:2" from="{L},{T}" to="{R},{B}" strokecolor="black" strokeweight="1.25pt"/>
          <v:line style="position:absolute;z-index:2" from="{R},{T}" to="{L},{B}" strokecolor="black" strokeweight="1.25pt"/>
          <v:line style="position:absolute;z-index:2" from="{S/2},{T}" to="{R},{S/2}" strokecolor="black" strokeweight="1.25pt"/>
          <v:line style="position:absolute;z-index:2" from="{R},{S/2}" to="{S/2},{B}" strokecolor="black" strokeweight="1.25pt"/>
          <v:line style="position:absolute;z-index:2" from="{S/2},{B}" to="{L},{S/2}" strokecolor="black" strokeweight="1.25pt"/>
          <v:line style="position:absolute;z-index:2" from="{L},{S/2}" to="{S/2},{T}" strokecolor="black" strokeweight="1.25pt"/>
          {boxes_xml}
        </v:group>
      </w:pict>
    </w:r></w:p>
    '''
    return parse_xml(xml)


def kundali_w_p_with_centroid_labels(size_pt=220, lagna_sign=1):
    S=size_pt; TM=(S/2,0); RM=(S,S/2); BM=(S/2,S); LM=(0,S/2); P_lt=(S/4,S/4); P_rt=(3*S/4,S/4); P_rb=(3*S/4,3*S/4); P_lb=(S/4,3*S/4); O=(S/2,S/2)
    labels = rotated_house_labels(lagna_sign)
    houses = {"1":[TM,P_rt,O,P_lt],"2":[(0,0),TM,P_lt],"3":[(0,0),LM,P_lt],"4":[LM,O,P_lt,P_lb],"5":[LM,(0,S),P_lb],"6":[(0,S),BM,P_lb],"7":[BM,P_rb,O,P_lb],"8":[BM,(S,S),P_rb],"9":[RM,(S,S),P_rb],"10":[RM,O,P_rt,P_rb],"11":[(S,0),RM,P_rt],"12":[TM,(S,0),P_rt]}
    def centroid(poly):
        A=Cx=Cy=0.0; n=len(poly)
        for i in range(n):
            x1,y1=poly[i]; x2,y2=poly[(i+1)%n]; cross=x1*y2 - x2*y1; A+=cross; Cx+=(x1+x2)*cross; Cy+=(y1+y2)*cross
        A*=0.5
        if abs(A)<1e-9: xs,ys=zip(*poly); return (sum(xs)/n, sum(ys)/n)
        return (Cx/(6*A), Cy/(6*A))
    w=h=20; boxes=[]
    for k,poly in houses.items():
        x,y = centroid(poly); left = x - w/2; top = y - h/2; txt = labels[k]
        boxes.append(f'''
        <v:rect style="position:absolute;left:{left}pt;top:{top}pt;width:{w}pt;height:{h}pt;z-index:5" strokecolor="none">
          <v:textbox inset="0,0,0,0">
            <w:txbxContent xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:t>{txt}</w:t></w:r></w:p>
            </w:txbxContent>
          </v:textbox>
        </v:rect>''')
    boxes_xml = "\\n".join(boxes)
    xml = f'''<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:r>
        <w:pict xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w10="urn:schemas-microsoft-com:office:word"><w10:wrap type="topAndBottom"/>
          <v:group style="position:relative;margin-left:0;margin-top:0;width:{S}pt;height:{int(S*0.80)}pt" coordorigin="0,0" coordsize="{S},{S}">
            <v:rect style="position:absolute;left:0;top:0;width:{S}pt;height:{S}pt;z-index:1" strokecolor="black" strokeweight="1.25pt" fillcolor="#fff2cc"/>
            <v:line style="position:absolute;z-index:2" from="0,0" to="{S},{S}" strokecolor="black" strokeweight="1.25pt"/>
            <v:line style="position:absolute;z-index:2" from="{S},0" to="0,{S}" strokecolor="black" strokeweight="1.25pt"/>
            <v:line style="position:absolute;z-index:2" from="{S/2},0" to="{S},{S/2}" strokecolor="black" strokeweight="1.25pt"/>
            <v:line style="position:absolute;z-index:2" from="{S},{S/2}" to="{S/2},{S}" strokecolor="black" strokeweight="1.25pt"/>
            <v:line style="position:absolute;z-index:2" from="{S/2},{S}" to="0,{S/2}" strokecolor="black" strokeweight="1.25pt"/>
            <v:line style="position:absolute;z-index:2" from="0,{S/2}" to="{S/2},0" strokecolor="black" strokeweight="1.25pt"/>
            {boxes_xml}
          </v:group>
        </w:pict></w:r></w:p>'''
    return parse_xml(xml)

def add_table_borders(table, size=6):
    tbl = table._tbl; tblPr = tbl.tblPr; tblBorders = OxmlElement('w:tblBorders')
    for edge in ('top','left','bottom','right','insideH','insideV'):
        el = OxmlElement(f'w:{edge}'); el.set(qn('w:val'),'single'); el.set(qn('w:sz'),str(size)); tblBorders.append(el)
    tblPr.append(tblBorders)

def set_table_font(table, pt=8.0):
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for r in p.runs: r.font.size = Pt(pt)

def center_header_row(table):
    for cell in table.rows[0].cells:
        for par in cell.paragraphs:
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if par.runs: par.runs[0].bold = True

def set_col_widths(table, widths_inch):
    table.autofit = False
    for row in table.rows:
        for i, w in enumerate(widths_inch):
            row.cells[i].width = Inches(w)

def sanitize_filename(name: str) -> str:
    # Keep spaces; strip leading/trailing; allow letters/digits/space/_/- only
    raw = (name or 'Horoscope').strip()
    cleaned = ''.join(ch for ch in raw if ch.isalnum() or ch in ' _-')
    return cleaned or 'Horoscope'

def _utc_to_local(dt_utc, tzname, tz_hours, used_manual):
    if used_manual: return dt_utc + datetime.timedelta(hours=tz_hours)
    try:
        tz = pytz.timezone(tzname); return tz.fromutc(dt_utc.replace(tzinfo=pytz.utc))
    except Exception:
        return dt_utc + datetime.timedelta(hours=tz_hours)

# Core UI

def _house_from_lagna(sign:int, lagna_sign:int)->int:
    return ((sign - lagna_sign) % 12) + 1  # 1..12

def _english_bhav_label(h:int)->str:
    try:
        h_int = int(h)
    except Exception:
        return f"{h}वाँ भाव"
    return f"{h_int}वाँ भाव"

def detect_muntha_house(lagna_sign:int, dob_dt):
    # Approx: years elapsed since birth to today -> advance houses from lagna
    try:
        from datetime import datetime, timezone
        years = datetime.now(timezone.utc).year - dob_dt.year
        return ((lagna_sign - 1 + years) % 12) + 1
    except Exception:
        return None

def detect_sade_sati_or_dhaiyya(sidelons:dict, transit_dt=None):
    # Returns: (status, phase) where status in {"साढ़ेसाती", "शनि ढैय्या", None}
    # Uses *transit Saturn* vs *natal Moon*. Phase only if साढ़ेसाती: "प्रथम चरण" / "द्वितीय चरण" / "तृतीय चरण".
    try:
        # Natal Moon sign
        moon = planet_rasi_sign(sidelons['Mo'])
        # Transit Saturn sign at transit_dt (or now)
        from datetime import datetime, timezone
        if transit_dt is None:
            tdt = datetime.now(timezone.utc)
        else:
            tdt = transit_dt
        _jd, _ay, trans = sidereal_positions(tdt.replace(tzinfo=None) if hasattr(tdt, 'tzinfo') else tdt)
        sat = planet_rasi_sign(trans['Sa'])
        d = (sat - moon) % 12
        if d in (11, 0, 1):
            phase = {11: "प्रथम चरण", 0: "द्वितीय चरण", 1: "तृतीय चरण"}[d]
            return "साढ़ेसाती", phase
        if d in (3, 7):
            return "शनि ढैय्या", None
        return None, None
    except Exception:
        return None, None

def detect_kaalsarp(sidelons:dict)->bool:
    try:
        ra = sidelons['Ra'] % 360.0
        ke = (ra + 180.0) % 360.0
        span = (ke - ra) % 360.0  # should be 180
        inside = 0
        for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa']:
            ang = (sidelons[code] - ra) % 360.0
            if ang <= span:
                inside += 1
        return inside == 7
    except Exception:
        return False

def detect_chandal(sidelons:dict)->bool:
    try:
        ju = planet_rasi_sign(sidelons['Ju'])
        return ju == planet_rasi_sign(sidelons['Ra']) or ju == planet_rasi_sign(sidelons['Ke'])
    except Exception:
        return False

def detect_pitru(sidelons:dict)->bool:
    try:
        su = planet_rasi_sign(sidelons['Su'])
        return su == planet_rasi_sign(sidelons['Ra']) or su == planet_rasi_sign(sidelons['Ke'])
    except Exception:
        return False

def detect_neech_bhang(sidelons:dict, lagna_sign:int)->bool:
    try:
        stats = compute_statuses_all(sidelons)
        for code in ['Su','Mo','Ma','Me','Ju','Ve','Sa']:
            if stats[code]['debil_rasi']:
                debil_sign = stats[code]['rasi']
                lord = SIGN_LORD.get(debil_sign)
                if lord and lord in sidelons:
                    lord_sign = planet_rasi_sign(sidelons[lord])
                    h = _house_from_lagna(lord_sign, lagna_sign)
                    if h in (1,4,7,10):
                        return True
        return False
    except Exception:
        return False

def compact_table_paragraphs(tbl):
    try:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.paragraph_format.space_before = Pt(0)
                    p.paragraph_format.space_after = Pt(0)
    except Exception:
        pass

def add_pramukh_bindu_section(container_cell, sidelons, lagna_sign, dob_dt):
    spacer = container_cell.add_paragraph("")
    spacer.paragraph_format.space_after = Pt(4)
    # Title
    title = container_cell.add_paragraph("प्रमुख बिंदु")
    # Match other section titles
    _apply_hindi_caption_style(title, size_pt=11, underline=True, bold=True)
    title.paragraph_format.space_before = Pt(0)
    title.paragraph_format.space_after = Pt(2)
    title.paragraph_format.space_before = Pt(6)
    title.paragraph_format.space_after = Pt(3)

    rows = []

    # Muntha
    m = detect_muntha_house(lagna_sign, dob_dt)
    if m:
        rows.append(("मुन्था (वर्तमान वर्ष)", _english_bhav_label(m)))

    # Sade Sati / Dhaiyya
    status, phase = detect_sade_sati_or_dhaiyya(sidelons)
    if status:
        rows.append(("साढ़ेसाती/शनि ढैय्या", status))
        if status == "साढ़ेसाती" and phase:
            rows.append(("साढ़ेसाती का चरण", phase))

    # Dosha/Yoga (only if True)
    if detect_kaalsarp(sidelons):
        rows.append(("कालसर्प दोष", "हाँ"))
    if detect_chandal(sidelons):
        rows.append(("चांडाल योग", "हाँ"))
    if detect_pitru(sidelons):
        rows.append(("पितृ दोष", "हाँ"))
    if detect_neech_bhang(sidelons, lagna_sign):
        rows.append(("नीच भंग राज योग", "हाँ"))

    if not rows:
        # Nothing to show; avoid adding an empty table
        return

    t = container_cell.add_table(rows=0, cols=2)
    t.autofit = True
    # Match font size with other tables
    try:
        set_table_font(t, pt=BASE_FONT_PT)
    except Exception:
        pass
    for left_txt, right_txt in rows:
        r = t.add_row().cells
        r[0].text = left_txt
        r[1].text = right_txt

    # Borders similar to other tables
    add_table_borders(t, size=6)
    compact_table_paragraphs(t)
def main():
    st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Crimson+Text:ital@1&display=swap');
    .app-brand h1 { font-family: 'Playfair Display', serif; font-weight:700; font-size: 2.0rem; margin: 0 0 .1rem 0; letter-spacing:.5px; }
    .app-brand h2 { font-family: 'Crimson Text', serif; font-style: italic; font-size: 1.25rem; margin:.1rem 0 1rem 0; }
    </style>
    Midraastro\3
      <h2>In the light of the divine, let your soul journey shine.</h2>
    </div>
    """,
    unsafe_allow_html=True,
)

    col0, col1 = st.columns([1.2, 1])
    row1_col1, row1_col2 = st.columns(2)
# Back-compat alias to avoid NameError if old code refers to 'rowl_col1/2'
try:
    row1_col1
    row1_col2
except NameError:
    row1_col1, row1_col2 = st.columns(2)
rowl_col1 = row1_col1
rowl_col2 = row1_col2

with row1_col1:
    name = st.text_input('Name')
with row1_col2:
    dob = st.date_input('Date of Birth', min_value=datetime.date(1800,1,1), max_value=datetime.date(2100,12,31))

row2_col1, row2_col2 = st.columns(2)
with row2_col1:
    tob = st.time_input('Time of Birth', step=datetime.timedelta(minutes=1), help='24-hour format (HH:MM)')
with row2_col2:
    place = st.text_input('Place of Birth (City, State, Country)', help="Tip: City not found? Type manually — use 'City, State, Country'.")

row3_col1, row3_col2 = st.columns(2)
with row3_col1:
    tz_override = st.text_input('UTC offset override (optional, e.g., 5.5)', '')

# --- Validation: require City, State, Country ---
if not _place_is_valid(place):
    st.warning("Please enter **City, State, Country**. Example: 'Jabalpur, Madhya Pradesh, India'.")
    st.stop()
with row3_col2:
    st.write('')

api_key = st.secrets.get("GEOAPIFY_API_KEY","")

if True:
    try:
        lat, lon, disp = geocode(place, api_key)
        dt_local = datetime.datetime.combine(dob, tob).replace(tzinfo=None)
        used_manual = False
        if tz_override.strip():
            tz_hours = float(tz_override)
            dt_utc = dt_local - datetime.timedelta(hours=tz_hours)
            tzname = f"UTC{tz_hours:+.2f} (manual)"
            used_manual = True
        else:
            tzname, tz_hours, dt_utc = tz_from_latlon(lat, lon, dt_local)
    
        jd, ay, sidelons = sidereal_positions(dt_utc)
        lagna_sign, asc_sid = ascendant_sign(jd, lat, lon, ay)
        nav_lagna_sign = navamsa_sign_from_lon_sid(asc_sid)
    
        df_positions = positions_table_no_symbol(sidelons)
    
        ORDER = ['Ke','Ve','Su','Mo','Ma','Ra','Ju','Sa','Me']
        YEARS = {'Ke':7,'Ve':20,'Su':6,'Mo':10,'Ma':7,'Ra':18,'Ju':16,'Sa':19,'Me':17}
    
        def moon_balance_days(moon_sid):
            NAK=360.0/27.0; part = moon_sid % 360.0; ni = int(part // NAK); pos = part - ni*NAK
            md_lord = ORDER[ni % 9]; frac = pos/NAK; remaining_days = YEARS[md_lord]*(1 - frac)*YEAR_DAYS
            return md_lord, remaining_days
    
        def build_mahadashas_days_utc(birth_utc_dt, moon_sid):
            md_lord, rem_days = moon_balance_days(moon_sid); end_limit = birth_utc_dt + datetime.timedelta(days=100*YEAR_DAYS)
            segments=[]; birth_md_start = birth_utc_dt; birth_md_end = min(birth_md_start + datetime.timedelta(days=rem_days), end_limit)
            segments.append({"planet": md_lord, "start": birth_md_start, "end": birth_md_end, "days": rem_days})
            idx = (ORDER.index(md_lord) + 1) % 9; t = birth_md_end
            while t < end_limit:
                L = ORDER[idx]; dur_days = YEARS[L]*YEAR_DAYS; end = min(t + datetime.timedelta(days=dur_days), end_limit)
                segments.append({"planet": L, "start": t, "end": end, "days": dur_days}); t = end; idx = (idx + 1) % 9
            return segments
        md_segments_utc = build_mahadashas_days_utc(dt_utc, sidelons['Mo'])
    
        def age_years(birth_dt_local, end_utc):
            local_end = _utc_to_local(end_utc, tzname, tz_hours, used_manual)
            days = (local_end.date() - birth_dt_local.date()).days
            return int(days // YEAR_DAYS)
    
        df_md = pd.DataFrame([
            {"ग्रह": HN[s["planet"]],
             "समाप्ति तिथि": _utc_to_local(s["end"], tzname, tz_hours, used_manual).strftime("%d-%m-%Y"),
             "आयु (वर्ष)": age_years(dt_local, s["end"])}
            for s in md_segments_utc
        ])
    
        now_utc = datetime.datetime.utcnow()
        rows_an = next_antar_in_days_utc(now_utc, md_segments_utc, days_window=365*10)
        df_an = pd.DataFrame([
            {"महादशा": HN[r["major"]], "अंतरदशा": HN[r["antar"]],
             "तिथि": _utc_to_local(r["end"], tzname, tz_hours, used_manual).strftime("%d-%m-%Y")}
            for r in rows_an
        ]).head(5)
    
        img_lagna = render_north_diamond(size_px=800, stroke=3)
        img_nav   = render_north_diamond(size_px=800, stroke=3)
    
        # DOCX
        doc = make_document()
        sec = doc.sections[0]; sec.page_width = Mm(210); sec.page_height = Mm(297)
        margin = Mm(12); sec.left_margin = sec.right_margin = margin; sec.top_margin = Mm(8); sec.bottom_margin = Mm(8)
    
        style = doc.styles['Normal']; style.font.name = LATIN_FONT; style.font.size = Pt(BASE_FONT_PT)
        style._element.rPr.rFonts.set(qn('w:eastAsia'), HINDI_FONT); style._element.rPr.rFonts.set(qn('w:cs'), HINDI_FONT)
    
        
        
        
        
        # ===== Report Header Block (exact lines) =====
        # (clean, properly indented — no nested try/except)
        hdr1 = doc.add_paragraph(); hdr1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = hdr1.add_run('Midraastro'); r.font.bold = True; r.font.small_caps = True; r.font.size = Pt(16)
        
        hdr2 = doc.add_paragraph(); hdr2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r2 = hdr2.add_run('In the light of the divine, let your soul journey shine.'); r2.italic = True; r2.font.size = Pt(10)
        
        hdr3 = doc.add_paragraph(); hdr3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r3 = hdr3.add_run('PERSONAL HOROSCOPE (JANMA KUNDALI)'); r3.bold = True; r3.font.size = Pt(13)
        
        hdr4 = doc.add_paragraph(); hdr4.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r4 = hdr4.add_run('Niyati Niraj Golwalkar'); r4.font.size = Pt(10); r4.bold = True
        
        hdr5 = doc.add_paragraph(); hdr5.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r5 = hdr5.add_run('Astrologer • Sound & Mantra Healer'); r5.font.size = Pt(9.5)
        
        hdr6 = doc.add_paragraph(); hdr6.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r6 = hdr6.add_run('Phone: +91 9302413816  |  Electronic City Phase 1, Bangalore, India'); r6.font.size = Pt(9.5)
        # ===== End Header Block (exact lines) =====

    # ===== End Header Block (simplified & robust) =====
    # ===== End Header Block (safe) =====
    
    
        outer = doc.add_table(rows=1, cols=2); outer.autofit=False
        right_width_in = 3.70; outer.columns[0].width = Inches(3.70); outer.columns[1].width = Inches(3.70)
    
        CHART_W_PT = int(right_width_in * 72 - 10)
        CHART_H_PT = int(CHART_W_PT * 0.80)
        ROW_HEIGHT_PT = int(CHART_H_PT + 14)
        tbl = outer._tbl; tblPr = tbl.tblPr; tblBorders = OxmlElement('w:tblBorders')
        for edge in ('top','left','bottom','right','insideH','insideV'):
            el = OxmlElement(f'w:{edge}'); el.set(qn('w:val'),'single'); el.set(qn('w:sz'),'6'); tblBorders.append(el)
        tblPr.append(tblBorders)
    
        left = outer.rows[0].cells[0]
    # व्यक्तिगत विवरण styled: bold section, underlined labels, larger font
        p = left.add_paragraph('व्यक्तिगत विवरण'); p.runs[0].bold = True; p.runs[0].underline = True; p.runs[0].font.size = Pt(BASE_FONT_PT+5)
        # Name
        pname = left.add_paragraph();
        r1 = pname.add_run('नाम: '); r1.underline = True; r1.bold = True; r1.font.size = Pt(BASE_FONT_PT+3)
        r2 = pname.add_run(str(name)); r2.bold = True; r2.font.size = Pt(BASE_FONT_PT+3)
        # DOB | TOB
        pname.paragraph_format.space_after = Pt(1)
        
    # Personal Details (spacing tuned)
    # Name already added above; add DOB, TOB, Place each on its own line
        # Personal Details (spacing tuned)
        # Name already added above; add DOB, TOB, Place each on its own line
        
        # Personal Details (compact spacing)
        pdate = left.add_paragraph()
        r1 = pdate.add_run('जन्म तिथि: '); r1.underline = True; r1.bold = True; r1.font.size = Pt(BASE_FONT_PT+3)
        r2 = pdate.add_run(str(dob)); r2.bold = True; r2.font.size = Pt(BASE_FONT_PT+3)
        pdate.paragraph_format.space_before = Pt(0)
        pdate.paragraph_format.space_after = Pt(1)
    
        ptime = left.add_paragraph()
        r3 = ptime.add_run('जन्म समय: '); r3.underline = True; r3.bold = True; r3.font.size = Pt(BASE_FONT_PT+3)
        r4 = ptime.add_run(str(tob)); r4.bold = True; r4.font.size = Pt(BASE_FONT_PT+3)
        ptime.paragraph_format.space_before = Pt(0)
        ptime.paragraph_format.space_after = Pt(1)
    
        pplace = left.add_paragraph()
        try:
            place_disp = disp
        except Exception:
            place_disp = place if 'place' in locals() else ''
        r5 = pplace.add_run('स्थान: '); r5.underline = True; r5.bold = True; r5.font.size = Pt(BASE_FONT_PT+3)
        r6 = pplace.add_run(str(place_disp)); r6.bold = True; r6.font.size = Pt(BASE_FONT_PT+3)
        pplace.paragraph_format.space_before = Pt(0)
        pplace.paragraph_format.space_after = Pt(8)
        h1 = left.add_paragraph("ग्रह स्थिति"); _apply_hindi_caption_style(h1, size_pt=11, underline=True, bold=True)
        t1 = left.add_table(rows=1, cols=len(df_positions.columns)); t1.autofit=False
        for i,c in enumerate(df_positions.columns): t1.rows[0].cells[i].text=c
        for _,row in df_positions.iterrows():
            r=t1.add_row().cells
            for i,c in enumerate(row): r[i].text=str(c)
        center_header_row(t1); set_table_font(t1, pt=BASE_FONT_PT); add_table_borders(t1, size=6)
        set_col_widths(t1, [0.70, 0.55, 0.85, 0.80, 0.80])
        # Left align ONLY the header cell of the last column (उप‑नक्षत्र / Sublord)
        for p in t1.rows[0].cells[-1].paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    
    
        h2 = left.add_paragraph("विंशोत्तरी महादशा"); _apply_hindi_caption_style(h2, size_pt=11, underline=True, bold=True); h2.paragraph_format.keep_with_next = True; h2.paragraph_format.space_after = Pt(2)
        t2 = left.add_table(rows=1, cols=len(df_md.columns)); t2.autofit=False
        for i,c in enumerate(df_md.columns): t2.rows[0].cells[i].text=c
        for _,row in df_md.iterrows():
            r=t2.add_row().cells
            for i,c in enumerate(row): r[i].text=str(c)
        center_header_row(t2); set_table_font(t2, pt=BASE_FONT_PT); add_table_borders(t2, size=6)
        set_col_widths(t2, [1.20, 1.50, 1.00])
    
        h3 = left.add_paragraph("महादशा / अंतरदशा"); _apply_hindi_caption_style(h3, size_pt=11, underline=True, bold=True)
        t3 = left.add_table(rows=1, cols=len(df_an.columns)); t3.autofit=False
        for i,c in enumerate(df_an.columns): t3.rows[0].cells[i].text=c
        for _,row in df_an.iterrows():
            r=t3.add_row().cells
            for i,c in enumerate(row): r[i].text=str(c)
        center_header_row(t3); set_table_font(t3, pt=BASE_FONT_PT); add_table_borders(t3, size=6)
        compact_table_paragraphs(t3)
        set_col_widths(t3, [1.20, 1.50, 1.10])
    
        # One-page: place Pramukh Bindu under tables (left column) to free right column for charts
        try:
            add_pramukh_bindu_section(left, sidelons, lagna_sign, dt_utc)
            add_phalit_section(left)
        except Exception:
            pass
        right = outer.rows[0].cells[1]
    
        # Ensure the OUTER right cell has zero inner margins so the kundali touches the cell borders
        try:
            right_tcPr = right._tc.get_or_add_tcPr()
            right_tcMar = right_tcPr.find('./w:tcMar')
            if right_tcMar is None:
                right_tcMar = OxmlElement('w:tcMar')
                right_tcPr.append(right_tcMar)
            for side in ('top','left','bottom','right'):
                el = OxmlElement(f'w:{side}')
                el.set(qn('w:w'),'0')
                el.set(qn('w:type'),'dxa')
                right_tcMar.append(el)
        except Exception:
            pass
    
        kt = right.add_table(rows=2, cols=1); kt.autofit=False; kt.columns[0].width = Inches(right_width_in)
    
        # remove cell padding for chart table to let kundali touch the cell borders
        try:
            tcPr = kt._tbl.tblPr
            tblCellMar = OxmlElement('w:tblCellMar')
            for side in ('top','left','bottom','right'):
                el = OxmlElement(f'w:{side}')
                el.set(qn('w:w'),'0')
                el.set(qn('w:type'),'dxa')
                tblCellMar.append(el)
            tcPr.append(tblCellMar)
        except Exception:
            pass
        # Compact right-cell paragraph spacing
        try:
            for p in right.paragraphs:
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
        except Exception:
            pass
        right.vertical_alignment = WD_ALIGN_VERTICAL.TOP
        kt.autofit = False
        kt.columns[0].width = Inches(right_width_in)
        for row in kt.rows: row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY; row.height = Pt(ROW_HEIGHT_PT)
        
    
        cell1 = kt.rows[0].cells[0]; cap1 = cell1.add_paragraph("लग्न कुंडली")
        cap1.alignment = WD_ALIGN_PARAGRAPH.CENTER; _apply_hindi_caption_style(cap1, size_pt=11, underline=True, bold=True); cap1.paragraph_format.space_before = Pt(2); cap1.paragraph_format.space_after = Pt(2)
        p1 = cell1.add_paragraph(); p1.paragraph_format.space_before = Pt(0); p1.paragraph_format.space_after = Pt(0)
        # Lagna chart with planets in single box per house
        rasi_house_planets = build_rasi_house_planets_marked(sidelons, lagna_sign)
        p1._p.addnext(kundali_with_planets(size_pt=CHART_W_PT, lagna_sign=lagna_sign, house_planets=rasi_house_planets))
    
        cell2 = kt.rows[1].cells[0]; cap2 = cell2.add_paragraph("नवांश कुंडली")
        cap2.alignment = WD_ALIGN_PARAGRAPH.CENTER; _apply_hindi_caption_style(cap2, size_pt=11, underline=True, bold=True); cap2.paragraph_format.space_before = Pt(2); cap2.paragraph_format.space_after = Pt(2)
        p2 = cell2.add_paragraph(); p2.paragraph_format.space_before = Pt(0); p2.paragraph_format.space_after = Pt(0)
        nav_house_planets = build_navamsa_house_planets_marked(sidelons, nav_lagna_sign)
        p2._p.addnext(kundali_with_planets(size_pt=CHART_W_PT, lagna_sign=nav_lagna_sign, house_planets=nav_house_planets))
        # (प्रमुख बिंदु moved to row 2 of outer table)
        # Ensure content goes below chart shape
        cell2.add_paragraph("")
        cell2.add_paragraph("")
        # (Pramukh Bindu moved above charts)
        with st.spinner('Generating Kundali…'):
            out = BytesIO(); doc.save(out); out.seek(0)
        st.success('Kundali ready ✓')
        try:
            st.toast('Kundali ready ✓')
        except Exception:
            pass
        st.download_button("⬇️ Download Kundali (DOCX)", out.getvalue(), file_name=f"{sanitize_filename(name)}_Horoscope.docx")

    except Exception as e:
        st.error(f'Error while generating Kundali: {e}')
if __name__=='__main__':
    main()
