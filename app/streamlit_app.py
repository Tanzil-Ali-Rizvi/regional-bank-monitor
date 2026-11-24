"""Regional Bank Monitor: Streamlit front end (dark terminal style).

Run:  streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bankmon import agent, llm  # noqa: E402
from bankmon import data as d  # noqa: E402
from bankmon import metrics as m  # noqa: E402
from bankmon import tools as t  # noqa: E402

BG, PANEL, LINE, TEXT, MUTED = "#0A0E13", "#111821", "#223042", "#D7E0EA", "#7F8EA3"
AMBER, GREEN, RED, CYAN, VIOLET = "#FFB020", "#3DDC97", "#FF5C6C", "#4FC3F7", "#B39DFF"
BAND_COLOR = {"$10-20B": CYAN, "$20-50B": GREEN, "$50-100B": AMBER, "$100-250B": VIOLET}
EXCEL = ROOT / "excel" / "Regional_Bank_Rate_Scenario_Model.xlsx"
PBI_PDF = ROOT / "powerbi" / "Regional Bank Monitor.pdf"

st.set_page_config(page_title="Regional Bank Monitor", page_icon="🏦", layout="wide")
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;600&display=swap');
html, body, [class*="css"], .stMarkdown, p, li {{font-family: 'Inter', sans-serif;}}
.block-container {{padding-top: 3.6rem; max-width: 1320px;}}
h1, h2, h3, h4 {{font-family: 'JetBrains Mono', monospace !important; color: {TEXT}; letter-spacing: -.01em;}}
.bar {{display:flex; justify-content:space-between; align-items:center; border:1px solid {LINE}; background:{PANEL};
       padding:8px 14px; border-radius:6px; font-family:'JetBrains Mono', monospace; font-size:.78rem; color:{MUTED}; margin-bottom:14px;}}
.bar b {{color:{AMBER};}} .live {{color:{GREEN};}}
.hero h1 {{font-size:1.9rem; margin:0 0 4px 0;}} .hero p {{color:{MUTED}; margin:0 0 14px 0; max-width:1050px;}}
.tile {{background:{PANEL}; border:1px solid {LINE}; border-top:2px solid var(--c); border-radius:6px; padding:10px 14px; height:100%;}}
.tile .l {{font-family:'JetBrains Mono', monospace; font-size:.68rem; color:{MUTED}; text-transform:uppercase; letter-spacing:.08em;}}
.tile .v {{font-family:'JetBrains Mono', monospace; font-size:1.65rem; font-weight:700; color:var(--c); font-variant-numeric:tabular-nums;}}
.tile .s {{font-size:.76rem; color:{MUTED};}}
.callout {{border:1px solid {LINE}; border-left:3px solid {AMBER}; background:{PANEL}; padding:12px 16px; border-radius:6px; margin:6px 0 10px 0;}}
.callout b {{color:{AMBER};}}
.mono {{font-family:'JetBrains Mono', monospace; font-size:.8rem; color:{MUTED};}}
.stTabs [data-baseweb="tab"] {{font-family:'JetBrains Mono', monospace; font-size:.82rem;}}
.stTabs [aria-selected="true"] {{color:{AMBER} !important;}}
div[data-testid="stDataFrame"] {{border:1px solid {LINE}; border-radius:6px;}}
</style>""", unsafe_allow_html=True)


@st.cache_data
def tool(name: str, **kw):
    return t.TOOLS[name](**kw)


@st.cache_data
def trends() -> pd.DataFrame:
    return m.trends()


@st.cache_data
def betas() -> pd.DataFrame:
    return m.betas()


@st.cache_data
def snapshot() -> pd.DataFrame:
    return d.snapshot()


@st.cache_data
def crisis() -> pd.DataFrame:
    return m.crisis_snapshot()


@st.cache_data
def screen() -> pd.DataFrame:
    return m.risk_screen()


@st.cache_data
def exposure() -> pd.DataFrame:
    return m.rate_exposure()


@st.cache_data
def series(cert: int) -> pd.DataFrame:
    return d.series(cert)


