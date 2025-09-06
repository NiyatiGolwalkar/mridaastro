
import sys
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def clear_inside_vertical_border(table):
    try:
        tbl = table._tbl
        tblPr = tbl.tblPr
        # remove any existing tblBorders first
        for el in list(tblPr):
            if el.tag.endswith('tblBorders'):
                tblPr.remove(el)
        tblBorders = OxmlElement('w:tblBorders')
        for edge in ('top','left','bottom','right','insideH','insideV'):
            el = OxmlElement(f'w:{edge}')
            # keep all as-is except insideV, which we nil
            val = 'nil' if edge in ('insideV',) else 'nil'
            el.set(qn('w:val'), val)
            tblBorders.append(el)
        tblPr.append(tblBorders)
    except Exception:
        pass

def right_align_paragraph(p):
    try:
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    except Exception:
        pass

def main(inp, outp):
    doc = Document(inp)
    # 1) remove vertical divider on the first 1x2 table we find
    for t in doc.tables:
        try:
            if len(t.rows) == 1 and len(t.columns) == 2:
                clear_inside_vertical_border(t)
                break
        except Exception:
            pass
    # 2) align chart paragraphs to right: find titles and align next 2 paras
    titles = {"लग्न कुंडली", "नवांश कुंडली"}
    paras = doc.paragraphs
    n = len(paras)
    for i, p in enumerate(paras):
        if (p.text or "").strip() in titles:
            for j in range(1, 3):
                if i + j < n:
                    right_align_paragraph(paras[i+j])
    doc.save(outp)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python postprocess_align_and_nodivider.py input.docx output.docx")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
