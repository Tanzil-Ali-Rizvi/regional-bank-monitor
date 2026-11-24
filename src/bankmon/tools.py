"""Governed tools for the bank analyst assistant. Each returns a small JSON-safe dict of rounded facts from metrics.py.

The assistant may only quote numbers that appear in these results (see agent.check_grounding).
"""
from __future__ import annotations

import re
from functools import lru_cache

import pandas as pd

from . import data as d
from . import metrics as m

METRIC_ALIASES = {
    "nim": ["net interest margin", "nim", "margin", "margins", "spread income"],
    "deposit_cost": ["cost of deposits", "deposit cost", "deposit costs", "deposit rate", "paying for deposits", "pays for deposits",
                     "pay for deposits", "most for deposits", "least for deposits", "for deposits",
                     "expensive deposits", "cheapest deposits", "cheap deposits", "funding cost"],
    "cost_of_funds": ["cost of funds"],
    "uninsured_share": ["uninsured deposits", "uninsured", "run risk", "flight-prone", "flighty deposits"],
    "loan_to_deposit": ["loan-to-deposit", "loan to deposit", "loans to deposits", "loans / deposits", "loan/deposit", "ltd ratio",
                        "loan-heavy", "lends the most"],
    "brokered_share": ["brokered deposits", "brokered", "hot money"],
    "fhlb_to_assets": ["fhlb", "home loan bank", "wholesale borrowing", "advances"],
    "cre_concentration": ["commercial real estate", "cre", "real estate concentration", "office exposure", "office loans", "office"],
    "construction_concentration": ["construction"],
    "unrealized_to_tier1": ["unrealized loss", "unrealized losses", "securities losses", "underwater bonds", "bond losses", "aoci",
                            "htm losses", "mark-to-market"],
    "cet1_marked": ["cet1 after securities losses", "marked cet1", "marked capital", "capital after losses", "true capital"],
    "cet1_ratio": ["cet1", "capital ratio", "capital", "best capitalized", "well capitalized", "capitalised", "capitalized"],
    "leverage_ratio": ["leverage ratio", "tier 1 leverage"],
    "uninsured_coverage": ["liquidity", "liquid", "cash and securities", "coverage of uninsured"],
    "roa": ["return on assets", "roa", "most profitable", "profitability", "profitable", "returns"],
    "roe": ["return on equity", "roe"],
    "efficiency": ["efficiency ratio", "efficiency", "cost-to-income", "cost to income", "efficient", "overhead"],
    "nco_rate": ["net charge-offs", "charge-offs", "charge offs", "chargeoffs", "credit losses", "loan losses", "nco"],
    "noncurrent_rate": ["noncurrent", "non-current", "nonperforming", "non-performing", "past due", "bad loans", "problem loans"],
    "assets": ["total assets", "largest", "biggest", "smallest", "size"],
    "up_beta": ["deposit beta", "beta", "betas", "passed through", "pass-through", "pass through", "repriced"],
    "nim_per_100bp": ["rate sensitivity", "rate sensitive", "rising rates", "higher rates", "rates rise", "rate hikes", "+100bp",
                      "100bp", "liability sensitive", "asset sensitive", "rate exposure", "exposed to rates"],
}
BETA_METRICS = {"up_beta", "down_beta", "nim_per_100bp"}
UNITS = {"up_beta": "", "down_beta": "", "nim_per_100bp": " pp", "assets": " $B"}
EXTRA_BANK_ALIASES = {"svb": 24735, "silicon valley": 24735, "signature": 57053, "first republic": 59017, "frc": 59017,
                      "m&t": 588, "m and t": 588, "key": 17534, "keycorp": 17534, "ozk": 110, "zions": 2270, "flagstar": 32541,
                      "new york community": 32541, "nycb": 32541, "western alliance": 57512, "pacwest": 24045, "pacific western": 24045,
                      "east west": 31628, "cullen": 5510, "frost": 5510, "first horizon": 4977, "comerica": 983, "valley": 9396,
                      "synovus": 873, "webster": 18221, "wintrust": 33935}
