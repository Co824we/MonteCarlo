# ALGO Edge Trading Analytics — Streamlit App

This is a Streamlit version of the trading analytics tool.

Users upload a balance-history CSV and the app generates:

- Daily return distribution
- 1-year and 10-year Monte Carlo projections
- Monte Carlo assumption check
- Return magnitude / volatility clustering check
- 1-year and 10-year sit-out-rule overlays
- Full report zip

## CSV requirements

Required columns:

- `Date`
- `Day_PL_Percent`
- `Deposits/Withdrawals`

Optional but recommended:

- `NLV`

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy on Streamlit Community Cloud

Use:

- Repository: your repo
- Branch: `main`
- Main file path: `streamlit_app.py`

The app does not need Discord tokens, API keys, or secrets.
