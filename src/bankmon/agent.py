"""Bank analyst assistant: plans tool calls, runs them, and answers only from their results.

Offline mode (default): a deterministic planner maps the question to one governed tool (banks, metric, size band and direction
resolved from the text) and templates write the answer. LLM mode (LLM_BASE_URL + LLM_MODEL set): the model picks tools through
OpenAI-style function calling (max 4 rounds); a grounding check rejects any number not present in the tool results and falls
back to the template answer.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from . import data as d
from . import llm
from . import metrics as m
from .tools import TOOL_SPECS, TOOLS, UNITS, resolve_banks, resolve_metric, resolve_size_band

LESSONS = re.compile(r"\b(svb|silicon valley|signature|first republic|2023|fail\w*|collaps\w*|bank runs?|run on|early[- ]warning|lessons?"
                     r"|could (it|this|they) happen again|spotted|predicted?)\b", re.I)
BETA = re.compile(r"\b(betas?|pass(ed|es)? (through|on)|pass-through|repric\w*|what drove deposit costs?|why did deposit costs?"
                  r"|depositors? (got|get|were paid))\b", re.I)
RATE = re.compile(r"\b(rising rates|rates (rise|go up|keep rising|increase)|higher rates|rate (sensitiv\w*|exposure|risk)|\+?100 ?bp"
                  r"|exposed to (rates|rate|higher|rising)|liability[- ]sensitive|asset[- ]sensitive|higher for longer|new (rate )?hikes"
                  r"|rate hikes? (now|resum\w*|again)|if the fed (hikes|raises))\b", re.I)
CRE = re.compile(r"\b(cre|commercial real estate|office|300%|construction)\b", re.I)
RISK = re.compile(r"\b(risk\w*|flag\w*|watch ?list|worr\w*|danger\w*|trouble\w*|weak\w*|stress\w*|fragile|safe|vulnerab\w*|red flags?"
                  r"|concern\w*|next svb)\b", re.I)
TREND = re.compile(r"\b(trend\w*|over time|history|historical|since 2019|how has|changed?|path|year by year|over the (cycle|years))\b", re.I)
RANK = re.compile(r"\b(best|worst|top|bottom|highest|lowest|most|least|largest|biggest|smallest|rank\w*|leaders?|laggards?|which banks?"
                  r"|who (has|pays|is)|cheapest|strongest|weakest)\b", re.I)
HIGH = re.compile(r"\b(highest|most|largest|biggest|top|max\w*|greatest|heaviest|strongest)\b", re.I)
LOW = re.compile(r"\b(lowest|least|smallest|fewest|min\w*|cheapest|bottom)\b", re.I)
OVERVIEW = re.compile(r"\b(overview|big picture|summary|summar\w*|state of|how are (the )?(regional )?banks|sector|industry|peer group)\b", re.I)


@dataclass
class Answer:
    question: str
    text: str
    calls: list[dict] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)
    mode: str = "offline"
    grounded: bool = True
    ungrounded: list[str] = field(default_factory=list)


def _order(q: str, metric: str) -> str:
    if re.search(r"\b(worst|weakest|laggards?|bottom)\b", q, re.I):
        return "worst"
    if re.search(r"\b(best|strongest|leaders?)\b", q, re.I):
        return "best"
    lower = metric in m.LOWER_IS_BETTER
    if metric == "assets":
        return "worst" if LOW.search(q) else "best"
    if HIGH.search(q):
        return "worst" if lower else "best"
    if LOW.search(q):
        return "best" if lower else "worst"
    return "best"


def plan(question: str) -> list[dict]:
    q = question
    certs = resolve_banks(q)
    failed = [c for c in certs if c in d.FAILED]
    live = [d.institutions().set_index("CERT").loc[c, "short"] for c in certs if c not in d.FAILED]
    metric = resolve_metric(q)
    band = resolve_size_band(q)
    if failed or (LESSONS.search(q) and not live):
        return [{"tool": "lessons_2023", "args": {}}]
    if len(live) >= 2:
        return [{"tool": "compare_banks", "args": {"banks": live[:5]}}]
    if len(live) == 1:
        b = live[0]
        if RATE.search(q) or metric == "nim_per_100bp":
            return [{"tool": "rate_exposure", "args": {"bank": b}}]
        if TREND.search(q):
            return [{"tool": "bank_trend", "args": {"bank": b, "metric": metric or "nim"}}]
        if re.search(r"\bflags?\b|watch ?list", q, re.I):
            return [{"tool": "risk_screen", "args": {"bank": b}}]
        return [{"tool": "bank_profile", "args": {"bank": b}}]
    if RATE.search(q) or metric == "nim_per_100bp":
        return [{"tool": "rate_exposure", "args": {}}]
    if BETA.search(q) and not (RANK.search(q) and re.search(r"\b(which|who|banks?)\b", q, re.I) and metric == "up_beta"
                               and re.search(r"\b(highest|lowest|most|least|top|worst|best)\b", q, re.I)):
        return [{"tool": "deposit_betas", "args": {}}]
    if metric and RANK.search(q) and not (metric == "cre_concentration" and not HIGH.search(q) and not LOW.search(q)
                                          and not re.search(r"\b(best|worst|top|rank)", q, re.I)):
        return [{"tool": "rank_banks", "args": {"metric": metric, "order": _order(q, metric), **({"size_band": band} if band else {})}}]
    if CRE.search(q) or metric in ("cre_concentration", "construction_concentration"):
        return [{"tool": "cre_credit", "args": {}}]
    if RISK.search(q):
        return [{"tool": "risk_screen", "args": {}}]
    if metric and metric not in ("assets",):
        return [{"tool": "rank_banks", "args": {"metric": metric, "order": _order(q, metric), **({"size_band": band} if band else {})}}]
    return [{"tool": "peer_overview", "args": {}}]


def _u(v, unit: str = "%") -> str:
    if v is None:
        return "n/a"
    if unit == "%":
        return f"{v}%"
    if unit == " $B":
        return f"${v}B"
    return f"{v}{unit}"


def _money(v) -> str:
    return f"-${abs(v)}M" if v < 0 else f"${v}M"


def _p(v) -> str:
    return "p < 0.001" if v == 0 else f"p = {v}"


def _unit(metric: str) -> str:
    return UNITS.get(metric, "%")


def _render(call: dict, r: dict) -> str:  # noqa: C901 - one template per tool
    t = call["tool"]
    if "error" in r:
        return f"I could not answer that from the data: {r['error']}."
    if t == "peer_overview":
        bands = ", ".join(f"{v} in {k}" for k, v in r["size_bands"].items())
        return (f"{r['banks']} US regional banks with $10-250B of assets ({bands}; ${r['assets_trillion']}T in total), {r['quarter']}:\n"
                f"- Median net interest margin {r['median_nim']}%, up from a low of {r['median_nim_trough']}% in {r['nim_trough_quarter']}.\n"
                f"- Median cost of deposits {r['median_deposit_cost']}%, down from a peak of {r['median_deposit_cost_peak']}%.\n"
                f"- The median bank passed {r['median_deposit_beta']} of each point of Fed hikes on to depositors (deposit beta).\n"
                f"- Median CET1 ratio {r['median_cet1']}%; median uninsured deposits {r['median_uninsured']}%.\n"
                f"- {r['banks_no_flags']} banks raise no risk flag; {r['banks_two_plus_flags']} raise two or more.\n"
                f"Fed funds averaged {r['fed_funds_q2_2026']}% in Q2 2026 and {r['fed_funds_latest']}% in {r['fed_funds_latest_month']}. "
                f"Source: {r['source']}.")
    if t == "bank_profile":
        mt = r["metrics"]
        rows = "\n".join(f"- {v['label']}: {v['value']} (peer median {v['peer_median']}; rank {v['rank']} of {v['of']})"
                         for v in mt.values())
        flags = ("no risk flags" if not r["flags"] else f"{r['flag_count']} risk flag{'s' if r['flag_count'] > 1 else ''}: "
                 + "; ".join(r["flags"]))
        sens = "loses" if r["nim_per_100bp"] < 0 else "gains"
        return (f"{r['bank']} ({r['state']}, ${r['assets_bn']}B, {r['size_band']}), {r['quarter']}: {flags}. Deposit beta "
                f"{r['deposit_beta_hikes']} in the 2022-24 hikes (peer median {r['peer_median_beta']}); on its own history it {sens} "
                f"{abs(r['nim_per_100bp'])} points of margin per +100bp. Overall scorecard {r['overall_score']} of 100 (rank 1 = best "
                f"in each line below).\n{rows}")
    if t == "compare_banks":
        lab = r["labels"]
        head = "| | " + " | ".join(b["bank"] for b in r["banks"]) + " | Peer median |"
        sep = "|---" * (len(r["banks"]) + 2) + "|"
        rows = [f"| {label} | " + " | ".join("n/a" if b[k] is None else str(b[k]) for b in r["banks"]) +
                f" | {'n/a' if r['peer_median'][k] is None else r['peer_median'][k]} |" for k, label in lab.items()]
        rows.append("| Risk flags (of 7) | " + " | ".join(str(b["flags"]) for b in r["banks"]) + " | |")
        best = max(r["banks"], key=lambda b: -1e9 if b["nim"] is None else b["nim"])
        return (f"{r['quarter']}. {best['bank']} has the widest net interest margin ({best['nim']}%).\n\n" + "\n".join([head, sep, *rows]))
    if t == "rank_banks":
        unit = _unit(r["metric_key"])
        rows = ", ".join(f"{b['bank']} {_u(b['value'], unit)}" for b in r["banks"])
        high = (r["order"] == "worst") == r["lower_is_better"]
        word = ("Highest" if high else "Lowest") + (" (best)" if r["order"] == "best" else " (weakest)")
        if r["metric_key"] == "assets":
            word = "Largest" if r["order"] == "best" else "Smallest"
        note = " (lower is better)" if r["lower_is_better"] else ""
        return (f"{r['metric']}{note}, {r['quarter']}, {r['scope']}. {word}: {rows}. Peer median {_u(r['peer_median'], unit)} across "
                f"{r['count']} banks.")
    if t == "deposit_betas":
        drv = "; ".join(f"{x['trait']} rho {x['rho']} ({_p(x['p_value'])})" for x in r["drivers"])
        terc = "; ".join(f"{x['group']} ({x['banks']} banks, loans/deposits {x['loan_to_deposit']}%): beta {x['beta']}, NIM change "
                         f"{x['nim_change']:+} points" for x in r["by_loan_to_deposit"])
        return (f"Over the hiking cycle, {r['cycle']}, the median bank passed {r['median_beta']} of each point of Fed hikes to depositors "
                f"(middle half {r['beta_q1']} to {r['beta_q3']}); on the way down the median beta is {r['median_beta_cuts']}. Median "
                f"deposit costs peaked at {r['deposit_cost_peak']}% and are {r['deposit_cost_latest']}% now.\n"
                f"What drove it (rank correlation with traits at the start of the cycle): {drv}.\n"
                f"Banks that had lent out more of their deposits paid up the most: {terc}.")
    if t == "lessons_2023":
        c = r["comparison"]

        def line(k):
            v = c[k]
            return (f"- {v['label']}: SVB {v['SVB']}, Signature {v['Signature']}, First Republic {v['First Republic']}; "
                    f"survivor median {v['peer_median']}")
        run = r["first_republic_run"]
        two = ", ".join(r["survivors_two_names"]) or "none"
        return (f"At {r['as_of']}:\n" + "\n".join(line(k) for k in c) + "\n"
                f"Screen ({'; '.join(r['rules'])}): {r['failed_all_three']} of 3 failures tripped all three rules and "
                f"{r['survivors_all_three']} surviving banks did; {r['survivors_two']} survivors tripped two ({two}). Securities losses "
                f"alone did not separate them: {r['survivors_losses_worse_than_signature']} survivors had deeper losses relative to "
                f"capital than Signature. The thresholds were set with hindsight, so I tested {r['grid_settings']} settings: "
                f"{r['grid_all_caught']} catch all three failures and none flags more than {r['grid_max_survivors']} survivor.\n"
                f"First Republic's deposits fell from ${run['deposits_q4_2022_bn']}B to ${run['deposits_q1_2023_bn']}B "
                f"({run['change_pct']}%) in Q1 2023 while FHLB borrowing rose from {run['fhlb_to_assets_q4_2022']}% to "
                f"{run['fhlb_to_assets_q1_2023']}% of assets.")
    if t == "risk_screen":
        if "bank" in r:
            b = r["bank"]
            if not b["reasons"]:
                return f"{b['bank']} raises none of the seven risk flags in {r['quarter']}."
            return (f"{b['bank']} raises {b['flags']} of the seven risk flags in {r['quarter']}: " + "; ".join(b["reasons"]) + ".")
        counts = "; ".join(f"{x['flag']}: {x['banks']}" for x in r["flag_counts"])
        watch = "\n".join(f"- {x['bank']} (${x['assets_bn']}B): {x['flags']} flags ({'; '.join(x['reasons'])})" for x in r["watch_list"])
        return (f"Risk screen, {r['quarter']}: {r['banks_no_flags']} banks raise no flag and {r['banks_two_plus']} raise two or more.\n"
                f"Banks per flag: {counts}.\nWatch list:\n{watch}\nA flag is a prompt to look closer, not a verdict.")
    if t == "cre_credit":
        top = ", ".join(f"{x['bank']} {x['cre_concentration']}%" for x in r["most_concentrated"])
        bands = "; ".join(f"{x['band']} ({x['banks']} banks): net charge-offs {x['nco_rate']}%, noncurrent {x['noncurrent_rate']}%"
                          for x in r["nco_by_band_since_2024"])
        return (f"{r['banks_over_300']} banks hold CRE above 300% of capital in {r['quarter']}, down from {r['peak_over_300']} in "
                f"{r['peak_quarter']} (median {r['median_cre_concentration']}%). Most concentrated: {top}.\n"
                f"Credit since 2024 by concentration band: {bands}. So far the concentrated banks have not lost more, but {r['caveat']}.")
    if t == "rate_exposure":
        if "bank" in r:
            b = r["bank"]
            verb = "loses" if b["nim_per_100bp"] < 0 else "gains"
            return (f"{b['bank']} {verb} {abs(b['nim_per_100bp'])} points of net interest margin per +100bp on its own 2022-24 history "
                    f"(asset-yield beta {b['yield_beta']} vs funding-cost beta {b['funding_beta']}), about {_money(b['nii_per_100bp_musd'])} of "
                    f"net interest income a year. It ranks {b['rank_most_exposed']} of {b['of']} (1 = most exposed); NIM is "
                    f"{b['nim_latest']}% now. Across the peer group {r['banks_losing_margin']} banks lose margin when rates rise "
                    f"(median {r['median_nim_per_100bp']:+} points). Fed funds averaged {r['fed_funds_latest']}% in {r['fed_funds_latest_month']}.")
        worst = ", ".join(f"{x['bank']} {x['nim_per_100bp']} pp ({_money(x['nii_per_100bp_musd'])})" for x in r["most_exposed"])
        best = ", ".join(f"{x['bank']} {x['nim_per_100bp']:+} pp" for x in r["most_asset_sensitive"])
        return (f"{r['banks_losing_margin']} banks lose margin when rates rise ({r['basis']}; median {r['median_nim_per_100bp']:+} "
                f"points per +100bp). Most exposed, NIM change and net interest income per +100bp: {worst}. Biggest gainers: {best}. "
                f"This matters again: Fed funds averaged {r['fed_funds_latest']}% in {r['fed_funds_latest_month']}.")
    if t == "bank_trend":
        unit = _unit(r["metric_key"])
        rows = ", ".join(f"{x['quarter']} {_u(x['value'], unit)}" for x in r["series"])
        f, la = r["first"], r["latest"]
        return (f"{r['bank']}, {r['metric'].lower()}: {rows}. Peer median went from {_u(f['peer_median'], unit)} in {f['quarter']} to "
                f"{_u(la['peer_median'], unit)} in {la['quarter']}.")
    return json.dumps(r)


_NUM = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?(?:e-?\d+)?")


def _norm(t: str) -> str:
    t = t.replace(",", "").lstrip("-+")
    if "e" in t.lower():
        return f"{float(t):.1e}"
    return t.rstrip("0").rstrip(".") if "." in t else t


def _numbers(obj) -> set[str]:
    out: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out |= _numbers(v) | _numbers(k)
    elif isinstance(obj, list):
        for v in obj:
            out |= _numbers(v)
    elif isinstance(obj, bool) or obj is None:
        pass
    elif isinstance(obj, (int, float)):
        x = float(obj)
        for s in (f"{x:g}", f"{x:.1f}", f"{x:.0f}", f"{x:.2f}", f"{x:.3f}", f"{abs(x):g}", f"{abs(x):.2f}"):
            out.add(_norm(s))
    elif isinstance(obj, str):
        out |= {_norm(mm.group(0)) for mm in _NUM.finditer(obj)}
    return out


# "+100bp", "seven flags", "rank 1", "two or more", "all three", the 101-bank peer group, 2022-24 hiking cycle, the 10-250 size range
ALLOWED_CONSTANTS = {"0.001", "100", "1", "2", "3", "7", "101", "2022", "24", "2023", "2024", "10", "250"}


def check_grounding(text: str, results: list[dict]) -> list[str]:
    allowed = set().union(*[_numbers(r) for r in results]) if results else set()
    return [mm.group(0) for mm in _NUM.finditer(text) if _norm(mm.group(0)) not in allowed | ALLOWED_CONSTANTS]


def run(calls: list[dict]) -> list[dict]:
    return [TOOLS[c["tool"]](**c["args"]) for c in calls]


SYSTEM = ("You are a bank analyst assistant covering 101 US regional banks ($10-250B of assets) from FDIC call reports, Q1 2019 to "
          "Q2 2026, plus SVB, Signature and First Republic as a 2023 case study. Use the tools to get facts, then answer in 2-6 "
          "sentences, bullets or a small table. Use ONLY numbers returned by the tools, copied exactly; do not compute new numbers. "
          "A risk flag is a prompt to look closer, not a verdict; do not give investment advice.")


def ask(question: str) -> Answer:
    if not llm.enabled():
        calls = plan(question)
        results = run(calls)
        text = "\n\n".join(_render(c, r) for c, r in zip(calls, results))
        bad = check_grounding(text, results)
        return Answer(question, text, calls, results, "offline", not bad, bad)
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    calls, results, msg = [], [], {}
    try:
        for _ in range(4):
            msg = llm.chat(msgs, tools=TOOL_SPECS)
            msgs.append(msg)
            if not msg.get("tool_calls"):
                break
            for tc in msg["tool_calls"]:
                name, args = tc["function"]["name"], json.loads(tc["function"].get("arguments") or "{}")
                res = TOOLS[name](**args) if name in TOOLS else {"error": f"unknown tool {name}"}
                calls.append({"tool": name, "args": args})
                results.append(res)
                msgs.append({"role": "tool", "tool_call_id": tc.get("id", name), "content": json.dumps(res)})
    except Exception:  # noqa: BLE001 - any endpoint failure falls back to the governed offline answer
        msg = {}
    text = (msg.get("content") or "").strip()
    bad = check_grounding(text, results)
    if text and results and not bad:
        return Answer(question, text, calls, results, "llm")
    calls = calls or plan(question)
    results = results or run(calls)
    fallback = "\n\n".join(_render(c, r) for c, r in zip(calls, results))
    return Answer(question, fallback, calls, results, "llm-fallback", True, bad)


# ------------------------------------------------------------------ one-page bank brief
def _size_peers(bank: str, k: int = 2) -> list[str]:
    s = d.snapshot()
    cert = resolve_banks(bank)[0]
    near = (s["assets"] - s.loc[cert, "assets"]).abs().sort_values()
    return [s.loc[c, "short"] for c in near.index if c != cert][:k]


def brief_results(bank: str) -> list[dict]:
    peers = _size_peers(bank)
    return [TOOLS["bank_profile"](bank), TOOLS["bank_trend"](bank, "nim"), TOOLS["bank_trend"](bank, "deposit_cost"),
            TOOLS["rate_exposure"](bank), TOOLS["compare_banks"]([bank, *peers]), TOOLS["deposit_betas"]()]


def bank_brief(bank: str) -> str:
    """One-page note for a credit analyst, treasurer or investor, built only from tool results."""
    prof, nim, dc, rx, comp, beta = brief_results(bank)
    if "error" in prof:
        return f"I could not build a brief: {prof['error']}."
    mt = prof["metrics"]
    rows = "\n".join(f"| {v['label']} | {v['value']} | {v['peer_median']} | {v['rank']} of {v['of']} |" for v in mt.values())
    b = rx["bank"]
    beta_view = "above" if prof["deposit_beta_hikes"] > prof["peer_median_beta"] else "at or below"
    flags = ("No risk flags." if not prof["flags"] else f"**Risk flags ({prof['flag_count']}):** {'; '.join(prof['flags'])}.")
    peer_names = ", ".join(x["bank"] for x in comp.get("banks", [])[1:])
    verb = "loses" if b["nim_per_100bp"] < 0 else "gains"
    lines = [
        f"### {prof['bank']}: {prof['quarter']} peer brief",
        f"**{prof['bank']}** ({prof['state']}, ${prof['assets_bn']}B, {prof['size_band']}) earns a {mt['nim']['value']}% net interest "
        f"margin against a peer median of {mt['nim']['peer_median']}% (rank {mt['nim']['rank']} of {mt['nim']['of']}). "
        f"Overall scorecard {prof['overall_score']} of 100.", "",
        "| Metric | Bank | Peer median | Rank (1 = best) |", "|---|---|---|---|", rows, "",
        f"**Funding through the cycle:** deposit beta {prof['deposit_beta_hikes']} in the 2022-24 hikes, {beta_view} the peer median of "
        f"{prof['peer_median_beta']}. Cost of deposits went from {dc['first']['value']}% in {dc['first']['quarter']} to "
        f"{dc['latest']['value']}% in {dc['latest']['quarter']} (peer median {dc['latest']['peer_median']}%). NIM moved from "
        f"{nim['first']['value']}% to {nim['latest']['value']}% over the same span.", "",
        f"**If rates keep rising:** on its own history the bank {verb} {abs(b['nim_per_100bp'])} points of margin per +100bp, about "
        f"{_money(b['nii_per_100bp_musd'])} of net interest income a year (rank {b['rank_most_exposed']} of {b['of']}, 1 = most exposed). "
        f"Fed funds averaged {rx['fed_funds_latest']}% in {rx['fed_funds_latest_month']}.", "",
        f"**What to watch:** {flags} Across the peer group, loan-heavy funding was one of the two strongest drivers of deposit costs "
        f"(rho {beta['drivers'][0]['rho']}).", "",
        f"_Nearest peers by size: {peer_names or 'none'}. Source: FDIC call reports (insured-bank level, not the holding company)._"]
    return "\n".join(lines)
