"""Generate the Power BI project (PBIP: TMDL semantic model + PBIR report) for the Regional Bank Monitor.

House format (power-bi-dashboard-format): source -> staging -> Quarterly fact with the business logic in Power Query, a governance
label and Needs Review flag, measures in numbered folders, a DAX vs Python reconciliation with PASS/REVIEW status, nine pages
(Executive Overview, Governance & QA, detail pages, Cohort Analysis, How This Dashboard Works, Model Guide), navy theme,
1280 x 790 canvas with a header banner. Run after scripts/export_powerbi.py:

    python powerbi/build_pbip.py --data-dir "C:/Users/<you>/Downloads/regional_bank_powerbi/data/"

Open RegionalBankMonitor.pbip in Power BI Desktop, refresh, then save as .pbix.
"""
from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "RegionalBankMonitor"
NAME = "RegionalBankMonitor"
TITLE = "Regional Bank Monitor"
VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json"
PG = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
# Palette from the user's reference dashboards: light rounded cards, bright blue / cyan / green / pink / orange accents.
NAVY, BLUE, TEAL, GOLD, RED, GREY = "#2F6BFF", "#22B8E6", "#1FC796", "#FF9F43", "#F2557A", "#A3B1C6"
PURPLE, INK, MUTED, LINE, BG = "#7B61FF", "#24324D", "#7D8BA3", "#E3E9F2", "#EEF2F8"
KPI_COLORS = [NAVY, BLUE, TEAL, PURPLE, GOLD]
W, H, M = 1280, 790, 15
M_ = "_Measures"
LATEST = "DATE(2026, 6, 30)"
TROUGH, PEAK, CRISIS, BASE19 = "DATE(2021, 12, 31)", "DATE(2024, 6, 30)", "DATE(2022, 12, 31)", "DATE(2019, 12, 31)"


def tag(*parts) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "regional-bank-monitor/" + "/".join(map(str, parts))))


def m_csv(file: str, columns: int) -> str:
    return (f'let\n    Source = Csv.Document(File.Contents(DataFolder & "{file}"), [Delimiter = ",", Columns = {columns}, Encoding = 65001, '
            'QuoteStyle = QuoteStyle.Csv]),\n    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),\n'
            '    Blanks = Table.TransformColumns(Promoted, {}, each if _ = "" then null else _)\nin\n    Blanks')


def m_rows(rows: list[tuple], cols: list[str]) -> str:
    def lit_(v):
        if v is None:
            return "null"
        if isinstance(v, (int, float)):
            return str(v)
        return '"' + str(v).replace('"', '""') + '"'
    body = ",\n        ".join("{" + ", ".join(lit_(x) for x in r) + "}" for r in rows)
    return f"let\n    Source = Table.FromRows({{\n        {body}\n    }}, {{{', '.join(chr(34) + c + chr(34) for c in cols)}}})\nin\n    Source"


def tmdl_expr(text: str, indent: int) -> str:
    pad = "\t" * indent
    return "\n".join(pad + line for line in text.split("\n"))


def column(name: str, dtype: str, fmt: str | None = None, hidden: bool = False, sort_by: str | None = None, table: str = "") -> str:
    lines = [f"\tcolumn {quote(name)}", f"\t\tdataType: {dtype}"]
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    if hidden:
        lines.append("\t\tisHidden")
    if sort_by:
        lines.append(f"\t\tsortByColumn: {quote(sort_by)}")
    lines += [f"\t\tlineageTag: {tag(table, 'col', name)}", f"\t\tsummarizeBy: {'none' if dtype in ('string', 'boolean') or name.endswith(('year', 'order')) else 'sum'}",
              f"\t\tsourceColumn: {name}", ""]
    return "\n".join(lines)


def quote(n: str) -> str:
    return n if n.replace("_", "").isalnum() else "'" + n.replace("'", "''") + "'"


def table_tmdl(name: str, cols: list[tuple], m: str, hidden: bool = False, extra: str = "") -> str:
    head = [f"table {quote(name)}", f"\tlineageTag: {tag(name)}"]
    if hidden:
        head.append("\tisHidden")
    body = "\n".join(head) + "\n\n" + extra + "".join(column(*c, table=name) if isinstance(c, tuple) else c for c in cols)
    part = f"\tpartition {quote(name)} = m\n\t\tmode: import\n\t\tsource =\n{tmdl_expr(m, 4)}\n\n\tannotation PBI_ResultType = Table\n"
    return body + part


def measures_tmdl() -> str:
    lines = [f"table {M_}", f"\tlineageTag: {tag(M_)}", ""]
    for name, folder, fmt, expr, hidden in measures():
        lines.append(f"\tmeasure {quote(name)} =")
        lines.append(tmdl_expr(expr, 3))
        if fmt:
            lines.append(f"\t\tformatString: {fmt}")
        if hidden:
            lines.append("\t\tisHidden")
        lines += [f"\t\tdisplayFolder: {folder}", f"\t\tlineageTag: {tag(M_, name)}", ""]
    lines += ["\tcolumn Placeholder", "\t\tdataType: string", "\t\tisHidden", f"\t\tlineageTag: {tag(M_, 'placeholder')}", "\t\tsummarizeBy: none",
              "\t\tsourceColumn: Placeholder", "",
              f"\tpartition {M_} = m", "\t\tmode: import", "\t\tsource =",
              tmdl_expr('let\n    Source = Table.FromRows({}, type table [Placeholder = text])\nin\n    Source', 4), "",
              "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(lines)

def lit(v):
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}}


def legend(pos):
    return [{"properties": {"show": lit(True), "position": lit(pos)}}]


def color(c):
    return {"solid": {"color": lit(c)}}


def meas(name):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": M_}}, "Property": name}}


