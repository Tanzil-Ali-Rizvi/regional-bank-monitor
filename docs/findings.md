# US Regional Banks: funding, rate and credit risk after the 2022-24 hiking cycle

*Analyst memo, November 2026. 101 US regional banks with $10-250B in assets ($3.94 trillion combined), FDIC call reports
Q1 2019 to Q2 2026, plus Silicon Valley Bank, Signature Bank and First Republic Bank up to their last call reports.*

## Bottom line

1. **Funding need, not uninsured deposits, set what banks paid depositors.** The median bank passed on 41% of the Fed's
   5.25-point hiking cycle to its deposit costs (deposit beta 0.41; middle half 0.33 to 0.51). Banks that lent out more of
   their deposits paid up the most (Spearman rho 0.62 with loans/deposits) and saw margins fall, while deposit-rich banks
   widened theirs.
2. **The 2023 failures were visible in the last call report, but only as a combination.** SVB, Signature and First Republic
   all had uninsured deposits above 60%, deposit growth above 90% since 2019 and less than 8% CET1 once securities losses were
   counted. No surviving bank had all three. Unrealized losses alone did not separate them: 28 survivors had deeper losses
   relative to capital than Signature.
3. **Today's screen is mostly clean, with a short watch list.** 59 of 101 banks raise none of seven risk flags; 10 raise two
   or more. ConnectOne Bank raises four.
4. **Rates are rising again, and 29 banks lose margin when they do.** Fed funds moved from 3.63% to 3.88% in October 2026 and
   the 10-year Treasury reached 5.13%. Based on each bank's own behaviour in the last cycle, 29 banks' margins shrink as rates
   rise; Bell Bank is the most exposed (-0.26 points of NIM per +100bp) and Flagstar has the largest dollar exposure
   ($154M a year of net interest income per +100bp).

## 1. What drove deposit costs

| Loan-to-deposit tercile (Q4 2021) | Median loans/deposits | Median deposit beta | Median NIM change, Q4 2021 to Q2 2024 |
|---|---|---|---|
| Low (deposit-rich) | 62% | 0.31 | +0.35 points |
| Middle | 74% | 0.44 | +0.40 points |
| High (loan-heavy) | 92% | 0.50 | -0.05 points |

- **Funding need** explains most of the spread. Deposit betas rise with loans/deposits (rho 0.62, p < 0.001) and brokered
  deposits (rho 0.63), and fall with securities holdings (rho -0.56): banks with liquidity on hand did not have to bid for
  deposits.
- **Uninsured deposits did not predict betas** (rho 0.09, p = 0.385). They matter for run risk, not for pricing.
- **Margins recovered.** The peer median NIM bottomed at 2.94% in Q1 2022, before deposit costs caught up, and is 3.66% in
  Q2 2026. Median deposit costs peaked at 2.38% and are now 1.81%.
- **Cuts passed through more slowly.** From Q2 2024 to Q2 2026 deposit costs fell 0.33 for each point of Fed cuts (median),
  against 0.41 on the way up.

## 2. What the 2023 failures looked like at Q4 2022

| | Peer median | SVB | Signature | First Republic |
|---|---|---|---|---|
| Uninsured deposits | 42% | 94% | 90% | 68% |
| Deposit growth, Q4 2019 to Q4 2022 | 46% | 179% | 119% | 96% |
| CET1 if securities losses were taken | 9.8% | 2.7% | 7.6% | 6.4% |
| Unrealized securities loss / Tier 1 | -21% | -104% | -32% | -30% |

- **Each failure sat at the extreme on funding.** All three were in the top 3% of the peer group for uninsured deposits and
  in the top 16% for deposit growth.
- **Securities losses were common.** The median survivor had a loss equal to 21% of Tier 1 capital. SVB's was 104%, but
  Signature's and First Republic's were not unusual on their own.
- **A three-flag screen separates them.** Uninsured deposits above 60%, deposit growth above 90% and marked CET1 below 8%
  flags all three failures and no survivor; four survivors raise two of the three flags.
