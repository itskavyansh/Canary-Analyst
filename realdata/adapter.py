"""Adapter: turns a raw prototype recording into 1-minute NodeReading objects.

The events (ground-truth) file is NEVER read here, except for two narrow
purposes that never produce detector input:
  * ``read_events_timezone`` returns only the timezone string (needed to
    interpret naive timestamps),
  * ``quiet_minutes_at_start`` returns a single integer used for a console
    warning.
Nothing from the events file is stored in ``Session`` or passed to detectors.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from datetime import timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd

from generator.schema import NodeReading

MAX_FFILL_MINUTES = 2

MAX_CHANNELS = ["vibration", "piezo_peak", "piezo_peak_to_peak"]
MEDIAN_CHANNELS = ["tilt_x", "tilt_y", "distance", "piezo_rms"]
REQUIRED_CHANNELS = MAX_CHANNELS + MEDIAN_CHANNELS
STATUS_COLUMNS = ["mpu6050_status", "hc_sr04_status", "ads1115_status"]
NOISE_CHANNELS = ["tilt_x", "tilt_y", "vibration", "distance"]

_TZ_ALIASES = {"IST": "Asia/Kolkata", "UTC": "UTC", "Z": "UTC", "GMT": "UTC"}


def parse_timezone(name: str):
    """Parse an IANA name, alias or a +HH:MM / UTC+HH:MM offset into a tzinfo."""
    raw = (name or "").strip()
    if not raw:
        return timezone.utc
    key = _TZ_ALIASES.get(raw.upper())
    if key:
        return ZoneInfo(key) if key != "UTC" else timezone.utc
    m = re.fullmatch(r"(?:UTC|GMT)?\s*([+-])(\d{1,2})(?::?(\d{2}))?", raw, flags=re.I)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        delta = timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0))
        return timezone(sign * delta)
    return ZoneInfo(raw)


def read_events_timezone(events_path: Path) -> str:
    """Return ONLY the timezone column of the events file (first non-empty value)."""
    events_path = Path(events_path)
    if not events_path.exists():
        return ""
    tzs: List[str] = []
    with open(events_path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            v = (row.get("timezone") or "").strip()
            if v:
                tzs.append(v)
    if not tzs:
        return ""
    if len(set(tzs)) > 1:
        print(f"[adapter] WARNING: events file lists several timezones {sorted(set(tzs))}; using '{tzs[0]}'.")
    return tzs[0]


def to_utc(ts_str, default_tz) -> Optional[pd.Timestamp]:
    """Parse one timestamp string to a UTC Timestamp; naive values use default_tz."""
    if ts_str is None or (isinstance(ts_str, float) and pd.isna(ts_str)):
        return None
    s = str(ts_str).strip()
    if not s:
        return None
    try:
        t = pd.Timestamp(s)
    except (ValueError, TypeError):
        try:
            t = pd.Timestamp(pd.to_datetime(s, format="mixed"))
        except Exception:
            return None
    if t.tzinfo is None:
        t = t.tz_localize(default_tz, ambiguous=True, nonexistent="shift_forward")
    return t.tz_convert("UTC")


def load_layout(layout_path: Path) -> Dict[str, List[float]]:
    """Return {node_id: [x, y]} in meters. Accepts several simple JSON shapes."""
    with open(layout_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and isinstance(data.get("nodes"), (dict, list)):
        data = data["nodes"]
    out: Dict[str, List[float]] = {}
    if isinstance(data, list):
        for item in data:
            nid = item.get("node_id") or item.get("id")
            out[str(nid)] = [float(item["x"]), float(item["y"])]
    elif isinstance(data, dict):
        for nid, v in data.items():
            if isinstance(v, dict):
                out[nid] = [float(v["x"]), float(v["y"])]
            elif isinstance(v, (list, tuple)) and len(v) >= 2:
                out[nid] = [float(v[0]), float(v[1])]
    if not out:
        raise ValueError(f"Could not read any node coordinates from {layout_path}")
    return out


@dataclass
class Session:
    name: str
    layout: Dict[str, List[float]]
    readings: List[NodeReading]
    nodes: List[str]
    start: str
    end: str
    minutes_per_node: Dict[str, int]
    gaps: List[dict] = field(default_factory=list)
    filled_minutes: Dict[str, int] = field(default_factory=dict)
    missing_columns: List[str] = field(default_factory=list)
    unparsed_rows: int = 0
    ignored_nodes: Dict[str, int] = field(default_factory=dict)
    noise: Dict[str, Dict[str, float]] = field(default_factory=dict)
    timezone_used: str = "UTC"


def session_name_from_path(csv_path: Path) -> str:
    stem = Path(csv_path).stem
    return stem[len("session_"):] if stem.startswith("session_") else stem


def sibling(csv_path: Path, suffix: str) -> Path:
    p = Path(csv_path)
    return p.with_name(p.stem + suffix)


def _is_fault(v) -> bool:
    return isinstance(v, str) and v.strip().lower() == "fault"


def resample_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Resample ONE node's raw rows (column 'ts' UTC) to 1-minute bins.

    Rule: MAX for vibration/piezo_peak/piezo_peak_to_peak, MEDIAN for the rest,
    sensor status 'fault' if ANY raw reading in the bin is fault.
    """
    df = raw.copy()
    df["minute"] = df["ts"].dt.floor("min")
    agg: Dict[str, str] = {c: "max" for c in MAX_CHANNELS if c in df}
    agg.update({c: "median" for c in MEDIAN_CHANNELS if c in df})
    for c in STATUS_COLUMNS:
        if c in df:
            df[c] = df[c].map(_is_fault).astype(int)
            agg[c] = "max"
    return df.groupby("minute").agg(agg)


