# ORB Trade Desk

The Day Trader skill pack (github.com/Jakeschincariol/day-trader-skill, MIT) plus a
dashboard that shows its whole pipeline on one page: scanner hits, news, the entry
trigger, the exit plan, the Time Machine's 10,000 replays, position size, the risk
gate and the bracket ticket.

Nothing here can place an order. Paper trading is the default. Not financial advice:
most people who day trade lose money.

## What's in the folder

```
skills/      the 11 trader-* skills, unchanged (SKILL.md + one Python tool each)
desk/        run_desk.py (runs the skills in order), build_dashboard.py, dashboard_template.html
setup.sh     installs the skills for Claude Code (Mac / Linux)
setup.bat    same, for Windows
```

## 1. One-time setup

1. Install Python 3.8 or newer (python.org). Nothing to pip install.
2. Unzip this folder somewhere you keep projects and open a terminal in it.
3. First run creates `trader/config.json` with the example limits:

   ```
   python3 desk/run_desk.py --scan skip
   ```

   On Windows use `py` instead of `python3`.
4. Open `trader/config.json` and set your own numbers: `budget`, `max_loss_per_trade_usd`,
   `max_daily_loss_usd`, `max_trades_per_day`. Keep `"paper": true`.
   Put your name and email in `sec_user_agent` (SEC asks every caller to identify
   themselves); until you do, the news step skips 8-K filings.

## 2. Every trading day

| when (New York time) | command | what you get |
| --- | --- | --- |
| before 9:30 | `python3 desk/run_desk.py --open` | pre-market daily scan + news on the top hits |
| after 9:50 | `python3 desk/run_desk.py --open` | opening-range breakout scan |
| you picked a chart | `python3 desk/run_desk.py --symbol TSLA --scan skip --open` | entry check; if triggered: plan, Time Machine, size, risk, ticket, alerts |
| while you wait | `python3 desk/run_desk.py --symbol TSLA --scan skip --watch 5` | rebuilds every 5 minutes until 4:00 PM; reload the page |

The full-market scan reads about 5,900 charts and takes about 4 minutes. For a fast
scan of names you trade: `--symbols TSLA,NVDA,AMD,AAPL,META`.

Options: `--target 1R` (default 2R), `--stop or-low` / `pct:1` / `atr:1.5`
(default the opening-range midpoint), `--level 371.20` for a level breakout.

The page is `dashboard.html` in this folder. The runner never picks a stock for you:
the scan lists charts that match a rule, and you choose.

## 3. Use the skills inside Claude

- **Claude Code** (best: the tools need internet access to Yahoo, SEC and Nasdaq):
  run `./setup.sh` (or `setup.bat`). It copies the skills to `~/.claude/skills`.
  Then in Claude Code type `/trader-scanner`, `/trader-entry TSLA`, and so on.
- **claude.ai**: Settings > Capabilities > Skills > upload each `trader-*.zip` from
  `claude-ai-uploads/`. The method works there, but the claude.ai sandbox may not be
  able to reach Yahoo, so live data is most reliable from Claude Code or this runner.

## Host it on the web for free

See HOSTING.md: GitHub Pages rebuilds the page every 10 minutes during market hours.

## 4. Placing an order (optional, paper first)

Only `/trader-broker` can lead to an order, and only after trader-risk passes that exact
order, you type yes for it, and you click Allow once on Claude's card. Its SKILL.md has
the Alpaca paper setup (Claude Desktop > Settings > Developer > Edit Config). Your API
keys go in that config file only, never in a chat. Set `place_stock_order` to
"Needs approval", never "Always allow".

## Data

Yahoo Finance's chart and headline feeds are free, unofficial and delayed. Bars are
5-minute bars, never tick by tick. Check anything that matters against your broker.
