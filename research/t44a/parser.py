"""
parser.py
Turns raw text (files, directories, stdin) into structured T44Record
objects. Handles only EXTRACTION and STRUCTURAL parsing here --
duplicate/snapshot resolution and semantic validation (arithmetic
consistency, range checks) live in aggregate.py, since they need to
compare across records rather than within one.

Record format (see spec Section 1):

T44C
|SYM=<symbol>
|CLASS=<asset_class>
|COHORT=<cohort>
|CELL=<cell>
|PAIR=<n>
|ERET=<mean_event_return>
...

Records may be copied directly from a TradingView console/log, so this
parser is deliberately tolerant of surrounding unrelated text, CRLF/LF,
and stray whitespace -- it only ever extracts "|KEY=VALUE" tokens that
appear after a "T44C" marker, and ignores everything else. It never
guesses or repairs an unparseable numeric value; a bad value is flagged,
not silently coerced.
"""

import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

IDENTITY_FIELDS = ["SYM", "CLASS", "COHORT", "CELL", "PAIR"]
METRIC_ATTR_MAP = {
    "ERET": "eret", "CRET": "cret", "DRET": "dret",
    "EHIT": "ehit", "CHIT": "chit",
    "EMFE": "emfe", "CMFE": "cmfe", "DMFE": "dmfe",
    "EMAE": "emae", "CMAE": "cmae", "DMAE": "dmae",
}
ALL_FIELDS = IDENTITY_FIELDS + list(METRIC_ATTR_MAP.keys())

SIDE_LABELS = {"B": "BUY", "S": "SELL"}
SOURCE_VALUES = ("BAND", "DIV")
AGE_BUCKETS = ("T01-05", "T06-10", "T11-15", "T16-20")
CANONICAL_CELLS = [
    f"{side}_{source}_{age}"
    for side in ("B", "S")
    for source in SOURCE_VALUES
    for age in AGE_BUCKETS
]  # 16 cells, in spec's listed order

CELL_RE = re.compile(r"^([BS])_(BAND|DIV)_(T\d{2}-\d{2})$")
FIELD_RE = re.compile(r"\|\s*([A-Za-z_]+)\s*=\s*([^|\r\n]*)")
MARKER_RE = re.compile(r"T44C")

READABLE_EXTENSIONS = ("*.txt", "*.log", "*.csv")


@dataclass
class T44Record:
    record_index: int
    source_file: str
    raw_text: str

    sym: Optional[str] = None
    asset_class: Optional[str] = None
    cohort: Optional[str] = None
    cell: Optional[str] = None
    side: Optional[str] = None
    source: Optional[str] = None
    age_bucket: Optional[str] = None
    pair: Optional[int] = None

    eret: Optional[float] = None
    cret: Optional[float] = None
    dret: Optional[float] = None
    ehit: Optional[float] = None
    chit: Optional[float] = None
    emfe: Optional[float] = None
    cmfe: Optional[float] = None
    dmfe: Optional[float] = None
    emae: Optional[float] = None
    cmae: Optional[float] = None
    dmae: Optional[float] = None

    delta_hit: Optional[float] = None
    dret_sign: int = 0
    dmfe_sign: int = 0
    dmae_sign: int = 0

    field_present: dict = field(default_factory=dict)
    field_raw: dict = field(default_factory=dict)

    parse_ok: bool = True
    parse_errors: list = field(default_factory=list)

    valid: bool = True
    warnings: list = field(default_factory=list)

    ret_delta_ok: Optional[bool] = None
    mfe_delta_ok: Optional[bool] = None
    mae_delta_ok: Optional[bool] = None

    is_duplicate_dropped: bool = False
    is_snapshot_conflict: bool = False
    retained: bool = False

    @property
    def eligible(self) -> bool:
        """Survived dedup AND passed semantic validation -- the set that
        feeds 01_records.csv and every aggregation level."""
        return self.retained and self.valid


def _parse_metric(raw: Optional[str]):
    """Returns (value, status) where status in {'ok','na','missing','invalid'}."""
    if raw is None or raw.strip() == "":
        return None, "missing"
    s = raw.strip()
    if s.upper() == "NA":
        return None, "na"
    try:
        return float(s), "ok"
    except ValueError:
        return None, "invalid"


def _parse_pair(raw: Optional[str]):
    if raw is None or raw.strip() == "":
        return None, "missing"
    s = raw.strip()
    try:
        return int(s), "ok"
    except ValueError:
        pass
    try:
        f = float(s)
        if f == int(f):
            return int(f), "ok"
    except ValueError:
        pass
    return None, "invalid"


