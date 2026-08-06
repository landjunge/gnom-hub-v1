#!/usr/bin/env python3
"""
Server simulation against layer SQLite DB — NO LLM.

Workload mix (default 60s):
  50%  search  (tier / agent / name LIKE)
  30%  read    (random layer chunk payload)
  15%  write   (append small meta chunk to random layer)
  5%   list    (layer headers by tier)

Uses existing bench_data/layer_10k.sqlite if present (~10GB),
else builds with bench_layer_db fill logic (slow).

  python3.12 scripts/bench_layer_server_sim.py
  python3.12 scripts/bench_layer_server_sim.py --seconds 30 --workers 8
  python3.12 scripts/bench_layer_server_sim.py --db bench_data/layer_10k.sqlite
"""

from __future__ import annotations

import argparse
import os
import random
import sqlite3
import struct
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def human_bytes(n: int) -> str:
    x = float(n)
    for u in ("B", "KiB", "MiB", "GiB"):
        if x < 1024 or u == "GiB":
            return f"{x:.2f} {u}"
        x /= 1024.0
    return f"{n} B"


def db_file_size(path: Path) -> int:
    n = path.stat().st_size if path.is_file() else 0
    for suf in ("-wal", "-shm"):
        p = Path(str(path) + suf)
        if p.is_file():
            n += p.stat().st_size
    return n