def style(fig: go.Figure, title: str, height: int = 380, legend: bool = True) -> go.Figure:
    fig.update_layout(title=dict(text=title, font=dict(size=14, color=TEXT, family="JetBrains Mono, monospace"), x=0, xanchor="left"),
                      height=height, margin=dict(l=10, r=10, t=54, b=10), plot_bgcolor=PANEL, paper_bgcolor=PANEL,
                      font=dict(color=MUTED, size=12, family="Inter, sans-serif"), showlegend=legend,
                      legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom", bgcolor="rgba(0,0,0,0)"),
                      hoverlabel=dict(bgcolor=BG, font_color=TEXT, bordercolor=AMBER, font_family="JetBrains Mono"))
    fig.update_xaxes(showgrid=False, linecolor=LINE, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=LINE, zeroline=True, zerolinecolor=LINE, tickfont=dict(color=MUTED))
    return fig


def tile(col, label: str, value: str, sub: str = "", c: str = AMBER) -> None:
    col.markdown(f'<div class="tile" style="--c:{c}"><div class="l">{label}</div><div class="v">{value}</div><div class="s">{sub}</div></div>',
                 unsafe_allow_html=True)


def qlabel(ts) -> str:
    ts = pd.Timestamp(ts)
    return f"Q{ts.quarter} {ts.year}"


ov = tool("peer_overview")
beta = tool("deposit_betas")
less = tool("lessons_2023")
rsk = tool("risk_screen")
cre = tool("cre_credit")
rx = tool("rate_exposure")

st.markdown(f"""<div class="bar"><span><b>REGIONAL BANK MONITOR</b> · {ov['banks']} US banks · $10-250B · FDIC call reports Q1 2019 - {ov['quarter']}</span>
<span>FED FUNDS <b>{ov['fed_funds_latest']}%</b> ({ov['fed_funds_latest_month']}) · <span class="live">● rates rising again</span></span></div>
<div class="hero"><h1>Who pays up for deposits, who loses when rates rise, and what 2023 taught us</h1>
<p>Funding, rate and credit risk across {ov['banks']} US regional banks (${ov['assets_trillion']}T of assets), built from FDIC call reports with
SVB, Signature and First Republic kept as a case study. Every number on this page comes from the same governed tools the assistant uses.</p></div>""",
            unsafe_allow_html=True)

c = st.columns(5)
tile(c[0], "Median NIM", f"{ov['median_nim']}%", f"low {ov['median_nim_trough']}% in {ov['nim_trough_quarter']}", CYAN)
tile(c[1], "Median cost of deposits", f"{ov['median_deposit_cost']}%", f"peak {ov['median_deposit_cost_peak']}%", AMBER)
tile(c[2], "Median deposit beta", f"{ov['median_deposit_beta']}", "share of 2022-24 hikes passed on", GREEN)
tile(c[3], "Lose margin if rates rise", f"{rx['banks_losing_margin']}", f"of {ov['banks']} banks", RED)
tile(c[4], "Banks with 2+ risk flags", f"{ov['banks_two_plus_flags']}", f"{ov['banks_no_flags']} raise none", VIOLET)
st.write("")

tabs = st.tabs(["01 Overview", "02 Deposit betas", "03 Lessons from 2023", "04 Risk screen", "05 Bank brief", "06 Rate scenario",
                "07 Ask the analyst"])

