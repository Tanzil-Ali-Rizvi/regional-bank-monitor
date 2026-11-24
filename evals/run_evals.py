"""Evaluate the bank analyst assistant and the headline statistical claims. Gates CI.

1. tool selection   the offline planner picks the expected tool with the expected key arguments
                    (questions.yaml gated; held_out.yaml reported, written after the build set and never tuned on)
2. grounding        every offline answer and all 101 bank briefs pass the grounding check
3. tamper           altering any number in an answer must be caught by the grounding check
4. claims           (a) deposit betas rise with loans/deposits at the start of the cycle (Spearman > 0, p < 0.001);
                    (b) the 2023 screen flags all three failures and no survivor on all three rules;
                    (c) uninsured deposits do not predict deposit betas (p > 0.05): they matter for runs, not pricing
Writes evals/results.json and evals/results.md; exits 1 if a gate fails.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bankmon import agent, data, metrics  # noqa: E402


def score_tools(cases: list[dict], misses: list[str]) -> tuple[int, int]:
    ok = 0
    for c in cases:
        got = agent.plan(c["q"])[0]
        want = c.get("args") or {}
        if got["tool"] == c["tool"] and all(got["args"].get(k) == v for k, v in want.items()):
            ok += 1
        else:
            misses.append(f"{c['q']} -> expected {c['tool']} {want}, got {got}")
    return ok, len(cases)


def tamper(text: str) -> list[tuple[str, str]]:
    """Every number altered once; returns (tampered_text, inserted_value)."""
    out = []
    for mm in re.finditer(r"(?<![\w.-])\d[\d,]*(?:\.\d+)?", text):
        raw = mm.group(0).replace(",", "")
        dec = len(raw.split(".")[1]) if "." in raw else 0
        new = f"{float(raw) * 1.1 + 1:.{dec}f}"
        out.append((text[:mm.start()] + new + text[mm.end():], new))
    return out


def main() -> int:
    qs = yaml.safe_load((ROOT / "evals" / "questions.yaml").read_text())
    ho = yaml.safe_load((ROOT / "evals" / "held_out.yaml").read_text())
    misses, ho_misses = [], []
    t_ok, t_n = score_tools(qs, misses)
    h_ok, h_n = score_tools(ho, ho_misses)

    g_ok = g_n = c_ok = c_n = collisions = 0
    for c in qs + ho:
        a = agent.ask(c["q"])
        g_n += 1
        g_ok += int(a.grounded)
        if not a.grounded:
            misses.append(f"ungrounded answer: {c['q']} {a.ungrounded}")
        allowed = set().union(*[agent._numbers(r) for r in a.results]) | agent.ALLOWED_CONSTANTS
        for bad, new in tamper(a.text):
            if agent._norm(new) in allowed:
                collisions += 1           # swapped to another legitimate value: undetectable by number matching
                continue
            c_n += 1
            c_ok += int(bool(agent.check_grounding(bad, a.results)))
    for bank in data.snapshot()["short"]:
        bad = agent.check_grounding(agent.bank_brief(bank), agent.brief_results(bank))
        g_n += 1
        g_ok += int(not bad)
        if bad:
            misses.append(f"ungrounded brief {bank}: {bad}")

    drv = metrics.beta_drivers().set_index("column")
    h = metrics.headline()
    claim = {"beta_vs_loan_to_deposit_spearman": float(drv.loc["loan_to_deposit", "rho"]),
             "beta_vs_loan_to_deposit_p": float(drv.loc["loan_to_deposit", "p_value"]),
             "failures_flagged_all_three": h["ew_failed_all_three"], "survivors_flagged_all_three": h["ew_survivors_all_three"],
             "beta_vs_uninsured_p": float(drv.loc["uninsured_share", "p_value"])}
    claim_ok = (claim["beta_vs_loan_to_deposit_spearman"] > 0 and claim["beta_vs_loan_to_deposit_p"] < 0.001
                and claim["failures_flagged_all_three"] == 3 and claim["survivors_flagged_all_three"] == 0
                and claim["beta_vs_uninsured_p"] > 0.05)
    res = {
        "tool_selection": {"passed": t_ok, "total": t_n, "score": t_ok / t_n, "gate": 0.95},
        "grounding": {"passed": g_ok, "total": g_n, "score": g_ok / g_n, "gate": 1.0},
        "tamper_caught": {"passed": c_ok, "total": c_n, "score": c_ok / c_n, "gate": 1.0},
        "claims": {"passed": int(claim_ok), "total": 1, "score": float(claim_ok), "gate": 1.0, **claim},
    }
    held = {"passed": h_ok, "total": h_n, "score": h_ok / h_n}
    passed = all(v["score"] >= v["gate"] for v in res.values())
    (ROOT / "evals" / "results.json").write_text(json.dumps(
        {"results": res, "held_out_tool_selection": held, "misses": misses, "held_out_misses": ho_misses,
         "tamper_collisions_skipped": collisions, "passed": passed}, indent=2, default=float))
    md = ["| Check | Result | CI gate |", "| --- | --- | --- |",
          f"| Tool selection (build set) | {t_ok}/{t_n} | 95% |",
          f"| Tool selection (held-out, never tuned) | {h_ok}/{h_n} | reported |",
          f"| Answers and 101 bank briefs grounded in tool results | {g_ok}/{g_n} | 100% |",
          f"| Tampered answers caught | {c_ok}/{c_n} | 100% |",
          f"| Claims: betas rise with loans/deposits; 2023 screen catches 3 of 3 failures and 0 survivors; uninsured deposits do not "
          f"predict betas | rho {claim['beta_vs_loan_to_deposit_spearman']:.2f} (p = {claim['beta_vs_loan_to_deposit_p']:.0e}); "
          f"{claim['failures_flagged_all_three']} and {claim['survivors_flagged_all_three']}; p = {claim['beta_vs_uninsured_p']:.2f} "
          f"| p < 0.001; 3 and 0; p > 0.05 |"]
    md.append(f"\n{collisions} alterations that produced another legitimate value from the tool results were skipped "
              "(a number-matching check cannot detect them).")
    if ho_misses:
        md.append("\nHeld-out misses (left unfixed so the score stays honest):\n" + "\n".join(f"- {x}" for x in ho_misses))
    (ROOT / "evals" / "results.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    for x in misses:
        print("  MISS", x)
    print("PASSED" if passed else "FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
