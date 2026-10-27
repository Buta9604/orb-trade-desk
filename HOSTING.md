# Host the dashboard for free (GitHub Pages)

GitHub runs the skills every 10 minutes on weekdays during market hours and publishes
`dashboard.html` as a web page. It costs nothing on a **public** repository: GitHub
Actions is free for public repos, and GitHub Pages on the Free plan only publishes
from public repos.

**Everything in a public repo is public.** That includes `config.json` (your budget and
limits) and the dashboard page itself. Leave your SEC email out of `config.json` and put
it in a secret instead (step 4). The page never shows it.

## Steps (about 10 minutes, all in the browser)

1. **Make a repository.** On github.com: New repository, name it `orb-trade-desk`,
   Public, no README. Create.
2. **Upload the files.** On the new repo's page click "uploading an existing file".
   Drag in everything inside this folder: `.github`, `skills`, `desk`, `config.json`,
   `README.md`, `HOSTING.md`. Commit.
   - The `.github` folder is hidden on Mac. In Finder press Cmd+Shift+. to show it.
     If the upload still skips it, open the repo's Actions tab > "set up a workflow
     yourself", name it `desk.yml`, paste the contents of `.github/workflows/desk.yml`,
     and commit.
3. **Turn on Pages.** Settings > Pages > Build and deployment > Source: **GitHub Actions**.
4. **Add your settings.** Settings > Secrets and variables > Actions.
   - Secrets tab > New repository secret: `SEC_USER_AGENT` = `Your Name you@email.com`
     (optional; without it the news skips SEC 8-K filings).
   - Variables tab > New repository variable: `SYMBOLS` = the tickers to scan, comma
     separated, for example `TSLA,NVDA,AMD,AAPL,META`. Keep it to a few dozen names:
     a full-market scan takes minutes and hammers Yahoo every run.
   - Optional variable `PICK` = the one chart you picked (for example `TSLA`). With it,
     each run also does the entry check and, once it triggers, the plan, Time Machine,
     sizing, risk check and ticket. Change or delete it to switch stocks.
5. **First run.** Actions tab > ORB Trade Desk > Run workflow. When it turns green, the
   page is at `https://<your-username>.github.io/orb-trade-desk/` (the run's deploy
   step shows the link).
6. **Edit your limits** in `config.json` in the repo (pencil icon): `budget`,
   `max_loss_per_trade_usd`, `max_daily_loss_usd`, `max_trades_per_day`. Keep
   `"paper": true`.

## Good to know

- GitHub can start a scheduled run late, sometimes by 10 to 30 minutes at busy times,
  and gives no timing guarantee. The page shows when it was built. For timing an
  actual entry, run `desk/run_desk.py --watch 5` on your own computer.
- In a public repo GitHub turns schedules off after 60 days with no commits. Any
  commit (for example changing `config.json`) keeps it on, or re-enable it in the
  Actions tab.
- Yahoo's free feed is unofficial and may rate-limit or block cloud servers. If a run
  shows empty panels, the run log on the page (and in the Actions tab) says why.
- The cron times are in UTC. `*/10 13-21 * * 1-5` covers 9:30 AM to 4:00 PM New York in
  both daylight and standard time. Every 5 minutes (`*/5`) is the fastest GitHub allows.
- The hosted page cannot place orders. Trading stays in a Claude chat through
  `/trader-broker`, with your typed yes and the Allow once card.
