"""
live_signal.py
Signals-only live watcher. Polls MT5 for newly closed bars on configured
instruments, runs the GAF pipeline, and prints/logs what it would signal.

THIS SCRIPT NEVER PLACES, MODIFIES, OR CLOSES AN ORDER. It has no access to
mt5.order_send() or any execution function — it only reads bars and writes
lines to your terminal and a local CSV log. Every signal it prints is
something for YOU to evaluate and, if you choose, act on manually in MT5.

Run: py live_signal.py [--instruments US500,EURUSD] [--poll-interval 30]
"""

import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone

import mt5_feed
from gaf_indicator import GAFIndicator, GAFIndicatorConfig

DEFAULT_INSTRUMENTS = ["US500", "US100", "DJIA", "EURUSD", "XAUUSD"]
WARMUP_BARS = 1000
DEFAULT_CFG = GAFIndicatorConfig()  # used for any instrument without a validated config


def load_best_configs(timeframe: str):
    path = f"best_configs_{timeframe}.json"
    if not os.path.exists(path):
        print(f"(no {path} found — run `py run_validation.py --timeframe {timeframe}` first for "
              f"empirically chosen parameters; using library defaults for now)")
        return {}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    out = {}
    for kw, c in raw.items():
        out[kw] = GAFIndicatorConfig(
            window=c["window"], atr_period=c["atr_period"], horizon=c["horizon"],
            method=c["method"], similarity_threshold=c["similarity_threshold"],
            min_matches=c["min_matches"], max_db_size=c["max_db_size"],
        )
        if not c.get("beats_random_baseline", False):
            print(f"NOTE: {kw}'s validated config did NOT beat the random-direction baseline in "
                  f"VALIDATION_REPORT.md — treat its signals as informational only.")
    return out


class Tracker:
    def __init__(self, keyword: str, cfg: GAFIndicatorConfig, timeframe: str):
        self.keyword = keyword
        self.cfg = cfg
        self.timeframe = timeframe
        self.ind = GAFIndicator(cfg)
        self.last_bar_time = None
        self.next_bar_index = 0

    def warmup(self):
        bars = mt5_feed.fetch_history(self.keyword, self.timeframe, count=WARMUP_BARS)
        for i in range(len(bars.close)):
            self.ind.on_bar(i, bars.high[i], bars.low[i], bars.close[i])
        self.next_bar_index = len(bars.close)
        self.last_bar_time = int(bars.time[-1])
        print(f"[{self.keyword}] warmed up on {len(bars.close)} bars, last closed bar @ "
              f"{datetime.fromtimestamp(self.last_bar_time, tz=timezone.utc).isoformat()}")

    def poll(self, log_writer):
        latest = mt5_feed.fetch_history(self.keyword, self.timeframe, count=1)
        t = int(latest.time[-1])
        if t == self.last_bar_time:
            return  # no new closed bar yet
        self.last_bar_time = t
        c = float(latest.close[-1])
        h = float(latest.high[-1])
        l = float(latest.low[-1])
        sig = self.ind.on_bar(self.next_bar_index, h, l, c)
        self.next_bar_index += 1

        ts = datetime.fromtimestamp(t, tz=timezone.utc).isoformat()
        if sig is None:
            print(f"[{ts}] {self.keyword:8s} new bar, still warming up (not enough history yet)")
            return

        usable = sig.n_matches >= self.cfg.min_matches
        tag = "SIGNAL" if usable else "no-signal"
        direction_str = "BULLISH" if sig.direction > 0 else ("BEARISH" if sig.direction < 0 else "flat")
        print(f"[{ts}] {self.keyword:8s} {tag:10s} {direction_str:8s} "
              f"confidence={sig.confidence:.3f} matches={sig.n_matches} close={c:.5f} "
              f"-- nothing executed, this is informational only")

        if log_writer:
            log_writer.writerow([ts, self.keyword, c, sig.direction, sig.confidence, sig.n_matches, usable])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instruments", default=",".join(DEFAULT_INSTRUMENTS))
    parser.add_argument("--timeframe", choices=["M15", "H1", "D1"], default="H1")
    parser.add_argument("--poll-interval", type=float, default=30.0, help="seconds between MT5 checks")
    parser.add_argument("--log-file", default="signals_log.csv")
    args = parser.parse_args()
    instruments = [s.strip() for s in args.instruments.split(",") if s.strip()]

    print("=" * 70)
    print("live_signal.py — SIGNALS ONLY. No order will ever be placed by this script.")
    print("=" * 70)

    mt5_feed.connect()
    acct = mt5_feed.account_summary()
    print(f"Connected to MT5 ({acct['trade_mode']} account on {acct['server']}).")

    best_configs = load_best_configs(args.timeframe)
    trackers = [Tracker(kw, best_configs.get(kw, DEFAULT_CFG), args.timeframe) for kw in instruments]
    for t in trackers:
        t.warmup()

    new_log = not os.path.exists(args.log_file)
    log_file = open(args.log_file, "a", newline="", encoding="utf-8")
    log_writer = csv.writer(log_file)
    if new_log:
        log_writer.writerow(["timestamp_utc", "instrument", "close", "direction", "confidence", "n_matches", "usable"])

    print(f"\nPolling every {args.poll_interval}s for new closed {args.timeframe} bars. Ctrl+C to stop.\n")
    try:
        while True:
            for t in trackers:
                t.poll(log_writer)
            log_file.flush()
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        log_file.close()
        mt5_feed.disconnect()


if __name__ == "__main__":
    main()
