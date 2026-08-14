"""
yahoo_feed.py
Secondary/cross-check data source via Yahoo Finance (yfinance). Used to
sanity-check MT5 results against an independent data source, and to reach
further back in history than MT5's intraday retention on some brokers.

Yahoo's intraday (60m) history is capped at roughly the last 730 days by
Yahoo's own API, regardless of how far back you ask.
"""

import time
from dataclasses import dataclass

import numpy as np
import yfinance as yf

# Best-effort mapping from this project's instrument keywords to Yahoo
# tickers. Yahoo has no direct CFD equivalents, so indices/metals are
# proxied by their underlying index/futures ticker — expect small
# differences from a broker's CFD price (dividends, funding, roll dates).
YAHOO_TICKERS = {
    "US500": "^GSPC",
    "US100": "^NDX",
    "DJIA": "^DJI",
    "EURUSD": "EURUSD=X",
    "XAUUSD": "GC=F",  # COMEX gold futures, closest liquid free proxy for spot gold
}

INTERVALS = {"M15": "15m", "M30": "30m", "H1": "60m", "D1": "1d"}


@dataclass
class Bars:
    time: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray


def fetch_history(keyword: str, timeframe: str, period: str = "730d", retries: int = 3) -> Bars:
    ticker = YAHOO_TICKERS.get(keyword.upper(), keyword)
    interval = INTERVALS[timeframe]

    # Yahoo's endpoint is intermittently flaky under back-to-back requests
    # (raises internal 'NoneType is not subscriptable' errors) — retry
    # with backoff rather than surfacing a transient failure as data loss.
    last_err = None
    df = None
    for attempt in range(retries):
        try:
            df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
            if not df.empty:
                break
        except Exception as e:
            last_err = e
        time.sleep(1.5 * (attempt + 1))
    if df is None or df.empty:
        raise ValueError(f"Yahoo Finance returned no data for '{ticker}' ({timeframe}, {period}) "
                          f"after {retries} attempts. Last error: {last_err}")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    return Bars(
        time=(df.index.view(np.int64) // 10**9),
        open=df["Open"].to_numpy(dtype=np.float64),
        high=df["High"].to_numpy(dtype=np.float64),
        low=df["Low"].to_numpy(dtype=np.float64),
        close=df["Close"].to_numpy(dtype=np.float64),
    )


if __name__ == "__main__":
    for kw in ["US500", "US100", "DJIA", "EURUSD", "XAUUSD"]:
        try:
            b = fetch_history(kw, "H1")
            print(f"{kw:8s} -> {YAHOO_TICKERS[kw]:8s} {len(b.close)} H1 bars, "
                  f"latest close={b.close[-1]:.4f}")
        except Exception as e:
            print(f"{kw:8s} -> FAILED: {e}")
