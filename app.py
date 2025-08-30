# -*- coding: utf-8 -*-
# Consolidated kundali generator with D1/D9 rules and markers

from docx import Document
from docx.oxml import parse_xml
from docx.enum.text import WD_ALIGN_PARAGRAPH

HN_ABBR = {
    'Su': 'सू', 'Mo': 'चं', 'Ma': 'मं', 'Me': 'बु',
    'Ju': 'गु', 'Ve': 'शु', 'Sa': 'श', 'Ra': 'रा', 'Ke': 'के'
}

SELF_SIGNS = {
    'Su': {5}, 'Mo': {4}, 'Ma': {1, 8}, 'Me': {3, 6}, 'Ju': {9, 12},
    'Ve': {2, 7}, 'Sa': {10, 11}, 'Ra': set(), 'Ke': set()
}

EXALT_SIGN = {'Su': 1, 'Mo': 2, 'Ma': 10, 'Me': 6, 'Ju': 4, 'Ve': 12, 'Sa': 7}
DEBIL_SIGN = {p: ((s + 5) % 12) + 1 for p, s in EXALT_SIGN.items()}
COMB_ORB = {'Mo': 12, 'Ma': 17, 'Me': 12, 'Ju': 11, 'Ve': 10, 'Sa': 15, 'Ra': 0, 'Ke': 0}

UP_ARROW, DOWN_ARROW, COMBUST, VARG_SQ = '↑', '↓', '^', '◱'

def _sep_deg(a, b):
    d = abs((a - b) % 360.0)
    return d if d <= 180 else 360 - d

