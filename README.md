# ALGO Edge Trading Analytics — Streamlit App

This is a Streamlit version of the trading analytics tool.

Users upload a balance-history CSV and the app generates:

- Daily return distribution
- 1-year / 10-year Monte Carlo projections
- Monte Carlo assumption check
- Return magnitude / volatility clustering check
- Sit-out-rule overlay
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

1. Create a GitHub repository.
2. Upload these files:
   - `streamlit_app.py`
   - `trading_analytics.py`
   - `requirements.txt`
   - `README.md`
3. Go to Streamlit Community Cloud.
4. Click **Create app**.
5. Choose your GitHub repo, branch, and entrypoint file:
   - `streamlit_app.py`
6. Deploy.

## Notes

The app does not need Discord tokens, API keys, or secrets.

Anyone with the Streamlit app link can upload a CSV and generate charts.
