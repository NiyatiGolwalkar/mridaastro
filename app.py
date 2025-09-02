# Usage: python apply_kundali_label_upgrade.py path/to/app.py
import sys, re, pathlib

if len(sys.argv) != 2:
    print("Usage: python apply_kundali_label_upgrade.py /path/to/app.py")
    sys.exit(1)

p = pathlib.Path(sys.argv[1]).resolve()
code = p.read_text(encoding="utf-8")

# 1) Ensure rectangular charts and keep them inside the right column
code = re.sub(r"CHART_W_PT\s*=\s*int\(right_width_in\s*\*\s*72\s*-\s*\d+\)",
              "CHART_W_PT = int(right_width_in * 72 - 16)", code)
code = re.sub(r"CHART_H_PT\s*=\s*int\(CHART_W_PT\s*\*\s*0\.\d+\)",
              "CHART_H_PT = int(CHART_W_PT * 0.80)", code)
code = re.sub(r"ROW_HEIGHT_PT\s*=\s*int\(CHART_H_PT\s*\+\s*\d+\)",
              "ROW_HEIGHT_PT = int(CHART_H_PT + 18)", code)

# 2) Make *all* planet labels larger (both charts share constants)
code = re.sub(r"PLANET_W_PT\s*=\s*\d+", "PLANET_W_PT = 28", code)
code = re.sub(r"PLANET_H_PT\s*=\s*\d+", "PLANET_H_PT = 20", code)
code = re.sub(r"PLANET_FONT_PT\s*=\s*\d+", "PLANET_FONT_PT = 12", code)

# Optional: increase row gap for stacked planets within one house
code = re.sub(r"ROW_GAP_PT\s*=\s*\d+", "ROW_GAP_PT = 18", code)

# 3) Guarantee the chart holder table uses full column width and no inner padding
code = code.replace("kt = right.add_table(rows=2, cols=1)",
                    "kt = right.add_table(rows=2, cols=1); kt.autofit=False; kt.columns[0].width = Inches(right_width_in)")
if "tblCellMar" not in code:
    inject = """
            # remove inner cell padding so VML fits perfectly in cell
            try:
                tcPr = kt._tbl.tblPr
                tblCellMar = OxmlElement('w:tblCellMar')
                for side in ('top','left','bottom','right'):
                    el = OxmlElement(f'w:{side}')
                    el.set(DOCX_QN('w:w'),'0')
                    el.set(DOCX_QN('w:type'),'dxa')
                    tblCellMar.append(el)
                tcPr.append(tblCellMar)
            except Exception:
                pass
    """
    pos = code.find("kt = right.add_table")
    if pos != -1:
        eol = code.find("\\n", pos)
        code = code[:eol+1] + inject + code[eol+1:]

# 4) Save backup and write
backup = p.with_suffix(".bak.py")
backup.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
p.write_text(code, encoding="utf-8")
print("Patched", p, " (backup saved as", backup.name, ")")
