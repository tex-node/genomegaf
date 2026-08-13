"""
data_loader.py
Load real OHLC data (e.g. an MT5 CSV export) for use with GAFIndicator,
replacing demo.py's synthetic generator.

Expected CSV columns (case-insensitive, order doesn't matter): a column
each for high, low, close. Common MT5 export headers like
"<HIGH>"/"<LOW>"/"<CLOSE>" or "High"/"Low"/"Close" are both recognized.
"""

import csv
import numpy as np

_ALIASES = {
    "high": {"high", "<high>"},
    "low": {"low", "<low>"},
    "close": {"close", "<close>"},
}


def _match_column(fieldnames, key):
    aliases = _ALIASES[key]
    for name in fieldnames:
        if name.strip().lower() in aliases:
            return name
    raise ValueError(
        f"Could not find a '{key}' column in header {fieldnames}. "
        f"Expected one of {sorted(aliases)}."
    )


def load_ohlc_csv(path: str, delimiter: str = None):
    """
    Read a CSV file into (high, low, close) numpy arrays, oldest bar first.

    delimiter: pass explicitly ("," or "\\t") if sniffing fails on your export.
    """
    with open(path, newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        if delimiter is None:
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
            except csv.Error:
                delimiter = ","
        reader = csv.DictReader(f, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError(f"{path} has no header row")

        high_col = _match_column(reader.fieldnames, "high")
        low_col = _match_column(reader.fieldnames, "low")
        close_col = _match_column(reader.fieldnames, "close")

        high, low, close = [], [], []
        for row in reader:
            high.append(float(row[high_col]))
            low.append(float(row[low_col]))
            close.append(float(row[close_col]))

    if not close:
        raise ValueError(f"{path} contained a header but no data rows")

    return np.array(high), np.array(low), np.array(close)
