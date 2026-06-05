#!/usr/bin/env python3
"""
compare_cnabf_rr.py
====================
Compares the "Colombia" column (CNABF, col 3) against the "Región 2" column
(ITU Radio Regulations) and outputs an Excel report of all differences.

Usage:
    python compare_cnabf_rr.py CNABF.pdf RR_Vol1.pdf [output.xlsx]

Requirements:
    pip install pdfplumber pandas openpyxl

Author: generated for CNABF 2026 vs RR comparison
"""

import re
import sys
from pathlib import Path

import openpyxl
import pandas as pd
import pdfplumber
from openpyxl.styles import Alignment, Font, PatternFill

# ─────────────────────────────────────────────
# CONFIGURATION  (edit if needed)
# ─────────────────────────────────────────────
CNABF_PDF = "CNABF2026.pdf"       # 55-page CNABF
RR_PDF    = "2400594-RR-Vol1.pdf" # 70-page ITU RR Vol 1
OUTPUT    = "diferencias_CNABF_RR.xlsx"

# pdfplumber table extraction settings (works best with bordered lattice tables)
TABLE_SETTINGS = {
    "vertical_strategy":   "lines",
    "horizontal_strategy": "lines",
    "intersection_tolerance": 3,
    "snap_tolerance": 3,
}

# ─────────────────────────────────────────────
# NORMALISATION HELPERS
# ─────────────────────────────────────────────

def norm(text: str) -> str:
    """
    Canonical form for comparison:
      - uppercase
      - comma → period  (14,95 → 14.95)
      - collapse whitespace / non-breaking spaces
    """
    if not text:
        return ""
    t = str(text).upper()
    t = t.replace(",", ".")
    t = re.sub(r"[\s\u00a0\u200b]+", " ", t)   # normalise all whitespace variants
    t = t.strip()
    return t


def norm_freq(text: str) -> str:
    """Normalise a frequency range token, e.g. '14 - 19,95' → '14-19.95'."""
    t = norm(text)
    t = re.sub(r"\s*[-–]\s*", "-", t)  # remove spaces around hyphen/dash
    return t


def is_freq_range(text: str) -> bool:
    """Return True if text looks like 'NNN-NNN' (frequency range)."""
    t = norm_freq(text).replace(" ", "")
    return bool(re.match(r"^[\d.]+[-][\d.]+$", t))


def cell_to_services(text: str) -> set[str]:
    """
    Split a multi-line cell into a set of normalised service strings.
    Each non-empty line becomes one element.
    """
    t = norm(text)
    # pdfplumber sometimes returns cells with \n between services
    lines = {l.strip() for l in t.splitlines() if l.strip()}
    return lines


# ─────────────────────────────────────────────
# CNABF EXTRACTION
# ─────────────────────────────────────────────
# Table structure (4 columns):
#   [0] Unidad | [1] Región 2 | [2] Colombia | [3] Notas nacionales
#
# Both col[1] and col[2] start with the frequency range on the first line,
# then list the allocated services below it.

def extract_cnabf(pdf_path: str) -> list[dict]:
    """
    Returns a list of dicts:
        page, unit, freq_range, colombia_raw, colombia_norm,
        colombia_services (set), notas
    """
    entries = []
    current_unit = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables(TABLE_SETTINGS)
            for table in tables:
                for row in table:
                    if not row:
                        continue
                    # Pad to at least 4 cells
                    row = list(row) + [""] * max(0, 4 - len(row))
                    c0 = (row[0] or "").strip()
                    c1 = (row[1] or "").strip()   # Región 2 column (has freq range too)
                    c2 = (row[2] or "").strip()   # Colombia ← our interest
                    c3 = (row[3] or "").strip() if len(row) > 3 else ""

                    # Skip header rows
                    skip_kw = ("unidad", "región", "region", "colombia", "notas")
                    if any(kw in c0.lower() for kw in skip_kw):
                        continue
                    if any(kw in c2.lower() for kw in ("colombia",)):
                        continue

                    # Track frequency unit
                    if c0.lower() in ("khz", "mhz", "ghz"):
                        current_unit = c0
                        c0 = ""

                    # Extract frequency range from col 1 (Región 2);
                    # its first line carries the same range as Colombia col.
                    freq = ""
                    lines_c1 = [l.strip() for l in c1.splitlines() if l.strip()]
                    if lines_c1 and is_freq_range(lines_c1[0]):
                        freq = norm_freq(lines_c1[0])

                    # Fallback: look for freq range inside Colombia cell
                    if not freq:
                        lines_c2 = [l.strip() for l in c2.splitlines() if l.strip()]
                        if lines_c2 and is_freq_range(lines_c2[0]):
                            freq = norm_freq(lines_c2[0])

                    # Only keep rows that have some Colombia content
                    if c2.strip() or freq:
                        entries.append({
                            "page":               page_num,
                            "unit":               current_unit,
                            "freq_range":         freq,
                            "colombia_raw":       c2,
                            "colombia_norm":      norm(c2),
                            "colombia_services":  cell_to_services(c2),
                            "notas":              c3,
                        })

    return entries


