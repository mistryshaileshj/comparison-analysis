# Comparison Analysis

A Streamlit dashboard for period-over-period comparison of retail sales / returns
data (`Sales_SalesRtn`). Pick a metric and a time granularity, then optionally
overlay a second date range to compare like-for-like.

## Features

- **Compare for** — Quantity, Return Qty, Net Quantity, Sales Value, Return Value,
  Net Value, Bill count
- **Group by** — Year / Month / Week (ISO week no.) / Day (defaults to Month wise)
- **Compare with** — optional second date range plotted as grouped bars in a
  separate colour, aligned by ordinal position, with a difference summary
  (totals + % change)
- Value labels rendered on the bars; axis titles on both X and Y

## Metric definitions

| Metric        | Definition |
|---------------|------------|
| Quantity      | `SUM(QTY)` |
| Return Qty    | `SUM(RTN_QTY)` |
| Net Quantity  | `SUM(QTY - RTN_QTY)` (all rows) |
| Sales Value   | `SUM(NET_AMT)` where `Trj_Type = 'Sales'` |
| Return Value  | `SUM(NET_AMT)` where `Trj_Type = 'Sales Rtn'` |
| Net Value     | Sales Value − Return Value |
| Bill count    | `COUNT(DISTINCT PDOC_NO)` per period |

## Project structure

```
.
├── comparison_analysis.py     # the Streamlit app (main file)
├── requirements.txt
├── README.md
├── .gitignore
├── .streamlit/
│   └── config.toml            # theme + server config
└── Sales_SalesRtn.csv         # dataset (see note below)
```

## Data

The app reads `Sales_SalesRtn.csv` from the repo root. If the file is missing,
it falls back to a file uploader so it still runs.

> For a **public** repo, commit an anonymised version of the dataset (or add
> `Sales_SalesRtn.csv` to `.gitignore` and rely on the uploader).

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run comparison_analysis.py
```

The app opens at http://localhost:8501.

## Deploy to Streamlit Community Cloud

1. Push this folder to a GitHub repo:

   ```bash
   git init
   git add .
   git commit -m "Comparison analysis dashboard"
   git branch -M main
   git remote add origin https://github.com/<user>/<repo>.git
   git push -u origin main
   ```

2. Go to https://share.streamlit.io → **New app**.
3. Select the repo, branch `main`, and set **Main file path** to
   `comparison_analysis.py`.
4. Click **Deploy**. Streamlit installs `requirements.txt` automatically.

If your dataset is private, don't commit it — deploy with the uploader fallback,
or load it from a private source using Streamlit **Secrets**
(`.streamlit/secrets.toml`, which is git-ignored).