def col(table, name):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def proj(f, display=None):
    k = "Measure" if "Measure" in f else "Column"
    ent, prop = f[k]["Expression"]["SourceRef"]["Entity"], f[k]["Property"]
    p = {"field": f, "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}
    if display:
        p["displayName"] = display
    return p


class Page:
    def __init__(self, name, display, subtitle, prefix):
        self.name, self.display, self.prefix, self.visuals, self.z = name, display, prefix, [], 0
        self.text(f"{TITLE}  |  {display} - {subtitle}", M, 8, W - 2 * M, 46, size=15, bold=True, fg="#FFFFFF", bg=NAVY, border=False, name="header",
                  radius=14)

    def add(self, vtype, x, y, w, h, roles=None, title=None, objects=None, sort=None, container=None, name=None, filters=None):
        self.z += 1
        v = {"visualType": vtype, "objects": objects or {}, "drillFilterOtherVisuals": True}
        if roles:
            v["query"] = {"queryState": {r: {"projections": ps} for r, ps in roles.items()}}
            if sort:
                f, d = sort
                v["query"]["sortDefinition"] = {"sort": [{"field": f, "direction": d}], "isDefaultSort": True}
        vco = container or {}
        vco.setdefault("subTitle", [{"properties": {"show": lit(False)}}])
        if vtype == "areaChart":  # light shading under each line, as in the reference dashboards
            v["objects"].setdefault("dataPoint", []).append({"properties": {"transparency": lit(85)}})
        if vtype == "tableEx":
            v["objects"].setdefault("total", [{"properties": {"totals": lit(False)}}])
        if vtype == "slicer":
            v["objects"].setdefault("header", [{"properties": {"show": lit(False)}}])
            v["objects"].setdefault("data", [{"properties": {"mode": lit("Dropdown")}}])
        if title is not None:
            vco.setdefault("title", [{"properties": {"show": lit(True), "text": lit(title), "fontColor": color(INK), "fontSize": lit(11), "bold": lit(True)}}])
        if vco:
            v["visualContainerObjects"] = vco
        body = {"$schema": VC, "name": name or f"{self.prefix}_v{self.z:02d}",
                "position": {"x": x, "y": y, "z": self.z * 1000, "height": h, "width": w, "tabOrder": self.z * 1000}, "visual": v}
        if filters:
            body["filterConfig"] = {"filters": filters}
        self.visuals.append(body)

    def text(self, text, x, y, w, h, size=10, bold=False, fg=INK, bg="#FFFFFF", border=True, name=None, radius=14):
        paras = []
        for line in text.split("\n"):
            b = bold or line.startswith("**")
            line = line.replace("**", "")
            paras.append({"textRuns": [{"value": line or " ", "textStyle": {"fontSize": f"{size}pt", "color": fg, **({"fontWeight": "bold"} if b else {})}}]})
        cont = {"background": [{"properties": {"show": lit(True), "color": color(bg), "transparency": lit(0)}}],
                "border": [{"properties": {"show": lit(True), "color": color(LINE if border else bg), "radius": lit(radius)}}],
                "dropShadow": [{"properties": {"show": lit(border)}}]}
        self.add("textbox", x, y, w, h, objects={"general": [{"properties": {"paragraphs": paras}}]}, container=cont, name=name and f"{self.prefix}_{name}")

    def card(self, measure, label, x, y, w, h, fg=NAVY, filled=False):
        cont = {"title": [{"properties": {"show": lit(False)}}]}
        if filled:  # highlighted card: solid accent fill with white text, like the reference dashboards
            cont["background"] = [{"properties": {"show": lit(True), "color": color(fg), "transparency": lit(0)}}]
            cont["border"] = [{"properties": {"show": lit(True), "color": color(fg), "radius": lit(14)}}]
        self.add("card", x, y, w, h, {"Values": [proj(meas(measure), label)]}, container=cont,
                 objects={"labels": [{"properties": {"fontSize": lit(19), "color": color("#FFFFFF" if filled else fg), "bold": lit(True)}}],
                          "categoryLabels": [{"properties": {"show": lit(True), "color": color("#EAF1FF" if filled else MUTED), "fontSize": lit(9)}}]})

    def kpis(self, items, y=64, h=86):
        n = len(items)
        w = (W - 2 * M - (n - 1) * 10) / n
        for i, (m, lab, *fg) in enumerate(items):
            self.card(m, lab, round(M + i * (w + 10)), y, round(w), h, *(fg or [KPI_COLORS[i % len(KPI_COLORS)]]), filled=(i == 0))

    def write(self, root: Path):
        d = root / "pages" / self.name
        (d / "visuals").mkdir(parents=True, exist_ok=True)
        (d / "page.json").write_text(json.dumps({"$schema": PG, "name": self.name, "displayName": self.display, "displayOption": "FitToPage",
                                                 "height": H, "width": W}, indent=2))
        for v in self.visuals:
            vd = d / "visuals" / v["name"]
            vd.mkdir(exist_ok=True)
            (vd / "visual.json").write_text(json.dumps(v, indent=2))


def series_colors(names_colors, metadata_prefix=M_):
    return [{"properties": {"fill": color(c)}, "selector": {"metadata": f"{metadata_prefix}.{n}"}} for n, c in names_colors]


def line_styles(items):
    return [{"properties": {"strokeWidth": lit(w), "lineStyle": lit(s)}, "selector": {"metadata": f"{M_}.{n}"}} for n, w, s in items]


def table_fmt(widths=None, wrap=False):
    o = {"columnHeaders": [{"properties": {"fontColor": color(MUTED), "backColor": color("#F5F8FC"), "bold": lit(True), "wordWrap": lit(True)}}],
         "values": [{"properties": {"fontColor": color(INK), "backColorPrimary": color("#FFFFFF"), "backColorSecondary": color("#FFFFFF"), "wordWrap": lit(wrap)}}],
         "horizontalGrid": [{"properties": {"show": lit(True), "gridHorizontalColor": color(LINE)}}],
         "grid": [{"properties": {"rowPadding": lit(4)}}]}
    if widths:
        o["columnWidth"] = [{"properties": {"value": lit(wv)}, "selector": {"metadata": k}} for k, wv in widths.items()]
    return o



def topn_filter(field_col, measure_name, n):
    return None  # Top-N filters are applied through sort + visual size instead (kept simple for portability)


# ================================================================== semantic model (TMDL)
SOURCE_COLS = ["cert", "quarter_end", "assets", "deposits", "domestic_deposits", "uninsured_deposits", "brokered_deposits", "loans",
               "construction_loans", "multifamily_loans", "nonowner_cre_loans", "tier1_capital", "allowance", "cet1_capital", "rwa",
               "earning_assets", "net_interest_income", "interest_income", "interest_expense", "deposit_interest_expense",
               "noninterest_income", "noninterest_expense", "provision", "net_income", "net_charge_offs", "noncurrent_loans", "cash",
               "afs_fair_value", "afs_amortized_cost", "htm_fair_value", "htm_amortized_cost", "fhlb_advances", "fdic_nim",
               "fdic_asset_yield", "fdic_cost_of_funds", "fdic_roa", "fdic_efficiency", "fdic_cet1_ratio", "fdic_leverage_ratio",
               "opening_assets", "opening_domestic_deposits", "opening_loans"]
NUMERIC = SOURCE_COLS[2:]

STAGING = """let
    Source = Quarterly_Source,
    Typed = Table.TransformColumnTypes(Source, {{"cert", Int64.Type}, {"quarter_end", type date}} & List.Transform(List.Skip(Table.ColumnNames(Source), 2), each {_, type number}), "en-US"),
    Kept = Table.SelectRows(Typed, each [cert] <> null and [quarter_end] <> null and [assets] <> null)
in
    Kept"""

FACT = """let
    Source = Quarterly_Staging,
    Status = Table.SelectColumns(Banks_Staging, {"cert", "failed"}),
    Joined = Table.NestedJoin(Source, {"cert"}, Status, {"cert"}, "b", JoinKind.LeftOuter),
    Expanded = Table.ExpandTableColumn(Joined, "b", {"failed"}),
    Avg = (closing, opening) => if closing = null then null else if opening = null then closing else (closing + opening) / 2,
    Z = (x) => if x = null then 0 else x,
    A1 = Table.AddColumn(Expanded, "avg_domestic_deposits", each Avg([domestic_deposits], [opening_domestic_deposits]), type number),
    A2 = Table.AddColumn(A1, "avg_loans", each Avg([loans], [opening_loans]), type number),
    C1 = Table.AddColumn(A2, "cre_loans", each Z([construction_loans]) + Z([multifamily_loans]) + Z([nonowner_cre_loans]), type number),
    C2 = Table.AddColumn(C1, "capital_base", each Z([tier1_capital]) + Z([allowance]), type number),
    U1 = Table.AddColumn(C2, "unrealized_securities", each (Z([afs_fair_value]) - Z([afs_amortized_cost])) + (Z([htm_fair_value]) - Z([htm_amortized_cost])), type number),
    U2 = Table.AddColumn(U1, "cet1_marked_capital", each [cet1_capital] + List.Min({0, [unrealized_securities]}) * (1 - 0.21), type number),
    L1 = Table.AddColumn(U2, "liquid_assets", each Z([cash]) + Z([afs_fair_value]) + Z([htm_fair_value]), type number),
    R1 = Table.AddColumn(L1, "revenue", each Z([net_interest_income]) + Z([noninterest_income]), type number),
    G1 = Table.AddColumn(R1, "asset_growth_qoq", each if [opening_assets] = null or [opening_assets] = 0 then null else [assets] / [opening_assets] - 1, type number),
    L2 = Table.AddColumn(G1, "governance_label", each
        if [failed] = true then "Case study: failed in 2023 (excluded from peer statistics)"
        else if [asset_growth_qoq] <> null and [asset_growth_qoq] > 0.25 then "Check: merger quarter (assets up more than 25%)"
        else if [fdic_cet1_ratio] = null then "Check: no CET1 ratio (community bank leverage ratio)"
        else "Include", type text),
    L3 = Table.AddColumn(L2, "needs_review", each Text.StartsWith([governance_label], "Check"), type logical),
    Out = Table.RemoveColumns(L3, {"failed"})
in
    Out"""

BANKS_STAGING = """let
    Source = Banks_Source,
    Typed = Table.TransformColumnTypes(Source, {{"cert", Int64.Type}, {"bank", type text}, {"state", type text}, {"holding_company", type text},
        {"failed", type logical}, {"size_band", type text}, {"size_order", Int64.Type}, {"bank_order", Int64.Type}}, "en-US")
in
    Typed"""

BANKS = """let
    Source = Banks_Staging,
    Status = Table.AddColumn(Source, "status", each if [failed] then "Failed in 2023" else "Peer", type text)
in
    Status"""

QUARTERS = """let
    Source = Rates_Source,
    Typed = Table.TransformColumnTypes(Source, {{"quarter_end", type date}, {"fed_funds", type number}, {"ust_2y", type number}, {"ust_10y", type number}}, "en-US"),
    Kept = Table.SelectRows(Typed, each [quarter_end] >= #date(2019, 3, 31) and [quarter_end] <= #date(2026, 6, 30)),
    Label = Table.AddColumn(Kept, "quarter", each "Q" & Text.From(Date.QuarterOfYear([quarter_end])) & " " & Text.From(Date.Year([quarter_end])), type text),
    Year = Table.AddColumn(Label, "year", each Date.Year([quarter_end]), Int64.Type),
    Cycle = Table.AddColumn(Year, "rate_cycle", each if [quarter_end] <= #date(2021, 12, 31) then "1 Low rates (to Q4 2021)"
        else if [quarter_end] <= #date(2024, 6, 30) then "2 Hiking (Q1 2022 - Q2 2024)" else "3 Cutting (from Q3 2024)", type text)
in
    Cycle"""

METRIC_ROWS = [  # label, public measure, peer median measure, lower is better
    ("Net interest margin (%)", "NIM %", True and False),
    ("Cost of deposits (%)", "Cost of Deposits %", True),
    ("Uninsured deposits (%)", "Uninsured Deposits %", True),
    ("Loans / deposits (%)", "Loans / Deposits %", True),
    ("CRE / (Tier 1 + reserves) (%)", "CRE / Capital %", True),
    ("Unrealized securities loss / Tier 1 (%)", "Unrealized Loss / Tier 1 %", False),
    ("CET1 ratio (%)", "CET1 Ratio %", False),
    ("CET1 after securities losses (%)", "CET1 After Securities Losses %", False),
    ("Liquidity / uninsured deposits (%)", "Liquidity / Uninsured %", False),
    ("Return on assets (%)", "ROA %", False),
    ("Efficiency ratio (%)", "Efficiency %", True),
    ("Net charge-offs / loans (%)", "NCO Rate %", True),
]

FLAG_ROWS = [  # label, flag measure, short description
    ("Uninsured deposits > 60%", "Flag Uninsured > 60%"),
    ("CET1 after securities losses < 8%", "Flag Marked CET1 < 8%"),
    ("CRE > 300% of capital", "Flag CRE > 300%"),
    ("Construction > 100% of capital", "Flag Construction > 100%"),
    ("Loans > deposits", "Flag Loans > Deposits"),
    ("Liquidity < 50% of uninsured deposits", "Flag Liquidity < 50%"),
    ("Net charge-offs > 0.5%", "Flag NCO > 0.5%"),
]

PEERS = "KEEPFILTERS(Banks[failed] = FALSE())"


def wavg(col: str, weight: str) -> str:
    return (f"DIVIDE(SUMX(FILTER(Quarterly, NOT ISBLANK(Quarterly[{col}])), Quarterly[{col}] * Quarterly[{weight}]), "
            f"SUMX(FILTER(Quarterly, NOT ISBLANK(Quarterly[{col}])), Quarterly[{weight}]))")


RAW = {  # unscoped base measures (hidden): ratios of sums, so any filter context aggregates correctly
    "_NIM": wavg("fdic_nim", "earning_assets"),
    "_Asset Yield": wavg("fdic_asset_yield", "earning_assets"),
    "_Cost of Funds": wavg("fdic_cost_of_funds", "earning_assets"),
    "_Deposit Cost": "DIVIDE(SUM(Quarterly[deposit_interest_expense]) * 4, SUM(Quarterly[avg_domestic_deposits])) * 100",
    "_Uninsured Share": "DIVIDE(SUM(Quarterly[uninsured_deposits]), SUM(Quarterly[domestic_deposits])) * 100",
    "_Loan to Deposit": "DIVIDE(SUM(Quarterly[loans]), SUM(Quarterly[deposits])) * 100",
    "_Brokered Share": "DIVIDE(SUM(Quarterly[brokered_deposits]), SUM(Quarterly[deposits])) * 100",
    "_CRE Concentration": "DIVIDE(SUM(Quarterly[cre_loans]), SUM(Quarterly[capital_base])) * 100",
    "_Construction Concentration": "DIVIDE(SUM(Quarterly[construction_loans]), SUM(Quarterly[capital_base])) * 100",
    "_Unrealized to Tier1": "DIVIDE(SUM(Quarterly[unrealized_securities]), SUM(Quarterly[tier1_capital])) * 100",
    "_Liquidity Coverage": "DIVIDE(SUM(Quarterly[liquid_assets]), SUM(Quarterly[uninsured_deposits])) * 100",
    "_CET1 Ratio": wavg("fdic_cet1_ratio", "rwa"),
    "_CET1 Marked": "DIVIDE(SUM(Quarterly[cet1_marked_capital]), SUM(Quarterly[rwa])) * 100",
    "_NCO Rate": "DIVIDE(SUM(Quarterly[net_charge_offs]) * 4, SUM(Quarterly[avg_loans])) * 100",
    "_Noncurrent Rate": "DIVIDE(SUM(Quarterly[noncurrent_loans]), SUM(Quarterly[loans])) * 100",
    "_ROA": wavg("fdic_roa", "assets"),
    "_Efficiency": wavg("fdic_efficiency", "revenue"),
    "_Deposits $B": "DIVIDE(SUM(Quarterly[deposits]), 1000)",
    "_Assets $B": "DIVIDE(SUM(Quarterly[assets]), 1000)",
    "_Fed Funds": "AVERAGE(Quarters[fed_funds])",
}
PUBLIC = [  # name, raw, folder
    ("NIM %", "_NIM", "02 Earnings"), ("Asset Yield %", "_Asset Yield", "02 Earnings"), ("Cost of Funds %", "_Cost of Funds", "02 Earnings"),
    ("ROA %", "_ROA", "02 Earnings"), ("Efficiency %", "_Efficiency", "02 Earnings"),
    ("Cost of Deposits %", "_Deposit Cost", "03 Funding & Liquidity"), ("Uninsured Deposits %", "_Uninsured Share", "03 Funding & Liquidity"),
    ("Loans / Deposits %", "_Loan to Deposit", "03 Funding & Liquidity"), ("Brokered Deposits %", "_Brokered Share", "03 Funding & Liquidity"),
    ("Liquidity / Uninsured %", "_Liquidity Coverage", "03 Funding & Liquidity"),
    ("CET1 Ratio %", "_CET1 Ratio", "04 Capital & Credit"), ("CET1 After Securities Losses %", "_CET1 Marked", "04 Capital & Credit"),
    ("Unrealized Loss / Tier 1 %", "_Unrealized to Tier1", "04 Capital & Credit"), ("CRE / Capital %", "_CRE Concentration", "04 Capital & Credit"),
    ("Construction / Capital %", "_Construction Concentration", "04 Capital & Credit"), ("NCO Rate %", "_NCO Rate", "04 Capital & Credit"),
    ("Noncurrent Loans %", "_Noncurrent Rate", "04 Capital & Credit"),
]
MEDIAN_OF = {"NIM %": "_NIM", "Cost of Deposits %": "_Deposit Cost", "Uninsured Deposits %": "_Uninsured Share", "Loans / Deposits %": "_Loan to Deposit",
             "CRE / Capital %": "_CRE Concentration", "Unrealized Loss / Tier 1 %": "_Unrealized to Tier1", "Liquidity / Uninsured %": "_Liquidity Coverage",
             "CET1 Ratio %": "_CET1 Ratio", "CET1 After Securities Losses %": "_CET1 Marked", "NCO Rate %": "_NCO Rate", "ROA %": "_ROA",
             "Efficiency %": "_Efficiency", "Noncurrent Loans %": "_Noncurrent Rate"}

RECON = {
    "banks": f"CALCULATE([Banks], Quarters[quarter_end] = {LATEST})",
    "assets_t": f"CALCULATE([Total Assets $B], Quarters[quarter_end] = {LATEST}) / 1000",
    "nim_median": f"CALCULATE([Median NIM %], Quarters[quarter_end] = {LATEST})",
    "depcost_median": f"CALCULATE([Median Cost of Deposits %], Quarters[quarter_end] = {LATEST})",
    "uninsured_median": f"CALCULATE([Median Uninsured Deposits %], Quarters[quarter_end] = {LATEST})",
    "cet1_median": f"CALCULATE([Median CET1 Ratio %], Quarters[quarter_end] = {LATEST})",
    "beta_up": "[Median Deposit Beta (Hikes)]",
    "beta_down": "[Median Deposit Beta (Cuts)]",
    "nim100_median": "[Median NIM Change per +100bp]",
    "liab_sensitive": "[Banks Losing Margin as Rates Rise]",
    "flags_total": f"CALCULATE([Total Risk Flags], Quarters[quarter_end] = {LATEST})",
    "flags_two_plus": f"CALCULATE([Banks With 2+ Flags], Quarters[quarter_end] = {LATEST})",
    "flags_zero": f"CALCULATE([Banks With No Flags], Quarters[quarter_end] = {LATEST})",
    "cre_over_300": f"CALCULATE([Banks CRE Over 300%], Quarters[quarter_end] = {LATEST})",
    "svb_uninsured": f"CALCULATE([_Uninsured Share], Banks[cert] = 24735, Quarters[quarter_end] = {CRISIS})",
    "frc_marked": f"CALCULATE([_CET1 Marked], Banks[cert] = 59017, Quarters[quarter_end] = {CRISIS})",
    "ew_failed": "[Failed Banks Raising All 3]",
    "ew_survivors": "[Survivors Raising All 3]",
    "flagstar_nim100": "CALCULATE([NIM Change per +100bp], Banks[cert] = 32541)",
    "mt_depcost_peak": f"CALCULATE([_Deposit Cost], Banks[cert] = 588, Quarters[quarter_end] = {PEAK})",
}


def scoped(x: str) -> str:
    return f"VAR q = [Selected Quarter]\nRETURN CALCULATE({x}, REMOVEFILTERS(Quarters), Quarters[quarter_end] = q)"


def at(x: str, date: str) -> str:
    return f"CALCULATE({x}, REMOVEFILTERS(Quarters), Quarters[quarter_end] = {date})"


def per_bank_median(raw: str) -> str:
    return f"MEDIANX(FILTER(VALUES(Banks[cert]), NOT ISBLANK({raw})), {raw})"


def peer_count(cond: str) -> str:
    return f"COUNTROWS(FILTER(CALCULATETABLE(VALUES(Banks[cert]), {PEERS}), {cond})) + 0"


def measures() -> list[tuple[str, str, str, str, bool]]:
    out = [(k, "00 Base (unscoped)", "0.00", v, True) for k, v in RAW.items()]
    out.append(("Selected Quarter", "01 Core", "yyyy-mm-dd",
                "IF(HASONEVALUE(Quarters[quarter_end]), VALUES(Quarters[quarter_end]), CALCULATE(MAX(Quarterly[quarter_end]), REMOVEFILTERS()))", False))
    out.append(("Selected Quarter Label", "01 Core", "", 'VAR q = [Selected Quarter]\nRETURN "Q" & QUARTER(q) & " " & YEAR(q)', False))
    out.append(("Banks", "01 Core", "0", scoped(f"CALCULATE(DISTINCTCOUNT(Quarterly[cert]), {PEERS})"), False))
    out.append(("Total Assets $B", "01 Core", "#,0", scoped(f"CALCULATE([_Assets $B], {PEERS})"), False))
    out.append(("Assets by Quarter $B", "01 Core", "#,0", f"CALCULATE([_Assets $B], {PEERS})", False))
    out.append(("Deposits by Quarter $B", "01 Core", "#,0.0", "[_Deposits $B]", False))
    out.append(("Fed Funds %", "01 Core", "0.00", scoped("[_Fed Funds]"), False))
    out.append(("Fed Funds by Quarter %", "01 Core", "0.00", "[_Fed Funds]", False))
    for name, raw, folder in PUBLIC:
        out.append((name, folder, "0.00", scoped(f"[{raw}]"), False))
    for name, raw in MEDIAN_OF.items():
        med = per_bank_median(f"[{raw}]")
        out.append((f"Median {name}", "07 Peer Medians", "0.00", scoped(f"CALCULATE({med}, {PEERS})"), False))
        out.append((f"Peer Median {name}", "07 Peer Medians", "0.00", scoped(f"CALCULATE({med}, REMOVEFILTERS(Banks), Banks[failed] = FALSE())"), False))
        out.append((f"Median {name} by Quarter", "12 Chart Helpers", "0.00", f"CALCULATE({med}, {PEERS})", False))
        out.append((f"Peer Median {name} by Quarter", "12 Chart Helpers", "0.00", f"CALCULATE({med}, REMOVEFILTERS(Banks), Banks[failed] = FALSE())", False))
        out.append((f"Bank {name} by Quarter", "12 Chart Helpers", "0.00", f"IF(HASONEVALUE(Banks[cert]), [{raw}])", False))

    # 05 rate sensitivity: betas from each bank's own history
    def beta(raw: str, d0: str, d1: str) -> str:
        return (f"VAR c0 = {at(raw, d0)}\nVAR c1 = {at(raw, d1)}\nVAR f0 = {at('[_Fed Funds]', d0)}\nVAR f1 = {at('[_Fed Funds]', d1)}\n"
                "RETURN IF(HASONEVALUE(Banks[cert]) && NOT ISBLANK(c0) && NOT ISBLANK(c1), DIVIDE(c1 - c0, f1 - f0))")
    rs = "05 Rate Sensitivity"
    out.append(("Deposit Beta (Hikes)", rs, "0.00", beta("[_Deposit Cost]", TROUGH, PEAK), False))
    out.append(("Deposit Beta (Cuts)", rs, "0.00", beta("[_Deposit Cost]", PEAK, LATEST), False))
    out.append(("Asset Yield Beta", rs, "0.00", beta("[_Asset Yield]", TROUGH, PEAK), False))
    out.append(("Funding Cost Beta", rs, "0.00", beta("[_Cost of Funds]", TROUGH, PEAK), False))
    out.append(("NIM Change per +100bp", rs, "+0.00;-0.00;0.00", "[Asset Yield Beta] - [Funding Cost Beta]", False))
    out.append(("NII Change per +100bp $M", rs, "+#,0;-#,0;0",
                f"VAR s = [NIM Change per +100bp]\nRETURN IF(NOT ISBLANK(s), s / 100 * {at('SUM(Quarterly[earning_assets])', LATEST)})", False))
    out.append(("Loans / Deposits at Q4 2021 %", rs, "0.0", f"IF(HASONEVALUE(Banks[cert]), {at('[_Loan to Deposit]', TROUGH)})", False))
    for nm, src in [("Median Deposit Beta (Hikes)", "Deposit Beta (Hikes)"), ("Median Deposit Beta (Cuts)", "Deposit Beta (Cuts)"),
                    ("Median NIM Change per +100bp", "NIM Change per +100bp")]:
        out.append((nm, rs, "0.00", f"CALCULATE({per_bank_median('[' + src + ']')}, {PEERS})", False))
    out.append(("Banks Losing Margin as Rates Rise", rs, "0", peer_count("[NIM Change per +100bp] < 0"), False))

    # 06 risk screen (one bank, selected quarter)
    flag_expr = {
        "Flag Uninsured > 60%": "[Uninsured Deposits %] > 60", "Flag Marked CET1 < 8%": "[CET1 After Securities Losses %] < 8",
        "Flag CRE > 300%": "[CRE / Capital %] > 300", "Flag Construction > 100%": "[Construction / Capital %] > 100",
        "Flag Loans > Deposits": "[Loans / Deposits %] > 100", "Flag Liquidity < 50%": "[Liquidity / Uninsured %] < 50",
        "Flag NCO > 0.5%": "[NCO Rate %] > 0.5"}
    for k, cond in flag_expr.items():
        val = cond.rsplit(" ", 2)[0]
        out.append((k, "06 Risk Screen", "0", f"IF(HASONEVALUE(Banks[cert]) && NOT ISBLANK({val}), IF({cond}, 1, 0))", False))
    out.append(("Risk Flags", "06 Risk Screen", "0", "IF(HASONEVALUE(Banks[cert]) && NOT ISBLANK([NIM %]), " + " + ".join(f"[{k}]" for k in flag_expr) + ")", False))
    out.append(("Total Risk Flags", "06 Risk Screen", "0", f"SUMX(CALCULATETABLE(VALUES(Banks[cert]), {PEERS}), [Risk Flags]) + 0", False))
    out.append(("Banks With 2+ Flags", "06 Risk Screen", "0", peer_count("[Risk Flags] >= 2"), False))
    out.append(("Banks With No Flags", "06 Risk Screen", "0", peer_count("[Risk Flags] = 0"), False))
    out.append(("Banks Raising Flag", "06 Risk Screen", "0", "SWITCH(SELECTEDVALUE(Flags[flag]),\n" + ",\n".join(
        f'    "{lab}", {peer_count(f"[{ms}] = 1")}' for lab, ms in FLAG_ROWS) + ")", False))
    out.append(("Banks CRE Over 300%", "06 Risk Screen", "0", peer_count("[CRE / Capital %] > 300"), False))
    out.append(("Banks CRE Over 300% by Quarter", "12 Chart Helpers", "0", peer_count("[_CRE Concentration] > 300"), False))

    # 08 lessons from 2023: everything measured at Q4 2022, failed banks included
    ls = "08 Lessons from 2023"
    out.append(("Uninsured at Q4 2022 %", ls, "0.0", f"IF(HASONEVALUE(Banks[cert]), {at('[_Uninsured Share]', CRISIS)})", False))
    out.append(("Marked CET1 at Q4 2022 %", ls, "0.0", f"IF(HASONEVALUE(Banks[cert]), {at('[_CET1 Marked]', CRISIS)})", False))
    out.append(("Unrealized Loss / Tier 1 at Q4 2022 %", ls, "0.0", f"IF(HASONEVALUE(Banks[cert]), {at('[_Unrealized to Tier1]', CRISIS)})", False))
    out.append(("Deposit Growth 2019-22 %", ls, "0.0",
                f"VAR d0 = {at('SUM(Quarterly[deposits])', BASE19)}\nVAR d1 = {at('SUM(Quarterly[deposits])', CRISIS)}\n"
                "RETURN IF(HASONEVALUE(Banks[cert]) && d0 > 0, (d1 / d0 - 1) * 100)", False))
    out.append(("Early-Warning Flags", ls, "0",
                "VAR u = [Uninsured at Q4 2022 %]\nVAR c = [Marked CET1 at Q4 2022 %]\nVAR g = [Deposit Growth 2019-22 %]\n"
                "RETURN IF(NOT ISBLANK(u), IF(u > 60, 1, 0) + IF(c < 8, 1, 0) + IF(g > 90, 1, 0))", False))
    for nm, flag in [("Failed Banks Raising All 3", "TRUE()"), ("Survivors Raising All 3", "FALSE()")]:
        out.append((nm, ls, "0", f"COUNTROWS(FILTER(CALCULATETABLE(VALUES(Banks[cert]), REMOVEFILTERS(Banks), Banks[failed] = {flag}), "
                                 "[Early-Warning Flags] = 3)) + 0", False))
    out.append(("Survivors Raising 2 Flags", ls, "0", "COUNTROWS(FILTER(CALCULATETABLE(VALUES(Banks[cert]), REMOVEFILTERS(Banks), Banks[failed] = FALSE()), "
                                                     "[Early-Warning Flags] = 2)) + 0", False))
    for nm, src in [("Survivor Median Uninsured at Q4 2022 %", "Uninsured at Q4 2022 %"), ("Survivor Median Marked CET1 at Q4 2022 %", "Marked CET1 at Q4 2022 %"),
                    ("Survivor Median Deposit Growth 2019-22 %", "Deposit Growth 2019-22 %")]:
        out.append((nm, ls, "0.0", f"CALCULATE({per_bank_median('[' + src + ']')}, REMOVEFILTERS(Banks), Banks[failed] = FALSE())", False))

    # 10 scorecard helpers
    def sw(prefix: str) -> str:
        return "SWITCH(SELECTEDVALUE(Metrics[metric]),\n" + ",\n".join(f'    "{lab}", [{prefix}{ms}]' for lab, ms, _ in METRIC_ROWS) + ")"
    out.append(("Metric Value", "10 Scorecard", "0.00", sw(""), False))
    out.append(("Metric Peer Median", "10 Scorecard", "0.00", sw("Peer Median "), False))
    out.append(("Metric Rank", "10 Scorecard", "0",
                "VAR v = [Metric Value]\nVAR lower = SELECTEDVALUE(Metrics[lower_is_better])\n"
                "RETURN IF(NOT ISBLANK(v), CALCULATE(IF(lower, COUNTROWS(FILTER(VALUES(Banks[cert]), [Metric Value] < v)),\n"
                "    COUNTROWS(FILTER(VALUES(Banks[cert]), [Metric Value] > v))), REMOVEFILTERS(Banks), Banks[failed] = FALSE()) + 1)", False))

    # 11 governance & reconciliation
    g = "11 Governance & QA"
    out.append(("Rows Included", g, "0", 'CALCULATE(COUNTROWS(Quarterly), KEEPFILTERS(Quarterly[governance_label] = "Include"))', False))
    out.append(("Rows Needing Review", g, "0", "CALCULATE(COUNTROWS(Quarterly), KEEPFILTERS(Quarterly[needs_review] = TRUE())) + 0", False))
    out.append(("Fact Rows", g, "#,0", "COUNTROWS(Quarterly)", False))
    out.append(("Python Value", g, "0.000", "SUM(Reconciliation[python_value])", False))
    out.append(("DAX Value", g, "0.000", "SWITCH(SELECTEDVALUE(Reconciliation[check_id]),\n" + ",\n".join(f'    "{k}", {v}' for k, v in RECON.items()) + ")", False))
    out.append(("Difference", g, "0.000", "IF(HASONEVALUE(Reconciliation[check_id]), [DAX Value] - [Python Value])", False))
    out.append(("Check Status", g, "", 'IF(HASONEVALUE(Reconciliation[check_id]), IF(ABS([Difference]) <= 0.01, "PASS", "REVIEW"))', False))
    out.append(("Checks Passed", g, "0", "SUMX(VALUES(Reconciliation[check_id]), IF(ABS([DAX Value] - [Python Value]) <= 0.01, 1, 0))", False))
    out.append(("Reconciliation Status", g, "",
                'IF([Checks Passed] = COUNTROWS(Reconciliation), "PASS (" & [Checks Passed] & " of " & COUNTROWS(Reconciliation) & ")", "REVIEW")', False))
    out.append(("Finding Value", g, "0.00", "SUM(Findings[value])", False))
    out.append(("Finding p-value", g, "0.000", "SUM(Findings[p_value])", False))
    return out


GUIDE_COLS = ["Object", "Object Type", "Group", "What it does", "Why it was created", "What it helps find out", "Question Type", "Question it answers"]
GUIDE = [
    ("Quarterly", "Table", "Fact", "One row per bank and quarter: call-report lines in $M, average balances, CRE loans, unrealized securities, marked CET1, governance label",
     "Holds the business logic so every measure is a ratio of sums", "Funding, capital, credit and earnings for any bank-quarter", "WHAT",
     "What did each bank hold and earn each quarter?"),
    ("Banks", "Table", "Dimension", "101 peer banks plus SVB, Signature and First Republic, with state, size band and status",
     "Slices every page by bank and size; keeps failed banks out of peer statistics", "Who is in the peer group", "WHAT", "Which banks are compared?"),
    ("Quarters", "Table", "Dimension", "Q1 2019 to Q2 2026 with quarter-average Fed funds, 2- and 10-year Treasury yields and the rate cycle",
     "One quarter axis and the rate path for betas", "How metrics move with rates", "WHAT", "What was the Fed funds rate each quarter?"),
    ("Metrics / Flags", "Table", "Helper", "Lists of scorecard metrics (with lower-is-better) and risk flags", "Drive the scorecard table and the flag chart",
     "A bank against peer medians; how many banks raise each flag", "HOW", "How does a bank rank on each metric?"),
    ("Findings", "Table", "Python results", "Deposit-beta drivers, beta by funding need, early-warning robustness, CRE credit",
     "Statistics Power BI should show but not recompute", "Why betas differ; how robust the 2023 screen is", "WHY", "What drove deposit costs?"),
    ("Reconciliation", "Table", "QA", "20 headline figures with the Python value", "Proves the DAX model matches the governed Python metrics",
     "Any drift between report and analysis", "HOW", "Do the dashboard numbers match the analysis?"),
    ("Cost of Deposits %", "Measure", "03 Funding & Liquidity", "4 x quarterly deposit interest expense / average domestic deposits",
     "The price a bank pays for its funding", "Who paid up for deposits", "WHAT", "What does each bank pay depositors?"),
    ("Deposit Beta (Hikes)", "Measure", "05 Rate Sensitivity", "Change in cost of deposits Q4 2021 to Q2 2024 / change in Fed funds (0.08% to 5.33%)",
     "Measures how much of the Fed's hikes a bank passed to depositors", "Funding pressure by bank", "WHY", "Which banks had to pay up for deposits?"),
    ("NIM Change per +100bp", "Measure", "05 Rate Sensitivity", "Asset yield beta minus funding cost beta over the hiking cycle",
     "A first-order rate sensitivity from the bank's own history", "Who gains or loses margin if rates rise", "HOW", "Which banks lose margin as rates rise?"),
    ("CET1 After Securities Losses %", "Measure", "04 Capital & Credit", "(CET1 + unrealized securities losses after 21% tax) / RWA",
     "Capital if every bond loss were taken, the SVB question", "Hidden capital holes", "WHY", "How much capital is left if bond losses are realised?"),
    ("CRE / Capital %", "Measure", "04 Capital & Credit", "(Construction + multifamily + non-owner-occupied CRE) / (Tier 1 + reserves)",
     "The interagency 300% concentration test", "CRE concentration", "WHAT", "Which banks are above the CRE guidance?"),
    ("Risk Flags", "Measure", "06 Risk Screen", "Count of seven flags for one bank in the selected quarter",
     "A simple, explainable early-warning screen", "Banks to watch", "WHY", "Which banks look most exposed today?"),
    ("Early-Warning Flags", "Measure", "08 Lessons from 2023", "Uninsured > 60%, marked CET1 < 8%, deposit growth 2019-22 > 90%, at Q4 2022",
     "Tests whether the 2023 failures were visible in public data", "What set SVB, Signature and First Republic apart", "WHY",
     "Could the 2023 failures have been spotted?"),
    ("Selected Quarter", "Measure", "01 Core", "The quarter in the slicer, or Q2 2026 when none is selected",
     "Every ratio card shows one quarter, never a sum across quarters", "Consistent quarter scoping", "HOW", "Which quarter is the page showing?"),
    ("Reconciliation Status", "Measure", "11 Governance & QA", "PASS when all 20 DAX values are within 0.01 of Python", "Control check",
     "Report and analysis agree", "HOW", "Can I trust these numbers?"),
]


def model_guide_m() -> str:
    return m_rows(GUIDE, GUIDE_COLS)


def write_model(root: Path, data_dir: str) -> None:
    sm = root / f"{NAME}.SemanticModel"
    (sm / "definition" / "tables").mkdir(parents=True, exist_ok=True)
    (sm / "definition.pbism").write_text(json.dumps({"$schema": SCHEMA + "item/semanticModel/definitionProperties/1.0.0/schema.json", "version": "4.2",
                                                     "settings": {}}, indent=2))
    (sm / ".platform").write_text(platform("SemanticModel"))
    (sm / "definition" / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1606\n\n")
    tables = ["Quarterly", "Banks", "Quarters", "Metrics", "Flags", "Findings", "Reconciliation", "Model Guide", M_]
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3", "\tsourceQueryCulture: en-US", "\tvalueFilterBehavior: independent",
             "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
             "annotation PBI_QueryOrder = " + json.dumps(["DataFolder", "Quarterly_Source", "Quarterly_Staging", "Banks_Source", "Banks_Staging", "Rates_Source",
                                                          *tables]), "", "annotation __PBI_TimeIntelligenceEnabled = 0", ""]
    for i, grp in enumerate(["1 Parameters", "2 Source (raw)", "3 Staging"]):
        model += [f"queryGroup '{grp}'", "", f"\tannotation PBI_QueryGroupOrder = {i}", ""]
    model += [f"ref table {quote(t)}" for t in tables]
    (sm / "definition" / "model.tmdl").write_text("\n".join(model) + "\n")

    def shared(name, m, group):
        return f"expression {name} =\n{tmdl_expr(m, 2)}\n\tlineageTag: {tag('expr', name)}\n\tqueryGroup: '{group}'\n\n\tannotation PBI_ResultType = Table\n\n"
    ex = (f'expression DataFolder = "{data_dir}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
          f"\tlineageTag: {tag('expr', 'DataFolder')}\n\tqueryGroup: '1 Parameters'\n\n\tannotation PBI_ResultType = Text\n\n")
    ex += shared("Quarterly_Source", m_csv("quarterly.csv", len(SOURCE_COLS)), "2 Source (raw)")
    ex += shared("Banks_Source", m_csv("banks.csv", 8), "2 Source (raw)")
    ex += shared("Rates_Source", m_csv("rates.csv", 4), "2 Source (raw)")
    ex += shared("Quarterly_Staging", STAGING, "3 Staging")
    ex += shared("Banks_Staging", BANKS_STAGING, "3 Staging")
    (sm / "definition" / "expressions.tmdl").write_text(ex)

    q_cols = [("cert", "int64", "0"), ("quarter_end", "dateTime", "yyyy-mm-dd")] + [(c, "double", "#,0.0", c.startswith("opening_")) for c in NUMERIC]
    q_cols += [(c, "double", "#,0.0") for c in ["avg_domestic_deposits", "avg_loans", "cre_loans", "capital_base", "unrealized_securities",
                                                "cet1_marked_capital", "liquid_assets", "revenue"]]
    q_cols += [("asset_growth_qoq", "double", "0.000"), ("governance_label", "string"), ("needs_review", "boolean")]
    metric_m = m_rows([(lab, i + 1, "true" if low else "false") for i, (lab, _, low) in enumerate(METRIC_ROWS)], ["metric", "metric_order", "lower_is_better"])
    metric_m = (metric_m.replace('"true"', "true").replace('"false"', "false")
                .replace("\nin\n", ',\n    Typed = Table.TransformColumnTypes(Source, {{"metric_order", Int64.Type}, {"lower_is_better", type logical}})\nin\n')
                .replace("in\n    Source", "in\n    Typed"))
    flags_m = m_rows([(lab, i + 1) for i, (lab, _) in enumerate(FLAG_ROWS)], ["flag", "flag_order"]).replace(
        "\nin\n", ',\n    Typed = Table.TransformColumnTypes(Source, {{"flag_order", Int64.Type}})\nin\n').replace("in\n    Source", "in\n    Typed")
    typed = lambda cols: ",\n    Typed = Table.TransformColumnTypes(Blanks, {" + ", ".join(cols) + "}, \"en-US\")\nin\n    Typed"  # noqa: E731
    tabs = {
        "Quarterly": table_tmdl("Quarterly", q_cols, FACT),
        "Banks": table_tmdl("Banks", [("cert", "int64", "0"), ("bank", "string", None, False, "bank_order"), ("state", "string"), ("holding_company", "string"),
                                      ("failed", "boolean"), ("size_band", "string", None, False, "size_order"), ("size_order", "int64", "0", True),
                                      ("bank_order", "int64", "0", True), ("status", "string")], BANKS),
        "Quarters": table_tmdl("Quarters", [("quarter_end", "dateTime", "yyyy-mm-dd"), ("fed_funds", "double", "0.00"), ("ust_2y", "double", "0.00"),
                                            ("ust_10y", "double", "0.00"), ("quarter", "string", None, False, "quarter_end"), ("year", "int64", "0"),
                                            ("rate_cycle", "string")], QUARTERS),
        "Metrics": table_tmdl("Metrics", [("metric", "string", None, False, "metric_order"), ("metric_order", "int64", "0", True), ("lower_is_better", "boolean")],
                              metric_m),
        "Flags": table_tmdl("Flags", [("flag", "string", None, False, "flag_order"), ("flag_order", "int64", "0", True)], flags_m),
        "Findings": table_tmdl("Findings", [("group", "string"), ("finding", "string", None, False, "order"), ("value", "double", "0.00"),
                                            ("p_value", "double", "0.000"), ("note", "string"), ("order", "int64", "0", True)],
                               m_csv("findings.csv", 6).replace("\nin\n    Blanks", typed(['{"value", type number}', '{"p_value", type number}', '{"order", Int64.Type}']))),
        "Reconciliation": table_tmdl("Reconciliation", [("order", "int64", "0", True), ("check_id", "string", None, True), ("check", "string", None, False, "order"),
                                                        ("python_value", "double", "0.000")],
                                     m_csv("reconciliation.csv", 4).replace("\nin\n    Blanks", typed(['{"order", Int64.Type}', '{"python_value", type number}']))),
        "Model Guide": table_tmdl("Model Guide", [(c, "string") for c in GUIDE_COLS], model_guide_m()),
    }
    for name, body in tabs.items():
        (sm / "definition" / "tables" / f"{name}.tmdl").write_text(body)
    (sm / "definition" / "tables" / f"{M_}.tmdl").write_text(measures_tmdl())
    rel = [("Quarterly", "cert", "Banks", "cert"), ("Quarterly", "quarter_end", "Quarters", "quarter_end")]
    (sm / "definition" / "relationships.tmdl").write_text("".join(
        f"relationship {tag('rel', a, b)}\n\tfromColumn: {a}.{b}\n\ttoColumn: {c}.{d}\n\n" for a, b, c, d in rel))


# ================================================================== report (PBIR)
def text_filter(table: str, column: str, value: str, name: str) -> dict:
    return {"name": name, "field": col(table, column), "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": "t", "Entity": table, "Type": 0}],
                       "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": column}}],
                                                       "Values": [[{"Literal": {"Value": "'" + value + "'"}}]]}}}]}}