# ─────────────────────────────────────────────
# RR EXTRACTION
# ─────────────────────────────────────────────
# Table structure (3 columns):
#   [0] Región 1 | [1] Región 2 | [2] Región 3
#
# Frequency bands appear either:
#   a) as a BOLD spanning header row (only col[0] has content, others empty), OR
#   b) as the first line of col[0] when the band differs by region.
#
# Pages also contain plain-text footnotes (5.77, 5.78, …) — those are
# automatically ignored because they won't be inside table cells with
# a Región 2 column.

def extract_rr(pdf_path: str) -> list[dict]:
    """
    Returns a list of dicts:
        page, freq_range, region2_raw, region2_norm, region2_services (set)
    """
    entries = []

    with pdfplumber.open(pdf_path) as pdf:
        current_freq = ""

        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables(TABLE_SETTINGS)

            for table in tables:
                r2_col = None   # index of "Región 2" column within this table

                for row in table:
                    if not row:
                        continue

                    # ── Detect header row to locate Región 2 column ──────────
                    if r2_col is None:
                        for idx, cell in enumerate(row):
                            if cell and re.search(r"regi[oó]n\s*2", str(cell), re.I):
                                r2_col = idx
                                break
                        if r2_col is not None:
                            continue   # skip the header row itself
                        # Default assumption: 3-col table → Reg2 is index 1
                        # (only activate once we see a multi-column row)
                        non_empty = sum(1 for c in row if c and str(c).strip())
                        if non_empty >= 2:
                            r2_col = 1
                        else:
                            continue

                    if len(row) <= r2_col:
                        continue

                    c0   = (row[0]     or "").strip()
                    c_r2 = (row[r2_col] or "").strip()

                    # ── Detect spanning frequency-range header row ─────────
                    # All columns except col[0] are empty → it's a freq header.
                    others_empty = all(
                        not row[i] or str(row[i]).strip() == ""
                        for i in range(1, len(row))
                    )
                    if c0 and others_empty:
                        # Pull first line and check if it is a freq range
                        first_line = c0.splitlines()[0].strip() if c0 else ""
                        if is_freq_range(first_line):
                            current_freq = norm_freq(first_line)
                        continue   # header row, no Reg2 data here

                    # ── Regular data row ────────────────────────────────────
                    # Sometimes the freq range is the first line of col[0]
                    freq = current_freq
                    lines_c0 = [l.strip() for l in c0.splitlines() if l.strip()]
                    if lines_c0 and is_freq_range(lines_c0[0]):
                        freq = norm_freq(lines_c0[0])
                        current_freq = freq

                    # Skip empty Región 2 cells
                    if not c_r2.strip():
                        continue

                    entries.append({
                        "page":             page_num,
                        "freq_range":       freq,
                        "region2_raw":      c_r2,
                        "region2_norm":     norm(c_r2),
                        "region2_services": cell_to_services(c_r2),
                    })

    return entries


# ─────────────────────────────────────────────
# COMPARISON
# ─────────────────────────────────────────────

def compare(cnabf: list[dict], rr: list[dict]) -> list[dict]:
    """
    Match entries by frequency range and compare Colombia vs Región 2 services.
    Returns a list of difference dicts.
    """
    # Build RR index: freq_range → merged entry
    rr_idx: dict[str, dict] = {}
    for e in rr:
        f = e["freq_range"]
        if not f:
            continue
        if f not in rr_idx:
            rr_idx[f] = {
                "page":             e["page"],
                "freq_range":       f,
                "region2_raw":      e["region2_raw"],
                "region2_norm":     e["region2_norm"],
                "region2_services": set(e["region2_services"]),
            }
        else:
            # Merge multiple rows that share the same freq band
            rr_idx[f]["region2_services"].update(e["region2_services"])
            rr_idx[f]["region2_raw"] += "\n" + e["region2_raw"]

    differences = []
    seen = set()   # avoid duplicate freq entries from CNABF multi-page rows

    # ── CNABF entries vs RR ──────────────────────────────────────────────────
    for c in cnabf:
        f = c["freq_range"]
        if not f or f in seen:
            continue
        seen.add(f)

        r = rr_idx.get(f)
        if r is None:
            differences.append({
                "estado":        "SIN COINCIDENCIA EN RR",
                "banda":         f,
                "unidad":        c["unit"],
                "colombia":      c["colombia_norm"],
                "region2":       "",
                "solo_colombia": "",
                "solo_rr":       "",
                "pagina_cnabf":  c["page"],
                "pagina_rr":     "",
            })
            continue

        col_svc = c["colombia_services"]
        rr_svc  = r["region2_services"]
        only_col = col_svc - rr_svc
        only_rr  = rr_svc  - col_svc

        if only_col or only_rr:
            differences.append({
                "estado":        "DIFERENCIA",
                "banda":         f,
                "unidad":        c["unit"],
                "colombia":      c["colombia_norm"],
                "region2":       r["region2_norm"],
                "solo_colombia": "\n".join(sorted(only_col)),
                "solo_rr":       "\n".join(sorted(only_rr)),
                "pagina_cnabf":  c["page"],
                "pagina_rr":     r["page"],
            })

    # ── RR bands not found at all in CNABF ──────────────────────────────────
    for f, r in rr_idx.items():
        if f not in seen:
            differences.append({
                "estado":        "SIN COINCIDENCIA EN CNABF",
                "banda":         f,
                "unidad":        "",
                "colombia":      "",
                "region2":       r["region2_norm"],
                "solo_colombia": "",
                "solo_rr":       "",
                "pagina_cnabf":  "",
                "pagina_rr":     r["page"],
            })

    return differences


