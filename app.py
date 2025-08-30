# -*- coding: utf-8 -*-
"""
app_docx_borders_85pt_editable_v6_9_7_locked_MARKERS.py

Library-only module. No side effects, no auto-saving.
Drop-in rendering for editable North-Indian Kundali with planet markers.

What it does (built on your stable baseline layout):
- One editable textbox per house (line 1 = house number, line 2 = planets).
- Vector overlays (VML) drawn BEHIND text so house numbers never clip:
    * Self-ruling (स्वराशि): a tight circle around the planet glyph (planet sits inside the circle).
    * Vargottama (वर्गोत्तम): a tiny square at the top-right corner of the planet glyph.
- Exalted / Debilitated / Combust are appended inline as ↑ / ↓ / ^.
- Separate D1 (Rāśi) and D9 (Navāṁśa) rules.
- Rahu/Ketu excluded from exalt/debil/combust.

Public entrypoints:
    render_kundalis_into_doc(doc, sidelons, lagna_sign, nav_lagna_sign, size_pt=230)
    add_kundali(doc, title_text, house_map, size_pt=230)
    (helpers) house_planets_rasi / house_planets_navamsa

Inputs expected:
    sidelons: dict of sidereal longitudes 0..360 for keys: Su,Mo,Ma,Me,Ju,Ve,Sa,Ra,Ke
    lagna_sign: D1 lagna sign number 1..12
    nav_lagna_sign: D9 lagna sign number 1..12
"""

from docx.oxml import parse_xml
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx import Document

# ---------------- Planet labels (Hindi short) ----------------
HN_ABBR = {
    'Su': 'सू', 'Mo': 'चं', 'Ma': 'मं', 'Me': 'बु',
    'Ju': 'गु', 'Ve': 'शु', 'Sa': 'श', 'Ra': 'रा', 'Ke': 'के'
}
PLANETS = ['Su','Mo','Ma','Me','Ju','Ve','Sa','Ra','Ke']

# ---------------- Dignities & rules ----------------
def _norm12(n):
    n %= 12
    return 12 if n == 0 else n

EXALT_SIGN = {'Su':1,'Mo':2,'Ma':10,'Me':6,'Ju':4,'Ve':12,'Sa':7}
DEBIL_SIGN = {p: _norm12(s+6) for p, s in EXALT_SIGN.items()}

SELF_SIGNS = {
    'Su': {5}, 'Mo': {4}, 'Ma': {1,8}, 'Me': {3,6}, 'Ju': {9,12}, 'Ve': {2,7}, 'Sa': {10,11},
    'Ra': set(), 'Ke': set()
}

# D1 combustion orbs (deg)
COMB_ORB = {'Mo':12.0,'Ma':17.0,'Me':12.0,'Ju':11.0,'Ve':10.0,'Sa':15.0}

UP_ARROW, DOWN_ARROW, COMBUST = '↑','↓','^'

def _sep(a, b):
    d = abs((a - b) % 360.0)
    return d if d <= 180.0 else 360.0 - d

