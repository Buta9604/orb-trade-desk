#!/usr/bin/env python3
"""ORB Trade Desk: run the Day Trader skill pack's tools in order and build the dashboard.

Run it from your project folder (where trader/ lives, or will be created):

    python3 desk/run_desk.py                          # scan + news on the top hits -> dashboard.html
    python3 desk/run_desk.py --symbol TSLA            # full pipeline for the chart YOU picked
    python3 desk/run_desk.py --symbol TSLA --watch 5  # rebuild every 5 minutes until the close
    python3 desk/run_desk.py --symbols TSLA,NVDA,AMD,AAPL,META --symbol NVDA   # fast scan of your list

Order, exactly as the skills hand off:
    scanner -> news -> entry -> exit -> timemachine -> (quote) -> budget -> risk -> alerts -> dashboard

It never picks a stock for you, and it never places an order. The last step it can
reach is a READY ticket; placing it is trader-broker's job in a Claude chat, after
your typed yes and Claude's Allow once card. Standard library only (Python 3.8+).
"""
import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_dashboard as BD  # noqa: E402


def find_skills(given):
    cands = [given] if given else []
    cands += [os.path.join(HERE, "..", "skills"), os.path.join(HERE, "..", "day-trader-skill"),
              os.path.join(os.path.expanduser("~"), ".claude", "skills")]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "trader-scanner", "scan.py")):
            return os.path.abspath(c)
    sys.exit("Could not find the trader-* skill folders. Pass --skills PATH (the folder that holds trader-scanner/).")


def ny_now():
    u = dt.datetime.now(dt.timezone.utc)
    return (u + BD.ny_offset(u)).replace(tzinfo=None)


class Runner:
    def __init__(self, skills, log):
        self.skills, self.log = skills, log

    def run(self, tool, *args, quiet=False, stdout_to=None):
        cmd = [sys.executable, os.path.join(self.skills, tool)] + [str(a) for a in args]
        short = "python3 " + tool + " " + " ".join(str(a) for a in args)
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        out = (p.stdout or "") + (("\n" + p.stderr) if p.stderr.strip() else "")
        if stdout_to:
            with open(stdout_to, "w", encoding="utf-8") as f:
                f.write(p.stdout or "")
            shown = (p.stderr or "").strip() or "(JSON saved to %s)" % stdout_to
        else:
            shown = out.strip()
        self.log.append({"cmd": short, "code": p.returncode, "out": shown[-4000:]})
        if not quiet:
            print("\n$ " + short + "   [exit %d]" % p.returncode)
            print(shown)
        return p.returncode, p.stdout or ""


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def ensure_config(skills):
    os.makedirs(os.path.join("trader", "desk"), exist_ok=True)
    cfg = os.path.join("trader", "config.json")
    if not os.path.exists(cfg):
        shutil.copy(os.path.join(skills, "trader-budget", "config.example.json"), cfg)
        print("Created trader/config.json from the example: $5,000 budget, $50 max loss a trade, PAPER.")
        print("Edit it before trading anything (budget, max loss, limits, sec_user_agent).")
    return load(cfg) or {}


