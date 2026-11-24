"""Load FDIC call-report data and build the bank-quarter panel.

Dollar amounts in the FDIC API are in thousands; the panel converts them to USD millions.
Ratios reported by the FDIC (NIM, ROA, efficiency, capital ratios) are kept in percent.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"

FAILED = {24735: "Silicon Valley Bank", 57053: "Signature Bank", 59017: "First Republic Bank"}
FAILED_SHORT = {24735: "SVB", 57053: "Signature", 59017: "First Republic"}

# Rate-cycle anchors (quarter ends)
TROUGH = "2021-12-31"      # Fed funds ~0.08%
PEAK = "2024-06-30"        # Fed funds 5.33%, last quarter before cuts
LATEST = "2026-06-30"      # latest call report
CRISIS = "2022-12-31"      # last call report before the March 2023 failures

DOLLAR_FIELDS = ["ASSET", "EQTOT", "LNLSGR", "LNATRES", "DEP", "DEPDOM", "DEPINS", "DEPUNINS", "BRO", "COREDEP", "CHBAL", "SC",
                 "SCAF", "SCAA", "SCHA", "SCHF", "OTHBFHLB", "OTHBOR", "ERNAST", "LNRECONS", "LNREMULT", "LNRENRES", "LNRENROT",
                 "LNRENROW", "LNRERES", "LNCI", "LNCON", "NCLNLS", "RBCT1", "RBCT1C", "RWAJ", "EQCCOMPI", "INTINQ", "EINTXQ",
                 "NIMQ", "EDEPDOMQ", "NONIIQ", "NONIXQ", "ELNATQ", "NETINCQ", "NTLNLSQ"]

SIZE_BANDS = [(0, 20_000, "$10-20B"), (20_000, 50_000, "$20-50B"), (50_000, 100_000, "$50-100B"), (100_000, 1e9, "$100-250B")]


NAME_OVERRIDES = {
    17266: "Columbia Bank (OR)", 28834: "Columbia Bank (NJ)", 6600: "First Financial Bank (OH)", 3066: "First Financial Bank (TX)",
    588: "M&T Bank", 17534: "KeyBank", 8273: "UMB Bank", 110: "Bank OZK", 59052: "NBH Bank", 7230: "NBT Bank", 57993: "ServisFirst Bank",
    57919: "ConnectOne Bank", 33555: "SouthState Bank", 28359: "OceanFirst Bank", 27476: "BancFirst", 17491: "PlainsCapital Bank",
    26610: "Bank of Hope", 24045: "Banc of California", 18053: "Bank of Hawaii", 58979: "BankUnited", 4214: "BOKF",
    28088: "WaFd Bank", 803: "WesBanco Bank", 4063: "MidFirst Bank", 34775: "EverBank", 29209: "NexBank", 35095: "TowneBank",
    8663: "FirstBank (TN)", 15019: "First Bank (NC)", 4239: "First United Bank", 11063: "First Citizens Bank", 9712: "Rockland Trust",
    32245: "Dollar Bank", 30012: "Third Federal Savings", 17838: "WSFS Bank", 1225: "Farmers & Merchants Bank of Long Beach",
    17798: "Beacon Bank & Trust", 5452: "First National Bank of Omaha", 7888: "First National Bank of Pennsylvania",
    19629: "International Bank of Commerce", 8056: "Merchants Bank of Indiana", 6653: "Park National Bank", 12633: "Central Trust Bank",
    2270: "Zions Bank", 258: "Stock Yards Bank", 6989: "Community Bank NA", 58665: "Live Oak Bank",
}


def _short(name: str) -> str:
    n = name.title().replace("National Association", "").replace(", N.A.", "").replace(" N.A.", "").replace(", Inc.", "")
    for w in [" Bank & Trust Company", " Bank And Trust Company", " Trust Company", " Company"]:
        n = n.replace(w, "")
    return " ".join(n.replace(",", "").split()).replace("Fsb", "FSB").replace("Ssb", "SSB").replace("Bmo", "BMO")


@lru_cache(maxsize=1)
def institutions() -> pd.DataFrame:
    i = pd.read_csv(RAW / "fdic_regional_institutions.csv")
    i["failed"] = i["CERT"].isin(FAILED)
    i["short"] = i["NAME"].map(_short)
    i.loc[i["CERT"].isin(NAME_OVERRIDES), "short"] = i.loc[i["CERT"].isin(NAME_OVERRIDES), "CERT"].map(NAME_OVERRIDES)
    i.loc[i["failed"], "short"] = i.loc[i["failed"], "CERT"].map(FAILED_SHORT)
    i["holding_company"] = i["NAMEHCR"].fillna("").str.title()
    return i[["CERT", "NAME", "short", "STALP", "SPECGRPN", "holding_company", "failed", "ENDEFYMD"]]


@lru_cache(maxsize=1)
def rates() -> pd.DataFrame:
    """Quarter-average Fed funds, 2-year and 10-year Treasury yields (percent)."""
    r = pd.read_csv(RAW / "fred_rates_monthly.csv", parse_dates=["date"])
    r["quarter"] = r["date"].dt.to_period("Q").dt.to_timestamp(how="end").dt.normalize()
    q = r.groupby("quarter")[["FEDFUNDS", "DGS2", "DGS10"]].mean().reset_index()
    q = q.rename(columns={"quarter": "date", "FEDFUNDS": "fed_funds", "DGS2": "ust_2y", "DGS10": "ust_10y"})
    return q


@lru_cache(maxsize=1)
def panel() -> pd.DataFrame:
    """One row per bank-quarter with balances in USD millions and derived ratios in percent."""
    f = pd.read_csv(RAW / "fdic_regional_financials.csv")
    f["date"] = pd.to_datetime(f["REPDTE"].astype(str), format="%Y%m%d")
    for c in DOLLAR_FIELDS:
        f[c] = f[c].astype(float) / 1000.0
    f = f.sort_values(["CERT", "date"]).reset_index(drop=True)
    g = f.groupby("CERT")

    def avg(col: str) -> pd.Series:
        prev = g[col].shift(1)
        return ((f[col] + prev) / 2).fillna(f[col])

    out = pd.DataFrame({"cert": f["CERT"], "date": f["date"]})
    out["assets"] = f["ASSET"]
    out["deposits"] = f["DEP"]
    out["domestic_deposits"] = f["DEPDOM"]
    out["loans"] = f["LNLSGR"]
    out["equity"] = f["EQTOT"]
    out["tier1"] = f["RBCT1"]
    out["cet1_capital"] = f["RBCT1C"]
    out["rwa"] = f["RWAJ"]
    out["allowance"] = f["LNATRES"]
    out["earning_assets"] = f["ERNAST"]

    # Quarterly income (annualised where a rate is needed)
    out["net_interest_income"] = f["NIMQ"]
    out["interest_income"] = f["INTINQ"]
    out["interest_expense"] = f["EINTXQ"]
    out["deposit_interest_expense"] = f["EDEPDOMQ"]
    out["noninterest_income"] = f["NONIIQ"]
    out["noninterest_expense"] = f["NONIXQ"]
    out["provision"] = f["ELNATQ"]
    out["net_income"] = f["NETINCQ"]
    out["net_charge_offs"] = f["NTLNLSQ"]

    # FDIC-computed ratios (percent)
    out["nim"] = f["NIMYQ"]
    out["asset_yield"] = f["INTINCYQ"]
    out["cost_of_funds"] = f["INTEXPYQ"]
    out["roa"] = f["ROAQ"]
    out["roe"] = f["ROEQ"]
    out["efficiency"] = f["EEFFQR"]
    out["cet1_ratio"] = f["RBCT1CER"]
    out["tier1_ratio"] = f["RBC1RWAJ"]
    out["total_capital_ratio"] = f["RBCRWAJ"]
    out["leverage_ratio"] = f["RBC1AAJ"]

    # Derived ratios (percent)
    out["deposit_cost"] = 400 * f["EDEPDOMQ"] / avg("DEPDOM")
    out["uninsured_share"] = 100 * f["DEPUNINS"] / f["DEPDOM"]
    out["brokered_share"] = 100 * f["BRO"] / f["DEP"]
    out["loan_to_deposit"] = 100 * f["LNLSGR"] / f["DEP"]
    out["fhlb_to_assets"] = 100 * f["OTHBFHLB"] / f["ASSET"]
    cre = f["LNRECONS"] + f["LNREMULT"] + f["LNRENROT"]
    out["cre_loans"] = cre
    cap_base = f["RBCT1"] + f["LNATRES"]
    out["cre_concentration"] = 100 * cre / cap_base
    out["construction_concentration"] = 100 * f["LNRECONS"] / cap_base
    out["cre_to_loans"] = 100 * cre / f["LNLSGR"]
    out["htm_unrealized"] = f["SCHF"] - f["SCHA"]
    out["afs_unrealized"] = f["SCAF"] - f["SCAA"]
    out["securities_unrealized"] = out["htm_unrealized"] + out["afs_unrealized"]
    out["unrealized_to_tier1"] = 100 * out["securities_unrealized"] / f["RBCT1"]
    out["securities_to_assets"] = 100 * (f["SCAF"] + f["SCHA"]) / f["ASSET"]
    out["htm_share"] = 100 * f["SCHA"] / (f["SCAF"] + f["SCHA"]).replace(0, np.nan)
    liquid = f["CHBAL"] + f["SCAF"] + f["SCHF"]
    out["uninsured_coverage"] = 100 * liquid / f["DEPUNINS"].replace(0, np.nan)
    out["nco_rate"] = 400 * f["NTLNLSQ"] / avg("LNLSGR")
    out["noncurrent_rate"] = 100 * f["NCLNLS"] / f["LNLSGR"]
    out["allowance_to_loans"] = 100 * f["LNATRES"] / f["LNLSGR"]
    # CET1 if every unrealized securities loss were recognised (after 21% tax), a stress view
    after_tax = out["securities_unrealized"].clip(upper=0) * (1 - 0.21)
    aoci_in_cet1 = 0.0  # most banks of this size opt out of AOCI in CET1; AFS losses are therefore added back here too
    out["cet1_marked"] = 100 * (f["RBCT1C"] + after_tax + aoci_in_cet1) / f["RWAJ"]

    # Scope changes (mergers): assets jump by more than 25% in a quarter
    jump = g["ASSET"].pct_change()
    out["scope_change"] = jump > 0.25

    r = rates()
    out = out.merge(r, on="date", how="left")
    inst = institutions().rename(columns={"CERT": "cert"})
    out = out.merge(inst[["cert", "short", "STALP", "failed"]], on="cert", how="left")
    latest_assets = out[out["date"] == out.groupby("cert")["date"].transform("max")].set_index("cert")["assets"]
    out["size_band"] = out["cert"].map(lambda c: next(b for lo, hi, b in SIZE_BANDS if lo <= latest_assets[c] < hi))
    return out


def peers(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """The 101 active regional banks (failed banks excluded)."""
    df = panel() if df is None else df
    return df[~df["failed"]]


def snapshot(date: str = LATEST, include_failed: bool = False) -> pd.DataFrame:
    df = panel()
    s = df[df["date"] == pd.Timestamp(date)]
    if not include_failed:
        s = s[~s["failed"]]
    return s.set_index("cert")


def series(cert: int) -> pd.DataFrame:
    df = panel()
    return df[df["cert"] == cert].set_index("date")