# 01 overview ------------------------------------------------------------------------------------------------------------
with tabs[0]:
    tr = trends()
    x = [qlabel(i) for i in tr.index]
    fig = go.Figure()
    for col, name, colr, dash in [("nim", "Median NIM", CYAN, "solid"), ("deposit_cost", "Median cost of deposits", AMBER, "solid"),
                                  ("fed_funds", "Fed funds", RED, "dot")]:
        fig.add_trace(go.Scatter(x=x, y=tr[col], name=name, mode="lines", line=dict(color=colr, width=2.6, dash=dash, shape="spline"),
                                 hovertemplate="%{x}: %{y:.2f}%<extra>" + name + "</extra>"))
    st.plotly_chart(style(fig, "Margins bottomed in Q1 2022, deposit costs peaked in 2024 (%)", 400), width="stretch")
    a, b = st.columns([1.1, 1])
    a.markdown(f"""<div class="callout"><b>Read-out.</b> The median bank passed {beta['median_beta']} of each point of Fed hikes to depositors;
loan-heavy banks paid {beta['by_loan_to_deposit'][-1]['beta']} and their margins fell. Median NIM bottomed at {ov['median_nim_trough']}% and is
{ov['median_nim']}% now. {rx['banks_losing_margin']} banks lose margin when rates rise, and the Fed has resumed hiking
(Fed funds {ov['fed_funds_latest']}% in {ov['fed_funds_latest_month']}).</div>""", unsafe_allow_html=True)
    fig = go.Figure(go.Bar(x=tr.index.map(qlabel), y=tr["banks_cre_over_300"], marker_color=VIOLET,
                           hovertemplate="%{x}: %{y} banks<extra></extra>"))
    b.plotly_chart(style(fig, "Banks above the 300% CRE guidance", 260, legend=False), width="stretch")
    st.markdown('<div class="mono">Source: FDIC BankFind Suite call reports (insured-bank level) and FRED. Peer group: US-owned, '
                'deposit-funded banks with $10-250B of assets; card, custody, broker-sweep, foreign-owned and Puerto Rico banks excluded.</div>',
                unsafe_allow_html=True)

# 02 deposit betas -------------------------------------------------------------------------------------------------------
with tabs[1]:
    bt = betas().join(snapshot()[["size_band"]])
    fig = go.Figure()
    for band, colr in BAND_COLOR.items():
        s = bt[bt["size_band"] == band]
        fig.add_trace(go.Scatter(x=s["loan_to_deposit"], y=s["up_beta"], mode="markers", name=band, text=s["bank"],
                                 marker=dict(color=colr, size=9, opacity=.85, line=dict(color=BG, width=1)),
                                 hovertemplate="%{text}<br>loans/deposits %{x:.0f}%<br>beta %{y:.2f}<extra></extra>"))
    a, b = st.columns([1.35, 1])
    a.plotly_chart(style(fig, f"Banks that lent more of their deposits paid more for them (rho {beta['drivers'][0]['rho']})", 430),
                   width="stretch")
    terc = pd.DataFrame(beta["by_loan_to_deposit"])
    fig = go.Figure([go.Bar(x=terc["group"], y=terc["beta"], name="Deposit beta", marker_color=AMBER, text=terc["beta"], textposition="outside"),
                     go.Bar(x=terc["group"], y=terc["nim_change"], name="NIM change, pts", marker_color=CYAN, text=terc["nim_change"],
                            textposition="outside")])
    b.plotly_chart(style(fig, "By loans/deposits at the start of the cycle", 430), width="stretch")
    drv = pd.DataFrame(beta["drivers"]).rename(columns={"trait": "Trait at Q4 2021", "rho": "Rank correlation with beta", "p_value": "p-value"})
    st.dataframe(drv, hide_index=True, width="stretch")
    st.markdown(f"""<div class="callout"><b>So what.</b> Pricing power came from funding need, not from how many depositors were uninsured:
uninsured share did not predict betas (rho {beta['drivers'][3]['rho']}, p = {beta['drivers'][3]['p_value']}). On the way down the median beta
is {beta['median_beta_cuts']}, so deposit costs lag cuts as well as hikes.</div>""", unsafe_allow_html=True)

