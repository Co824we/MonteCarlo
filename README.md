# ALGO Edge Trading Analytics — Streamlit App

This version generates the main required outputs immediately after upload:

1. Daily return distribution
2. 1-year Monte Carlo projection
3. 10-year Monte Carlo projection

Optional checkboxes in the sidebar can also generate:

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

## Deploy on Streamlit Community Cloud

Use:

- Repository: your repo
- Branch: `main`
- Main file path: `streamlit_app.py`

The app does not need Discord tokens, API keys, or secrets.