def default_slicer(table: str, column: str, value: str) -> dict:
    return {"data": [{"properties": {"mode": lit("Dropdown")}}], "selection": [{"properties": {"singleSelect": lit(True)}}],
            "general": [{"properties": {"filter": {"filter": {
                "Version": 2, "From": [{"Name": "c", "Entity": table, "Type": 0}],
                "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": column}}],
                                                "Values": [[{"Literal": {"Value": "'" + value + "'"}}]]}}}]}}}}]}


def build() -> list[Page]:
    pages = []
    bk = lambda c: col("Banks", c)  # noqa: E731
    qt = lambda c: col("Quarters", c)  # noqa: E731
    peers_only = [text_filter("Banks", "status", "Peer", "peers_only")]
    dd = {"data": [{"properties": {"mode": lit("Dropdown")}}]}

    # 1 Executive Overview -----------------------------------------------------------------------------------------------
    p = Page("p1_overview", "Executive Overview", "Q2 2026 (slicer changes the quarter)", "ov")
    p.kpis([("Banks", "Regional banks ($10-250B)"), ("Median NIM %", "Median net interest margin (%)"),
            ("Median Cost of Deposits %", "Median cost of deposits (%)"), ("Median Deposit Beta (Hikes)", "Median deposit beta, 2022-24 hikes"),
            ("Banks With 2+ Flags", "Banks with 2+ risk flags", RED)])
    p.add("areaChart", M, 162, 760, 330, {"Category": [proj(qt("quarter"), "Quarter")],
                                          "Y": [proj(meas("Median NIM % by Quarter"), "Median NIM"), proj(meas("Median Cost of Deposits % by Quarter"), "Median cost of deposits"),
                                                proj(meas("Fed Funds by Quarter %"), "Fed funds")]},
          title="Margins recovered after deposit costs peaked (%)", sort=(qt("quarter"), "Ascending"),
          objects={"dataPoint": series_colors([("Median NIM % by Quarter", NAVY), ("Median Cost of Deposits % by Quarter", RED), ("Fed Funds by Quarter %", GOLD)]),
                   "legend": legend("Top")})
    p.add("slicer", 790, 162, 230, 70, {"Values": [proj(qt("quarter"), "Quarter")]}, title="Quarter", objects=dict(dd))
    p.add("slicer", 1030, 162, W - 1030 - M, 70, {"Values": [proj(bk("size_band"), "Size band")]}, title="Size band", objects=dict(dd))
    p.add("clusteredBarChart", 790, 242, W - 790 - M, 250, {"Category": [proj(col("Flags", "flag"), "Flag")], "Y": [proj(meas("Banks Raising Flag"), "Banks")]},
          title="Banks raising each risk flag", sort=(col("Flags", "flag"), "Ascending"),
          objects={"dataPoint": [{"properties": {"fill": color(RED)}}], "labels": [{"properties": {"show": lit(True)}}]})
    p.add("tableEx", M, 502, 760, 273, {"Values": [proj(bk("bank"), "Bank"), proj(meas("Risk Flags"), "Flags"), proj(meas("Total Assets $B"), "Assets $B"),
                                                   proj(meas("Uninsured Deposits %"), "Uninsured %"), proj(meas("Loans / Deposits %"), "Loans/dep. %"),
                                                   proj(meas("CRE / Capital %"), "CRE/cap. %"), proj(meas("Liquidity / Uninsured %"), "Liq./unins. %"),
                                                   proj(meas("NIM Change per +100bp"), "NIM per +100bp")]},
          title="Watch list: banks sorted by risk flags", sort=(meas("Risk Flags"), "Descending"), objects=table_fmt({"Banks.bank": 135}), filters=peers_only)
    p.text("**Read-out**\n"
           "The median bank passed 41% of the Fed's 2022-24 hikes to depositors (beta 0.41); loan-heavy banks paid 0.50 and saw margins fall.\n"
           "Median NIM bottomed at 2.94% in Q1 2022 and is 3.66% now; deposit costs peaked at 2.38%.\n"
           "59 of 101 banks raise no risk flag; 10 raise two or more, led by ConnectOne (4).\n"
           "29 banks lose margin when rates rise, and rates are rising again (Fed funds 3.88% in October 2026).",
           790, 502, W - 790 - M, 273, size=10)
    pages.append(p)

    # 2 Governance / QA -----------------------------------------------------------------------------------------------------
    p = Page("p2_qa", "Governance & QA", "reconciliation to the Python metrics layer", "qa")
    p.kpis([("Reconciliation Status", "Reconciliation status", TEAL), ("Checks Passed", "Checks passed (of 20)"), ("Fact Rows", "Bank-quarters in the model"),
            ("Rows Needing Review", "Rows needing review", GOLD)])
    p.add("tableEx", M, 162, 760, 613, {"Values": [proj(col("Reconciliation", "check"), "Check"), proj(meas("Python Value"), "Python"),
                                                   proj(meas("DAX Value"), "DAX"), proj(meas("Difference"), "Diff"), proj(meas("Check Status"), "Status")]},
          title="Every headline number, DAX vs Python", objects=table_fmt({"Reconciliation.check": 380}), sort=(col("Reconciliation", "check"), "Ascending"))
    p.add("tableEx", 785, 162, W - 785 - M, 230, {"Values": [proj(col("Quarterly", "governance_label"), "Governance label"),
                                                             proj(meas("Fact Rows"), "Bank-quarters")]},
          title="Rows by governance label", objects=table_fmt({"Quarterly.governance_label": 330}, wrap=True))
    p.text("**Data rules**\n"
           "Source: FDIC call reports (BankFind Suite API), Q1 2019 to Q2 2026, insured-bank level; Fed funds and Treasury yields from FRED.\n"
           "Peer group: 101 US-owned, deposit-funded banks with $10-250B of assets; card, consumer, custody, broker-sweep, foreign-owned and Puerto Rico "
           "banks excluded.\n"
           "SVB, Signature and First Republic are kept as a case study and excluded from every peer statistic.\n"
           "Check labels: merger quarters (assets up more than 25%) and banks with no CET1 ratio (community bank leverage ratio).\n"
           "Status turns REVIEW if any DAX value differs from Python by more than 0.01.", 785, 402, W - 785 - M, 373, size=10)
    pages.append(p)

    # 3 Funding & deposit betas ------------------------------------------------------------------------------------------------
    p = Page("p3_funding", "Funding & Deposit Betas", "what drove deposit costs in 2022-24", "fb")
    p.add("scatterChart", M, 64, 760, 450, {"Category": [proj(bk("bank"), "Bank")], "Series": [proj(bk("size_band"), "Size band")],
                                            "X": [proj(meas("Loans / Deposits at Q4 2021 %"), "Loans / deposits, Q4 2021 (%)")],
                                            "Y": [proj(meas("Deposit Beta (Hikes)"), "Deposit beta, 2022-24")]},
          title="Banks that lent more of their deposits paid more for them (rho 0.62)",
          objects={"categoryLabels": [{"properties": {"show": lit(False)}}], "legend": legend("Bottom")}, filters=peers_only)
    p.add("tableEx", 785, 64, W - 785 - M, 450, {"Values": [proj(col("Findings", "finding"), "Finding"), proj(meas("Finding Value"), "Value"),
                                                            proj(meas("Finding p-value"), "p")]},
          title="Python results: what drives the deposit beta", objects=table_fmt({"Findings.finding": 260}, wrap=True),
          sort=(col("Findings", "finding"), "Ascending"),
          filters=[text_filter("Findings", "group", "Deposit beta drivers", "f_drivers")])
    p.add("areaChart", M, 524, 620, 251, {"Category": [proj(qt("quarter"), "Quarter")],
                                          "Y": [proj(meas("Median Cost of Deposits % by Quarter"), "Median cost of deposits"), proj(meas("Fed Funds by Quarter %"), "Fed funds")]},
          title="Deposit costs lagged the Fed both ways (%)", sort=(qt("quarter"), "Ascending"),
          objects={"dataPoint": series_colors([("Median Cost of Deposits % by Quarter", RED), ("Fed Funds by Quarter %", GOLD)]), "legend": legend("Top")})
    p.text("**What the data says**\n"
           "Median deposit beta 0.41 (middle half 0.33 to 0.51) over the 5.25-point hiking cycle; 0.33 on the way down.\n"
           "Betas rise with loans/deposits (rho 0.62) and brokered deposits (0.63) and fall with securities holdings (-0.56).\n"
           "Uninsured deposits did not predict betas (rho 0.09, p = 0.39): they matter for runs, not pricing.\n"
           "Loan-heavy third: beta 0.50, NIM -0.05 points over the cycle; deposit-rich third: beta 0.31, NIM +0.35.", 645, 524, W - 645 - M, 251, size=10)
    pages.append(p)

    # 4 Lessons from 2023 -------------------------------------------------------------------------------------------------------
    p = Page("p4_lessons", "Lessons from 2023", "SVB, Signature and First Republic at their last call report (Q4 2022)", "ls")
    p.kpis([("Survivor Median Uninsured at Q4 2022 %", "Survivor median uninsured deposits (%)"),
            ("Survivor Median Deposit Growth 2019-22 %", "Survivor median deposit growth 2019-22 (%)"),
            ("Survivor Median Marked CET1 at Q4 2022 %", "Survivor median marked CET1 (%)"),
            ("Failed Banks Raising All 3", "Failures raising all 3 flags", RED), ("Survivors Raising All 3", "Survivors raising all 3 flags", TEAL)])
    p.add("scatterChart", M, 162, 620, 420, {"Category": [proj(bk("bank"), "Bank")], "Series": [proj(bk("status"), "Status")],
                                             "X": [proj(meas("Uninsured at Q4 2022 %"), "Uninsured deposits, Q4 2022 (%)")],
                                             "Y": [proj(meas("Marked CET1 at Q4 2022 %"), "CET1 after securities losses, Q4 2022 (%)")]},
          title="The failures sat in the corner: flight-prone funding and thin marked capital",
          objects={"categoryLabels": [{"properties": {"show": lit(True)}}], "legend": legend("Bottom"),
                   "dataPoint": [{"properties": {"fill": color(RED)}, "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": {
                       "Column": {"Expression": {"SourceRef": {"Entity": "Banks"}}, "Property": "status"}}, "Right": {"Literal": {"Value": "'Failed in 2023'"}}}}}]}},
                                 {"properties": {"fill": color(GREY)}, "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": {
                                     "Column": {"Expression": {"SourceRef": {"Entity": "Banks"}}, "Property": "status"}}, "Right": {"Literal": {"Value": "'Peer'"}}}}}]}}]})
    p.add("tableEx", 645, 162, W - 645 - M, 200, {"Values": [proj(bk("bank"), "Bank"), proj(meas("Uninsured at Q4 2022 %"), "Uninsured %"),
                                                             proj(meas("Deposit Growth 2019-22 %"), "Dep. growth %"), proj(meas("Marked CET1 at Q4 2022 %"), "Marked CET1 %"),
                                                             proj(meas("Unrealized Loss / Tier 1 at Q4 2022 %"), "Loss/T1 %"), proj(meas("Early-Warning Flags"), "Flags")]},
          title="The three failures at Q4 2022", objects=table_fmt({"Banks.bank": 110}),
          filters=[text_filter("Banks", "status", "Failed in 2023", "failed_only")])
    p.add("areaChart", 645, 372, W - 645 - M, 210, {"Category": [proj(qt("quarter"), "Quarter")], "Series": [proj(bk("bank"), "Bank")],
                                                    "Y": [proj(meas("Deposits by Quarter $B"), "Deposits $B")]},
          title="Deposits ($B): growth into 2022, then the run", sort=(qt("quarter"), "Ascending"), objects={"legend": legend("Top")},
          filters=[text_filter("Banks", "status", "Failed in 2023", "failed_only2")])
    p.text("**What set them apart**\n"
           "All three had uninsured deposits above 60%, deposit growth above 90% since 2019 and CET1 below 8% once securities losses are counted; no surviving bank "
           "had all three, and four had two.\n"
           "Securities losses alone did not separate them: 28 survivors had deeper losses relative to capital than Signature.\n"
           "First Republic's deposits fell from $176B to $104B (-41%) in Q1 2023. The thresholds were chosen with hindsight: 36 of 80 tested settings catch all "
           "three failures and none flags more than one survivor.", M, 592, W - 2 * M, 183, size=10)
    pages.append(p)

    # 5 Bank scorecard -------------------------------------------------------------------------------------------------------
    p = Page("p5_scorecard", "Bank Scorecard", "one bank against the peer median", "sc")
    p.add("slicer", M, 64, 300, 86, {"Values": [proj(bk("bank"), "Bank")]}, title="Bank", objects=default_slicer("Banks", "bank", "Flagstar Bank"))
    p.add("slicer", 325, 64, 160, 86, {"Values": [proj(qt("quarter"), "Quarter")]}, title="Quarter", objects=dict(dd))
    for i, (mm, lab, fg) in enumerate([("NIM %", "NIM (%)", NAVY), ("Deposit Beta (Hikes)", "Deposit beta, hikes", BLUE),
                                        ("NIM Change per +100bp", "NIM change per +100bp (pts)", PURPLE), ("Risk Flags", "Risk flags (of 7)", RED)]):
        p.card(mm, lab, 500 + i * 192, 64, 182, 86, fg)
    p.add("tableEx", M, 162, 620, 613, {"Values": [proj(col("Metrics", "metric"), "Metric"), proj(meas("Metric Value"), "Bank"),
                                                   proj(meas("Metric Peer Median"), "Peer median"), proj(meas("Metric Rank"), "Rank")]},
          title="Scorecard (rank 1 = best of 101)", objects=table_fmt({"Metrics.metric": 290}), sort=(col("Metrics", "metric"), "Ascending"))
    p.add("areaChart", 645, 162, W - 645 - M, 300, {"Category": [proj(qt("quarter"), "Quarter")],
                                                    "Y": [proj(meas("Bank NIM % by Quarter"), "Bank"), proj(meas("Peer Median NIM % by Quarter"), "Peer median")]},
          title="Net interest margin vs peer median (%)", sort=(qt("quarter"), "Ascending"),
          objects={"dataPoint": series_colors([("Bank NIM % by Quarter", NAVY), ("Peer Median NIM % by Quarter", GOLD)]), "legend": legend("Top")})
    p.add("areaChart", 645, 472, W - 645 - M, 303, {"Category": [proj(qt("quarter"), "Quarter")],
                                                    "Y": [proj(meas("Bank Cost of Deposits % by Quarter"), "Bank"),
                                                          proj(meas("Peer Median Cost of Deposits % by Quarter"), "Peer median"),
                                                          proj(meas("Fed Funds by Quarter %"), "Fed funds")]},
          title="Cost of deposits vs peers and the Fed (%)", sort=(qt("quarter"), "Ascending"),
          objects={"dataPoint": series_colors([("Bank Cost of Deposits % by Quarter", NAVY), ("Peer Median Cost of Deposits % by Quarter", GOLD),
                                               ("Fed Funds by Quarter %", GREY)]), "legend": legend("Top")})
    pages.append(p)

    # 6 CRE & credit -----------------------------------------------------------------------------------------------------------
    p = Page("p6_cre", "CRE & Credit", "concentration against the 300% guidance, and losses so far", "cr")
    p.kpis([("Banks CRE Over 300%", "Banks above 300% CRE", RED), ("Median CRE / Capital %", "Median CRE / capital (%)"),
            ("Median NCO Rate %", "Median net charge-offs (%)"), ("Median Noncurrent Loans %", "Median noncurrent loans (%)")])
    p.add("columnChart", M, 162, 620, 300, {"Category": [proj(qt("quarter"), "Quarter")], "Y": [proj(meas("Banks CRE Over 300% by Quarter"), "Banks above 300%")]},
          title="Banks above the 300% CRE guidance, by quarter", sort=(qt("quarter"), "Ascending"),
          objects={"dataPoint": [{"properties": {"fill": color(NAVY)}}], "labels": [{"properties": {"show": lit(True)}}]})
    p.add("scatterChart", 645, 162, W - 645 - M, 300, {"Category": [proj(bk("bank"), "Bank")],
                                                       "X": [proj(meas("CRE / Capital %"), "CRE / capital (%)")], "Y": [proj(meas("NCO Rate %"), "Net charge-offs (%)")]},
          title="Concentration has not yet meant losses (selected quarter)", objects={"dataPoint": [{"properties": {"fill": color(NAVY)}}]}, filters=peers_only)
    p.add("tableEx", M, 472, 620, 303, {"Values": [proj(bk("bank"), "Bank"), proj(meas("CRE / Capital %"), "CRE / cap. %"),
                                                   proj(meas("Construction / Capital %"), "Constr. / cap. %"), proj(meas("NCO Rate %"), "NCO %"),
                                                   proj(meas("Noncurrent Loans %"), "Noncurrent %")]},
          title="Most CRE-concentrated banks", sort=(meas("CRE / Capital %"), "Descending"), objects=table_fmt({"Banks.bank": 200}), filters=peers_only)
    p.add("tableEx", 645, 472, W - 645 - M, 185, {"Values": [proj(col("Findings", "finding"), "Finding"), proj(meas("Finding Value"), "Value")]},
          title="Median NCO rate since 2024 by CRE band (Python)", objects=table_fmt({"Findings.finding": 380}, wrap=True),
          sort=(col("Findings", "finding"), "Ascending"), filters=[text_filter("Findings", "group", "CRE and credit", "f_cre")])
    p.text("**Read-out**\n"
           "Banks above 300% peaked at 24 in Q1 2024 and are 16 now. Since 2024 the median charge-off rate is 0.13% for them and 0.19% for banks under 200%. "
           "CRE losses lag and office loans are not reported separately, so this is 'not yet', not 'not a risk'.", 645, 667, W - 645 - M, 108, size=10)
    pages.append(p)

    # 7 Cohort analysis ------------------------------------------------------------------------------------------------------------
    p = Page("p7_cohorts", "Cohort Analysis", "size bands across the rate cycle", "co")
    heat = {"values": [{"properties": {"backColor": {"solid": {"color": {"expr": {"FillRule": {
        "Input": meas("Median Cost of Deposits % by Quarter"),
        "FillRule": {"linearGradient3": {"min": {"color": {"Literal": {"Value": "'#FFFFFF'"}}}, "mid": {"color": {"Literal": {"Value": f"'{GOLD}'"}}},
                                         "max": {"color": {"Literal": {"Value": f"'{RED}'"}}},
                                         "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}}}}}}}}}},
        "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": f"{M_}.Median Cost of Deposits % by Quarter"}}]}
    heat.update({k: v for k, v in table_fmt().items() if k == "columnHeaders"})
    p.add("pivotTable", M, 64, 760, 300, {"Rows": [proj(bk("size_band"), "Size band")], "Columns": [proj(qt("year"), "Year")],
                                          "Values": [proj(meas("Median Cost of Deposits % by Quarter"), "Median cost of deposits")]},
          title="Heatmap: median cost of deposits by size band and year (%)", objects=heat, filters=peers_only)
    p.add("lineClusteredColumnComboChart", 785, 64, W - 785 - M, 300,
          {"Category": [proj(qt("quarter"), "Quarter")], "Y": [proj(meas("Assets by Quarter $B"), "Assets $B")],
           "Y2": [proj(meas("Median NIM % by Quarter"), "Median NIM")]},
          title="Assets of the 101 (columns, $B) and median NIM (line, %)", sort=(qt("quarter"), "Ascending"),
          objects={"dataPoint": series_colors([("Assets by Quarter $B", NAVY), ("Median NIM % by Quarter", GOLD)]), "legend": legend("Top"),
                   "valueAxis": [{"properties": {"secShow": lit(True)}}]})
    p.add("tableEx", M, 374, 760, 401, {"Values": [proj(bk("size_band"), "Size band"), proj(meas("Banks"), "Banks"), proj(meas("Median NIM %"), "Median NIM"),
                                                   proj(meas("Median Deposit Beta (Hikes)"), "Median beta"), proj(meas("Median Uninsured Deposits %"), "Median uninsured"),
                                                   proj(meas("Median CRE / Capital %"), "Median CRE/cap."), proj(meas("Banks With 2+ Flags"), "2+ flags")]},
          title="Size-band summary (selected quarter)", objects=table_fmt(), sort=(bk("size_band"), "Ascending"), filters=peers_only)
    p.add("clusteredColumnChart", 785, 374, W - 785 - M, 401, {"Category": [proj(bk("size_band"), "Size band")],
                                                              "Y": [proj(meas("Banks With No Flags"), "No flags"), proj(meas("Banks With 2+ Flags"), "2+ flags")]},
          title="Risk flags by size band", sort=(bk("size_band"), "Ascending"),
          objects={"dataPoint": series_colors([("Banks With No Flags", TEAL), ("Banks With 2+ Flags", RED)]), "legend": legend("Top"),
                   "labels": [{"properties": {"show": lit(True)}}]}, filters=peers_only)
    pages.append(p)

    # 8 How this dashboard works -----------------------------------------------------------------------------------------------------
    p = Page("p8_how", "How This Dashboard Works", "build log, page guide and open items", "hw")
    p.text("**Build log**\n"
           "Day 1 - Data: pulled 3,079 bank-quarters of call-report data for 104 banks from the FDIC BankFind API and Fed funds / Treasury yields from FRED; "
           "checked SVB's 94% uninsured deposits and First Republic's Q1 2023 run against public reporting.\n"
           "Day 2 - Metrics (Python): deposit betas, rate sensitivity, the 2023 early-warning screen with a robustness grid, a seven-flag risk screen, CRE and "
           "credit; tests and gated evals in CI.\n"
           "Day 3 - Excel: an 8-quarter rate-scenario model with 1,600+ formulas and its own PASS checks.\n"
           "Day 4 - Power BI: source -> staging -> Quarterly fact in Power Query, Banks and Quarters dimensions, 130+ measures in numbered folders, generated as "
           "code (TMDL / PBIR), and 20 DAX vs Python checks.\n"
           "Day 5 - Report: nine pages in a light-card theme (rounded 3D cards, shaded area charts, dark pop-up tooltips); data frozen into the file for portability.", M, 64, 620, 360, size=11)
    p.text("**What each page shows**\n"
           "Executive Overview - KPIs, margin and deposit-cost trend, flag counts, watch list.\n"
           "Governance & QA - DAX vs Python checks, rows by governance label, data rules.\n"
           "Funding & Deposit Betas - who paid up for deposits and why.\n"
           "Lessons from 2023 - the three failures against 101 survivors at Q4 2022.\n"
           "Bank Scorecard - pick a bank: twelve metrics against the peer median, with ranks and trends.\n"
           "CRE & Credit - concentration against the 300% guidance and losses so far.\n"
           "Cohort Analysis - size bands across the rate cycle.\n"
           "Model Guide - every table and key measure.", 645, 64, W - 645 - M, 360, size=11)
    p.text("**Key rules**\n"
           "Every card shows one quarter: the slicer quarter, or Q2 2026 when none is selected. Ratios are ratios of sums, so a group total weights by size; "
           "medians are medians of bank ratios across peers only. Betas use quarter-average Fed funds: 0.08% (Q4 2021), 5.33% (Q2 2024), 3.63% (Q2 2026).\n\n"
           "**Open items for the data owner (FDIC data)**\n"
           "1. Figures are for insured banks, not holding companies; holding-company debt and parent liquidity are not covered.\n"
           "2. Office CRE is not reported separately in the call report, so CRE credit risk is measured on the whole non-owner-occupied book.\n"
           "3. Deposit growth and betas include acquisitions; merger quarters are labelled Check rather than removed.",
           M, 434, W - 2 * M, 341, size=11)
    pages.append(p)

    # 9 Model guide -------------------------------------------------------------------------------------------------------------------
    p = Page("p9_guide", "Model Guide", "every table and key measure", "mg")
    for i, (c, lab) in enumerate([("Object Type", "Object type"), ("Question Type", "Question type"), ("Group", "Group")]):
        p.add("slicer", M + i * 210, 64, 200, 70, {"Values": [proj(col("Model Guide", c))]}, title=lab, objects=dict(dd))
    p.text("**How to read this page:** each row is a table or measure in the model. Filter by type, question type (WHAT happened, WHY it "
           "happened, HOW we know) or group, then read across: what it does, why it exists, and the question it answers.", 645, 64, W - 645 - M, 70, size=10)
    widths = {"Object": 150, "Object Type": 70, "Group": 120, "What it does": 230, "Why it was created": 190, "What it helps find out": 160,
              "Question Type": 70, "Question it answers": 190}
    p.add("tableEx", M, 144, W - 2 * M, 631, {"Values": [proj(col("Model Guide", c)) for c in GUIDE_COLS]}, title="Model guide",
          objects=table_fmt({f"Model Guide.{k}": v for k, v in widths.items()}, wrap=True))
    pages.append(p)
    return pages


THEME = {
    "name": "Regional Bank Monitor Light Cards",
    "dataColors": [NAVY, BLUE, TEAL, RED, GOLD, PURPLE, GREY, "#5B8DEF", "#7FE0C4", "#FFC46B", "#F78CA8", "#A99BFF"],
    "background": "#FFFFFF", "foreground": INK, "tableAccent": NAVY, "good": TEAL, "bad": RED, "neutral": GOLD,
    "maximum": RED, "center": GOLD, "minimum": "#FFFFFF",
    "textClasses": {"title": {"fontFace": "Segoe UI Semibold", "color": INK, "fontSize": 11}, "label": {"fontFace": "Segoe UI", "color": MUTED},
                    "callout": {"fontFace": "Segoe UI Semibold", "color": INK}},
    "visualStyles": {
        "*": {"*": {"background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}],
                    "border": [{"show": True, "color": {"solid": {"color": LINE}}, "radius": 14}],
                    "dropShadow": [{"show": True, "color": {"solid": {"color": "#4A6FA5"}}, "position": "Outer", "preset": "Custom",
                                    "shadowBlur": 22, "shadowDistance": 7, "angle": 90, "shadowSpread": 1, "transparency": 72}],
                    "visualTooltip": [{"show": True, "type": "Default", "titleFontColor": {"solid": {"color": "#FFFFFF"}},
                                       "valueFontColor": {"solid": {"color": "#FFFFFF"}}, "background": {"solid": {"color": INK}}, "transparency": 0}],
                    "visualHeader": [{"show": True, "foreground": {"solid": {"color": MUTED}}}],
                    "title": [{"show": True, "fontColor": {"solid": {"color": INK}}, "fontSize": 11, "bold": True}],
                    "categoryAxis": [{"labelColor": {"solid": {"color": MUTED}}, "gridlineShow": False}],
                    "valueAxis": [{"labelColor": {"solid": {"color": MUTED}}, "gridlineColor": {"solid": {"color": LINE}}, "gridlineStyle": "dotted"}],
                    "legend": [{"labelColor": {"solid": {"color": MUTED}}, "fontSize": 9}]}},
        "page": {"*": {"background": [{"color": {"solid": {"color": BG}}, "transparency": 0}],
                       "outspace": [{"color": {"solid": {"color": BG}}, "transparency": 0}]}},
        "tableEx": {"*": {"columnHeaders": [{"fontColor": {"solid": {"color": MUTED}}, "backColor": {"solid": {"color": "#F5F8FC"}}, "bold": True}],
                          "values": [{"fontColor": {"solid": {"color": INK}}, "backColorPrimary": {"solid": {"color": "#FFFFFF"}},
                                      "backColorSecondary": {"solid": {"color": "#FFFFFF"}}}],
                          "grid": [{"gridHorizontal": True, "gridHorizontalColor": {"solid": {"color": LINE}}, "gridVertical": False}]}},
        "pivotTable": {"*": {"columnHeaders": [{"fontColor": {"solid": {"color": MUTED}}, "backColor": {"solid": {"color": "#F5F8FC"}}, "bold": True}],
                             "rowHeaders": [{"fontColor": {"solid": {"color": INK}}, "bold": True}]}},
        "card": {"*": {"labels": [{"fontFamily": "Segoe UI Semibold"}]}},
        "lineChart": {"*": {"lineStyles": [{"lineChartType": "smooth", "strokeWidth": 3, "showMarker": False}]}},
        "lineClusteredColumnComboChart": {"*": {"lineStyles": [{"lineChartType": "smooth", "strokeWidth": 3}]}},
        "areaChart": {"*": {"dataPoint": [{"transparency": 85}], "lineStyles": [{"lineChartType": "smooth", "strokeWidth": 3, "showMarker": False, "areaShow": True, "transparency": 70}]}},
        "slicer": {"*": {"items": [{"fontColor": {"solid": {"color": INK}}}]}},
    },
}
THEME_FILE = "RegionalBankTheme.json"
BASE_THEME = "Fluent2-CY26SU10"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/"


def platform(kind: str) -> str:
    return json.dumps({"$schema": SCHEMA + "gitIntegration/platformProperties/2.0.0/schema.json",
                       "metadata": {"type": kind, "displayName": TITLE},
                       "config": {"version": "2.0", "logicalId": tag("platform", kind)}}, indent=2)


def write_report(root: Path) -> int:
    rp = root / f"{NAME}.Report"
    d = rp / "definition"
    d.mkdir(parents=True, exist_ok=True)
    (rp / "definition.pbir").write_text(json.dumps({"$schema": SCHEMA + "item/report/definitionProperties/2.0.0/schema.json", "version": "4.0",
                                                    "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}}, indent=2))
    (rp / ".platform").write_text(platform("Report"))
    base = rp / "StaticResources" / "SharedResources" / "BaseThemes"
    base.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "assets" / f"{BASE_THEME}.json", base / f"{BASE_THEME}.json")
    (d / "version.json").write_text(json.dumps({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
                                                "version": "2.0.0"}, indent=2))
    res = rp / "StaticResources" / "RegisteredResources"
    res.mkdir(parents=True, exist_ok=True)
    (res / THEME_FILE).write_text(json.dumps(THEME, indent=2))
    rv = {"visual": "2.14.0", "report": "3.4.0", "page": "2.3.1"}
    (d / "report.json").write_text(json.dumps({
        "$schema": SCHEMA + "item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {"baseTheme": {"name": BASE_THEME, "reportVersionAtImport": rv, "type": "SharedResources"},
                            "customTheme": {"name": THEME_FILE, "reportVersionAtImport": rv, "type": "RegisteredResources"}},
        "objects": {"section": [{"properties": {"verticalAlignment": lit("Top")}}]},
        "resourcePackages": [{"name": "SharedResources", "type": "SharedResources",
                              "items": [{"name": BASE_THEME, "path": f"BaseThemes/{BASE_THEME}.json", "type": "BaseTheme"}]},
                             {"name": "RegisteredResources", "type": "RegisteredResources",
                              "items": [{"name": THEME_FILE, "path": THEME_FILE, "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}}, indent=2))
    pages = build()
    for p in pages:
        p.write(d)
    (d / "pages" / "pages.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": [p.name for p in pages], "activePageName": pages[0].name}, indent=2))
    return sum(len(p.visuals) for p in pages)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(ROOT / "data") + "/", help="folder with the exported CSVs, ending in a slash")
    args = ap.parse_args()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    (OUT / f"{NAME}.pbip").write_text(json.dumps({"$schema": SCHEMA + "pbip/pbipProperties/1.0.0/schema.json", "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
                                                  "settings": {"enableAutoRecovery": True}}, indent=2))
    (OUT / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    write_model(OUT, args.data_dir.replace("\\", "/") if False else args.data_dir)
    n = write_report(OUT)
    print(f"wrote {OUT}: {len(measures())} measures, {n} visuals")


if __name__ == "__main__":
    main()