GENERIC = {"first", "citizens", "national", "american", "united", "community", "central", "first national", "home", "peoples",
           "city", "state", "trust", "bank", "savings", "federal", "the", "commerce", "western", "southern", "northern", "eastern",
           "pacific", "atlantic", "merchants", "farmers", "liberty", "union", "capital", "associated", "independent"}


def _r(x, n=2):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    v = round(float(x), n)
    return int(v) if v == int(v) and abs(v) >= 10 else v


def _pct(x):
    return _r(x, 1) if x is not None and abs(float(x)) >= 10 else _r(x, 2)


def _bn(musd):
    return _r(float(musd) / 1000, 1)


@lru_cache(maxsize=1)
def bank_aliases() -> dict[str, int]:
    inst = d.institutions()
    out: dict[str, int] = {}
    for cert, short in zip(inst["CERT"], inst["short"]):
        name = short.lower()
        out[name] = int(cert)
        core = re.sub(r"\s*\((.*)\)$", "", name)
        core = re.sub(r"\b(bank|bank na|na|fsb|ssb|bank & trust|& trust|trust)\b", "", core).strip(" &,")
        if core and core not in GENERIC and len(core) >= 3 and not re.search(r"\(", name):
            out.setdefault(core, int(cert))
    for k, v in EXTRA_BANK_ALIASES.items():
        if v in set(inst["CERT"]):
            out[k] = v
    return out


def bank_name(cert: int) -> str:
    return str(d.institutions().set_index("CERT").loc[cert, "short"])


def resolve_banks(text: str) -> list[int]:
    low = text.lower()
    taken: list[tuple[int, int]] = []
    found: list[tuple[int, int]] = []
    for alias, cert in sorted(bank_aliases().items(), key=lambda kv: -len(kv[0])):
        for mm in re.finditer(r"(?<![\w&])" + re.escape(alias) + r"(?:'s)?(?![\w&])", low):
            s, e = mm.span()
            if any(s < te and e > ts for ts, te in taken):
                continue
            if alias == "key" and not re.search(r"\bkey\b(?!\s+(metric|driver|risk|number|figure|question|lesson|takeaway|ratio|point|factor))",
                                                low[s:e + 12]):
                continue
            if alias == "valley" and "silicon valley" in low:
                continue
            taken.append((s, e))
            found.append((s, cert))
    out: list[int] = []
    for _, c in sorted(found):
        if c not in out:
            out.append(c)
    return out


def resolve_metric(text: str) -> str | None:
    low = text.lower()
    best: tuple[int, int, str] | None = None
    for metric, aliases in METRIC_ALIASES.items():
        for a in aliases:
            mm = re.search(r"(?<![\w])" + re.escape(a) + r"(?![\w])", low)
            if mm and (best is None or len(a) > best[0] or (len(a) == best[0] and mm.start() < best[1])):
                best = (len(a), mm.start(), metric)
    return best[2] if best else None


def resolve_size_band(text: str) -> str | None:
    low = text.lower().replace(" ", "")
    for lo, hi, band in d.SIZE_BANDS:
        if band.lower().replace(" ", "") in low:
            return band
    if re.search(r"\b(smallest|small banks|smaller banks)\b", text, re.I):
        return "$10-20B"
    if re.search(r"\b(super-?regionals?|larger banks|large banks|big banks)\b", text, re.I):
        return "$100-250B"
    return None


def _label(metric: str) -> str:
    return m.LABELS.get(metric, metric).replace(" ($M)", " ($B)")


def _value(metric: str, v):
    if metric == "assets":
        return _bn(v)
    return _r(v, 2) if metric in BETA_METRICS else _pct(v)


def _bank_frame() -> pd.DataFrame:
    s = d.snapshot().copy()
    b = m.betas()
    for c in ["up_beta", "down_beta", "nim_per_100bp"]:
        s[c] = b[c]
    return s


