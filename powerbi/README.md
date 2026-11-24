# Power BI report

Nine pages, 1280 x 790, in a light card theme. The pages have rounded white cards with soft shadows and bright
blue, cyan, green, purple and pink accents. Line charts are shaded, and tooltips are dark.

| Page | What it shows |
|---|---|
| Executive Overview | KPI cards, median NIM, cost of deposits and Fed funds by quarter, banks raising each risk flag, watch list, read-out |
| Governance & QA | 20 headline figures, DAX vs Python, with PASS/REVIEW; rows by governance label; data rules |
| Funding & Deposit Betas | Loans/deposits at Q4 2021 vs deposit beta, the Python driver statistics, deposit costs vs Fed funds |
| Lessons from 2023 | Uninsured deposits vs marked CET1 at Q4 2022 with the failures highlighted, the three failures' metrics, their deposits by quarter |
| Bank Scorecard | Pick a bank (default Flagstar): twelve metrics vs the peer median with ranks, NIM and deposit-cost trends |
| CRE & Credit | Banks above 300% by quarter, concentration vs charge-offs, the most concentrated banks, charge-offs by band |
| Cohort Analysis | Heatmap of median cost of deposits by size band and year, assets and NIM combo, size-band summary, flags by size band |
| How This Dashboard Works | Build log, page guide, key rules, open items |
| Model Guide | Every table and key measure: what it does, why, and the question it answers (with slicers) |

## Built as code

| File | What it does |
|---|---|
| `../scripts/export_powerbi.py` | Writes `data/quarterly.csv` (3,079 bank-quarters, call-report line items), `banks.csv`, `rates.csv`, `findings.csv` (Python statistics) and `reconciliation.csv` (20 Python reference values) |
| `build_pbip.py` | Generates `RegionalBankMonitor/`: the TMDL semantic model (Power Query source -> staging -> fact, 9 tables, 2 relationships, 160 measures in numbered folders) and the PBIR report (9 pages, theme) |

**Model.** `Quarterly` is the fact table. In Power Query it:

- computes average balances (deposits, loans, earning assets);
- computes CRE loans, the capital base, unrealized securities gains and losses, and CET1 marked for those losses
  (after a 21% tax);
- computes liquid assets;
- labels each row for governance: failed-bank case study, merger quarter (assets up more than 25%), no CET1 ratio, or
  Include.

`Banks` (status: Peer / Failed in 2023, size band) and `Quarters` (rate-cycle label) are the dimensions.

**DAX** keeps to ratios of sums. Every public measure covers one quarter: the slicer quarter, or Q2 2026 when none is
selected. Peer medians are `MEDIANX` over `VALUES(Banks[cert])` with the failed banks excluded. Betas compare the Q4 2021,
Q2 2024 and Q2 2026 quarters, with quarter-average Fed funds from `rates.csv`.

**Reconciliation.** The `Reconciliation` table holds 20 values from the Python metrics layer:

- bank count and total assets;
- medians for NIM, cost of deposits, uninsured deposits and CET1;
- deposit betas in both directions;
- rate sensitivity;
- risk-flag counts;
- CRE concentration;
- SVB and First Republic at Q4 2022;
- the early-warning results;
- Flagstar and M&T spot checks.

`Check Status` compares each one with its DAX equivalent (tolerance 0.01), and the Governance & QA page shows
**PASS (20 of 20)**.

## Rebuild

```bash
python scripts/export_powerbi.py
python powerbi/build_pbip.py --data-dir "C:/Users/<you>/Downloads/regional_bank_powerbi/data/"
```

Copy `powerbi/RegionalBankMonitor/` and `powerbi/data/` to the Windows path above. Open `RegionalBankMonitor.pbip` in
Power BI Desktop and refresh. To save it as a `.pbix`:

1. Use File > Save as and choose the `.pbix` type.
2. Set `excludeFromModelRefresh` on the five tables that read CSVs, so the data stays frozen inside the file.
