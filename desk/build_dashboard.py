#!/usr/bin/env python3
"""Build the ORB Trade Desk dashboard from the Day Trader skill pack's trader/ files.

Reads what the skills already wrote (watchlist, entry, plan, timemachine, orders,
risk verdicts, alerts, config) plus the optional side files run_desk.py saves in
trader/desk/ (news.json, sizing.json, bars.json, log.json), and writes one
self-contained HTML page. Standard library only. It never talks to a broker.

    python3 build_dashboard.py                       # trader/ -> dashboard.html
    python3 build_dashboard.py --trader trader --out dashboard.html --open
    python3 build_dashboard.py --mode replay --as-of "2026-10-19 10:15 ET"
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "dashboard_template.html")


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# --- New York time without tz files (works on Windows too) ------------------
def _nth_sunday(year, month, n):
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(6 - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def ny_offset(utc):
    """-4 h in daylight time (2nd Sun Mar 2:00 to 1st Sun Nov 2:00 local), else -5 h."""
    y = utc.year
    start = dt.datetime.combine(_nth_sunday(y, 3, 2), dt.time(7))   # 2:00 EST = 07:00 UTC
    end = dt.datetime.combine(_nth_sunday(y, 11, 1), dt.time(6))    # 2:00 EDT = 06:00 UTC
    naive = utc.replace(tzinfo=None)
    return dt.timedelta(hours=-4 if start <= naive < end else -5)


def to_ny(iso):
    if not iso:
        return None
    try:
        t = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return str(iso)
    if t.tzinfo is None:
        return t.strftime("%Y-%m-%d %H:%M ET")
    u = t.astimezone(dt.timezone.utc)
    return (u + ny_offset(u)).strftime("%Y-%m-%d %H:%M ET")


# --- bars --------------------------------------------------------------------
def bars_from_yahoo(doc, day=None):
    """Yahoo v8 chart JSON -> [{t:'HH:MM', o,h,l,c,v}] for one regular session."""
    try:
        r = doc["chart"]["result"][0]
        ts = r["timestamp"]
        q = r["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError):
        return None
    out = []
    for i, t in enumerate(ts):
        u = dt.datetime.fromtimestamp(t, dt.timezone.utc)
        n = u + ny_offset(u)
        o, h, l, c = (q["open"][i], q["high"][i], q["low"][i], q["close"][i])
        if None in (o, h, l, c) or n.minute % 5 or n.second:
            continue
        if not (dt.time(9, 30) <= n.time() < dt.time(16, 0)):
            continue
        out.append({"d": n.strftime("%Y-%m-%d"), "t": n.strftime("%H:%M"), "o": round(o, 2), "h": round(h, 2),
                    "l": round(l, 2), "c": round(c, 2), "v": int(q["volume"][i] or 0)})
    if not out:
        return None
    day = day or out[-1]["d"]
    sess = [b for b in out if b["d"] == day]
    for b in sess:
        b.pop("d", None)
    return sess or None


def fetch_bars(symbol):
    url = "https://query2.finance.yahoo.com/v8/finance/chart/%s?range=1d&interval=5m" % symbol
    req = urllib.request.Request(url, headers={"User-Agent": "day-trader-skill/2.0 (orb-desk)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as exc:  # network is optional
        print("bars: could not fetch %s from Yahoo (%s); the chart will be empty" % (symbol, exc), file=sys.stderr)
        return None


def drop_closed_only(bars, now_ny):
    """Keep bars that have closed by now (start + 5 minutes <= now)."""
    if not bars or not now_ny:
        return bars
    hm = now_ny[11:16] if len(now_ny) >= 16 else None
    if not hm:
        return bars
    lim = dt.datetime.strptime(hm, "%H:%M")
    return [b for b in bars if dt.datetime.strptime(b["t"], "%H:%M") + dt.timedelta(minutes=5) <= lim] or bars


def build(args):
    T = args.trader
    X = os.path.join(T, "desk")
    data = {
        "mode": args.mode,
        "built_at": (args.built_at or to_ny(dt.datetime.now(dt.timezone.utc).isoformat())),
        "config": load(os.path.join(T, "config.json")) or {},
        "watchlist": load(os.path.join(T, "watchlist.json")),
        "entry": load(os.path.join(T, "entry.json")),
        "plan": load(os.path.join(T, "plan.json")),
        "timemachine": load(os.path.join(T, "timemachine.json")),
        "risk": load(os.path.join(T, "state", "risk.json")),
        "alerts": load(os.path.join(T, "alerts.json")),
        "alert_state": None,
        "broker_log": [],
    }
    data["config"].pop("sec_user_agent", None)  # personal; not needed on the page
    orders = load(os.path.join(T, "orders.json"))
    if isinstance(orders, dict):
        orders = orders.get("orders") or [orders]
    data["orders"] = orders or None

    st = load(os.path.join(T, "state", "alerts.json")) or {}
    data["alert_state"] = {"fired": {k: to_ny(v) for k, v in (st.get("rung") or {}).items()}}

    blog = load(os.path.join(T, "state", "broker.json"))
    if isinstance(blog, dict):
        data["broker_log"] = blog.get("log") or blog.get("entries") or []

    sizing = load(os.path.join(X, "sizing.json"))
    if isinstance(sizing, dict):
        data["sizing"] = sizing.get("sizing") if sizing.get("sizing", {}).get("qty") else None
        if not data["sizing"]:
            data["sizing_refused"] = (sizing.get("sizing") or {}).get("refusal") or sizing.get("error")

    news = load(os.path.join(X, "news.json"))
    if news:
        news["checked_ny"] = to_ny(news.get("checked"))
        for it in news.get("items", []):
            it["time_ny"] = to_ny(it.get("time"))
        for mv in news.get("moves", []):
            mv["time_ny"] = to_ny(mv.get("time"))
        data["news"] = news

    log = load(os.path.join(X, "log.json"))
    if log:
        data["log"] = log

    plan, entry = data["plan"], data["entry"]
    symbol = (plan or {}).get("symbol") or (entry or {}).get("symbol") or args.symbol
    data["symbol"] = symbol
    day = (plan or {}).get("date") or (entry or {}).get("date")

    raw = load(args.bars) if args.bars else load(os.path.join(X, "bars.json"))
    if raw is None and symbol and not args.no_fetch:
        raw = fetch_bars(symbol)
    bars = bars_from_yahoo(raw, day) if raw else None
    data["as_of"] = args.as_of or (data["watchlist"] or {}).get("as_of") or to_ny(dt.datetime.now(dt.timezone.utc).isoformat())
    if args.bars_until:
        bars = drop_closed_only(bars, "0000-00-00 " + args.bars_until)
    data["bars"] = bars

    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read().replace("__DESK_DATA__", blob, 1)
    if args.full_document:
        head = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body style="margin:0">'
        html = head + html + "</body></html>"
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trader", default="trader", help="the skills' trader/ folder")
    ap.add_argument("--out", default="dashboard.html")
    ap.add_argument("--bars", help="a saved Yahoo chart JSON for the session chart")
    ap.add_argument("--bars-until", help="HH:MM: only bars closed by then")
    ap.add_argument("--no-fetch", action="store_true", help="never fetch bars from Yahoo")
    ap.add_argument("--symbol")
    ap.add_argument("--mode", choices=["live", "replay"], default="live")
    ap.add_argument("--as-of")
    ap.add_argument("--built-at")
    ap.add_argument("--fragment", dest="full_document", action="store_false",
                    help="write the page without <html>/<head> (for publishing as a claude.ai artifact)")
    ap.add_argument("--open", action="store_true", help="open it in your browser")
    args = ap.parse_args(argv)
    d = build(args)
    n = sum(1 for k in ("watchlist", "entry", "plan", "timemachine", "risk") if d.get(k))
    print("Wrote %s (%d of 5 pipeline files found%s)." % (args.out, n, ", %d bars" % len(d["bars"]) if d.get("bars") else ""))
    if args.open:
        import pathlib
        webbrowser.open(pathlib.Path(args.out).resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