# ------------------------------------------------------------------ tools
def peer_overview() -> dict:
    h = m.headline()
    s = d.snapshot()
    return {"quarter": "Q2 2026", "banks": h["banks"], "assets_trillion": _r(h["assets_trillion"], 2),
            "size_bands": {band: int((s["size_band"] == band).sum()) for _, _, band in d.SIZE_BANDS},
            "median_nim": _pct(h["nim_latest_median"]), "median_nim_trough": _pct(h["nim_trough_median"]),
            "nim_trough_quarter": "Q1 2022", "median_deposit_cost": _pct(h["deposit_cost_latest_median"]),
            "median_deposit_cost_peak": _pct(h["deposit_cost_peak_median"]), "median_cet1": _pct(m.median_of("cet1_ratio")),
            "median_uninsured": _pct(m.median_of("uninsured_share")), "median_deposit_beta": _r(h["beta_median"], 2),
            "banks_two_plus_flags": h["screen_two_plus"], "banks_no_flags": h["screen_zero"],
            "fed_funds_q2_2026": _r(d.rates().set_index("date").loc[pd.Timestamp(d.LATEST), "fed_funds"], 2),
            "fed_funds_latest": _r(h["fed_funds_latest"], 2), "fed_funds_latest_month": "October 2026",
            "source": "FDIC call reports (BankFind Suite), Q1 2019 to Q2 2026; FRED rates"}


def bank_profile(bank: str | int) -> dict:
    cert = _cert(bank)
    if cert is None:
        return {"error": f"'{bank}' is not one of the 101 peer banks"}
    if cert in d.FAILED:
        return {"error": f"{bank_name(cert)} failed in 2023; ask about the 2023 failures instead"}
    p = m.bank_profile(cert)
    mt = {k: {"label": m.LABELS[k], "value": _pct(v["value"]), "peer_median": _pct(v["peer_median"]), "rank": v["rank"], "of": 101}
          for k, v in p["metrics"].items()}
    sc = m.scorecard().loc[cert]
    return {"bank": p["bank"], "state": p["state"], "quarter": "Q2 2026", "assets_bn": _bn(p["assets"]), "size_band": p["size_band"],
            "metrics": mt, "deposit_beta_hikes": _r(p["up_beta"], 2), "deposit_beta_cuts": _r(p["down_beta"], 2),
            "peer_median_beta": _r(m.headline()["beta_median"], 2), "nim_per_100bp": _r(p["nim_per_100bp"], 2),
            "flags": p["flags"], "flag_count": len(p["flags"]), "overall_score": _r(sc["Overall"], 0) if sc["Overall"] >= 10 else _r(sc["Overall"], 1)}


def compare_banks(banks: list) -> dict:
    certs = [c for c in (_cert(b) for b in banks) if c is not None and c not in d.FAILED]
    if len(certs) < 2:
        return {"error": "name at least two of the 101 peer banks to compare"}
    f = _bank_frame()
    cols = ["assets", "nim", "deposit_cost", "up_beta", "uninsured_share", "loan_to_deposit", "cre_concentration", "cet1_ratio",
            "cet1_marked", "roa", "nim_per_100bp"]
    rows = []
    for c in certs[:5]:
        rows.append({"bank": bank_name(c), **{k: _value(k, f.loc[c, k]) for k in cols},
                     "flags": int(m.risk_screen().loc[c, "flag_count"])})
    med = {k: _value(k, f[k].median()) for k in cols}
    return {"quarter": "Q2 2026", "banks": rows, "peer_median": med, "labels": {k: _label(k) for k in cols}}