def rasi_sign(lon):  # 1..12
    return int(lon // 30.0) + 1

def navamsa_sign(lon):  # 1..12 (modal start rule)
    s = rasi_sign(lon)
    inside = lon % 30.0
    idx = int(inside // (30.0/9.0))  # 0..8
    if s in (1,4,7,10):       # movable
        start = s
    elif s in (2,5,8,11):     # fixed
        start = _norm12(s + 8)
    else:                     # dual
        start = _norm12(s + 4)
    return _norm12(start + idx)

# ---------------- Status builders ----------------
def planet_status_cache(sidelons: dict):
    """Return per-planet status dict with flags for D1/D9 rules."""
    out = {}
    sun_n9 = navamsa_sign(sidelons.get('Su', 0.0))
    for code in PLANETS:
        lon = sidelons.get(code, 0.0)
        s1 = rasi_sign(lon)
        s9 = navamsa_sign(lon)
        is_self = s1 in SELF_SIGNS.get(code, set())
        is_ex   = (code not in ('Ra','Ke')) and (EXALT_SIGN.get(code) == s1)
        is_de   = (code not in ('Ra','Ke')) and (DEBIL_SIGN.get(code) == s1)
        # Combust:
        #   D1 by orb vs Sun
        #   D9 if planet shares Sun's Navamsa sign
        is_cb = False
        if code not in ('Ra','Ke','Su'):
            orb = COMB_ORB.get(code, None)
            if orb is not None and _sep(sidelons['Su'], lon) <= orb:
                is_cb = True
            if navamsa_sign(lon) == sun_n9:
                is_cb = True
        is_vg = (s1 == s9)  # vargottama
        out[code] = {'s1': s1, 's9': s9, 'self': is_self, 'ex': is_ex, 'de': is_de, 'cb': is_cb, 'vg': is_vg}
    return out

def decorate_label(code: str, st: dict) -> str:
    """Build planet label with inline ↑ ↓ ^ (self & varg are vector overlays)."""
    base = HN_ABBR.get(code, code)
    if st.get('ex'): base += UP_ARROW
    if st.get('de'): base += DOWN_ARROW
    if st.get('cb'): base += COMBUST
    return base  # circle/square drawn as VML overlays

# ---------------- House planet mapping ----------------
def house_planets_rasi(sidelons, lagna_sign):
    cache = planet_status_cache(sidelons)
    houses = {i: [] for i in range(1, 13)}
    for code in PLANETS:
        lon = sidelons.get(code, 0.0)
        sign = rasi_sign(lon)
        h = ((sign - lagna_sign) % 12) + 1
        houses[h].append({'code': code, 'label': decorate_label(code, cache[code]), 'flags': cache[code]})
    return houses

def house_planets_navamsa(sidelons, nav_lagna_sign):
    cache = planet_status_cache(sidelons)
    houses = {i: [] for i in range(1, 13)}
    for code in PLANETS:
        lon = sidelons.get(code, 0.0)
        nsign = navamsa_sign(lon)
        h = ((nsign - nav_lagna_sign) % 12) + 1
        houses[h].append({'code': code, 'label': decorate_label(code, cache[code]), 'flags': cache[code]})
    return houses

# ---------------- VML Kundali (baseline-safe) ----------------
def kundali_single_box(size_pt=230, house_map=None):
    """
    North-Indian frame + one textbox per house (centered lines).
    Vector overlays:
      - self: circle tightly around glyph
      - varg: tiny square at top-right of glyph
    """
    S = size_pt
    # frame
    rect  = f'<v:rect style="width:{S}pt;height:{S}pt" strokecolor="black" strokeweight="1pt"/>'
    diag1 = f'<v:line from="0,0" to="{S}pt,{S}pt" strokecolor="black" strokeweight="1pt"/>'
    diag2 = f'<v:line from="{S}pt,0" to="0,{S}pt" strokecolor="black" strokeweight="1pt"/>'
    mid1  = f'<v:line from="{S/2}pt,0" to="{S}pt,{S/2}pt" strokecolor="black" strokeweight="1pt"/>'
    mid2  = f'<v:line from="{S}pt,{S/2}pt" to="{S/2}pt,{S}pt" strokecolor="black" strokeweight="1pt"/>'
    mid3  = f'<v:line from="{S/2}pt,{S}pt" to="0,{S/2}pt" strokecolor="black" strokeweight="1pt"/>'
    mid4  = f'<v:line from="0,{S/2}pt" to="{S/2}pt,0" strokecolor="black" strokeweight="1pt"/>'

    # house centers tuned from stable earlier layout
    coords = {
        1:(S/2,S/8), 2:(3*S/4,S/4), 3:(7*S/8,S/2), 4:(3*S/4,3*S/4),
        5:(S/2,7*S/8), 6:(S/4,3*S/4), 7:(S/8,S/2), 8:(S/4,S/4),
        9:(S/2,S/2.7), 10:(S/1.35,S/2), 11:(S/2,S/1.35), 12:(S/2.7,S/2)
    }
    nums = {i: str(i) for i in range(1, 13)}

    # textbox metrics
    w, h = 36, 28
    glyph_w = 8.0
    gap     = 3.0
    y_off   = 4.0  # planets line below number

    # overlay sizing (tight & subtle)
    r_circle = 4.6     # circle radius, to hug glyph (planet sits inside)
    sq_size  = 3.4     # tiny square
    sq_dx    = 3.6     # right shift from glyph center
    sq_dy    = 6.2     # upward shift from glyph center

    boxes = []
    overlays = []

    for k, (x, y) in coords.items():
        items = house_map.get(k, []) if house_map else []
        # Build planet line (decorated labels)
        labels = [it['label'] for it in items]
        planets_text = " ".join(labels)
        content = f'<w:r><w:t>{nums[k]}</w:t></w:r>'
        if planets_text:
            content += f'<w:br/><w:r><w:t>{planets_text}</w:t></w:r>'
        # house textbox
        left, top = x - w/2, y - h/2
        boxes.append(
            f'<v:rect style="position:absolute;left:{left}pt;top:{top}pt;width:{w}pt;height:{h}pt;z-index:5" '
            f'strokecolor="none"><v:textbox inset="0,0,0,0">'
            f'<w:txbxContent xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:p><w:pPr><w:jc w:val="center"/></w:pPr>{content}</w:p>'
            f'</w:txbxContent></v:textbox></v:rect>'
        )
        # overlays per planet (behind text)
        if items:
            n = len(items)
            total_w = n*glyph_w + (n-1)*gap
            cx0 = x - total_w/2 + glyph_w/2
            cy  = y + y_off
            for idx, it in enumerate(items):
                flags = it['flags']
                cx = cx0 + idx*(glyph_w + gap)
                # self: draw tight circle centered on glyph
                if flags.get('self'):
                    overlays.append(
                        f'<v:oval o:shadow="f" style="position:absolute;left:{cx-r_circle}pt;top:{cy-r_circle}pt;'
                        f'width:{2*r_circle}pt;height:{2*r_circle}pt;z-index:4" '
                        f'strokecolor="black" strokeweight="1pt" fillcolor="none"/>'
                    )
                # varg: tiny square at top-right corner of glyph
                if flags.get('vg'):
                    overlays.append(
                        f'<v:rect o:shadow="f" style="position:absolute;left:{cx+sq_dx}pt;top:{cy-sq_dy}pt;'
                        f'width:{sq_size}pt;height:{sq_size}pt;z-index:4" '
                        f'strokecolor="black" strokeweight="1pt" fillcolor="none"/>'
                    )

    xml = (
        f'<w:pict xmlns:v="urn:schemas-microsoft-com:vml" '
        f'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        f'xmlns:o="urn:schemas-microsoft-com:office:office">'
        f'{rect}{diag1}{diag2}{mid1}{mid2}{mid3}{mid4}'
        f'{"".join(boxes)}'
        f'{"".join(overlays)}'
        f'</w:pict>'
    )
    return parse_xml(xml)

# --------------- Document helpers ---------------
def add_kundali(doc: Document, title_text: str, house_map: dict, size_pt: int = 230):
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p_title.add_run(title_text)
    r.bold = True
    r.underline = True
    p = doc.add_paragraph()
    p._p.append(kundali_single_box(size_pt=size_pt, house_map=house_map))
    doc.add_paragraph('')

def render_kundalis_into_doc(doc: Document, sidelons: dict, lagna_sign: int, nav_lagna_sign: int, size_pt: int = 230):
    d1_map = house_planets_rasi(sidelons, lagna_sign)
    d9_map = house_planets_navamsa(sidelons, nav_lagna_sign)
    add_kundali(doc, 'लग्न कुंडली', d1_map, size_pt=size_pt)
    add_kundali(doc, 'नवांश कुंडली', d9_map, size_pt=size_pt)