# 03 lessons from 2023 -----------------------------------------------------------------------------------------------------
with tabs[2]:
    cs = crisis()
    fig = go.Figure()
    for failed, colr, name, size in [(False, "#4B5D73", "101 survivors", 8), (True, RED, "Failed in 2023", 16)]:
        s = cs[cs["failed"] == failed]
        fig.add_trace(go.Scatter(x=s["uninsured_share"], y=s["cet1_marked"], mode="markers+text" if failed else "markers", name=name,
                                 text=s["short"], textposition="top center", textfont=dict(color=RED, family="JetBrains Mono"),
                                 marker=dict(color=colr, size=size, line=dict(color=BG, width=1)),
                                 hovertemplate="%{text}<br>uninsured %{x:.1f}%<br>marked CET1 %{y:.1f}%<extra></extra>"))
    fig.add_vline(x=60, line=dict(color=AMBER, dash="dot")).add_hline(y=8, line=dict(color=AMBER, dash="dot"))
    a, b = st.columns([1.35, 1])
    fig = style(fig, "Q4 2022: flight-prone funding and thin capital once bond losses count", 450)
    fig.update_layout(legend=dict(y=-0.2, yanchor="top", x=0, xanchor="left"), margin=dict(b=40))
    fig.update_xaxes(title="Uninsured deposits (%)").update_yaxes(title="CET1 after securities losses (%)")
    a.plotly_chart(fig, width="stretch")
    comp = pd.DataFrame(less["comparison"]).T.set_index("label")[["SVB", "Signature", "First Republic", "peer_median"]]
    comp = comp.rename(columns={"peer_median": "Survivors"})
    comp.index = ["Uninsured %", "Deposit growth 2019-22 %", "Marked CET1 %", "Bond loss / Tier 1 %"]
    comp.index.name = "Q4 2022"
    b.markdown("#### The three failures vs 101 survivors")
    b.dataframe(comp, width="stretch")
    run = less["first_republic_run"]
    b.markdown(f"""<div class="callout"><b>Screen:</b> uninsured > 60%, marked CET1 < 8% and deposit growth > 90% since 2019 caught
{less['failed_all_three']} of 3 failures and {less['survivors_all_three']} survivors. Tested on {less['grid_settings']} threshold settings,
{less['grid_all_caught']} still catch all three and none flags more than {less['grid_max_survivors']} survivor.<br>
<b>First Republic's run:</b> deposits ${run['deposits_q4_2022_bn']}B to ${run['deposits_q1_2023_bn']}B ({run['change_pct']}%) in Q1 2023.</div>""",
                unsafe_allow_html=True)

# 04 risk screen -------------------------------------------------------------------------------------------------------------
with tabs[3]:
    fc = pd.DataFrame(rsk["flag_counts"])
    a, b = st.columns([1, 1.35])
    fig = go.Figure(go.Bar(y=fc["flag"], x=fc["banks"], orientation="h", marker_color=RED, text=fc["banks"], textposition="outside"))
    fig.update_yaxes(autorange="reversed")
    a.plotly_chart(style(fig, f"Banks raising each flag, {rsk['quarter']}", 420, legend=False), width="stretch")
    sc = screen()
    band = b.selectbox("Size band", ["All"] + [x[2] for x in d.SIZE_BANDS])
    view = sc if band == "All" else sc[snapshot().loc[sc.index, "size_band"] == band]
    flags = [f[0] for f in m.RISK_FLAGS]
    tbl = view.assign(**{"Assets $B": (view["assets"] / 1000).round(1),
                         "Flags raised": view[flags].apply(lambda r: "; ".join(k for k in flags if r[k]), axis=1)})
    b.dataframe(tbl[["bank", "state", "Assets $B", "flag_count", "Flags raised"]].rename(columns={"bank": "Bank", "state": "State",
                                                                                                  "flag_count": "Flags"}).head(40),
                hide_index=True, width="stretch", height=380)
    st.markdown(f'<div class="callout"><b>{rsk["banks_no_flags"]} banks raise no flag; {rsk["banks_two_plus"]} raise two or more.</b> '
                "A flag is a prompt to look closer, not a verdict. Rules: " + "; ".join(rsk["rules"]) + ".</div>", unsafe_allow_html=True)

# 05 bank brief ----------------------------------------------------------------------------------------------------------------
names = sorted(snapshot()["short"])
with tabs[4]:
    bank = st.selectbox("Bank", names, index=names.index("Flagstar Bank"))
    cert = t.resolve_banks(bank)[0]
    a, b = st.columns([1.05, 1])
    a.markdown(agent.bank_brief(bank).replace("$", "\\$"))
    ser = series(cert)
    tr = trends()
    for colname, label, colr in [("nim", "Net interest margin (%)", CYAN), ("deposit_cost", "Cost of deposits (%)", AMBER)]:
        fig = go.Figure([go.Scatter(x=ser.index.map(qlabel), y=ser[colname], name=bank, line=dict(color=colr, width=2.8, shape="spline")),
                         go.Scatter(x=tr.index.map(qlabel), y=tr[colname], name="Peer median", line=dict(color=MUTED, width=1.8, dash="dot"))])
        b.plotly_chart(style(fig, label, 300), width="stretch")