def connect(path: Path, *, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        uri = f"file:{path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    else:
        conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-100000")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


class Stats:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.n = defaultdict(int)
        self.ms = defaultdict(float)
        self.bytes_r = 0
        self.bytes_w = 0
        self.errors = 0

    def add(self, op: str, dt_ms: float, br: int = 0, bw: int = 0) -> None:
        with self.lock:
            self.n[op] += 1
            self.ms[op] += dt_ms
            self.bytes_r += br
            self.bytes_w += bw

    def err(self) -> None:
        with self.lock:
            self.errors += 1


def worker_loop(
    path: Path,
    n_layers: int,
    stop_at: float,
    stats: Stats,
    wid: int,
    write_every: bool,
) -> None:
    rng = random.Random(1000 + wid)
    # writers need RW; readers can share — each thread own connection
    conn = connect(path, readonly=False)
    tiers = ["HOT", "WARM", "COLD", "WS"]
    agents = [
        "brainstorm",
        "memory",
        "flex",
        "coordinator",
        "worker1",
        "worker2",
        "worker3",
        "worker4",
    ]
    # small write blob 4KB
    blob_tpl = bytearray(4096)
    for i in range(0, 4096, 8):
        struct.pack_into("<Q", blob_tpl, i, rng.getrandbits(64))
    write_blob = bytes(blob_tpl)

    while time.perf_counter() < stop_at:
        r = rng.random()
        try:
            if r < 0.50:
                # SEARCH
                kind = rng.choice(["tier", "agent", "name", "tier_agent"])
                t0 = time.perf_counter()
                if kind == "tier":
                    tier = rng.choice(tiers)
                    rows = conn.execute(
                        "SELECT id, name, agent, module FROM layers WHERE tier=? LIMIT 100",
                        (tier,),
                    ).fetchall()
                elif kind == "agent":
                    ag = rng.choice(agents)
                    rows = conn.execute(
                        "SELECT id, name, tier, module FROM layers WHERE agent=? LIMIT 100",
                        (ag,),
                    ).fetchall()
                elif kind == "name":
                    # prefix search simulation
                    prefix = f"layer-{rng.randint(1, n_layers):05d}"[:9]
                    rows = conn.execute(
                        "SELECT id, name, tier FROM layers WHERE name LIKE ? LIMIT 50",
                        (prefix + "%",),
                    ).fetchall()
                else:
                    tier = rng.choice(tiers)
                    ag = rng.choice(agents)
                    rows = conn.execute(
                        "SELECT id, name FROM layers WHERE tier=? AND agent=? LIMIT 100",
                        (tier, ag),
                    ).fetchall()
                dt = (time.perf_counter() - t0) * 1000
                stats.add("search", dt)
                _ = len(rows)

            elif r < 0.80:
                # READ random chunk payload
                lid = rng.randint(1, n_layers)
                t0 = time.perf_counter()
                row = conn.execute(
                    "SELECT payload, nbytes FROM chunks WHERE layer_id=? AND seq=0",
                    (lid,),
                ).fetchone()
                dt = (time.perf_counter() - t0) * 1000
                br = len(row[0]) if row else 0
                stats.add("read", dt, br=br)

            elif r < 0.95 and write_every:
                # WRITE small chunk append (sim server ingest)
                lid = rng.randint(1, n_layers)
                seq = 1000 + rng.randint(0, 1_000_000)
                t0 = time.perf_counter()
                try:
                    conn.execute(
                        "INSERT INTO chunks(layer_id, seq, nbytes, payload) VALUES (?,?,?,?)",
                        (lid, seq, len(write_blob), write_blob),
                    )
                    conn.commit()
                    dt = (time.perf_counter() - t0) * 1000
                    stats.add("write", dt, bw=len(write_blob))
                except sqlite3.IntegrityError:
                    conn.rollback()
                    stats.add("write_skip", (time.perf_counter() - t0) * 1000)

            else:
                # LIST tier
                tier = rng.choice(tiers)
                t0 = time.perf_counter()
                n = conn.execute(
                    "SELECT COUNT(*) FROM layers WHERE tier=?",
                    (tier,),
                ).fetchone()[0]
                dt = (time.perf_counter() - t0) * 1000
                stats.add("list", dt)
                _ = n

        except sqlite3.Error:
            stats.err()
            try:
                conn.rollback()
            except sqlite3.Error:
                pass

    conn.close()


def ensure_db(path: Path, layers: int, gb: float) -> int:
    if path.is_file() and path.stat().st_size > 1_000_000_000:
        conn = connect(path)
        n = conn.execute("SELECT COUNT(*) FROM layers").fetchone()[0]
        conn.close()
        if n >= layers // 2:
            return int(n)
    # build via sibling script
    import subprocess
    import sys

    script = Path(__file__).resolve().parent / "bench_layer_db.py"
    cmd = [
        sys.executable,
        str(script),
        "--layers",
        str(layers),
        "--gb",
        str(gb),
        "--db",
        str(path),
        "--chunk-kb",
        "256",
    ]
    print("Building DB first:", " ".join(cmd), flush=True)
    subprocess.check_call(cmd)
    conn = connect(path)
    n = conn.execute("SELECT COUNT(*) FROM layers").fetchone()[0]
    conn.close()
    return int(n)


def main() -> int:
    ap = argparse.ArgumentParser(description="Layer DB server sim — no LLM")
    ap.add_argument("--db", type=Path, default=None)
    ap.add_argument("--layers", type=int, default=10_000)
    ap.add_argument("--gb", type=float, default=10.0)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--read-only", action="store_true", help="no write ops")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    db_path = args.db or (root / "bench_data" / "layer_10k.sqlite")

    print("=== Layer DB Server Simulation (NO LLM) ===", flush=True)
    print(f"db:       {db_path}", flush=True)
    n_layers = ensure_db(db_path, args.layers, args.gb)
    fsize = db_file_size(db_path)
    print(f"layers:   {n_layers}", flush=True)
    print(f"filesize: {human_bytes(fsize)}", flush=True)
    print(f"workers:  {args.workers}", flush=True)
    print(f"duration: {args.seconds}s", flush=True)
    print(
        "mix:      search 50% | read 30% | write 15% | list 5%"
        + (" (writes OFF)" if args.read_only else ""),
        flush=True,
    )

    # quick sanity
    conn = connect(db_path)
    chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    payload = conn.execute("SELECT SUM(nbytes) FROM chunks").fetchone()[0] or 0
    conn.close()
    print(f"chunks:   {chunks}  payload≈{human_bytes(int(payload))}", flush=True)

    stats = Stats()
    stop_at = time.perf_counter() + args.seconds
    write_on = not args.read_only
    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [
            ex.submit(
                worker_loop,
                db_path,
                n_layers,
                stop_at,
                stats,
                w,
                write_on,
            )
            for w in range(args.workers)
        ]
        for f in as_completed(futs):
            f.result()

    wall = time.perf_counter() - t0
    total_ops = sum(stats.n.values())

    print("\n-- RESULTS --", flush=True)
    print(f"wall time:     {wall:.2f} s", flush=True)
    print(f"total ops:     {total_ops}", flush=True)
    print(f"throughput:    {total_ops / wall:.1f} ops/s", flush=True)
    print(f"errors:        {stats.errors}", flush=True)
    print(f"bytes read:    {human_bytes(stats.bytes_r)}", flush=True)
    print(f"bytes written: {human_bytes(stats.bytes_w)}", flush=True)
    if wall > 0:
        print(
            f"read BW:       {stats.bytes_r / wall / (1024**2):.1f} MiB/s",
            flush=True,
        )
        print(
            f"write BW:      {stats.bytes_w / wall / (1024**2):.1f} MiB/s",
            flush=True,
        )

    print("\nper op:", flush=True)
    for op in sorted(stats.n.keys()):
        n = stats.n[op]
        avg = stats.ms[op] / n if n else 0
        print(
            f"  {op:12s}  n={n:7d}  avg={avg:7.2f} ms  "
            f"rate={n / wall:7.1f} /s",
            flush=True,
        )

    # latency percentiles approx via re-run sample single-thread 500 ops
    print("\n-- latency sample (1 thread, 500 ops each) --", flush=True)
    conn = connect(db_path)
    rng = random.Random(7)

    def lat_sample(name: str, fn, n: int = 500) -> None:
        samples = []
        for _ in range(n):
            t0 = time.perf_counter()
            fn()
            samples.append((time.perf_counter() - t0) * 1000)
        samples.sort()
        p50 = samples[len(samples) // 2]
        p95 = samples[int(len(samples) * 0.95)]
        p99 = samples[int(len(samples) * 0.99)]
        print(
            f"  {name:12s}  p50={p50:6.2f}  p95={p95:6.2f}  p99={p99:6.2f}  ms",
            flush=True,
        )

    def s_search() -> None:
        conn.execute(
            "SELECT id FROM layers WHERE tier=? LIMIT 50",
            (rng.choice(["HOT", "WARM", "COLD", "WS"]),),
        ).fetchall()

    def s_read() -> None:
        lid = rng.randint(1, n_layers)
        conn.execute(
            "SELECT payload FROM chunks WHERE layer_id=? AND seq=0",
            (lid,),
        ).fetchone()

    def s_list() -> None:
        conn.execute(
            "SELECT COUNT(*) FROM layers WHERE agent=?",
            (rng.choice(["worker1", "memory", "brainstorm"]),),
        ).fetchone()

    lat_sample("search", s_search)
    lat_sample("read", s_read)
    lat_sample("list", s_list)
    conn.close()

    report = db_path.with_name(db_path.stem + ".server_sim.txt")
    with report.open("w", encoding="utf-8") as f:
        f.write(f"wall={wall}\nops={total_ops}\nops_s={total_ops/wall}\n")
        f.write(f"bytes_r={stats.bytes_r}\nbytes_w={stats.bytes_w}\n")
        f.write(f"errors={stats.errors}\nn={dict(stats.n)}\nms={dict(stats.ms)}\n")
    print(f"\nreport: {report}", flush=True)
    print("\nNO LLM involved — pure SQLite server simulation.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
