# ALGO Edge Performance History

Deployable Streamlit app with:

- Historical equity curve
- Full participation vs. three-month sit-out overlay
- Configurable sit-out window
- 1-year Monte Carlo projection
- 10-year Monte Carlo projection
- Ending-value distributions
- Percentile summary table

## Streamlit Cloud deployment

1. Put these files in the root of your GitHub repository:
   - `app.py`
   - `requirements.txt`
   - `.streamlit/config.toml`

2. Commit and push:

```bash
git add app.py requirements.txt .streamlit/config.toml README.md
git commit -m "Add sit-out overlay deployment build"
git push
```

3. In Streamlit Cloud, set the main file path to:

```text
app.py
```

## Local test

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Expected CSV formats

Best format:

```csv
date,balance
2026-01-01,100000
2026-01-02,100850
```

Also supported:

```csv
date,return
2026-01-01,0.005
2026-01-02,-0.002
```

or:

```csv
date,pnl
2026-01-01,500
2026-01-02,-200
```

For P/L-only files, the app reconstructs the balance from the sidebar starting balance.
