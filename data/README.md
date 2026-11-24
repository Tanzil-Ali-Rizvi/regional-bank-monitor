# Data

| File | Source | Retrieved |
|---|---|---|
| `raw/fdic_regional_financials.csv` | FDIC BankFind Suite API, `/banks/financials`, 54 call-report fields, Q1 2019 - Q2 2026 (3,079 bank-quarters) | 24 Nov 2026 |
| `raw/fdic_regional_institutions.csv` | FDIC BankFind Suite API, `/banks/institutions` | 24 Nov 2026 |
| `raw/fred_rates_monthly.csv` | FRED: FEDFUNDS, DGS2, DGS10, monthly averages, Jan 2018 - Oct 2026 | 24 Nov 2026 |

All are public US government data.

## Peer group

Starting point: the 142 active FDIC-insured institutions with $10-250B of total assets at Q2 2026. Kept: 101 US-owned,
deposit-funded commercial and savings banks. Excluded (41), because their business model or economy is not comparable:

- **Credit-card and consumer lenders:** American Express National Bank, Synchrony, Barclays Bank Delaware, Comenity Capital,
  Ally, SoFi, Sallie Mae, USAA FSB, BMW Bank, Toyota Financial Savings Bank, Happen Bank, TD Bank USA.
- **Custody, wealth and broker sweep banks:** Northern Trust, BNY Mellon NA, UBS Bank USA, Raymond James Bank, TriState
  Capital, Stifel Bank and Stifel Bank & Trust, Charles Schwab Premier Bank and Charles Schwab Trust Bank, Ameriprise Bank,
  Safra National Bank.
- **Foreign-owned banks and branches:** HSBC USA, Santander Bank, City National Bank (RBC), CIBC Bank USA, Deutsche Bank
  Trust Americas, City National Bank of Florida, Israel Discount Bank of NY, Bank of China, State Bank of India, Bank of
  Baroda, Bank Hapoalim.
- **Captive or special-purpose:** Optum Bank, WEX Bank, Beal Bank USA, Bank of America California.
- **Puerto Rico:** Banco Popular de Puerto Rico, FirstBank Puerto Rico, Oriental Bank.

Case study: Silicon Valley Bank (CERT 24735) and Signature Bank (57053) through Q4 2022, and First Republic Bank (59017)
through Q1 2023, their last call reports. The comparison uses Q4 2022 for all three. They are kept out of every peer statistic.

## Notes

- Figures are for the insured bank, not the holding company.
- Quarterly income fields (`...Q`) are for the quarter, not year-to-date.
- Ten bank-quarters lack a CET1 ratio (banks using the community bank leverage ratio); they are left blank.
