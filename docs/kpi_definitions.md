# KPI definitions

All balances are FDIC call-report fields (thousands of dollars in the API, converted to USD millions). Field codes are the
FDIC BankFind "RIS" names. Rates are annualised percentages.

| KPI | Definition | FDIC fields |
|---|---|---|
| Net interest margin | FDIC quarterly NIM: net interest income / average earning assets | NIMYQ |
| Asset yield | Interest income / average earning assets | INTINCYQ |
| Cost of funds | Interest expense / average earning assets | INTEXPYQ |
| Cost of deposits | 4 x quarterly domestic deposit interest expense / average domestic deposits (all deposits, including non-interest-bearing) | EDEPDOMQ, DEPDOM |
| Deposit beta (hiking cycle) | Change in cost of deposits, Q4 2021 to Q2 2024, / change in quarter-average Fed funds (0.08% to 5.33%) | as above, FRED FEDFUNDS |
| Deposit beta (cutting cycle) | Same, Q2 2024 to Q2 2026 (Fed funds 5.33% to 3.63%) | |
| Asset yield beta, funding cost beta | Change in asset yield (or cost of funds) over the hiking cycle / change in Fed funds | |
| NIM change per +100bp | Asset yield beta minus funding cost beta, in points of NIM per point of Fed funds | |
| Uninsured deposits | Estimated uninsured deposits / domestic deposits | DEPUNINS, DEPDOM |
| Loans / deposits | Gross loans and leases / total deposits | LNLSGR, DEP |
| Brokered deposits | Brokered deposits / total deposits | BRO, DEP |
| CRE concentration | (Construction + multifamily + non-owner-occupied nonfarm nonresidential loans) / (Tier 1 capital + allowance), as in the 2006 interagency guidance | LNRECONS, LNREMULT, LNRENROT, RBCT1, LNATRES |
| Construction concentration | Construction and land development loans / (Tier 1 capital + allowance) | LNRECONS |
| Unrealized securities gain/(loss) | (AFS fair value - AFS amortized cost) + (HTM fair value - HTM amortized cost) | SCAF, SCAA, SCHF, SCHA |
| Unrealized loss / Tier 1 | Unrealized securities gain/(loss) / Tier 1 capital | RBCT1 |
| CET1 after securities losses | (CET1 capital + unrealized losses after 21% tax) / risk-weighted assets; most banks of this size exclude AFS losses from regulatory CET1 | RBCT1C, RWAJ |
| Liquidity / uninsured deposits | (Cash + AFS securities + HTM securities at fair value) / uninsured deposits | CHBAL, SCAF, SCHF |
| Net charge-off rate | 4 x quarterly net charge-offs / average gross loans | NTLNLSQ, LNLSGR |
| Noncurrent loans | Loans 90+ days past due or nonaccrual / gross loans | NCLNLS |
| CET1, Tier 1 leverage, ROA, ROE, efficiency | As published by the FDIC | RBCT1CER, RBC1AAJ, ROAQ, ROEQ, EEFFQR |
| Deposit growth 2019-22 | Total deposits Q4 2022 / Q4 2019 - 1 (includes acquisitions) | DEP |
| Scope change | Quarter in which total assets rose more than 25%, usually a merger | ASSET |

Risk-screen flags and thresholds are in `src/bankmon/metrics.py` (`RISK_FLAGS`, `EARLY_WARNING`) and on the Excel Inputs sheet.