# 06 rate scenario --------------------------------------------------------------------------------------------------------------
with tabs[5]:
    a, b = st.columns([1, 2])
    bank2 = a.selectbox("Bank ", names, index=names.index("Flagstar Bank"), key="scen_bank")
    shock = a.slider("Parallel rate move (bp)", -200, 300, 100, 25)
    r = exposure().loc[t.resolve_banks(bank2)[0]]
    d_nim = r["nim_per_100bp"] * shock / 100
    d_nii = r["nii_per_100bp_musd"] * shock / 100
    a.markdown(f"""<div class="callout"><b>{bank2}</b><br>Asset-yield beta {r['yield_beta']:.2f} vs funding-cost beta {r['funding_beta']:.2f}
(2022-24 cycle).<br>NIM {r['nim_latest']:.2f}% → <b>{r['nim_latest'] + d_nim:.2f}%</b> ({d_nim:+.2f} pts)<br>Net interest income
<b>{"-" if d_nii < 0 else "+"}${abs(d_nii):,.0f}M</b> a year</div>""", unsafe_allow_html=True)
    a.markdown('<div class="mono">First-order estimate from the bank\'s own repricing history; the Excel model adds deposit runoff, '
               'credit losses and capital over eight quarters.</div>', unsafe_allow_html=True)
    if EXCEL.exists():
        a.download_button("Download the Excel rate-scenario model", EXCEL.read_bytes(), EXCEL.name, width="stretch")
    ex = exposure().copy()
    ex["move"] = ex["nim_per_100bp"] * shock / 100
    ex = ex.sort_values("move")
    colors = [AMBER if n == bank2 else (RED if v < 0 else GREEN) for n, v in zip(ex["bank"], ex["move"])]
    fig = go.Figure(go.Bar(x=ex["bank"], y=ex["move"], marker_color=colors, hovertemplate="%{x}: %{y:+.2f} pts<extra></extra>"))
    fig.update_xaxes(showticklabels=False)
    b.plotly_chart(style(fig, f"NIM change for all {len(ex)} banks at {shock:+} bp (highlighted: {bank2})", 460, legend=False),
                   width="stretch")

# 07 ask the analyst --------------------------------------------------------------------------------------------------------------
with tabs[6]:
    mode = "LLM with grounding check" if llm.enabled() else "offline planner (no API key needed)"
    st.markdown(f'<div class="mono">Mode: {mode}. Answers use only numbers returned by ten governed tools; any other number is '
                'rejected and the template answer is shown instead.</div>', unsafe_allow_html=True)
    examples = ["Could SVB happen again?", "Which banks pay the most for deposits?", "How exposed is Bell Bank to rising rates?",
                "What drove deposit betas?", "How does Zions compare with KeyBank and Western Alliance?", "Is office real estate a problem?"]
    cols = st.columns(3)
    for i, q in enumerate(examples):
        if cols[i % 3].button(q, width="stretch"):
            st.session_state["q"] = q
    q = st.chat_input("Ask about deposit costs, rate risk, CRE, capital or the 2023 failures") or st.session_state.pop("q", None)
    if q:
        with st.chat_message("user"):
            st.write(q)
        ans = agent.ask(q)
        with st.chat_message("assistant"):
            st.markdown(ans.text.replace("$", "\\$"))
            status = "grounded: every number traced to a tool result" if ans.grounded else f"ungrounded numbers: {ans.ungrounded}"
            st.markdown(f'<div class="mono">{ans.mode} · {status} · tools: '
                        + ", ".join(f"{c['tool']}({', '.join(f'{k}={v}' for k, v in c['args'].items())})" for c in ans.calls) + "</div>",
                        unsafe_allow_html=True)

st.write("")
st.markdown('<div class="mono">Built by Tanzil Ali Rizvi · Python (pandas, scipy), Excel, Power BI, Streamlit · '
            '<a href="https://github.com/Tanzil-Ali-Rizvi/regional-bank-monitor" style="color:#FFB020">source on GitHub</a></div>',
            unsafe_allow_html=True)