def parse_block(raw_block: str, record_index: int, source_file: str) -> T44Record:
    fields_raw = {}
    for m in FIELD_RE.finditer(raw_block):
        key = m.group(1).strip().upper()
        val = m.group(2).strip()
        fields_raw[key] = val  # last occurrence wins within one block

    rec = T44Record(record_index=record_index, source_file=source_file, raw_text=raw_block.strip())
    rec.field_raw = {k: fields_raw.get(k) for k in ALL_FIELDS}
    rec.field_present = {k: (fields_raw.get(k, "") != "") for k in ALL_FIELDS}

    for attr, key in [("sym", "SYM"), ("asset_class", "CLASS"), ("cohort", "COHORT"), ("cell", "CELL")]:
        v = fields_raw.get(key)
        if v is None or v == "":
            rec.parse_ok = False
            rec.parse_errors.append(f"missing required field {key}")
        else:
            setattr(rec, attr, v)

    pair_val, pair_status = _parse_pair(fields_raw.get("PAIR"))
    if pair_status == "missing":
        rec.parse_ok = False
        rec.parse_errors.append("missing required field PAIR")
    elif pair_status == "invalid":
        rec.parse_ok = False
        rec.parse_errors.append(f"PAIR is not a valid integer: '{fields_raw.get('PAIR')}'")
    elif pair_val < 0:
        rec.parse_ok = False
        rec.parse_errors.append(f"PAIR is negative: {pair_val}")
    else:
        rec.pair = pair_val

    if rec.cell is not None:
        m = CELL_RE.match(rec.cell)
        if not m:
            rec.parse_ok = False
            rec.parse_errors.append(
                f"CELL '{rec.cell}' does not match an expected pattern (e.g. B_BAND_T01-05)"
            )
        else:
            rec.side = SIDE_LABELS[m.group(1)]
            rec.source = m.group(2)
            rec.age_bucket = m.group(3)

    for key, attr in METRIC_ATTR_MAP.items():
        val, status = _parse_metric(fields_raw.get(key))
        if status == "invalid":
            rec.parse_ok = False
            rec.parse_errors.append(f"{key} is not numeric or NA: '{fields_raw.get(key)}'")
        setattr(rec, attr, val)

    rec.valid = rec.parse_ok
    if not rec.parse_ok:
        rec.warnings.extend(rec.parse_errors)
    return rec


def parse_text(text: str, source_file: str, start_index: int = 0) -> list:
    """Splits text into per-record blocks at each 'T44C' marker and
    parses each one. Text between/around markers that isn't a
    '|KEY=VALUE' token is simply never matched by FIELD_RE, so unrelated
    surrounding text (other log lines, TradingView UI chrome, etc.) is
    naturally ignored rather than needing special-case stripping."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    starts = [m.start() for m in MARKER_RE.finditer(text)]
    records = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(text)
        block = text[s:e]
        records.append(parse_block(block, start_index + i, source_file))
    return records


def resolve_input_paths(paths: list) -> list:
    """Expands directories into their *.txt/*.log/*.csv files; passes
    '-' (stdin) and explicit file paths through unchanged."""
    resolved = []
    for p in paths:
        if p == "-":
            resolved.append(p)
            continue
        pth = Path(p)
        if pth.is_dir():
            found = []
            for pattern in READABLE_EXTENSIONS:
                found.extend(pth.glob(pattern))
            resolved.extend(str(f) for f in sorted(found))
        elif pth.is_file():
            resolved.append(str(pth))
        else:
            raise FileNotFoundError(f"input path not found: {p}")
    return resolved


def load_records(paths: list):
    """Reads every resolved input path (or stdin) and returns
    (records, file_hashes) -- the full, ordered list of parsed
    T44Record objects (not yet deduplicated or semantically validated,
    see aggregate.py) plus a {source_label: sha256_hexdigest} map for
    the reproducibility manifest."""
    all_records = []
    file_hashes = {}
    idx = 0
    for p in resolve_input_paths(paths):
        if p == "-":
            raw_bytes = sys.stdin.buffer.read()
            label = "<stdin>"
        else:
            raw_bytes = Path(p).read_bytes()
            label = p
        text = raw_bytes.decode("utf-8", errors="replace")
        file_hashes[label] = hashlib.sha256(raw_bytes).hexdigest()
        recs = parse_text(text, label, start_index=idx)
        idx += len(recs)
        all_records.extend(recs)
    return all_records, file_hashes
