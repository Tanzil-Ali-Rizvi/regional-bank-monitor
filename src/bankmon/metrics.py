"""Analyses on the bank-quarter panel: deposit betas, the 2023 failure case, today's risk screen, CRE and rate exposure."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from scipy import stats

from . import data as d

LABELS = {
    "nim": "Net interest margin (%)",
    "deposit_cost": "Cost of deposits (%)",
    "cost_of_funds": "Cost of funds (%)",
    "asset_yield": "Asset yield (%)",
    "uninsured_share": "Uninsured deposits (%)",
    "loan_to_deposit": "Loans / deposits (%)",
    "brokered_share": "Brokered deposits (%)",
    "fhlb_to_assets": "FHLB advances / assets (%)",
    "cre_concentration": "CRE / (Tier 1 + reserves) (%)",
    "construction_concentration": "Construction / (Tier 1 + reserves) (%)",
    "unrealized_to_tier1": "Unrealized securities loss / Tier 1 (%)",
    "uninsured_coverage": "Cash + securities / uninsured deposits (%)",
    "cet1_ratio": "CET1 ratio (%)",
    "cet1_marked": "CET1 after securities losses (%)",
    "leverage_ratio": "Tier 1 leverage ratio (%)",
    "roa": "Return on assets (%)",
    "roe": "Return on equity (%)",
    "efficiency": "Efficiency ratio (%)",
    "nco_rate": "Net charge-offs / loans (%)",
    "noncurrent_rate": "Noncurrent loans / loans (%)",
    "assets": "Total assets ($M)",
    "htm_share": "Held-to-maturity share of securities (%)",
    "securities_to_assets": "Securities / assets (%)",
    "up_beta": "Deposit beta, hiking cycle",
    "down_beta": "Deposit beta, cutting cycle",
    "nim_per_100bp": "NIM change per +100bp (pp)",
}
LOWER_IS_BETTER = {"deposit_cost", "cost_of_funds", "uninsured_share", "loan_to_deposit", "brokered_share", "fhlb_to_assets",
                   "cre_concentration", "construction_concentration", "efficiency", "nco_rate", "noncurrent_rate", "up_beta"}

# Today's risk screen: (label, column, operator, threshold, why it matters)
RISK_FLAGS = [
    ("Uninsured deposits > 60%", "uninsured_share", ">", 60.0, "flight-prone funding; all three 2023 failures were above it"),
    ("CET1 after securities losses < 8%", "cet1_marked", "<", 8.0, "capital if every unrealized securities loss were taken"),
    ("CRE > 300% of capital", "cre_concentration", ">", 300.0, "interagency CRE guidance threshold"),
    ("Construction > 100% of capital", "construction_concentration", ">", 100.0, "interagency construction guidance threshold"),
    ("Loans > deposits", "loan_to_deposit", ">", 100.0, "lends more than it gathers; relies on wholesale funding"),
    ("Liquidity < 50% of uninsured deposits", "uninsured_coverage", "<", 50.0, "cash and securities cannot cover half a run"),
    ("Net charge-offs > 0.5%", "nco_rate", ">", 0.5, "credit losses running above normal"),
]

# 2023 early-warning screen, measured at the last call report before the failures (2022 Q4)
EARLY_WARNING = [
    ("Uninsured deposits > 60%", "uninsured_share", ">", 60.0),
    ("CET1 after securities losses < 8%", "cet1_marked", "<", 8.0),
    ("Deposit growth 2019-22 > 90%", "deposit_growth", ">", 90.0),
]


def _ff(date: str) -> float:
    return float(d.rates().set_index("date").loc[pd.Timestamp(date), "fed_funds"])


def _at(df: pd.DataFrame, date: str, col: str) -> pd.Series:
    return df[df["date"] == pd.Timestamp(date)].set_index("cert")[col]


@lru_cache(maxsize=1)
def betas() -> pd.DataFrame:
    """Cycle betas per bank: change in a rate divided by the change in quarter-average Fed funds."""
    p = d.peers()
    up_ff = _ff(d.PEAK) - _ff(d.TROUGH)
    dn_ff = _ff(d.LATEST) - _ff(d.PEAK)
    b = pd.DataFrame({
        "up_beta": (_at(p, d.PEAK, "deposit_cost") - _at(p, d.TROUGH, "deposit_cost")) / up_ff,
        "down_beta": (_at(p, d.LATEST, "deposit_cost") - _at(p, d.PEAK, "deposit_cost")) / dn_ff,
        "funding_beta": (_at(p, d.PEAK, "cost_of_funds") - _at(p, d.TROUGH, "cost_of_funds")) / up_ff,
        "yield_beta": (_at(p, d.PEAK, "asset_yield") - _at(p, d.TROUGH, "asset_yield")) / up_ff,
        "deposit_cost_trough": _at(p, d.TROUGH, "deposit_cost"),
        "deposit_cost_peak": _at(p, d.PEAK, "deposit_cost"),
        "deposit_cost_latest": _at(p, d.LATEST, "deposit_cost"),
        "nim_trough": _at(p, d.TROUGH, "nim"),
        "nim_peak": _at(p, d.PEAK, "nim"),
        "nim_latest": _at(p, d.LATEST, "nim"),
        "loan_to_deposit": _at(p, d.TROUGH, "loan_to_deposit"),
        "brokered_share": _at(p, d.TROUGH, "brokered_share"),
        "securities_to_assets": _at(p, d.TROUGH, "securities_to_assets"),
        "uninsured_share": _at(p, d.TROUGH, "uninsured_share"),
        "cre_concentration": _at(p, d.TROUGH, "cre_concentration"),
        "assets": _at(p, d.TROUGH, "assets"),
    })
    # A first-order rate sensitivity from each bank's own history: asset yields and funding costs per earning asset
    b["nim_per_100bp"] = b["yield_beta"] - b["funding_beta"]
    b["nim_change_cycle"] = b["nim_peak"] - b["nim_trough"]
    names = d.institutions().set_index("CERT")["short"]
    b.insert(0, "bank", names.reindex(b.index).values)
    return b


def beta_drivers() -> pd.DataFrame:
    """Spearman correlation of the hiking-cycle deposit beta with balance-sheet traits at the 2021 trough."""
    b = betas()
    rows = []
    for col in ["loan_to_deposit", "brokered_share", "securities_to_assets", "uninsured_share", "cre_concentration", "assets"]:
        r = stats.spearmanr(b["up_beta"], b[col], nan_policy="omit")
        rows.append({"trait": LABELS.get(col, col), "column": col, "rho": float(r.statistic), "p_value": float(r.pvalue)})
    return pd.DataFrame(rows)


def beta_by_funding_need() -> pd.DataFrame:
    """Median deposit beta and NIM change by loan-to-deposit tercile at the trough."""
    b = betas().copy()
    b["ltd_tercile"] = pd.qcut(b["loan_to_deposit"], 3, labels=["Low (deposit-rich)", "Middle", "High (loan-heavy)"])
    g = b.groupby("ltd_tercile", observed=True).agg(banks=("up_beta", "size"), loan_to_deposit=("loan_to_deposit", "median"),
                                                    up_beta=("up_beta", "median"), nim_change_cycle=("nim_change_cycle", "median"))
    return g.reset_index()


@lru_cache(maxsize=1)
def crisis_snapshot() -> pd.DataFrame:
    """Every bank at 2022 Q4 (failed banks included) with deposit growth since 2019 Q4."""
    p = d.panel()
    c = p[p["date"] == pd.Timestamp(d.CRISIS)].set_index("cert").copy()
    base = p[p["date"] == pd.Timestamp("2019-12-31")].set_index("cert")["deposits"]
    c["deposit_growth"] = 100 * (c["deposits"] / base.reindex(c.index) - 1)
    return c


def _flag(values: pd.Series, op: str, threshold: float) -> pd.Series:
    return values > threshold if op == ">" else values < threshold


def early_warning() -> pd.DataFrame:
    c = crisis_snapshot()
    out = pd.DataFrame(index=c.index)
    out["bank"] = c["short"]
    out["failed"] = c["failed"]
    for label, col, op, thr in EARLY_WARNING:
        out[col] = c[col]
        out[label] = _flag(c[col], op, thr)
    out["flag_count"] = out[[e[0] for e in EARLY_WARNING]].sum(axis=1)
    return out


def failed_vs_peers() -> pd.DataFrame:
    """Where each failed bank sat in the 2022 Q4 peer distribution (percentile among the 101 survivors)."""
    c = crisis_snapshot()
    peer = c[~c["failed"]]
    rows = []
    for col in ["uninsured_share", "deposit_growth", "cet1_marked", "unrealized_to_tier1", "htm_share", "securities_to_assets",
                "uninsured_coverage", "cet1_ratio", "loan_to_deposit", "cre_concentration"]:
        row = {"metric": LABELS.get(col, "Deposit growth 2019-22 (%)" if col == "deposit_growth" else col), "column": col,
               "peer_median": float(peer[col].median())}
        for cert, short in d.FAILED_SHORT.items():
            v = float(c.loc[cert, col])
            row[short] = v
            row[f"{short}_pct"] = float((peer[col] < v).mean() * 100)
        rows.append(row)
    return pd.DataFrame(rows)


def early_warning_robustness() -> dict:
    """Vary all three thresholds; count how often every failure is caught and how many survivors also trip all three."""
    c = crisis_snapshot()
    grid = []
    for u in [50, 55, 60, 65]:
        for m in [7.0, 7.5, 8.0, 8.5, 9.0]:
            for g in [70, 80, 90, 100]:
                hit = (c["uninsured_share"] > u) & (c["cet1_marked"] < m) & (c["deposit_growth"] > g)
                grid.append({"uninsured": u, "cet1_marked": m, "growth": g,
                             "failed_caught": int(hit[c["failed"]].sum()), "survivors_flagged": int(hit[~c["failed"]].sum())})
    gdf = pd.DataFrame(grid)
    return {"settings": len(gdf), "all_three_caught": int((gdf["failed_caught"] == 3).sum()),
            "median_survivors_flagged": float(gdf["survivors_flagged"].median()), "max_survivors_flagged": int(gdf["survivors_flagged"].max()),
            "grid": gdf}


def risk_screen(date: str = d.LATEST) -> pd.DataFrame:
    s = d.snapshot(date)
    out = pd.DataFrame(index=s.index)
    out["bank"] = s["short"]
    out["state"] = s["STALP"]
    out["assets"] = s["assets"]
    for label, col, op, thr, _ in RISK_FLAGS:
        out[col] = s[col]
        out[label] = _flag(s[col], op, thr)
    out["flag_count"] = out[[f[0] for f in RISK_FLAGS]].sum(axis=1)
    return out.sort_values(["flag_count", "assets"], ascending=[False, False])


def flag_counts(date: str = d.LATEST) -> pd.DataFrame:
    r = risk_screen(date)
    return pd.DataFrame([{"flag": lab, "banks": int(r[lab].sum()), "why": why} for lab, _, _, _, why in RISK_FLAGS])


def trends() -> pd.DataFrame:
    """Peer medians by quarter for the main ratios, plus Fed funds."""
    p = d.peers()
    cols = ["nim", "deposit_cost", "asset_yield", "cost_of_funds", "uninsured_share", "loan_to_deposit", "cre_concentration",
            "unrealized_to_tier1", "cet1_ratio", "cet1_marked", "nco_rate", "noncurrent_rate", "roa", "efficiency"]
    t = p.groupby("date")[cols].median()
    t["fed_funds"] = d.rates().set_index("date")["fed_funds"].reindex(t.index)
    t["banks_cre_over_300"] = p.assign(x=p["cre_concentration"] > 300).groupby("date")["x"].sum()
    return t


def cre_credit() -> pd.DataFrame:
    """Credit since 2024 by CRE concentration band at 2023 Q4."""
    p = d.peers()
    band = _at(p, "2023-12-31", "cre_concentration")
    bands = pd.cut(band, [-1, 200, 300, 1e9], labels=["Under 200%", "200-300%", "Over 300%"])
    later = p[p["date"] >= pd.Timestamp("2024-03-31")]
    per_bank = later.groupby("cert").agg(nco_rate=("nco_rate", "mean"), noncurrent_rate=("noncurrent_rate", "last"))
    per_bank["band"] = bands
    g = per_bank.groupby("band", observed=True).agg(banks=("nco_rate", "size"), nco_rate=("nco_rate", "median"),
                                                    noncurrent_rate=("noncurrent_rate", "median"))
    return g.reset_index()


def rate_exposure() -> pd.DataFrame:
    """Banks ranked by their historical NIM response to higher rates."""
    b = betas()
    s = d.snapshot()
    out = b[["bank", "yield_beta", "funding_beta", "up_beta", "nim_per_100bp"]].copy()
    out["nim_latest"] = s["nim"]
    out["earning_assets"] = s["earning_assets"]
    out["nii_per_100bp_musd"] = out["nim_per_100bp"] / 100 * out["earning_assets"]
    return out.sort_values("nim_per_100bp")


def scorecard(date: str = d.LATEST) -> pd.DataFrame:
    """Percentile scores (100 = best in peer group) on funding, capital, credit and earnings."""
    s = d.snapshot(date)
    b = betas()
    parts = {
        "Funding": ["uninsured_share", "loan_to_deposit", "deposit_cost"],
        "Capital & liquidity": ["cet1_marked", "uninsured_coverage", "leverage_ratio"],
        "Credit": ["cre_concentration", "nco_rate", "noncurrent_rate"],
        "Earnings": ["nim", "roa", "efficiency"],
    }
    out = pd.DataFrame(index=s.index)
    out["bank"] = s["short"]
    for name, cols in parts.items():
        scores = []
        for c in cols:
            pct = s[c].rank(pct=True) * 100
            scores.append(100 - pct if c in LOWER_IS_BETTER else pct)
        out[name] = pd.concat(scores, axis=1).mean(axis=1)
    out["Overall"] = out[list(parts)].mean(axis=1)
    out["up_beta"] = b["up_beta"]
    return out.sort_values("Overall", ascending=False)


def bank_profile(cert: int) -> dict:
    s = d.snapshot()
    if cert not in s.index:
        raise KeyError(cert)
    row = s.loc[cert]
    peer = s
    b = betas().loc[cert]
    metrics = {}
    for col in ["nim", "deposit_cost", "uninsured_share", "loan_to_deposit", "cre_concentration", "unrealized_to_tier1",
                "cet1_ratio", "cet1_marked", "uninsured_coverage", "roa", "efficiency", "nco_rate"]:
        v = float(row[col])
        pct = float((peer[col] < v).mean() * 100)
        rank = int(peer[col].rank(ascending=col in LOWER_IS_BETTER, method="min")[cert])
        metrics[col] = {"value": v, "peer_median": float(peer[col].median()), "rank": rank, "percentile": pct}
    flags = risk_screen().loc[cert]
    return {"cert": cert, "bank": row["short"], "state": row["STALP"], "assets": float(row["assets"]), "size_band": row["size_band"],
            "metrics": metrics, "up_beta": float(b["up_beta"]), "down_beta": float(b["down_beta"]),
            "nim_per_100bp": float(b["nim_per_100bp"]), "flags": [f[0] for f in RISK_FLAGS if bool(flags[f[0]])]}


def median_of(col: str, date: str = d.LATEST) -> float:
    return float(np.nanmedian(d.snapshot(date)[col]))


@lru_cache(maxsize=1)
def headline() -> dict:
    """The numbers the memo, app, Excel checks and Power BI reconciliation all quote."""
    b = betas()
    t = trends()
    rs = risk_screen()
    drv = beta_drivers().set_index("column")
    ew = early_warning()
    rob = early_warning_robustness()
    fvp = failed_vs_peers().set_index("column")
    cc = cre_credit().set_index("band")
    ltd = beta_by_funding_need()
    s = d.snapshot()
    worst = b.sort_values("nim_per_100bp").iloc[0]
    trough_nim_date = t["nim"].idxmin()
    return {
        "banks": int(len(s)),
        "assets_trillion": float(s["assets"].sum() / 1e6),
        "beta_median": float(b["up_beta"].median()),
        "beta_q1": float(b["up_beta"].quantile(0.25)),
        "beta_q3": float(b["up_beta"].quantile(0.75)),
        "down_beta_median": float(b["down_beta"].median()),
        "rho_ltd": float(drv.loc["loan_to_deposit", "rho"]),
        "p_ltd": float(drv.loc["loan_to_deposit", "p_value"]),
        "rho_brokered": float(drv.loc["brokered_share", "rho"]),
        "rho_securities": float(drv.loc["securities_to_assets", "rho"]),
        "rho_uninsured": float(drv.loc["uninsured_share", "rho"]),
        "p_uninsured": float(drv.loc["uninsured_share", "p_value"]),
        "beta_low_ltd": float(ltd["up_beta"].iloc[0]),
        "beta_high_ltd": float(ltd["up_beta"].iloc[-1]),
        "nim_change_low_ltd": float(ltd["nim_change_cycle"].iloc[0]),
        "nim_change_high_ltd": float(ltd["nim_change_cycle"].iloc[-1]),
        "deposit_cost_peak_median": float(t["deposit_cost"].max()),
        "deposit_cost_latest_median": float(t["deposit_cost"].iloc[-1]),
        "nim_trough_median": float(t["nim"].min()),
        "nim_trough_date": str(trough_nim_date.date()),
        "nim_latest_median": float(t["nim"].iloc[-1]),
        "unrealized_worst_median": float(t["unrealized_to_tier1"].min()),
        "unrealized_latest_median": float(t["unrealized_to_tier1"].iloc[-1]),
        "uninsured_peer_2022": float(fvp.loc["uninsured_share", "peer_median"]),
        "uninsured_svb": float(fvp.loc["uninsured_share", "SVB"]),
        "uninsured_signature": float(fvp.loc["uninsured_share", "Signature"]),
        "uninsured_frc": float(fvp.loc["uninsured_share", "First Republic"]),
        "growth_peer": float(fvp.loc["deposit_growth", "peer_median"]),
        "growth_svb": float(fvp.loc["deposit_growth", "SVB"]),
        "growth_signature": float(fvp.loc["deposit_growth", "Signature"]),
        "growth_frc": float(fvp.loc["deposit_growth", "First Republic"]),
        "cet1_marked_peer_2022": float(fvp.loc["cet1_marked", "peer_median"]),
        "cet1_marked_svb": float(fvp.loc["cet1_marked", "SVB"]),
        "cet1_marked_signature": float(fvp.loc["cet1_marked", "Signature"]),
        "cet1_marked_frc": float(fvp.loc["cet1_marked", "First Republic"]),
        "unrealized_svb": float(fvp.loc["unrealized_to_tier1", "SVB"]),
        "survivors_unrealized_worse_than_signature": int((crisis_snapshot().loc[~crisis_snapshot()["failed"], "unrealized_to_tier1"]
                                                          < fvp.loc["unrealized_to_tier1", "Signature"]).sum()),
        "ew_failed_all_three": int((ew.loc[ew["failed"], "flag_count"] == 3).sum()),
        "ew_survivors_all_three": int((ew.loc[~ew["failed"], "flag_count"] == 3).sum()),
        "ew_survivors_two": int((ew.loc[~ew["failed"], "flag_count"] == 2).sum()),
        "ew_grid": int(rob["settings"]),
        "ew_grid_all_caught": int(rob["all_three_caught"]),
        "ew_grid_max_survivors": int(rob["max_survivors_flagged"]),
        "screen_zero": int((rs["flag_count"] == 0).sum()),
        "screen_two_plus": int((rs["flag_count"] >= 2).sum()),
        "screen_total_flags": int(rs[[f[0] for f in RISK_FLAGS]].values.sum()),
        "screen_top_bank": str(rs.iloc[0]["bank"]),
        "screen_top_flags": int(rs.iloc[0]["flag_count"]),
        "cre_over_300_latest": int(t["banks_cre_over_300"].iloc[-1]),
        "cre_over_300_peak": int(t["banks_cre_over_300"].max()),
        "cre_over_300_peak_date": str(t["banks_cre_over_300"].idxmax().date()),
        "nco_cre_high": float(cc.loc["Over 300%", "nco_rate"]),
        "nco_cre_low": float(cc.loc["Under 200%", "nco_rate"]),
        "liability_sensitive": int((b["nim_per_100bp"] < 0).sum()),
        "nim_per_100bp_median": float(b["nim_per_100bp"].median()),
        "most_exposed_bank": str(worst["bank"]),
        "most_exposed_nim_per_100bp": float(worst["nim_per_100bp"]),
        "flagstar_nii_per_100bp": float(rate_exposure().set_index("bank").loc["Flagstar Bank", "nii_per_100bp_musd"]),
        "fed_funds_latest": float(d.rates().iloc[-1]["fed_funds"]),
    }