def _rasi_sign(lon_sid):
    return int(lon_sid // 30) + 1

def navamsa_sign_from_lon_sid(lon_sid):
    rasi = int(lon_sid // 30) + 1
    part = int((lon_sid % 30) // (30/9.0))
    return ((rasi - 1) * 9 + part) % 12 + 1

def _is_combust_d1(code, sidelons):
    if code not in COMB_ORB or COMB_ORB[code] == 0: return False
    return _sep_deg(sidelons[code], sidelons['Su']) <= COMB_ORB[code]

def _is_combust_d9_same_nsign(code, sidelons):
    if code in ('Su','Ra','Ke'): return False
    sun_n = navamsa_sign_from_lon_sid(sidelons['Su'])
    pl_n  = navamsa_sign_from_lon_sid(sidelons[code])
    return sun_n == pl_n

def build_rasi_house_planets(sidelons, lagna_sign):
    house_map = {i: [] for i in range(1, 13)}
    for code in HN_ABBR.keys():
        lon = sidelons[code]; rasi = _rasi_sign(lon)
        h = ((rasi - lagna_sign) % 12) + 1
        is_self = rasi in SELF_SIGNS.get(code, set())
        is_ex   = (code not in ('Ra','Ke')) and (EXALT_SIGN.get(code) == rasi)
        is_de   = (code not in ('Ra','Ke')) and (DEBIL_SIGN.get(code) == rasi)
        is_cb   = _is_combust_d1(code, sidelons)
        is_vg   = (rasi == navamsa_sign_from_lon_sid(lon))
        base = HN_ABBR[code]; disp = base
        if is_ex: disp += UP_ARROW
        if is_de: disp += DOWN_ARROW
        if is_cb: disp += COMBUST
        house_map[h].append({'txt': base,'disp':disp,
            'flags':{'self':is_self,'exalt':is_ex,'debil':is_de,'comb':is_cb,'varg':is_vg}})
    return house_map

def build_navamsa_house_planets(sidelons, nav_lagna_sign):
    house_map = {i: [] for i in range(1, 13)}
    for code in HN_ABBR.keys():
        lon = sidelons[code]; nsign = navamsa_sign_from_lon_sid(lon)
        h = ((nsign - nav_lagna_sign) % 12) + 1
        is_self = nsign in SELF_SIGNS.get(code, set())
        is_ex   = (code not in ('Ra','Ke')) and (EXALT_SIGN.get(code) == nsign)
        is_de   = (code not in ('Ra','Ke')) and (DEBIL_SIGN.get(code) == nsign)
        is_cb   = _is_combust_d9_same_nsign(code, sidelons)
        is_vg   = (_rasi_sign(lon) == nsign)
        base = HN_ABBR[code]; disp = base
        if is_ex: disp += UP_ARROW
        if is_de: disp += DOWN_ARROW
        if is_cb: disp += COMBUST
        house_map[h].append({'txt': base,'disp':disp,
            'flags':{'self':is_self,'exalt':is_ex,'debil':is_de,'comb':is_cb,'varg':is_vg}})
    return house_map

def kundali_single_box(size_pt=220, house_planets=None):
    S=size_pt; w,h=36,28
    rect=f'<v:rect style="width:{S}pt;height:{S}pt" strokecolor="black" strokeweight="1pt"/>'
    diag1=f'<v:line from="0,0" to="{S}pt,{S}pt" strokecolor="black" strokeweight="1pt"/>'
    diag2=f'<v:line from="{S}pt,0" to="0,{S}pt" strokecolor="black" strokeweight="1pt"/>'
    mid1=f'<v:line from="{S/2}pt,0" to="{S}pt,{S/2}pt" strokecolor="black" strokeweight="1pt"/>'
    mid2=f'<v:line from="{S}pt,{S/2}pt" to="{S/2}pt,{S}pt" strokecolor="black" strokeweight="1pt"/>'
    mid3=f'<v:line from="{S/2}pt,{S}pt" to="0,{S/2}pt" strokecolor="black" strokeweight="1pt"/>'
    mid4=f'<v:line from="0,{S/2}pt" to="{S/2}pt,0" strokecolor="black" strokeweight="1pt"/>'
    coords={1:(S/2,S/8),2:(3*S/4,S/4),3:(7*S/8,S/2),4:(3*S/4,3*S/4),
            5:(S/2,7*S/8),6:(S/4,3*S/4),7:(S/8,S/2),8:(S/4,S/4),
            9:(S/2,S/2.7),10:(S/1.35,S/2),11:(S/2,S/1.35),12:(S/2.7,S/2)}
    nums={i:str(i) for i in range(1,13)}
    glyph_w,gap=8.0,3.0;r_circle,sq_size=5.2,4.2;y_off=4.0
    boxes=[]; overlays=[]
    for k,(x,y) in coords.items():
        items=house_planets.get(k,[]) if house_planets else []
        if items and not isinstance(items[0],dict): items=[{'txt':s,'disp':s,'flags':{}} for s in items]
        texts=[it.get('disp',it.get('txt','')) for it in items]; planets_text=" ".join(texts)
        content=f'<w:r><w:t>{nums[k]}</w:t></w:r>'
        if planets_text: content+=f'<w:br/><w:r><w:t>{planets_text}</w:t></w:r>'
        left,top=x-w/2,y-h/2
        boxes.append(f'<v:rect style="position:absolute;left:{left}pt;top:{top}pt;width:{w}pt;height:{h}pt;z-index:5" strokecolor="none"><v:textbox inset="0,0,0,0"><w:txbxContent xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:pPr><w:jc w:val="center"/></w:pPr>{content}</w:p></w:txbxContent></v:textbox></v:rect>')
        if items:
            n=len(items); total_w=n*glyph_w+(n-1)*gap; cx0=x-total_w/2+glyph_w/2; cy=y+y_off
            for idx,it in enumerate(items):
                cx=cx0+idx*(glyph_w+gap); flags=it.get('flags',{})
                if flags.get('self'): overlays.append(f'<v:oval style="position:absolute;left:{cx-r_circle}pt;top:{cy-6.0}pt;width:{2*r_circle}pt;height:{2*r_circle}pt;z-index:4" strokecolor="black" strokeweight="1pt" fillcolor="none"/>')
                if flags.get('varg'): overlays.append(f'<v:rect style="position:absolute;left:{cx+4.2}pt;top:{cy-7.4}pt;width:{sq_size}pt;height:{sq_size}pt;z-index:4" strokecolor="black" strokeweight="1pt" fillcolor="none"/>')
    xml=f'<w:pict xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:o="urn:schemas-microsoft-com:office:office">{rect}{diag1}{diag2}{mid1}{mid2}{mid3}{mid4}{"".join(boxes)}{"".join(overlays)}</w:pict>'
    return parse_xml(xml)

def add_kundali_to_doc(doc,title,house_planets,size_pt=220):
    p_title=doc.add_paragraph(); p_title.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=p_title.add_run(title); r.bold=True; r.underline=True
    p=doc.add_paragraph(); p._p.append(kundali_single_box(size_pt,house_planets)); doc.add_paragraph('')

def render_kundalis_into_doc(doc,sidelons,lagna_sign,nav_lagna_sign,size_pt=220):
    rasi_map=build_rasi_house_planets(sidelons,lagna_sign)
    nav_map=build_navamsa_house_planets(sidelons,nav_lagna_sign)
    add_kundali_to_doc(doc,'लग्न कुंडली',rasi_map,size_pt)
    add_kundali_to_doc(doc,'नवांश कुंडली',nav_map,size_pt)

if __name__=='__main__':
    sidelons={k:15.0+i*30 for i,k in enumerate(HN_ABBR.keys())}
    lagna_sign,nav_lagna_sign=2,4
    doc=Document(); render_kundalis_into_doc(doc,sidelons,lagna_sign,nav_lagna_sign,230)
    out='/mnt/data/kundali_demo.docx'; doc.save(out); print('Saved',out)
