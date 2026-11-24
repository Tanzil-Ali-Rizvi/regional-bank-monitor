import numpy as np
import pandas as pd
import pytest

from bankmon import data as d
from bankmon import metrics as m


def test_panel_shape_and_peer_group():
    p = d.panel()
    assert p["cert"].nunique() == 104
    assert d.peers()["cert"].nunique() == 101
    assert set(d.FAILED).isdisjoint(d.peers()["cert"])
    assert d.snapshot().shape[0] == 101
    assert p["date"].min() == pd.Timestamp("2019-03-31") and p["date"].max() == pd.Timestamp(d.LATEST)


def test_failed_banks_end_before_failure():
    p = d.panel()
    last = p[p["cert"].isin(d.FAILED)].groupby("cert")["date"].max()
    assert last[24735] == last[57053] == pd.Timestamp(d.CRISIS)
    assert last[59017] == pd.Timestamp("2023-03-31")   # First Republic filed one more report before failing on 1 May 2023


def test_known_values():
    c = d.snapshot(d.CRISIS, include_failed=True)
    assert c.loc[24735, "uninsured_share"] == pytest.approx(93.88, abs=0.01)   # SVB, widely reported ~94%
    assert c.loc[59017, "uninsured_share"] == pytest.approx(67.71, abs=0.01)   # First Republic ~68%
    mt = d.series(588)
    assert mt.loc[pd.Timestamp(d.PEAK), "deposit_cost"] == pytest.approx(2.0, abs=0.05)


def test_nim_equals_yield_minus_cost():
    s = d.snapshot()
    gap = (s["asset_yield"] - s["cost_of_funds"] - s["nim"]).abs()
    assert gap.median() < 0.02


def test_rates_quarter_average():
    r = d.rates().set_index("date")
    assert r.loc[pd.Timestamp(d.TROUGH), "fed_funds"] == pytest.approx(0.08, abs=0.005)
    assert r.loc[pd.Timestamp(d.PEAK), "fed_funds"] == pytest.approx(5.33, abs=0.005)


def test_beta_definition():
    b = m.betas()
    s, t = d.snapshot(d.PEAK), d.snapshot(d.TROUGH)
    ff = d.rates().set_index("date")["fed_funds"]
    cert = 588
    expected = (s.loc[cert, "deposit_cost"] - t.loc[cert, "deposit_cost"]) / (ff[pd.Timestamp(d.PEAK)] - ff[pd.Timestamp(d.TROUGH)])
    assert b.loc[cert, "up_beta"] == pytest.approx(expected)
    assert b["nim_per_100bp"].equals(b["yield_beta"] - b["funding_beta"])


def test_risk_screen_counts_match_thresholds():
    rs = m.risk_screen()
    s = d.snapshot()
    for label, col, op, thr, _ in m.RISK_FLAGS:
        expected = (s[col] > thr) if op == ">" else (s[col] < thr)
        assert rs[label].sum() == expected.sum()
    assert (rs["flag_count"] == rs[[f[0] for f in m.RISK_FLAGS]].sum(axis=1)).all()


def test_early_warning_separates_failures():
    ew = m.early_warning()
    assert (ew.loc[ew["failed"], "flag_count"] == 3).all()
    assert (ew.loc[~ew["failed"], "flag_count"] < 3).all()
    rob = m.early_warning_robustness()
    assert rob["settings"] == 80 and rob["max_survivors_flagged"] <= 1


def test_scorecard_bounds():
    sc = m.scorecard()
    cols = ["Funding", "Capital & liquidity", "Credit", "Earnings", "Overall"]
    assert sc[cols].min().min() >= 0 and sc[cols].max().max() <= 100
    assert len(sc) == 101


def test_bank_profile():
    p = m.bank_profile(32541)
    assert p["bank"] == "Flagstar Bank"
    assert p["nim_per_100bp"] < 0
    assert "CRE > 300% of capital" in p["flags"]


def test_headline_is_consistent():
    h = m.headline()
    assert h["banks"] == 101
    assert h["beta_q1"] < h["beta_median"] < h["beta_q3"]
    assert h["ew_failed_all_three"] == 3 and h["ew_survivors_all_three"] == 0
    assert h["screen_zero"] + h["screen_two_plus"] < 101
    assert np.isfinite(list(v for v in h.values() if isinstance(v, float))).all()
