"""Build the formula-driven Excel rate-scenario model from the FDIC panel.

Every projection, flag and check in the workbook is an Excel formula; only bank data (FDIC call reports, Q2 2026)
and assumptions are typed in. Run scripts/recalc afterwards so cached values exist for viewers that do not calculate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bankmon import data as d  # noqa: E402
from bankmon import metrics as m  # noqa: E402

OUT = ROOT / "excel" / "Regional_Bank_Rate_Scenario_Model.xlsx"
DEFAULT_BANK = "Flagstar Bank"

NAVY = "1F3A5F"
FONT = "Arial"
BLUE = Font(name=FONT, size=10, color="0000FF")
BLACK = Font(name=FONT, size=10, color="000000")
GREEN = Font(name=FONT, size=10, color="008000")
BOLD = Font(name=FONT, size=10, bold=True)
HEAD = Font(name=FONT, size=10, bold=True, color="FFFFFF")
TITLE = Font(name=FONT, size=14, bold=True, color=NAVY)
SUB = Font(name=FONT, size=10, italic=True, color="555555")
HEAD_FILL = PatternFill("solid", fgColor=NAVY)
INPUT_FILL = PatternFill("solid", fgColor="FFFF00")
LIGHT = PatternFill("solid", fgColor="EEF2F7")
THIN = Side(style="thin", color="C9D3E0")
BOX = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)

PCT = '0.00%;(0.00%);"-"'
PCT1 = '0.0%;(0.0%);"-"'
USD = '$#,##0;($#,##0);"-"'
USD1 = '$#,##0.0;($#,##0.0);"-"'
NUM2 = '0.00;(0.00);"-"'
INT = '0;(0);"-"'

QUARTERS = ["Q3 2026", "Q4 2026", "Q1 2027", "Q2 2027", "Q3 2027", "Q4 2027", "Q1 2028", "Q2 2028"]
SCENARIOS = [
    ("Base: Fed funds flat at 3.88%", [3.67, 3.88, 3.88, 3.88, 3.88, 3.88, 3.88, 3.88]),
    ("Rates +100bp by Q4 2027", [3.67, 3.88, 4.13, 4.38, 4.63, 4.88, 4.88, 4.88]),
    ("Rates +200bp, higher for longer", [3.67, 4.13, 4.63, 5.13, 5.63, 5.88, 5.88, 5.88]),
    ("Rates -100bp (cuts resume)", [3.67, 3.88, 3.63, 3.38, 3.13, 2.88, 2.88, 2.88]),
    ("Custom (edit this row)", [3.67, 3.88, 3.88, 3.88, 3.88, 3.88, 3.88, 3.88]),
]
START_FF = round(float(d.rates().set_index("date").loc[pd.Timestamp(d.LATEST), "fed_funds"]), 2)

# Bank_Data columns: (header, source column or callable, number format, divide-by-100)
COLS = [
    ("CERT", "cert", "0", False), ("Bank", "bank", "@", False), ("State", "state", "@", False), ("Size band", "size_band", "@", False),
    ("Total assets ($M)", "assets", USD, False), ("Earning assets ($M)", "earning_assets", USD, False), ("Loans ($M)", "loans", USD, False),
    ("CRE loans ($M)", "cre_loans", USD, False), ("Asset yield", "asset_yield", PCT, True), ("Cost of funds", "cost_of_funds", PCT, True),
    ("NIM", "nim", PCT, True), ("Cost of deposits", "deposit_cost", PCT, True), ("Asset yield beta", "yield_beta", NUM2, False),
    ("Funding cost beta", "funding_beta", NUM2, False), ("Deposit beta (hikes)", "up_beta", NUM2, False),
    ("Deposit beta (cuts)", "down_beta", NUM2, False), ("Uninsured deposits", "uninsured_share", PCT1, True),
    ("Loans / deposits", "loan_to_deposit", PCT1, True), ("CRE / capital", "cre_concentration", PCT1, True),
    ("Construction / capital", "construction_concentration", PCT1, True), ("Liquidity / uninsured", "uninsured_coverage", PCT1, True),
    ("Unrealized loss / Tier 1", "unrealized_to_tier1", PCT1, True), ("Unrealized securities gain/(loss) ($M)", "securities_unrealized", USD, False),
    ("CET1 capital ($M)", "cet1_capital", USD, False), ("Risk-weighted assets ($M)", "rwa", USD, False), ("CET1 ratio", "cet1_ratio", PCT, True),
    ("CET1 after securities losses", "cet1_marked", PCT, True), ("Net charge-offs / loans", "nco_rate", PCT, True),
    ("Noninterest income, qtr avg ($M)", "nonii_q", USD1, False), ("Noninterest expense, qtr avg ($M)", "nonix_q", USD1, False),
    ("Provision, qtr avg ($M)", "prov_q", USD1, False), ("Net income, qtr avg ($M)", "ni_q", USD1, False),
    ("Net interest income, Q2 2026 ($M)", "nii_last", USD1, False),
]


def bank_table() -> pd.DataFrame:
    s = d.snapshot()
    b = m.betas()
    p = d.peers()
    last4 = p[p["date"] > pd.Timestamp("2025-06-30")].groupby("cert")[
        ["noninterest_income", "noninterest_expense", "provision", "net_income"]].mean()
    t = pd.DataFrame(index=s.index)
    t["cert"] = s.index
    t["bank"] = s["short"]
    t["state"] = s["STALP"]
    t["size_band"] = s["size_band"]
    for c in ["assets", "earning_assets", "loans", "cre_loans", "asset_yield", "cost_of_funds", "nim", "deposit_cost", "uninsured_share",
              "loan_to_deposit", "cre_concentration", "construction_concentration", "uninsured_coverage", "unrealized_to_tier1",
              "securities_unrealized", "cet1_capital", "rwa", "cet1_ratio", "cet1_marked", "nco_rate"]:
        t[c] = s[c]
    for c in ["yield_beta", "funding_beta", "up_beta", "down_beta"]:
        t[c] = b[c]
    t["nonii_q"] = last4["noninterest_income"]
    t["nonix_q"] = last4["noninterest_expense"]
    t["prov_q"] = last4["provision"]
    t["ni_q"] = last4["net_income"]
    t["nii_last"] = s["net_interest_income"]
    return t.sort_values("bank").reset_index(drop=True)


def style_header(ws, row, c1, c2):
    for c in range(c1, c2 + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = HEAD
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BOX


def put(ws, ref, value, font=BLACK, fmt=None, fill=None, bold=False):
    c = ws[ref]
    c.value = value
    c.font = Font(name=FONT, size=10, color=font.color, bold=bold or font.bold, italic=font.italic)
    if fmt:
        c.number_format = fmt
    if fill:
        c.fill = fill
    return c


def build(path: Path = OUT) -> Path:
    t = bank_table()
    n = len(t)
    last = n + 1  # last data row on Bank_Data
    wb = Workbook()

    # ---------------- Cover ----------------
    cv = wb.active
    cv.title = "Cover"
    cv.sheet_view.showGridLines = False
    cv.column_dimensions["B"].width = 110
    put(cv, "B2", "Regional Bank Rate-Scenario Model", TITLE)
    put(cv, "B3", f"{n} US regional banks ($10-250B assets), FDIC call reports through Q2 2026; Fed funds from FRED.", SUB)
    lines = [
        ("How to use", True),
        ("1. On Inputs, pick a bank (yellow cell C4) and a rate scenario (C5). Edit any blue assumption.", False),
        ("2. Model projects 8 quarters: asset yields and funding costs move with Fed funds by the bank's own measured betas,", False),
        ("   then net interest income, earnings, an optional CRE loss stress and the CET1 ratio.", False),
        ("3. Scenarios compares all five rate paths for the selected bank. Peer_Screen applies the risk flags to every bank.", False),
        ("4. Checks ties the model to the reported call-report figures and to the Python analysis; every row should read PASS.", False),
        ("", False),
        ("Colour code", True),
        ("Blue text = typed input or source data.  Black = formula.  Green = link to another sheet.  Yellow fill = choose here.", False),
        ("", False),
        ("Method notes", True),
        ("Betas are measured over the 2021 Q4 to 2024 Q2 hiking cycle: change in the bank's asset yield (or cost of funds) divided by", False),
        ("the change in quarter-average Fed funds (0.08% to 5.33%). A bank whose funding beta exceeds its yield beta loses margin when rates rise.", False),
        ("Noninterest income, expense and provisions run at the last four quarters' average. Unrealized securities losses are held constant.", False),
        ("CRE stress applies a cumulative loss rate to construction, multifamily and non-owner-occupied CRE loans, spread evenly over 8 quarters.", False),
        ("This is a first-order earnings model for screening and discussion, not a regulatory stress test.", False),
        ("", False),
        ("Sources", True),
        ("FDIC BankFind Suite API (call reports, RIS fields), retrieved Nov 2026. FRED series FEDFUNDS, DGS2, DGS10.", False),
    ]
    for i, (txt, b) in enumerate(lines):
        put(cv, f"B{5 + i}", txt, BOLD if b else BLACK)

    # ---------------- Bank_Data ----------------
    bd = wb.create_sheet("Bank_Data")
    bd.freeze_panes = "C2"
    for j, (h, _, _, _) in enumerate(COLS, start=1):
        bd.cell(row=1, column=j, value=h)
        bd.column_dimensions[get_column_letter(j)].width = 14 if j > 2 else (8 if j == 1 else 30)
    style_header(bd, 1, 1, len(COLS))
    bd.row_dimensions[1].height = 42
    for i, row in t.iterrows():
        r = i + 2
        for j, (_, col, fmt, pct) in enumerate(COLS, start=1):
            v = row[col]
            if isinstance(v, float) and pct:
                v = v / 100.0
            if isinstance(v, float):
                v = round(v, 6)
            c = bd.cell(row=r, column=j, value=v)
            c.font = BLUE
            c.number_format = fmt
    note_row = last + 2
    put(bd, f"A{note_row}", "Source: FDIC call reports (BankFind Suite API, RIS fields) for Q2 2026; betas from the 2021 Q4 - 2024 Q2 hiking cycle "
        "(Python: src/bankmon/metrics.py). Dollar amounts in USD millions.", SUB)
    col_of = {h: get_column_letter(j) for j, (h, _, _, _) in enumerate(COLS, start=1)}

    def bdcol(h):
        return f"Bank_Data!${col_of[h]}$2:${col_of[h]}${last}"

    # ---------------- Inputs ----------------
    ip = wb.create_sheet("Inputs", 1)
    ip.sheet_view.showGridLines = False
    ip.column_dimensions["B"].width = 44
    ip.column_dimensions["C"].width = 34
    for col in "DEFGHIJK":
        ip.column_dimensions[col].width = 10
    put(ip, "B2", "Inputs", TITLE)
    put(ip, "B4", "Selected bank", BOLD)
    put(ip, "C4", DEFAULT_BANK, BLUE, fill=INPUT_FILL)
    put(ip, "B5", "Rate scenario", BOLD)
    put(ip, "C5", SCENARIOS[1][0], BLUE, fill=INPUT_FILL)
    put(ip, "B6", "Scenario number")
    put(ip, "C6", "=MATCH(C5,$B$21:$B$25,0)", BLACK, INT)
    dv_bank = DataValidation(type="list", formula1=f"=Bank_Data!$B$2:$B${last}", allow_blank=False)
    dv_scn = DataValidation(type="list", formula1="=$B$21:$B$25", allow_blank=False)
    ip.add_data_validation(dv_bank)
    ip.add_data_validation(dv_scn)
    dv_bank.add("C4")
    dv_scn.add("C5")

    put(ip, "B8", "Assumptions", BOLD)
    assumptions = [
        ("Asset yield beta override (blank = bank's own)", None, NUM2, "Leave blank to use the bank's measured hiking-cycle beta."),
        ("Funding cost beta override (blank = bank's own)", None, NUM2, "Leave blank to use the bank's measured hiking-cycle beta."),
        ("Earning asset growth per quarter", 0.0075, PCT, "About 3% a year, near the peer median since 2023."),
        ("Risk-weighted asset growth per quarter", 0.0075, PCT, "Kept equal to balance-sheet growth by default."),
        ("Tax rate", 0.21, PCT, "US federal statutory rate; state taxes ignored."),
        ("Payout ratio (dividends / net income)", 0.40, PCT, "Typical regional-bank payout."),
        ("CRE cumulative loss rate over 8 quarters", 0.015, PCT,
         "Applied to construction, multifamily and non-owner-occupied CRE. 1.5% is a moderate office-led stress."),
        ("Cost of funds floor", 0.001, PCT, "Funding costs cannot fall below this in the cuts scenario."),
        ("CET1 ratio alert level", 0.07, PCT, "4.5% minimum plus the 2.5% conservation buffer."),
    ]
    for k, (lab, val, fmt, note) in enumerate(assumptions):
        r = 9 + k
        put(ip, f"B{r}", lab)
        c = put(ip, f"C{r}", val, BLUE, fmt)
        c.comment = Comment(note, "Model")
    put(ip, "B19", "Fed funds path by scenario (quarter average)", BOLD)
    put(ip, "C19", "Start: Q2 2026 actual", SUB)
    put(ip, "B20", "Scenario")
    put(ip, "C20", START_FF / 100, BLUE, PCT)
    ip["C20"].comment = Comment("Q2 2026 quarter-average effective Fed funds rate (FRED FEDFUNDS).", "Model")
    for j, q in enumerate(QUARTERS):
        put(ip, f"{get_column_letter(4 + j)}20", q, BOLD)
    style_header(ip, 20, 2, 11)
    for i, (name, fpath) in enumerate(SCENARIOS):
        r = 21 + i
        put(ip, f"B{r}", name)
        for j, v in enumerate(fpath):
            put(ip, f"{get_column_letter(4 + j)}{r}", v / 100, BLUE, PCT)
    put(ip, "B26", "Q3 2026 is the actual quarter average (3.67%); Q4 starts from October's 3.88%. Edit the Custom row freely.", SUB)

    put(ip, "B28", "Risk-screen thresholds (used on Peer_Screen)", BOLD)
    thresholds = [("Uninsured deposits above", 0.60), ("CET1 after securities losses below", 0.08), ("CRE / capital above", 3.00),
                  ("Construction / capital above", 1.00), ("Loans / deposits above", 1.00), ("Liquidity / uninsured deposits below", 0.50),
                  ("Net charge-offs above", 0.005)]
    for k, (lab, v) in enumerate(thresholds):
        put(ip, f"B{29 + k}", lab)
        put(ip, f"C{29 + k}", v, BLUE, PCT1 if v >= 0.01 else PCT)

    # ---------------- Model ----------------
    md = wb.create_sheet("Model", 2)
    md.sheet_view.showGridLines = False
    md.column_dimensions["B"].width = 44
    for col in "CDEFGHIJKL":
        md.column_dimensions[col].width = 12
    put(md, "B2", '="Model: "&Inputs!C4&" - "&Inputs!C5', TITLE)
    put(md, "B3", "USD millions unless stated. Columns D-K are projected quarters; C is the Q2 2026 starting point.", SUB)

    def look(h):
        return f'=INDEX({bdcol(h)},MATCH(Inputs!$C$4,{bdcol("Bank")},0))'

    put(md, "B5", "Selected bank data", BOLD)
    pulled = [
        ("Earning assets", "Earning assets ($M)", USD), ("Asset yield", "Asset yield", PCT), ("Cost of funds", "Cost of funds", PCT),
        ("Asset yield beta (measured)", "Asset yield beta", NUM2), ("Funding cost beta (measured)", "Funding cost beta", NUM2),
        ("CRE loans", "CRE loans ($M)", USD), ("CET1 capital", "CET1 capital ($M)", USD), ("Risk-weighted assets", "Risk-weighted assets ($M)", USD),
        ("Unrealized securities gain/(loss)", "Unrealized securities gain/(loss) ($M)", USD),
        ("Noninterest income, qtr avg", "Noninterest income, qtr avg ($M)", USD1), ("Noninterest expense, qtr avg", "Noninterest expense, qtr avg ($M)", USD1),
        ("Provision, qtr avg", "Provision, qtr avg ($M)", USD1), ("Reported net interest income, Q2 2026", "Net interest income, Q2 2026 ($M)", USD1),
    ]
    ref = {}
    for k, (lab, h, fmt) in enumerate(pulled):
        r = 6 + k
        put(md, f"B{r}", lab)
        put(md, f"C{r}", look(h), GREEN, fmt)
        ref[lab] = f"$C${r}"
    put(md, "B20", "Asset yield beta used")
    put(md, "C20", f"=IF(Inputs!$C$9=\"\",{ref['Asset yield beta (measured)']},Inputs!$C$9)", BLACK, NUM2)
    put(md, "B21", "Funding cost beta used")
    put(md, "C21", f"=IF(Inputs!$C$10=\"\",{ref['Funding cost beta (measured)']},Inputs!$C$10)", BLACK, NUM2)

    hdr = 23
    put(md, f"B{hdr}", "Projection")
    put(md, f"C{hdr}", "Q2 2026")
    for j, q in enumerate(QUARTERS):
        put(md, f"{get_column_letter(4 + j)}{hdr}", q)
    style_header(md, hdr, 2, 11)
    rows = ["Fed funds", "Change vs start", "Asset yield", "Cost of funds", "Earning assets", "Net interest income", "NIM",
            "Noninterest income", "Noninterest expense", "Provision (run-rate)", "CRE stress provision", "Pre-tax income", "Tax",
            "Net income", "Dividends", "CET1 capital", "Risk-weighted assets", "CET1 ratio", "CET1 after securities losses"]
    R = {name: hdr + 1 + i for i, name in enumerate(rows)}
    fmts = {"Fed funds": PCT, "Change vs start": PCT, "Asset yield": PCT, "Cost of funds": PCT, "NIM": PCT, "CET1 ratio": PCT,
            "CET1 after securities losses": PCT}
    for name, r in R.items():
        put(md, f"B{r}", name, BOLD if name in ("Net interest income", "Net income", "CET1 ratio") else BLACK)
    # Start column C
    c0 = {
        "Fed funds": "=Inputs!$C$20", "Change vs start": 0, "Asset yield": f"={ref['Asset yield']}", "Cost of funds": f"={ref['Cost of funds']}",
        "Earning assets": f"={ref['Earning assets']}", "Net interest income": f"=C{R['Earning assets']}*(C{R['Asset yield']}-C{R['Cost of funds']})/4",
        "NIM": f"=C{R['Net interest income']}*4/C{R['Earning assets']}", "CET1 capital": f"={ref['CET1 capital']}",
        "Risk-weighted assets": f"={ref['Risk-weighted assets']}", "CET1 ratio": f"=C{R['CET1 capital']}/C{R['Risk-weighted assets']}",
        "CET1 after securities losses": f"=(C{R['CET1 capital']}+MIN(0,{ref['Unrealized securities gain/(loss)']})*(1-Inputs!$C$13))/C{R['Risk-weighted assets']}",
    }
    for name, f in c0.items():
        put(md, f"C{R[name]}", f, GREEN if "Inputs!" in str(f) else BLACK, fmts.get(name, USD1))
    for j in range(8):
        col = get_column_letter(4 + j)
        prev = get_column_letter(3 + j)
        scen_col = get_column_letter(4 + j)
        f = {
            "Fed funds": f"=INDEX(Inputs!{scen_col}$21:{scen_col}$25,Inputs!$C$6)",
            "Change vs start": f"={col}{R['Fed funds']}-$C${R['Fed funds']}",
            "Asset yield": f"=MAX(0,$C${R['Asset yield']}+$C$20*{col}{R['Change vs start']})",
            "Cost of funds": f"=MAX(Inputs!$C$16,$C${R['Cost of funds']}+$C$21*{col}{R['Change vs start']})",
            "Earning assets": f"={prev}{R['Earning assets']}*(1+Inputs!$C$11)",
            "Net interest income": f"={col}{R['Earning assets']}*({col}{R['Asset yield']}-{col}{R['Cost of funds']})/4",
            "NIM": f"={col}{R['Net interest income']}*4/{col}{R['Earning assets']}",
            "Noninterest income": f"={ref['Noninterest income, qtr avg']}",
            "Noninterest expense": f"={ref['Noninterest expense, qtr avg']}",
            "Provision (run-rate)": f"={ref['Provision, qtr avg']}",
            "CRE stress provision": f"={ref['CRE loans']}*Inputs!$C$15/8",
            "Pre-tax income": f"={col}{R['Net interest income']}+{col}{R['Noninterest income']}-{col}{R['Noninterest expense']}"
                              f"-{col}{R['Provision (run-rate)']}-{col}{R['CRE stress provision']}",
            "Tax": f"=MAX(0,{col}{R['Pre-tax income']}*Inputs!$C$13)",
            "Net income": f"={col}{R['Pre-tax income']}-{col}{R['Tax']}",
            "Dividends": f"=MAX(0,{col}{R['Net income']}*Inputs!$C$14)",
            "CET1 capital": f"={prev}{R['CET1 capital']}+{col}{R['Net income']}-{col}{R['Dividends']}",
            "Risk-weighted assets": f"={prev}{R['Risk-weighted assets']}*(1+Inputs!$C$12)",
            "CET1 ratio": f"={col}{R['CET1 capital']}/{col}{R['Risk-weighted assets']}",
            "CET1 after securities losses": (f"=({col}{R['CET1 capital']}+MIN(0,{ref['Unrealized securities gain/(loss)']})*(1-Inputs!$C$13))"
                                             f"/{col}{R['Risk-weighted assets']}"),
        }
        for name, formula in f.items():
            put(md, f"{col}{R[name]}", formula, GREEN if formula.startswith("=INDEX(Inputs") else BLACK, fmts.get(name, USD1))
    for r in R.values():
        for c in range(2, 12):
            md.cell(row=r, column=c).border = BOX
    s0 = R["CET1 after securities losses"] + 2
    put(md, f"B{s0}", "Summary", BOLD)
    summary = [
        ("Net interest income, next 8 quarters", f"=SUM(D{R['Net interest income']}:K{R['Net interest income']})", USD),
        ("Same at Q2 2026 run-rate (x8)", f"=C{R['Net interest income']}*8", USD),
        ("Change vs run-rate", f"=C{s0 + 1}-C{s0 + 2}", USD),
        ("NIM in Q2 2028", f"=K{R['NIM']}", PCT),
        ("NIM change vs Q2 2026 (pp)", f"=(K{R['NIM']}-C{R['NIM']})*100", NUM2),
        ("Net income, next 8 quarters", f"=SUM(D{R['Net income']}:K{R['Net income']})", USD),
        ("Lowest CET1 ratio in the projection", f"=MIN(D{R['CET1 ratio']}:K{R['CET1 ratio']})", PCT),
        ("CET1 status", f'=IF(C{s0 + 7}<Inputs!$C$17,"BELOW ALERT LEVEL","OK")', "@"),
        ("Rate sensitivity: NIM change per +100bp (pp)", "=(C20-C21)", NUM2),
    ]
    for k, (lab, f, fmt) in enumerate(summary):
        put(md, f"B{s0 + 1 + k}", lab)
        put(md, f"C{s0 + 1 + k}", f, BLACK, fmt, fill=LIGHT)
    status_cell = f"C{s0 + 8}"
    md.conditional_formatting.add(status_cell, CellIsRule(operator="equal", formula=['"BELOW ALERT LEVEL"'],
                                                          fill=PatternFill("solid", fgColor="F4CCCC")))
    summary_rows = {lab: s0 + 1 + k for k, (lab, _, _) in enumerate(summary)}

    # ---------------- Scenarios ----------------
    sc = wb.create_sheet("Scenarios", 3)
    sc.sheet_view.showGridLines = False
    sc.column_dimensions["B"].width = 36
    for col in "CDEFGHIJKLMN":
        sc.column_dimensions[col].width = 12
    put(sc, "B2", '="Scenario comparison: "&Inputs!C4', TITLE)
    put(sc, "B3", "Net interest income by quarter under each Fed funds path, same balance-sheet growth and betas as Model.", SUB)
    put(sc, "B5", "Scenario")
    for j, q in enumerate(QUARTERS):
        put(sc, f"{get_column_letter(3 + j)}5", q)
    put(sc, "K5", "8-qtr total")
    put(sc, "L5", "vs Base")
    put(sc, "M5", "NIM Q2 2028")
    style_header(sc, 5, 2, 13)
    for i in range(len(SCENARIOS)):
        r = 6 + i
        put(sc, f"B{r}", f"=Inputs!B{21 + i}", GREEN)
        for j in range(8):
            col = get_column_letter(3 + j)
            ff = f"Inputs!{get_column_letter(4 + j)}{21 + i}"
            ea = f"Model!{get_column_letter(4 + j)}{R['Earning assets']}"
            f = (f"={ea}*(MAX(0,Model!$C${R['Asset yield']}+Model!$C$20*({ff}-Inputs!$C$20))"
                 f"-MAX(Inputs!$C$16,Model!$C${R['Cost of funds']}+Model!$C$21*({ff}-Inputs!$C$20)))/4")
            put(sc, f"{col}{r}", f, BLACK, USD1)
        put(sc, f"K{r}", f"=SUM(C{r}:J{r})", BLACK, USD)
        put(sc, f"L{r}", f"=K{r}-$K$6", BLACK, USD)
        put(sc, f"M{r}", f"=J{r}*4/Model!K{R['Earning assets']}", BLACK, PCT)
        for c in range(2, 14):
            sc.cell(row=r, column=c).border = BOX
    # NIM path table for the chart
    put(sc, "B13", "NIM path by scenario", BOLD)
    put(sc, "B14", "Quarter")
    for i in range(len(SCENARIOS)):
        put(sc, f"{get_column_letter(3 + i)}14", f"=Inputs!B{21 + i}", GREEN)
    style_header(sc, 14, 2, 2 + len(SCENARIOS))
    for j, q in enumerate(QUARTERS):
        r = 15 + j
        put(sc, f"B{r}", q)
        for i in range(len(SCENARIOS)):
            put(sc, f"{get_column_letter(3 + i)}{r}", f"={get_column_letter(3 + j)}{6 + i}*4/Model!{get_column_letter(4 + j)}{R['Earning assets']}", BLACK, PCT)
    ch = LineChart()
    ch.title = "NIM by rate scenario"
    ch.y_axis.title = "NIM"
    ch.y_axis.number_format = "0.0%"
    ch.height, ch.width = 8, 18
    data_ref = Reference(sc, min_col=3, min_row=14, max_col=2 + len(SCENARIOS), max_row=22)
    ch.add_data(data_ref, titles_from_data=True)
    ch.set_categories(Reference(sc, min_col=2, min_row=15, max_row=22))
    sc.add_chart(ch, "B25")

    # ---------------- Peer_Screen ----------------
    ps = wb.create_sheet("Peer_Screen", 4)
    ps.freeze_panes = "C3"
    put(ps, "A1", "Peer risk screen: thresholds on Inputs rows 29-35; 1 = flag raised", TITLE)
    heads = ["CERT", "Bank", "Assets ($M)", "Uninsured > thr", "CET1 marked < thr", "CRE > thr", "Construction > thr", "Loans/deposits > thr",
             "Liquidity < thr", "NCO > thr", "Flags", "NIM change per +100bp (pp)", "NII change per +100bp ($M/yr)"]
    for j, h in enumerate(heads, start=1):
        ps.cell(row=2, column=j, value=h)
        ps.column_dimensions[get_column_letter(j)].width = 30 if j == 2 else 13
    style_header(ps, 2, 1, len(heads))
    ps.row_dimensions[2].height = 42
    tests = [("Uninsured deposits", ">", 29), ("CET1 after securities losses", "<", 30), ("CRE / capital", ">", 31),
             ("Construction / capital", ">", 32), ("Loans / deposits", ">", 33), ("Liquidity / uninsured", "<", 34), ("Net charge-offs / loans", ">", 35)]
    for i in range(n):
        r = 3 + i
        src = i + 2
        put(ps, f"A{r}", f"=Bank_Data!A{src}", GREEN, "0")
        put(ps, f"B{r}", f"=Bank_Data!B{src}", GREEN)
        put(ps, f"C{r}", f"=Bank_Data!{col_of['Total assets ($M)']}{src}", GREEN, USD)
        for k, (h, op, irow) in enumerate(tests):
            col = get_column_letter(4 + k)
            put(ps, f"{col}{r}", f"=IF(Bank_Data!{col_of[h]}{src}{op}Inputs!$C${irow},1,0)", BLACK, INT)
        put(ps, f"K{r}", f"=SUM(D{r}:J{r})", BLACK, INT)
        put(ps, f"L{r}", f"=Bank_Data!{col_of['Asset yield beta']}{src}-Bank_Data!{col_of['Funding cost beta']}{src}", BLACK, NUM2)
        put(ps, f"M{r}", f"=Bank_Data!{col_of['Earning assets ($M)']}{src}*L{r}/100", BLACK, USD1)
    end = 2 + n
    ps.conditional_formatting.add(f"D3:J{end}", CellIsRule(operator="equal", formula=["1"], fill=PatternFill("solid", fgColor="F4CCCC")))
    ps.conditional_formatting.add(f"K3:K{end}", CellIsRule(operator="greaterThanOrEqual", formula=["2"],
                                                           fill=PatternFill("solid", fgColor="E06666"), font=Font(name=FONT, bold=True, color="FFFFFF")))
    ps.conditional_formatting.add(f"A3:M{end}", FormulaRule(formula=["$B3=Inputs!$C$4"], fill=PatternFill("solid", fgColor="FFF2CC")))
    put(ps, f"B{end + 2}", "Banks flagged", BOLD)
    for k in range(7):
        col = get_column_letter(4 + k)
        put(ps, f"{col}{end + 2}", f"=SUM({col}3:{col}{end})", BLACK, INT)
    put(ps, f"B{end + 3}", "Banks with 2+ flags", BOLD)
    put(ps, f"K{end + 3}", f'=COUNTIF(K3:K{end},">=2")', BLACK, INT)
    put(ps, f"B{end + 4}", "Banks that lose margin when rates rise", BOLD)
    put(ps, f"L{end + 4}", f'=COUNTIF(L3:L{end},"<0")', BLACK, INT)

    # ---------------- Checks ----------------
    ck = wb.create_sheet("Checks", 5)
    ck.sheet_view.showGridLines = False
    ck.column_dimensions["B"].width = 62
    for col in "CDEF":
        ck.column_dimensions[col].width = 16
    put(ck, "B2", "Checks", TITLE)
    for j, h in enumerate(["Check", "Workbook", "Reference", "Difference", "Status"], start=2):
        ck.cell(row=4, column=j, value=h)
    style_header(ck, 4, 2, 6)
    rs = m.risk_screen()
    b = m.betas()
    flag_total = int(rs[[f[0] for f in m.RISK_FLAGS]].values.sum())
    two_plus = int((rs["flag_count"] >= 2).sum())
    neg = int((b["nim_per_100bp"] < 0).sum())
    checks = [
        ("Model start NII vs reported Q2 2026 NII (within 10%)", f"=Model!C{R['Net interest income']}", f"=Model!{ref['Reported net interest income, Q2 2026']}",
         "rel", 0.10),
        ("Banks in Bank_Data", f"=COUNTA(Bank_Data!B2:B{last})", n, "abs", 0),
        ("Total risk flags raised (Peer_Screen vs Python)", f"=SUM(Peer_Screen!D3:J{end})", flag_total, "abs", 0),
        ("Banks with 2+ flags (Peer_Screen vs Python)", f"=Peer_Screen!K{end + 3}", two_plus, "abs", 0),
        ("Banks losing margin when rates rise (vs Python)", f"=Peer_Screen!L{end + 4}", neg, "abs", 0),
        ("Median hiking-cycle deposit beta (vs Python)", f"=MEDIAN(Bank_Data!{col_of['Deposit beta (hikes)']}2:{col_of['Deposit beta (hikes)']}{last})",
         round(float(b["up_beta"].median()), 6), "abs", 0.0005),
        ("Scenario sheet row for the chosen scenario = Model 8-quarter NII", "=INDEX(Scenarios!K6:K10,Inputs!C6)",
         f"=Model!C{summary_rows['Net interest income, next 8 quarters']}", "rel", 0.0001),
        ("CET1 ratio at start = reported ratio (within 0.5pp)", f"=Model!C{R['CET1 ratio']}",
         f'=INDEX({bdcol("CET1 ratio")},MATCH(Inputs!$C$4,{bdcol("Bank")},0))', "abs", 0.005),
    ]
    for k, (lab, wbv, refv, kind, tol) in enumerate(checks):
        r = 5 + k
        put(ck, f"B{r}", lab)
        put(ck, f"C{r}", wbv, GREEN if "!" in str(wbv) else BLACK, NUM2)
        put(ck, f"D{r}", refv, BLUE if not str(refv).startswith("=") else GREEN, NUM2)
        if kind == "rel":
            put(ck, f"E{r}", f"=IFERROR(C{r}/D{r}-1,0)", BLACK, PCT)
        else:
            put(ck, f"E{r}", f"=C{r}-D{r}", BLACK, NUM2)
        put(ck, f"F{r}", f'=IF(ABS(E{r})<={tol},"PASS","REVIEW")', BLACK, "@")
    put(ck, "B14", "Overall", BOLD)
    put(ck, "F14", '=IF(COUNTIF(F5:F12,"PASS")=8,"PASS","REVIEW")', BOLD)
    ck.conditional_formatting.add("F5:F14", CellIsRule(operator="equal", formula=['"PASS"'], fill=PatternFill("solid", fgColor="D9EAD3")))
    ck.conditional_formatting.add("F5:F14", CellIsRule(operator="equal", formula=['"REVIEW"'], fill=PatternFill("solid", fgColor="F4CCCC")))
    put(ck, "B16", "Python reference values (blue) come from src/bankmon/metrics.py on the same FDIC data.", SUB)

    for ws in wb.worksheets:
        ws.sheet_properties.tabColor = NAVY if ws.title in ("Inputs", "Model") else "8EA9C1"
    wb.active = 1
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


if __name__ == "__main__":
    print(build())