- **The run shows up in First Republic's final report.** Its deposits fell from $176B to $104B (-41%) in Q1 2023, even
  counting the $30B the largest banks deposited in March, and FHLB borrowing rose from 6.6% to 12.1% of assets.
- **The thresholds were chosen with hindsight**, so I tested 80 combinations (uninsured 50-65%, CET1 7-9%, growth 70-100%).
  36 settings catch all three failures and none flags more than one survivor. Treat it as a pattern, not a validated model:
  three failures is a small sample, and deposit growth includes acquisitions.

## 3. Today's risk screen (Q2 2026)

| Flag | Banks |
|---|---|
| Uninsured deposits > 60% | 2 |
| CET1 after securities losses < 8% | 0 |
| CRE > 300% of capital (interagency guidance) | 16 |
| Construction > 100% of capital | 2 |
| Loans > deposits | 8 |
| Cash and securities < 50% of uninsured deposits | 20 |
| Net charge-offs > 0.5% of loans | 8 |

- **Watch list.** Ten banks raise two or more flags: ConnectOne (4), Provident (3), ServisFirst (3), and Flagstar, Valley
  National, Bank OZK, Simmons, Beacon, Merchants Bank of Indiana and Bell Bank (2 each).
- **No bank fails the 2023 combination today.** Only 2 banks have uninsured deposits above 60%, and none has marked CET1
  below 8%. The median securities loss has shrunk from 24% of Tier 1 (Q3 2022) to 9%.

## 4. Commercial real estate

- **Concentration is easing.** Banks above the 300% CRE guidance peaked at 24 in Q1 2024 and are 16 now.
- **Losses have not followed concentration so far.** Since 2024 the median net charge-off rate is 0.13% for banks above 300%
  and 0.19% for banks under 200%. CRE losses lag and office loans are not reported separately, so this is "not yet", not
  "not a risk".

## 5. Rate exposure as rates rise again

- **Method.** For each bank, NIM change per +100bp = asset-yield beta minus funding-cost beta over the last hiking cycle,
  both per dollar of earning assets. The median is +0.05 points, so the typical bank gains a little.
- **Liability-sensitive banks.** 29 banks have a funding beta above their asset beta. The most exposed are Bell Bank (-0.26),
  ConnectOne (-0.21), MidFirst and Flagstar (-0.19 each).
- **The Excel model** turns this into an 8-quarter projection. For Flagstar, a +100bp path lowers NIM from 2.17% to 1.93% by
  Q2 2028 and net interest income by $181M against the flat-rate base; with a 1.5% CRE loss stress the bank loses money in
  every quarter, but CET1 stays above 11%.

## Recommendations

- **Bank treasury and ALCO teams:** price deposits by funding need. Keep loans/deposits and brokered funding low enough to
  avoid paying the 0.50 beta of the loan-heavy third, and monitor uninsured deposits together with deposit growth and marked
  capital, not in isolation.
- **Credit and equity analysts:** use the combined funding screen rather than unrealized losses alone, and favour banks with
  positive rate sensitivity if rates keep rising. Liability-sensitive banks with high CRE (ConnectOne) deserve the closest
  look.
- **Risk and supervision:** the 20 banks whose liquid assets cover less than half of uninsured deposits are the ones where a
  2023-style run would bite first.

## Data and limits

- Bank-level call reports, not holding companies; ratios are the FDIC's where it publishes them (NIM, ROA, capital ratios)
  and computed from call-report lines otherwise. Definitions: [kpi_definitions.md](kpi_definitions.md).
- Deposit growth and betas include the effect of mergers; quarters where assets jump by more than 25% are tagged.
- Rate sensitivity is first-order and backward-looking: it assumes the next cycle repeats each bank's last one.
- Peer group: active US-owned, deposit-funded banks with $10-250B of assets; card, consumer, custody, broker-sweep,
  foreign-owned and Puerto Rico banks are excluded (list in [data/README.md](../data/README.md)).