def rank_banks(metric: str = "nim", order: str = "best", n: int = 5, size_band: str | None = None) -> dict:
    if metric not in m.LABELS:
        return {"error": f"unknown metric '{metric}'"}
    f = _bank_frame()
    if size_band:
        f = f[f["size_band"] == size_band]
        if f.empty:
            return {"error": f"no banks in size band '{size_band}'"}
    lower = metric in m.LOWER_IS_BETTER
    asc = lower if order == "best" else not lower
    if metric == "assets":
        asc = order != "best"
    s = f[metric].dropna().sort_values(ascending=asc)
    n = max(1, min(int(n), 10))
    rows = [{"bank": f.loc[c, "short"], "value": _value(metric, v)} for c, v in s.head(n).items()]
    return {"metric": _label(metric), "metric_key": metric, "order": order, "lower_is_better": lower and metric != "assets",
            "quarter": "Q2 2026" if metric not in BETA_METRICS else "2022-24 rate cycle", "banks": rows,
            "peer_median": _value(metric, f[metric].median()), "count": int(s.size), "scope": size_band or "all 101 peer banks"}


def deposit_betas() -> dict:
    h = m.headline()
    drv = m.beta_drivers()
    t = m.beta_by_funding_need()
    return {"cycle": "Q4 2021 to Q2 2024 (Fed funds 0.08% to 5.33%)", "median_beta": _r(h["beta_median"], 2),
            "beta_q1": _r(h["beta_q1"], 2), "beta_q3": _r(h["beta_q3"], 2), "median_beta_cuts": _r(h["down_beta_median"], 2),
            "drivers": [{"trait": r.trait, "rho": _r(r.rho, 2), "p_value": _r(r.p_value, 3)} for r in drv.itertuples()],
            "by_loan_to_deposit": [{"group": str(r.ltd_tercile), "banks": int(r.banks), "loan_to_deposit": _pct(r.loan_to_deposit),
                                    "beta": _r(r.up_beta, 2), "nim_change": _r(r.nim_change_cycle, 2)} for r in t.itertuples()],
            "deposit_cost_peak": _pct(h["deposit_cost_peak_median"]), "deposit_cost_latest": _pct(h["deposit_cost_latest_median"])}


def lessons_2023() -> dict:
    h = m.headline()
    fvp = m.failed_vs_peers().set_index("column")
    ew = m.early_warning()
    two = ew[(~ew["failed"]) & (ew["flag_count"] == 2)]["bank"].tolist()
    rows = {}
    for col in ["uninsured_share", "deposit_growth", "cet1_marked", "unrealized_to_tier1"]:
        rows[col] = {"label": fvp.loc[col, "metric"], "peer_median": _pct(fvp.loc[col, "peer_median"]),
                     **{s: _pct(fvp.loc[col, s]) for s in d.FAILED_SHORT.values()}}
    run = _frc_run()
    return {"as_of": "Q4 2022, the last call report before the March 2023 failures", "comparison": rows,
            "rules": [e[0] for e in m.EARLY_WARNING], "failed_all_three": h["ew_failed_all_three"],
            "survivors_all_three": h["ew_survivors_all_three"], "survivors_two": h["ew_survivors_two"], "survivors_two_names": two,
            "survivors_losses_worse_than_signature": h["survivors_unrealized_worse_than_signature"],
            "grid_settings": h["ew_grid"], "grid_all_caught": h["ew_grid_all_caught"], "grid_max_survivors": h["ew_grid_max_survivors"],
            "first_republic_run": run}


def _frc_run() -> dict:
    p = d.panel()
    f = p[p["cert"] == 59017].set_index("date")
    a, b = f.loc[pd.Timestamp("2022-12-31")], f.loc[pd.Timestamp("2023-03-31")]
    return {"deposits_q4_2022_bn": _bn(a["deposits"]), "deposits_q1_2023_bn": _bn(b["deposits"]),
            "change_pct": _r(100 * (b["deposits"] / a["deposits"] - 1), 0),
            "fhlb_to_assets_q4_2022": _pct(a["fhlb_to_assets"]), "fhlb_to_assets_q1_2023": _pct(b["fhlb_to_assets"])}