# ─────────────────────────────────────────────
# EXCEL REPORT
# ─────────────────────────────────────────────

COLOR = {
    "DIFERENCIA":               "FFF2CC",   # yellow
    "SIN COINCIDENCIA EN RR":   "FFCCCC",   # red
    "SIN COINCIDENCIA EN CNABF":"CCE5FF",   # blue
    "header":                   "1F3864",   # dark navy
}

def save_report(diffs: list[dict],
                cnabf_raw: list[dict],
                rr_raw: list[dict],
                out_path: str) -> None:

    wb = openpyxl.Workbook()

    # ── Sheet 1: Differences ────────────────────────────────────────────────
    ws = wb.active
    ws.title = "Diferencias"

    headers = [
        "Estado", "Banda (kHz/MHz/GHz)", "Unidad",
        "Colombia (CNABF)", "Región 2 (RR)",
        "Solo en Colombia ⚠️", "Solo en RR ⚠️",
        "Pág. CNABF", "Pág. RR",
    ]
    hfill = PatternFill("solid", fgColor=COLOR["header"])
    hfont = Font(bold=True, color="FFFFFF", size=10)
    halign = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for ci, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=ci, value=h)
        cell.fill, cell.font, cell.alignment = hfill, hfont, halign

    ws.row_dimensions[1].height = 30

    for ri, d in enumerate(diffs, 2):
        vals = [
            d["estado"], d["banda"], d["unidad"],
            d["colombia"], d["region2"],
            d["solo_colombia"], d["solo_rr"],
            d["pagina_cnabf"], d["pagina_rr"],
        ]
        row_fill = PatternFill("solid", fgColor=COLOR.get(d["estado"], "FFFFFF"))
        for ci, v in enumerate(vals, 1):
            cell = ws.cell(row=ri, column=ci, value=v)
            cell.fill = row_fill
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    # Column widths
    for col_letter, width in zip("ABCDEFGHI", [22, 22, 8, 55, 55, 35, 35, 10, 9]):
        ws.column_dimensions[col_letter].width = width

    ws.freeze_panes = "A2"

    # ── Sheet 2: Raw CNABF extract (for debugging) ──────────────────────────
    ws2 = wb.create_sheet("CNABF extraído")
    ws2.append(["Página", "Unidad", "Banda", "Colombia (raw)", "Notas"])
    for e in cnabf_raw:
        ws2.append([e["page"], e["unit"], e["freq_range"],
                    e["colombia_raw"], e["notas"]])

    # ── Sheet 3: Raw RR extract (for debugging) ─────────────────────────────
    ws3 = wb.create_sheet("RR extraído")
    ws3.append(["Página", "Banda", "Región 2 (raw)"])
    for e in rr_raw:
        ws3.append([e["page"], e["freq_range"], e["region2_raw"]])

    wb.save(out_path)

    # ── Summary ─────────────────────────────────────────────────────────────
    counts: dict[str, int] = {}
    for d in diffs:
        counts[d["estado"]] = counts.get(d["estado"], 0) + 1

    print(f"\n✅  Reporte guardado en: {out_path}")
    print(f"    CNABF entradas extraídas : {len(cnabf_raw)}")
    print(f"    RR    entradas extraídas : {len(rr_raw)}")
    print(f"    Total diferencias        : {len(diffs)}")
    for estado, n in sorted(counts.items()):
        print(f"      {estado}: {n}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    cnabf_path = args[0] if len(args) > 0 else CNABF_PDF
    rr_path    = args[1] if len(args) > 1 else RR_PDF
    out_path   = args[2] if len(args) > 2 else OUTPUT

    for p in (cnabf_path, rr_path):
        if not Path(p).exists():
            print(f"❌  No se encontró el archivo: {p}")
            sys.exit(1)

    print(f"📄  Extrayendo CNABF:  {cnabf_path}")
    cnabf_data = extract_cnabf(cnabf_path)
    print(f"    {len(cnabf_data)} filas encontradas")

    print(f"📄  Extrayendo RR:     {rr_path}")
    rr_data = extract_rr(rr_path)
    print(f"    {len(rr_data)} filas encontradas")

    print("🔍  Comparando…")
    diffs = compare(cnabf_data, rr_data)

    print("💾  Generando reporte…")
    save_report(diffs, cnabf_data, rr_data, out_path)


if __name__ == "__main__":
    main()