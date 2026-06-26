# Trading Analytics Discord Bot

A Discord slash-command bot for analyzing uploaded balance-history CSV files.

It reproduces the analyses we discussed:

- Daily return distribution
- Monte Carlo projections
- Monte Carlo assumption check
- Return magnitude / volatility clustering check
- Sit-out-rule overlay
- Full report zip

## Commands

### `/return_distribution`
Uploads a balance-history CSV and returns the daily return distribution chart.

### `/monte_carlo`
Uploads a balance-history CSV and returns a 1-year or 10-year Monte Carlo chart.

Options:
- `horizon`: 1 year or 10 years
- `paths`: default 1000, capped at 5000
- `all_paths`: whether to show all simulated paths in the background

### `/assumption_check`
Checks whether today's trading return predicts the next trading day's return.

### `/magnitude_clustering`
Checks whether large gains/losses tend to be followed by more large gains/losses.

### `/sitout_overlay`
Compares the baseline Monte Carlo against a rule where the trader sits out after a negative rolling 3-month period.

### `/full_report`
Generates all major charts and a summary text file in a zip.

## CSV requirements

The uploaded CSV needs these columns:

- `Date`
- `Day_PL_Percent`
- `Deposits/Withdrawals`

Optional but recommended:

- `NLV`

The cleaning logic removes:

- zero-return rows
- deposit/withdrawal rows
- obvious transfer/accounting artifacts where `|Day_PL_Percent| > 10`

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate   # Mac/Linux
# .venv\Scripts\activate    # Windows

pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add:

```bash
DISCORD_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_server_id_here
```

Then run:

```bash
python bot.py
```

## Discord setup

1. Create an application in the Discord Developer Portal.
2. Add a bot to the application.
3. Copy the bot token into `.env`.
4. Invite the bot to your server with:
   - `bot`
   - `applications.commands`

## Notes

During development, use `DISCORD_GUILD_ID` so commands sync directly to your server. Global slash commands can take longer to appear.

Do not commit `.env` to GitHub.
