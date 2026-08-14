"""
mt5_feed.py
Read-only connector to a locally running MetaTrader 5 terminal: historical
rates for backtesting/validation, and polling for live bars.

THIS FILE NEVER PLACES, MODIFIES, OR CLOSES ORDERS. It only reads market
data and (optionally) account balance/equity for display. Order execution
is intentionally not implemented — see README.md.

Usage assumes an MT5 terminal is already installed, running, and logged
into the account you want data from. `connect()` attaches to that running
terminal; it does not need or accept your password.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

try:
    import MetaTrader5 as mt5
except ImportError as e:  # pragma: no cover
    raise ImportError("pip install MetaTrader5 (Windows only, needs an MT5 terminal installed)") from e

# Default install location of the plain "MetaTrader 5" terminal on this
# machine (as opposed to a broker-branded copy, e.g. "Headway MT5
# Terminal") — pass a different `path` to connect() to target another one.
DEFAULT_TERMINAL_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"

TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

# Common aliases for the instruments this project validates against —
# actual tradable symbol names vary per broker, so resolve_symbol() below
# searches the connected terminal's symbol list rather than hardcoding one.
SYMBOL_ALIASES = {
    "US500": ["US500", "SPX500", "SP500", "US500.cash", "US500m"],
    "US100": ["US100", "USTEC", "NAS100", "US100.cash", "NDX100"],
    "DJIA": ["US30", "DJ30", "DJIA", "WS30", "US30.cash"],
    "EURUSD": ["EURUSD"],
    "XAUUSD": ["XAUUSD", "GOLD", "XAUUSD.cash"],
}


class MT5Error(RuntimeError):
    pass


def connect(path: str = DEFAULT_TERMINAL_PATH):
    """Attach to an already-running, already-logged-in MT5 terminal.

    Does not accept or need a password — it talks to whatever account the
    terminal you point it at is currently logged into.
    """
    ok = mt5.initialize(path=path)
    if not ok:
        code, msg = mt5.last_error()
        raise MT5Error(f"mt5.initialize() failed ({code}): {msg}. "
                        f"Is the terminal at '{path}' running and logged in?")


def disconnect():
    mt5.shutdown()


def account_summary() -> dict:
    """Read-only account info for display (balance/equity/currency/server).
    Never used to authorize or place trades."""
    info = mt5.account_info()
    if info is None:
        code, msg = mt5.last_error()
        raise MT5Error(f"account_info() failed ({code}): {msg}")
    return {
        "login": info.login,
        "server": info.server,
        "currency": info.currency,
        "balance": info.balance,
        "equity": info.equity,
        "leverage": info.leverage,
        "trade_mode": ["demo", "contest", "real"][info.trade_mode] if info.trade_mode in (0, 1, 2) else "unknown",
    }


def resolve_symbol(keyword: str) -> str:
    """Find the broker's actual symbol name for a friendly keyword like
    'US500' or 'XAUUSD'. Raises with the closest candidates if ambiguous
    or not found, since naming varies a lot per broker."""
    all_symbols = mt5.symbols_get()
    if all_symbols is None:
        raise MT5Error("symbols_get() returned None — not connected?")
    names = [s.name for s in all_symbols]

    candidates = SYMBOL_ALIASES.get(keyword.upper(), [keyword])
    for cand in candidates:
        for name in names:
            if name.upper() == cand.upper():
                return name
    # loose substring fallback
    key_core = candidates[0].upper()
    loose = [n for n in names if key_core in n.upper()]
    if len(loose) == 1:
        return loose[0]
    if loose:
        raise MT5Error(f"Ambiguous symbol for '{keyword}': candidates {loose}. Pass the exact broker symbol instead.")
    raise MT5Error(f"No symbol found for '{keyword}' among {len(names)} available symbols. "
                    f"Try mt5_feed.list_symbols() to browse.")


def list_symbols(filter_str: str = None):
    syms = mt5.symbols_get()
    names = sorted(s.name for s in syms)
    if filter_str:
        names = [n for n in names if filter_str.upper() in n.upper()]
    return names


def symbol_cost_info(symbol: str) -> dict:
    """Current spread, in price terms, for transaction-cost modeling."""
    info = mt5.symbol_info(symbol)
    if info is None:
        raise MT5Error(f"symbol_info('{symbol}') returned None")
    if not info.visible:
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)
    return {"point": info.point, "spread_points": info.spread, "digits": info.digits,
            "spread_price": info.spread * info.point}


@dataclass
class Bars:
    time: np.ndarray    # unix seconds, UTC
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray


def fetch_history(symbol_keyword: str, timeframe: str, count: int, retries: int = 3) -> Bars:
    """Most recent `count` closed bars for a resolved symbol."""
    import time as _time

    symbol = resolve_symbol(symbol_keyword)
    if not mt5.symbol_select(symbol, True):
        raise MT5Error(f"symbol_select('{symbol}') failed")

    tf = TIMEFRAMES[timeframe]
    rates = None
    last_msg = None
    for attempt in range(retries):
        if attempt > 0:
            _time.sleep(1.0)
        rates = mt5.copy_rates_from_pos(symbol, tf, 1, count)  # start at 1 = skip the still-forming bar
        if rates is not None and len(rates) > 0:
            break
        last_msg = mt5.last_error()
    if rates is None or len(rates) == 0:
        raise MT5Error(f"copy_rates_from_pos('{symbol}') failed after {retries} attempts: {last_msg}")
    return Bars(
        time=rates["time"].astype(np.int64),
        open=rates["open"].astype(np.float64),
        high=rates["high"].astype(np.float64),
        low=rates["low"].astype(np.float64),
        close=rates["close"].astype(np.float64),
    )


def fetch_history_range(symbol_keyword: str, timeframe: str, date_from: datetime, date_to: datetime) -> Bars:
    symbol = resolve_symbol(symbol_keyword)
    if not mt5.symbol_select(symbol, True):
        raise MT5Error(f"symbol_select('{symbol}') failed")
    tf = TIMEFRAMES[timeframe]
    rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)
    if rates is None or len(rates) == 0:
        code, msg = mt5.last_error()
        raise MT5Error(f"copy_rates_range('{symbol}') failed ({code}): {msg}")
    return Bars(
        time=rates["time"].astype(np.int64),
        open=rates["open"].astype(np.float64),
        high=rates["high"].astype(np.float64),
        low=rates["low"].astype(np.float64),
        close=rates["close"].astype(np.float64),
    )


_BAR_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}


def fetch_history_range_chunked(symbol_keyword: str, timeframe: str, date_from: datetime,
                                 date_to: datetime, max_bars_per_chunk: int = 80_000) -> Bars:
    """Like fetch_history_range, but splits into multiple calls if the
    requested span would exceed the terminal's maxbars setting (this
    account's terminal caps single requests at 100,000 bars — see
    terminal_info().maxbars — so a wide range on a fine timeframe, e.g.
    16 months of M5, needs chunking). Chunks are de-duplicated by
    timestamp at the boundaries and returned as one continuous Bars."""
    span_seconds = (date_to - date_from).total_seconds()
    bar_seconds = _BAR_SECONDS[timeframe]
    est_bars = span_seconds / bar_seconds
    if est_bars <= max_bars_per_chunk:
        return fetch_history_range(symbol_keyword, timeframe, date_from, date_to)

    chunk_span = timedelta(seconds=max_bars_per_chunk * bar_seconds)
    all_times, all_open, all_high, all_low, all_close = [], [], [], [], []
    cursor = date_from
    while cursor < date_to:
        chunk_end = min(cursor + chunk_span, date_to)
        try:
            b = fetch_history_range(symbol_keyword, timeframe, cursor, chunk_end)
            all_times.append(b.time)
            all_open.append(b.open)
            all_high.append(b.high)
            all_low.append(b.low)
            all_close.append(b.close)
        except MT5Error:
            pass  # a chunk with no data (e.g. before the symbol existed) is fine to skip
        cursor = chunk_end

    if not all_times:
        raise MT5Error(f"No data for '{symbol_keyword}' ({timeframe}) in {date_from} to {date_to}")

    times = np.concatenate(all_times)
    times, uniq_idx = np.unique(times, return_index=True)
    return Bars(
        time=times,
        open=np.concatenate(all_open)[uniq_idx],
        high=np.concatenate(all_high)[uniq_idx],
        low=np.concatenate(all_low)[uniq_idx],
        close=np.concatenate(all_close)[uniq_idx],
    )


def latest_closed_bar_time(symbol_keyword: str, timeframe: str) -> int:
    """Used by live_signal.py to detect when a new bar has closed."""
    b = fetch_history(symbol_keyword, timeframe, 1)
    return int(b.time[-1])


if __name__ == "__main__":
    connect()
    try:
        acct = account_summary()
        print(f"Connected: login={acct['login']} server={acct['server']} "
              f"mode={acct['trade_mode']} balance={acct['balance']} {acct['currency']}")
        for kw in ["US500", "US100", "DJIA", "EURUSD", "XAUUSD"]:
            try:
                sym = resolve_symbol(kw)
                cost = symbol_cost_info(sym)
                print(f"{kw:8s} -> {sym:14s} spread={cost['spread_points']} pts "
                      f"({cost['spread_price']:.5f} price units)")
            except MT5Error as e:
                print(f"{kw:8s} -> NOT FOUND: {e}")
    finally:
        disconnect()
