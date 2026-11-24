"""The memo quotes numbers; these tests fail if the analysis moves and the memo is not updated."""

from pathlib import Path

import pandas as pd

from bankmon import data as d
from bankmon import metrics as m

MEMO = " ".join((Path(__file__).resolve().parents[1] / "docs" / "findings.md").read_text().split())


def has(text: str) -> None:
    assert text in MEMO, f"memo is missing: {text!r}"


def test_memo_headline_numbers():
    h = m.headline()
    has(f"{h['banks']} US regional banks")
    has(f"${h['assets_trillion']:.2f} trillion")
    has(f"deposit beta {h['beta_median']:.2f}; middle half {h['beta_q1']:.2f} to {h['beta_q3']:.2f}")
    has(f"rho {h['rho_ltd']:.2f} with loans/deposits")
    has(f"brokered deposits (rho {h['rho_brokered']:.2f})")
    has(f"securities holdings (rho {h['rho_securities']:.2f})")
    has(f"(rho {h['rho_uninsured']:.2f}, p = {h['p_uninsured']:.3f})")
    has(f"bottomed at {h['nim_trough_median']:.2f}% in Q1 2022")
    has(f"is {h['nim_latest_median']:.2f}% in")
    has(f"peaked at {h['deposit_cost_peak_median']:.2f}% and are now {h['deposit_cost_latest_median']:.2f}%")
    has(f"fell {h['down_beta_median']:.2f} for each point")
    has(f"{h['survivors_unrealized_worse_than_signature']} survivors had deeper losses")
    has(f"{h['screen_zero']} of 101 banks raise none")
    has(f"{h['screen_two_plus']} raise two")
    has(f"{h['liability_sensitive']} banks' margins shrink")
    has(f"{h['ew_grid']} combinations")
    has(f"{h['ew_grid_all_caught']} settings catch all three")
    has(f"peaked at {h['cre_over_300_peak']} in Q1 2024 and are {h['cre_over_300_latest']} now")
    has(f"{h['nco_cre_high']:.2f}% for banks above 300%")
    has(f"{h['nco_cre_low']:.2f}% for banks under 200%")
    has(f"${abs(h['flagstar_nii_per_100bp']):.0f}M a year")
    has(f"is +{h['nim_per_100bp_median']:.2f} points")


def test_memo_crisis_table():
    h = m.headline()
    has(f"| Uninsured deposits | {h['uninsured_peer_2022']:.0f}% | {h['uninsured_svb']:.0f}% | {h['uninsured_signature']:.0f}% | {h['uninsured_frc']:.0f}% |")
    has(f"| {h['growth_peer']:.0f}% | {h['growth_svb']:.0f}% | {h['growth_signature']:.0f}% | {h['growth_frc']:.0f}% |")
    has(f"| {h['cet1_marked_peer_2022']:.1f}% | {h['cet1_marked_svb']:.1f}% | {h['cet1_marked_signature']:.1f}% | {h['cet1_marked_frc']:.1f}% |")


def test_memo_flag_table():
    for _, row in m.flag_counts().iterrows():
        assert f"| {row['banks']} |" in MEMO


def test_first_republic_run():
    s = d.series(59017)
    before, after = s.loc[pd.Timestamp("2022-12-31"), "deposits"], s.loc[pd.Timestamp("2023-03-31"), "deposits"]
    has(f"${before / 1000:.0f}B to ${after / 1000:.0f}B (-{(1 - after / before) * 100:.0f}%)")
