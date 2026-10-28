#!/usr/bin/env python3
"""ORB Trade Desk, hosted on this computer with live data.

Runs the Day Trader skills on a timer, rebuilds dashboard.html, and serves it at
http://localhost:8787 (only this computer can open it). The page reloads itself
after every rebuild. Stop it with Ctrl+C or by closing the window.

    python3 desk/serve_desk.py                     # settings from desk-settings.json
    python3 desk/serve_desk.py --symbol TSLA       # plan the chart you picked
    python3 desk/serve_desk.py --symbols TSLA,NVDA,AMD --every 5 --port 8787

Standard library only. It never places an order.
"""
import argparse
import datetime as dt
import functools
import http.server
import json
import os
import socketserver
import sys
import threading
import time
import traceback
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run_desk as RD  # noqa: E402

SETTINGS = os.path.join(ROOT, "desk-settings.json")
DEFAULTS = {
    "symbols": "TSLA,NVDA,AMD,AAPL,META,MSFT,AMZN,GOOGL,PLTR,NFLX",
    "pick": "",
    "every_minutes": 5,
    "closed_every_minutes": 30,
    "port": 8787,
    "target": "2R",
    "stop": "or-mid",
}
WAITING = """<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="10">
<title>ORB Trade Desk</title><body style="font:16px system-ui;padding:40px;background:#F2F5F6;color:#13242A">
<h1 style="font-size:22px">ORB Trade Desk is starting</h1>
<p>Running the scanner, news and entry checks on live data. The first build takes about a minute.
This page refreshes by itself.</p></body>"""


def load_settings(cli):
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            s.update({k: v for k, v in json.load(f).items() if v not in (None,)})
    except FileNotFoundError:
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(DEFAULTS, f, indent=2)
    except ValueError as exc:
        print("desk-settings.json is not valid JSON (%s); using the defaults" % exc)
    for k in ("symbols", "pick", "port", "target", "stop"):
        v = getattr(cli, k if k != "pick" else "symbol", None)
        if v:
            s[k] = v
    if cli.every:
        s["every_minutes"] = cli.every
    return s


def in_session(now):
    return now.weekday() < 5 and dt.time(9, 25) <= now.time() <= dt.time(16, 5)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.path = "/dashboard.html"
        if self.path.split("?")[0] == "/dashboard.html" and not os.path.exists(os.path.join(ROOT, "dashboard.html")):
            body = WAITING.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.split("?")[0] not in ("/dashboard.html", "/favicon.ico"):
            self.send_error(404)  # serve the page only, never trader/ or your config
            return
        super().do_GET()


def builder(s, stop):
    skills = RD.find_skills(os.path.join(ROOT, "skills") if os.path.isdir(os.path.join(ROOT, "skills")) else None)
    first = True
    while not stop.is_set():
        now = RD.ny_now()
        live = in_session(now)
        wait = float(s["every_minutes"] if live else s["closed_every_minutes"])
        args = argparse.Namespace(
            symbol=(s.get("pick") or "").upper() or None, scan="auto", symbols=s["symbols"], watchlist=None,
            level=None, stop=s["stop"], target=s["target"], news_top=5, skills=skills,
            out=os.path.join(ROOT, "dashboard.html"), open=False, watch=None, refresh=int(wait * 60) + 20)
        print("\n=== Rebuild %s New York (%s) ===" % (now.strftime("%Y-%m-%d %H:%M"), "market open" if live else "market closed"))
        try:
            RD.one_pass(args, skills)
        except Exception:
            traceback.print_exc()
            print("This rebuild failed; the last good page stays up. Trying again in %g minutes." % wait)
        if first:
            first = False
        print("Next rebuild in %g minutes. Dashboard: http://localhost:%s" % (wait, s["port"]))
        stop.wait(wait * 60)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", help="tickers to scan, comma separated")
    ap.add_argument("--symbol", help="the chart you picked (full plan, sizing and risk check)")
    ap.add_argument("--every", type=float, help="minutes between rebuilds while the market is open (default 5)")
    ap.add_argument("--port", type=int)
    ap.add_argument("--target")
    ap.add_argument("--stop")
    ap.add_argument("--no-browser", action="store_true")
    cli = ap.parse_args()
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    os.chdir(ROOT)  # trader/ and dashboard.html live next to desk/
    s = load_settings(cli)
    port = int(s["port"])

    handler = functools.partial(Quiet, directory=ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    except OSError:
        sys.exit("Port %d is busy (is the desk already running?). Close the other window, or set \"port\" in desk-settings.json." % port)
    httpd.daemon_threads = True

    stop = threading.Event()
    t = threading.Thread(target=builder, args=(s, stop), daemon=True)
    t.start()
    url = "http://localhost:%d" % port
    print("ORB Trade Desk is running at %s  (Ctrl+C to stop)" % url)
    print("Scanning: %s%s" % (s["symbols"], ("  |  planning: " + s["pick"]) if s.get("pick") else ""))
    print("Settings: %s   Limits: trader/config.json   Paper trading; this never places an order." % SETTINGS)
    if not cli.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        stop.set()
        httpd.server_close()


if __name__ == "__main__":
    main()