def risk_screen(bank: str | int | None = None) -> dict:
    rs = m.risk_screen()
    labels = [f[0] for f in m.RISK_FLAGS]
    out = {"quarter": "Q2 2026", "rules": [f"{f[0]} ({f[4]})" for f in m.RISK_FLAGS],
           "flag_counts": [{"flag": r.flag, "banks": r.banks} for r in m.flag_counts().itertuples()],
           "banks_no_flags": int((rs["flag_count"] == 0).sum()), "banks_two_plus": int((rs["flag_count"] >= 2).sum()),
           "watch_list": [{"bank": r["bank"], "flags": int(r["flag_count"]), "assets_bn": _bn(r["assets"]),
                           "reasons": [lab for lab in labels if bool(r[lab])]} for _, r in rs[rs["flag_count"] >= 2].iterrows()]}
    if bank is not None:
        cert = _cert(bank)
        if cert is None or cert not in rs.index:
            return {"error": f"'{bank}' is not one of the 101 peer banks"}
        r = rs.loc[cert]
        out["bank"] = {"bank": r["bank"], "flags": int(r["flag_count"]), "reasons": [lab for lab in labels if bool(r[lab])]}
    return out


def cre_credit() -> dict:
    h = m.headline()
    cc = m.cre_credit()
    s = d.snapshot().sort_values("cre_concentration", ascending=False)
    return {"quarter": "Q2 2026", "banks_over_300": h["cre_over_300_latest"], "peak_over_300": h["cre_over_300_peak"],
            "peak_quarter": "Q1 2024", "median_cre_concentration": _pct(m.median_of("cre_concentration")),
            "most_concentrated": [{"bank": r["short"], "cre_concentration": _pct(r["cre_concentration"]), "nco_rate": _pct(r["nco_rate"]),
                                   "noncurrent_rate": _pct(r["noncurrent_rate"])} for _, r in s.head(5).iterrows()],
            "nco_by_band_since_2024": [{"band": str(r.band), "banks": int(r.banks), "nco_rate": _pct(r.nco_rate),
                                        "noncurrent_rate": _pct(r.noncurrent_rate)} for r in cc.itertuples()],
            "caveat": "office loans are not reported separately in the call report, and CRE losses lag"}


def rate_exposure(bank: str | int | None = None) -> dict:
    h = m.headline()
    rx = m.rate_exposure()
    out = {"basis": "asset-yield beta minus funding-cost beta over the 2022-24 hiking cycle",
           "banks_losing_margin": h["liability_sensitive"], "median_nim_per_100bp": _r(h["nim_per_100bp_median"], 2),
           "most_exposed": [{"bank": r.bank, "nim_per_100bp": _r(r.nim_per_100bp, 2), "nii_per_100bp_musd": _r(r.nii_per_100bp_musd, 0)}
                            for r in rx.head(5).itertuples()],
           "most_asset_sensitive": [{"bank": r.bank, "nim_per_100bp": _r(r.nim_per_100bp, 2)} for r in rx.tail(3).iloc[::-1].itertuples()],
           "fed_funds_latest": _r(h["fed_funds_latest"], 2), "fed_funds_latest_month": "October 2026"}
    if bank is not None:
        cert = _cert(bank)
        if cert is None or cert not in rx.index:
            return {"error": f"'{bank}' is not one of the 101 peer banks"}
        r = rx.loc[cert]
        out["bank"] = {"bank": r["bank"], "nim_per_100bp": _r(r["nim_per_100bp"], 2), "nii_per_100bp_musd": _r(r["nii_per_100bp_musd"], 0),
                       "yield_beta": _r(r["yield_beta"], 2), "funding_beta": _r(r["funding_beta"], 2), "nim_latest": _pct(r["nim_latest"]),
                       "rank_most_exposed": int(list(rx.index).index(cert)) + 1, "of": int(len(rx))}
    return out


