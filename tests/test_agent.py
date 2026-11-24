import pytest

from bankmon import agent, data
from bankmon.tools import TOOLS, bank_name, resolve_banks, resolve_metric, resolve_size_band


@pytest.mark.parametrize("q,expected", [
    ("How does Flagstar compare with Valley National and Zions?", ["Flagstar Bank", "Valley National Bank", "Zions Bank"]),
    ("Tell me about First Citizens", ["First Citizens Bank"]),
    ("Is Citizens Bank risky?", ["Citizens Bank"]),
    ("What is the key risk for KeyBank?", ["KeyBank"]),
    ("What are the key lessons?", []),
    ("SVB vs Signature", ["SVB", "Signature"]),
    ("Columbia Bank (NJ) profile", ["Columbia Bank (NJ)"]),
    ("East West vs Eastern Bank", ["East West Bank", "Eastern Bank"]),
])
def test_resolve_banks(q, expected):
    assert [bank_name(c) for c in resolve_banks(q)] == expected


def test_resolvers():
    assert resolve_metric("Which banks pay the most for deposits?") == "deposit_cost"
    assert resolve_metric("best capitalized") == "cet1_ratio"
    assert resolve_metric("who is most exposed to rising rates") == "nim_per_100bp"
    assert resolve_metric("bad loans") == "noncurrent_rate"
    assert resolve_size_band("Which $10-20B banks have the highest NIM?") == "$10-20B"


def test_every_tool_runs_and_is_grounded():
    calls = [("peer_overview", {}), ("bank_profile", {"bank": "Flagstar Bank"}), ("compare_banks", {"banks": ["Zions", "KeyBank"]}),
             ("rank_banks", {"metric": "deposit_cost", "order": "worst"}), ("deposit_betas", {}), ("lessons_2023", {}),
             ("risk_screen", {"bank": "ConnectOne"}), ("cre_credit", {}), ("rate_exposure", {"bank": "Bell Bank"}),
             ("bank_trend", {"bank": "M&T", "metric": "deposit_cost"})]
    assert {c[0] for c in calls} == set(TOOLS)
    for name, args in calls:
        r = TOOLS[name](**args)
        assert "error" not in r, name
        text = agent._render({"tool": name, "args": args}, r)
        assert agent.check_grounding(text, [r]) == [], name


def test_errors_are_explained():
    assert "error" in TOOLS["bank_profile"]("JPMorgan Chase")
    assert "error" in TOOLS["compare_banks"](["Zions"])
    assert "could not answer" in agent.ask("Tell me about Silicon Valley Bank's NIM trend").text or \
        agent.plan("Tell me about Silicon Valley Bank's NIM trend")[0]["tool"] == "lessons_2023"


def test_headline_numbers_in_answers():
    assert "0.41" in agent.ask("What drove deposit betas?").text
    assert "93.9" in agent.ask("Could SVB happen again?").text
    assert "ConnectOne Bank" in agent.ask("Which banks are risky right now?").text


def test_grounding_catches_invented_numbers():
    a = agent.ask("Which banks pay the most for deposits?")
    assert a.grounded
    assert agent.check_grounding(a.text.replace("3.41", "3.71"), a.results) == ["3.71"]


@pytest.mark.parametrize("bank", ["Flagstar Bank", "Zions Bank", "Bell Bank", "First Citizens Bank", "Apple Bank"])
def test_briefs_are_grounded(bank):
    assert agent.check_grounding(agent.bank_brief(bank), agent.brief_results(bank)) == []


def test_failed_banks_are_not_peers():
    assert set(data.FAILED).isdisjoint(data.snapshot().index)
