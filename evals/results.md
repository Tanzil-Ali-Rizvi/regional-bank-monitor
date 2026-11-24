| Check | Result | CI gate |
| --- | --- | --- |
| Tool selection (build set) | 41/41 | 95% |
| Tool selection (held-out, never tuned) | 19/22 | reported |
| Answers and 101 bank briefs grounded in tool results | 164/164 | 100% |
| Tampered answers caught | 1477/1477 | 100% |
| Claims: betas rise with loans/deposits; 2023 screen catches 3 of 3 failures and 0 survivors; uninsured deposits do not predict betas | rho 0.62 (p = 3e-12); 3 and 0; p = 0.38 | p < 0.001; 3 and 0; p > 0.05 |

216 alterations that produced another legitimate value from the tool results were skipped (a number-matching check cannot detect them).

Held-out misses (left unfixed so the score stays honest):
- Compare Regions Bank and Huntington -> expected compare_banks {}, got {'tool': 'bank_profile', 'args': {'bank': 'Regions Bank'}}
- Weakest liquidity against uninsured deposits -> expected rank_banks {'metric': 'uninsured_coverage', 'order': 'worst'}, got {'tool': 'rank_banks', 'args': {'metric': 'uninsured_share', 'order': 'worst'}}
- Which banks carry the biggest unrealized securities losses? -> expected rank_banks {'metric': 'unrealized_to_tier1', 'order': 'worst'}, got {'tool': 'rank_banks', 'args': {'metric': 'unrealized_to_tier1', 'order': 'best'}}
