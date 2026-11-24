"""Export governed tables and Python reference values for the Power BI model (powerbi/data/)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bankmon import data as d  # noqa: E402
from bankmon import metrics as m  # noqa: E402

OUT = ROOT / "powerbi" / "data"

RAW_MAP = {  # FDIC field -> export column (USD millions)
    "ASSET": "assets", "DEP": "deposits", "DEPDOM": "domestic_deposits", "DEPUNINS": "uninsured_deposits", "BRO": "brokered_deposits",
    "LNLSGR": "loans", "LNRECONS": "construction_loans", "LNREMULT": "multifamily_loans", "LNRENROT": "nonowner_cre_loans",
    "RBCT1": "tier1_capital", "LNATRES": "allowance", "RBCT1C": "cet1_capital", "RWAJ": "rwa", "ERNAST": "earning_assets",
    "NIMQ": "net_interest_income", "INTINQ": "interest_income", "EINTXQ": "interest_expense", "EDEPDOMQ": "deposit_interest_expense",
    "NONIIQ": "noninterest_income", "NONIXQ": "noninterest_expense", "ELNATQ": "provision", "NETINCQ": "net_income",
    "NTLNLSQ": "net_charge_offs", "NCLNLS": "noncurrent_loans", "CHBAL": "cash", "SCAF": "afs_fair_value", "SCAA": "afs_amortized_cost",
    "SCHF": "htm_fair_value", "SCHA": "htm_amortized_cost", "OTHBFHLB": "fhlb_advances",
}
RATIO_MAP = {"NIMYQ": "fdic_nim", "INTINCYQ": "fdic_asset_yield", "INTEXPYQ": "fdic_cost_of_funds", "ROAQ": "fdic_roa",
             "EEFFQR": "fdic_efficiency", "RBCT1CER": "fdic_cet1_ratio", "RBC1AAJ": "fdic_leverage_ratio"}


def quarterly() -> pd.DataFrame:
    f = pd.read_csv(d.RAW / "fdic_regional_financials.csv")
    f["date"] = pd.to_datetime(f["REPDTE"].astype(str), format="%Y%m%d")
    f = f.sort_values(["CERT", "date"])
    out = pd.DataFrame({"cert": f["CERT"], "quarter_end": f["date"].dt.strftime("%Y-%m-%d")})
    for k, v in RAW_MAP.items():
        out[v] = (f[k] / 1000.0).round(4)
    for k, v in RATIO_MAP.items():
        out[v] = f[k]
    g = f.groupby("CERT")
    for k, v in [("ASSET", "opening_assets"), ("DEPDOM", "opening_domestic_deposits"), ("LNLSGR", "opening_loans")]:
        out[v] = (g[k].shift(1) / 1000.0).round(4)
    return out


def banks() -> pd.DataFrame:
    i = d.institutions()
    s = d.panel().sort_values("date").groupby("cert").last()
    out = pd.DataFrame({"cert": i["CERT"], "bank": i["short"], "state": i["STALP"], "holding_company": i["holding_company"],
                        "failed": i["failed"].map({True: "true", False: "false"})})
    out["size_band"] = out["cert"].map(s["size_band"])
    order = {b: k for k, (_, _, b) in enumerate(d.SIZE_BANDS, start=1)}
    out["size_order"] = out["size_band"].map(order)
    out = out.sort_values("bank").reset_index(drop=True)
    out["bank_order"] = range(1, len(out) + 1)
    return out


def findings() -> pd.DataFrame:
    rows = []
    for _, r in m.beta_drivers().iterrows():
        rows.append(("Deposit beta drivers", f"Beta vs {r['trait']}", r["rho"], r["p_value"], "Spearman, 101 banks, traits at Q4 2021"))
    for _, r in m.beta_by_funding_need().iterrows():
        rows.append(("Beta by funding need", f"Median beta, {r['ltd_tercile']} loans/deposits", r["up_beta"], None,
                     f"{int(r['banks'])} banks; NIM change {r['nim_change_cycle']:+.2f} pts"))
    rob = m.early_warning_robustness()
    rows.append(("2023 early warning", "Threshold settings tested", rob["settings"], None, "uninsured 50-65%, marked CET1 7-9%, growth 70-100%"))
    rows.append(("2023 early warning", "Settings catching all three failures", rob["all_three_caught"], None, ""))
    rows.append(("2023 early warning", "Most survivors flagged by any setting", rob["max_survivors_flagged"], None, ""))
    for _, r in m.cre_credit().iterrows():
        rows.append(("CRE and credit", f"Median NCO rate since 2024, CRE {r['band']}", r["nco_rate"], None, f"{int(r['banks'])} banks"))
    f = pd.DataFrame(rows, columns=["group", "finding", "value", "p_value", "note"])
    f["order"] = range(1, len(f) + 1)
    return f


def reconciliation() -> pd.DataFrame:
    h = m.headline()
    b = m.betas()
    s = d.snapshot()
    c = m.crisis_snapshot()
    ew = m.early_warning()
    checks = [
        ("banks", "Banks in the peer group, Q2 2026", h["banks"]),
        ("assets_t", "Total assets of the peer group ($T)", h["assets_trillion"]),
        ("nim_median", "Median NIM, Q2 2026 (%)", float(s["nim"].median())),
        ("depcost_median", "Median cost of deposits, Q2 2026 (%)", float(s["deposit_cost"].median())),
        ("uninsured_median", "Median uninsured deposits, Q2 2026 (%)", float(s["uninsured_share"].median())),
        ("cet1_median", "Median CET1 ratio, Q2 2026 (%)", float(s["cet1_ratio"].median())),
        ("beta_up", "Median deposit beta, hiking cycle", h["beta_median"]),
        ("beta_down", "Median deposit beta, cutting cycle", h["down_beta_median"]),
        ("nim100_median", "Median NIM change per +100bp (pts)", h["nim_per_100bp_median"]),
        ("liab_sensitive", "Banks losing margin when rates rise", h["liability_sensitive"]),
        ("flags_total", "Risk flags raised, Q2 2026", h["screen_total_flags"]),
        ("flags_two_plus", "Banks with 2+ risk flags", h["screen_two_plus"]),
        ("flags_zero", "Banks with no risk flags", h["screen_zero"]),
        ("cre_over_300", "Banks with CRE above 300% of capital", h["cre_over_300_latest"]),
        ("svb_uninsured", "SVB uninsured deposits, Q4 2022 (%)", float(c.loc[24735, "uninsured_share"])),
        ("frc_marked", "First Republic CET1 after securities losses, Q4 2022 (%)", float(c.loc[59017, "cet1_marked"])),
        ("ew_failed", "Failed banks raising all 3 early-warning flags", int((ew.loc[ew["failed"], "flag_count"] == 3).sum())),
        ("ew_survivors", "Surviving banks raising all 3 early-warning flags", int((ew.loc[~ew["failed"], "flag_count"] == 3).sum())),
        ("flagstar_nim100", "Flagstar NIM change per +100bp (pts)", float(b.loc[32541, "nim_per_100bp"])),
        ("mt_depcost_peak", "M&T cost of deposits, Q2 2024 (%)", float(d.snapshot(d.PEAK).loc[588, "deposit_cost"])),
    ]
    r = pd.DataFrame(checks, columns=["check_id", "check", "python_value"])
    r.insert(0, "order", range(1, len(r) + 1))
    return r


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    quarterly().to_csv(OUT / "quarterly.csv", index=False)
    banks().to_csv(OUT / "banks.csv", index=False)
    d.rates().assign(quarter_end=lambda x: x["date"].dt.strftime("%Y-%m-%d"))[["quarter_end", "fed_funds", "ust_2y", "ust_10y"]].round(4).to_csv(
        OUT / "rates.csv", index=False)
    findings().to_csv(OUT / "findings.csv", index=False)
    reconciliation().to_csv(OUT / "reconciliation.csv", index=False)
    for f in sorted(OUT.glob("*.csv")):
        print(f.name, len(pd.read_csv(f)))


if __name__ == "__main__":
    main()