def load_session(csv_path, layout_path=None, events_path=None, verbose: bool = True) -> Session:
    csv_path = Path(csv_path)
    layout_path = Path(layout_path) if layout_path else sibling(csv_path, "_layout.json")
    events_path = Path(events_path) if events_path else sibling(csv_path, "_events.csv")
    name = session_name_from_path(csv_path)

    layout = load_layout(layout_path)
    tz_name = read_events_timezone(events_path)
    tz = parse_timezone(tz_name)

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    if "node_id" not in df or "timestamp" not in df:
        raise ValueError(f"{csv_path} needs 'node_id' and 'timestamp' columns")

    ignored = df.loc[~df["node_id"].isin(layout), "node_id"].value_counts().to_dict()
    df = df[df["node_id"].isin(layout)].copy()
    if df.empty:
        raise ValueError(f"No rows left for layout nodes {sorted(layout)} in {csv_path}")

    missing_cols: List[str] = []
    for c in REQUIRED_CHANNELS:
        if c not in df.columns:
            missing_cols.append(f"{c} (column absent)")
            df[c] = ""
        elif (df[c].str.strip() == "").all():
            missing_cols.append(f"{c} (column entirely empty)")
    for c in STATUS_COLUMNS:
        if c not in df.columns:
            df[c] = ""
    if missing_cols:
        print("!" * 78)
        print("[adapter] LOUD WARNING: required channel(s) missing: " + ", ".join(missing_cols))
        print("[adapter] Missing channels are filled with 0.0. Detectors that rely on them are blind.")
        print("!" * 78)

    df["ts"] = [to_utc(v, tz) for v in df["timestamp"]]
    bad = int(df["ts"].isna().sum())
    df = df[df["ts"].notna()].copy()
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    for c in REQUIRED_CHANNELS:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    per_node: Dict[str, pd.DataFrame] = {}
    for nid in layout:
        sub = df[df["node_id"] == nid]
        if sub.empty:
            continue
        per_node[nid] = resample_frame(sub)

    if not per_node:
        raise ValueError("No node has any parsable data")
    nodes = [n for n in layout if n in per_node]
    t0 = min(f.index.min() for f in per_node.values())
    t1 = max(f.index.max() for f in per_node.values())
    grid = pd.date_range(t0, t1, freq="min")

    readings: List[NodeReading] = []
    gaps: List[dict] = []
    filled: Dict[str, int] = {}
    minutes_per_node: Dict[str, int] = {}
    aligned: Dict[str, pd.DataFrame] = {}

    for nid in nodes:
        f = per_node[nid].reindex(grid)
        real_mask = f[MEDIAN_CHANNELS[0]].notna() | f[MAX_CHANNELS[0]].notna()
        minutes_per_node[nid] = int(real_mask.sum())
        # forward fill at most MAX_FFILL_MINUTES, using only past data
        f = f.ffill(limit=MAX_FFILL_MINUTES)
        present = f[MEDIAN_CHANNELS[0]].notna() | f[MAX_CHANNELS[0]].notna()
        filled[nid] = int((present & ~real_mask).sum())
        aligned[nid] = f

        # report gaps (runs of minutes with no real data between first and last real bin)
        first_real = real_mask.idxmax() if real_mask.any() else None
        last_real = real_mask[::-1].idxmax() if real_mask.any() else None
        run_start = None
        for ts, ok in real_mask.items():
            inside = first_real is not None and first_real <= ts <= last_real
            if inside and not ok:
                run_start = run_start or ts
            elif run_start is not None:
                n = int((ts - run_start) / pd.Timedelta(minutes=1))
                gaps.append({"node": nid, "start": run_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                             "minutes": n, "left_missing": max(0, n - MAX_FFILL_MINUTES)})
                run_start = None

        for ts, row in f.iterrows():
            if pd.isna(row[MEDIAN_CHANNELS[0]]) and pd.isna(row[MAX_CHANNELS[0]]):
                continue  # missing minute: node absent from this timestamp
            def val(c):
                v = row.get(c)
                return 0.0 if pd.isna(v) else float(v)
            readings.append(NodeReading(
                node_id=nid,
                timestamp=ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                tilt_x=val("tilt_x"), tilt_y=val("tilt_y"),
                vibration=val("vibration"), distance=val("distance"),
                mpu6050_status="fault" if row.get("mpu6050_status", 0) == 1 else "ok",
                hc_sr04_status="fault" if row.get("hc_sr04_status", 0) == 1 else "ok",
                ads1115_status="fault" if row.get("ads1115_status", 0) == 1 else "ok",
                piezo_peak=val("piezo_peak"), piezo_rms=val("piezo_rms"),
                piezo_peak_to_peak=val("piezo_peak_to_peak"),
            ))
    readings.sort(key=lambda r: (r.timestamp, r.node_id))

    noise: Dict[str, Dict[str, float]] = {}
    first30 = grid[:30]
    for nid in nodes:
        noise[nid] = {}
        for c in NOISE_CHANNELS:
            s = aligned[nid].loc[aligned[nid].index.isin(first30), c].dropna()
            noise[nid][c] = float(s.std(ddof=1)) if len(s) > 1 else float("nan")

    sess = Session(
        name=name, layout={n: layout[n] for n in nodes}, readings=readings, nodes=nodes,
        start=t0.strftime("%Y-%m-%dT%H:%M:%SZ"), end=t1.strftime("%Y-%m-%dT%H:%M:%SZ"),
        minutes_per_node=minutes_per_node, gaps=gaps, filled_minutes=filled,
        missing_columns=missing_cols, unparsed_rows=bad, ignored_nodes=ignored,
        noise=noise, timezone_used=str(tz_name or "UTC"),
    )
    if verbose:
        print_session_summary(sess, quiet_minutes_at_start(events_path, t0))
    return sess