def bank_trend(bank: str | int, metric: str = "nim") -> dict:
    cert = _cert(bank)
    if cert is None:
        return {"error": f"'{bank}' is not one of the 101 peer banks"}
    if metric in BETA_METRICS or metric not in m.LABELS:
        metric = "nim"
    ser = d.series(cert)
    t = m.trends()
    keep = [pd.Timestamp(x) for x in ["2019-12-31", "2020-12-31", "2021-12-31", "2022-12-31", "2023-12-31", "2024-12-31", "2025-12-31",
                                      d.LATEST]]
    rows = []
    for q in keep:
        if q in ser.index:
            peers = d.peers()
            pm = t[metric].get(q) if metric in t.columns else peers[peers["date"] == q][metric].median()
            rows.append({"quarter": f"Q{q.quarter} {q.year}", "value": _value(metric, ser.loc[q, metric]), "peer_median": _value(metric, pm)})
    if not rows:
        return {"error": f"no history for {bank_name(cert)}"}
    return {"bank": bank_name(cert), "metric": _label(metric), "metric_key": metric, "series": rows, "first": rows[0], "latest": rows[-1]}


def _cert(bank) -> int | None:
    if bank is None:
        return None
    if isinstance(bank, (int,)) or (isinstance(bank, str) and bank.isdigit()):
        c = int(bank)
        return c if c in set(d.institutions()["CERT"]) else None
    found = resolve_banks(str(bank))
    return found[0] if found else None


TOOLS = {"peer_overview": peer_overview, "bank_profile": bank_profile, "compare_banks": compare_banks, "rank_banks": rank_banks,
         "deposit_betas": deposit_betas, "lessons_2023": lessons_2023, "risk_screen": risk_screen, "cre_credit": cre_credit,
         "rate_exposure": rate_exposure, "bank_trend": bank_trend}

_BANK = {"type": "string", "description": "Bank name, e.g. 'Flagstar Bank' or 'Zions'"}
_METRIC = {"type": "string", "enum": sorted(m.LABELS)}
TOOL_SPECS = [
    {"type": "function", "function": {"name": "peer_overview", "description": "Headline medians for the 101 US regional banks ($10-250B), Q2 2026.",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "bank_profile", "description": "One bank's twelve key ratios with peer median and rank, its deposit "
                                      "betas, rate sensitivity and risk flags.",
                                      "parameters": {"type": "object", "properties": {"bank": _BANK}, "required": ["bank"]}}},
    {"type": "function", "function": {"name": "compare_banks", "description": "Side-by-side key ratios for 2-5 banks plus the peer median.",
                                      "parameters": {"type": "object", "properties": {"banks": {"type": "array", "items": _BANK}},
                                                     "required": ["banks"]}}},
    {"type": "function", "function": {"name": "rank_banks", "description": "Best or worst banks on one metric, optionally within a size band.",
                                      "parameters": {"type": "object", "properties": {
                                          "metric": _METRIC, "order": {"type": "string", "enum": ["best", "worst"]},
                                          "n": {"type": "integer"}, "size_band": {"type": "string", "enum": [b[2] for b in d.SIZE_BANDS]}},
                                          "required": ["metric"]}}},
    {"type": "function", "function": {"name": "deposit_betas", "description": "How much of the 2022-24 Fed hikes banks passed to depositors, and why.",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "lessons_2023", "description": "SVB, Signature and First Republic against the 101 survivors at "
                                      "Q4 2022, and the early-warning screen.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "risk_screen", "description": "Today's seven-flag risk screen: counts per flag and the watch list; "
                                      "optionally one bank's flags.", "parameters": {"type": "object", "properties": {"bank": _BANK}}}},
    {"type": "function", "function": {"name": "cre_credit", "description": "CRE concentration against the 300% guidance and credit losses by band.",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "rate_exposure", "description": "Which banks lose margin when rates rise; optionally one bank.",
                                      "parameters": {"type": "object", "properties": {"bank": _BANK}}}},
    {"type": "function", "function": {"name": "bank_trend", "description": "One bank's metric at each year-end 2019-2025 and Q2 2026 vs the peer median.",
                                      "parameters": {"type": "object", "properties": {"bank": _BANK, "metric": _METRIC}, "required": ["bank"]}}},
]