def one_pass(args, skills):
    log = []
    R = Runner(skills, log)
    cfg = ensure_config(skills)
    ua = (os.environ.get("SEC_USER_AGENT") or cfg.get("sec_user_agent") or "")  # same order as news.py
    sec_ok = bool(ua) and "example.com" not in ua
    now = ny_now()
    print("New York time %s" % now.strftime("%a %Y-%m-%d %H:%M"))

    # 1. scanner ---------------------------------------------------------------
    mode = args.scan
    if mode == "auto":
        mode = "orb" if dt.time(9, 50) <= now.time() < dt.time(16, 0) and now.weekday() < 5 else "daily"
    if mode != "skip":
        scope = []
        if args.symbols:
            scope = ["--symbols", args.symbols]
        elif args.watchlist:
            scope = ["--watchlist", args.watchlist]
        else:
            uni = os.path.join("trader", "universe.txt")
            if not os.path.exists(uni) or time.time() - os.path.getmtime(uni) > 7 * 86400:
                R.run("trader-scanner/scan.py", "universe")
        code, _ = R.run("trader-scanner/scan.py", mode, *scope, "--show", "15")
        if code != 0 and mode == "orb":
            print("(no opening-range result; the pre-market daily scan still works before 9:50 or after the close)")

    wl = load(os.path.join("trader", "watchlist.json")) or {}
    sym = (args.symbol or "").upper() or None

    # 2. news -------------------------------------------------------------------
    tickers = [sym] if sym else [h["symbol"] for h in (wl.get("hits") or [])[: args.news_top]]
    if tickers:
        nargs = ["--tickers"] + tickers + ["--all", "--hours", "18", "--dry-run", "--json"]
        if not sec_ok:
            nargs.append("--no-sec")
        R.run("trader-news/news.py", *nargs, stdout_to=os.path.join("trader", "desk", "news.json"))
        if not sec_ok:
            log.append({"cmd": "note", "code": 0, "out": "SEC 8-K filings skipped: put \"Your Name you@email\" in sec_user_agent in trader/config.json."})

    if not sym:
        print("\nNo --symbol given. The scan is a list of charts that match a rule; pick one yourself, then run:")
        print("  python3 desk/run_desk.py --symbol TICKER")
    else:
        # fresh run for this symbol: clear yesterday's or another symbol's derived files
        for f in ("entry.json", "plan.json", "timemachine.json", "orders.json", os.path.join("desk", "sizing.json"),
                  os.path.join("desk", "bars.json")):
            p = os.path.join("trader", f)
            if os.path.exists(p):
                os.remove(p)
        # 3. entry --------------------------------------------------------------
        eargs = ["check", sym, "--write", "--interval", "5m"]
        if args.level:
            eargs += ["--setup", "level", "--level", args.level]
        R.run("trader-entry/entry.py", *eargs)
        entry = load(os.path.join("trader", "entry.json")) or {}
        if entry.get("status") == "triggered":
            # 4. exit plan --------------------------------------------------------
            code, _ = R.run("trader-exit/exit.py", "plan", "--stop", args.stop, "--target", args.target, "--write")
            if code == 0 and os.path.exists(os.path.join("trader", "plan.json")):
                plan = load(os.path.join("trader", "plan.json")) or {}
                # 5. time machine -------------------------------------------------
                R.run("trader-timemachine/timemachine.py", "run", "--write", "--until", plan.get("flat_by") or "15:55")
                # fresh delayed quote, so sizing and risk measure from the price now
                R.run("trader-alerts/alerts.py", "quote", sym, "--write")
                # 6. budget ----------------------------------------------------------
                R.run("trader-budget/size.py", "--json", stdout_to=os.path.join("trader", "desk", "sizing.json"), quiet=True)
                code, _ = R.run("trader-budget/size.py", "--write")
                # 7. risk ------------------------------------------------------------
                if code == 0:
                    R.run("trader-risk/check.py")
                    R.run("trader-broker/ticket.py", "show")
                # 8. alerts for the plan -----------------------------------------
                R.run("trader-alerts/alerts.py", "add", "--from-plan")
                R.run("trader-alerts/alerts.py", "check")
        else:
            print("\n%s has not triggered (%s). Nothing to plan yet; run again, or use --watch." % (sym, entry.get("status") or "no data"))

    with open(os.path.join("trader", "desk", "log.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, indent=1)
    extra = ["--refresh", str(args.refresh)] if getattr(args, "refresh", None) else []
    BD.main(["--trader", "trader", "--out", args.out] + (["--symbol", sym] if sym else []) + extra)
    print("\nNothing was placed. To trade a READY ticket, ask Claude: /trader-broker (paper by default).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbol", help="the chart you picked from the scan (long side only)")
    ap.add_argument("--scan", choices=["auto", "orb", "daily", "skip"], default="auto")
    ap.add_argument("--symbols", help="scan only these, comma separated (fast)")
    ap.add_argument("--watchlist", help="scan only the symbols in this watchlist file")
    ap.add_argument("--level", help="use a level setup at this price instead of the opening range")
    ap.add_argument("--stop", default="or-mid", help="or-mid | or-low | price:X | pct:X | atr:K (default or-mid)")
    ap.add_argument("--target", default="2R", help="2R | 1R | 1.5R | price:X (default 2R, the skill's default)")
    ap.add_argument("--news-top", type=int, default=5, help="news for this many top hits when no --symbol")
    ap.add_argument("--skills", help="folder that holds the trader-* skill folders")
    ap.add_argument("--out", default="dashboard.html")
    ap.add_argument("--open", action="store_true", help="open the dashboard in your browser")
    ap.add_argument("--watch", type=float, metavar="MIN", help="repeat every MIN minutes until 4:00 PM New York")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(errors="replace")  # Windows consoles
    except (AttributeError, ValueError):
        pass
    skills = find_skills(args.skills)
    opened = False
    while True:
        one_pass(args, skills)
        if args.open and not opened:
            import webbrowser
            import pathlib
            webbrowser.open(pathlib.Path(args.out).resolve().as_uri())
            opened = True
        if not args.watch or ny_now().time() >= dt.time(16, 0):
            break
        args.scan = "skip" if args.symbol else args.scan  # re-scan only when nothing is picked
        print("\nNext rebuild in %g minutes (Ctrl+C to stop; reload the page to see it)." % args.watch)
        time.sleep(args.watch * 60)


if __name__ == "__main__":
    main()