def quiet_minutes_at_start(events_path: Path, session_start: pd.Timestamp) -> Optional[int]:
    """Console-only diagnostic: minutes between session start and first non-quiet event.

    Returns an integer (or None if no events file). Never stored or given to detectors.
    """
    events_path = Path(events_path)
    if not events_path.exists():
        return None
    tz = parse_timezone(read_events_timezone(events_path))
    first_other = None
    with open(events_path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("type") or "").strip() == "quiet":
                continue
            t = to_utc(row.get("start"), tz)
            if t is not None and (first_other is None or t < first_other):
                first_other = t
    if first_other is None:
        return None
    return max(0, int((first_other - session_start) / pd.Timedelta(minutes=1)))


def print_session_summary(s: Session, quiet_minutes: Optional[int]) -> None:
    print("=" * 78)
    print(f"REAL SESSION '{s.name}' (timezone for naive stamps: {s.timezone_used})")
    print("=" * 78)
    print(f"nodes: {s.nodes}")
    print(f"time span (UTC): {s.start} -> {s.end}")
    print(f"minutes with data per node: {s.minutes_per_node}")
    print(f"forward-filled minutes (<= {MAX_FFILL_MINUTES} min each): {s.filled_minutes}")
    if s.ignored_nodes:
        print(f"ignored node names (not in layout): {s.ignored_nodes}")
    if s.unparsed_rows:
        print(f"WARNING: {s.unparsed_rows} rows had unparsable timestamps and were dropped")
    if s.gaps:
        print(f"gaps ({len(s.gaps)}):")
        for g in s.gaps[:25]:
            print(f"  {g['node']} from {g['start']}: {g['minutes']} min missing ({g['left_missing']} left missing after fill)")
        if len(s.gaps) > 25:
            print(f"  ... {len(s.gaps) - 25} more")
    else:
        print("gaps: none")
    print("per-channel noise (std) in first 30 minutes of the session:")
    for nid, ch in s.noise.items():
        print(f"  {nid}: " + ", ".join(f"{c}={v:.4f}" for c, v in ch.items()))
    if quiet_minutes is not None and quiet_minutes < 30:
        print(f"WARNING: quiet period at the start is only {quiet_minutes} min (< 30). "
              f"Detector baselines may learn from disturbed data.")
    elif quiet_minutes is None:
        print("note: no events file, quiet-period length not checked")
