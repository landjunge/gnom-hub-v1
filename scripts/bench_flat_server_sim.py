#!/usr/bin/env python3
"""
Server simulation on FLAT SQLite (~10GB) — NO layers, NO LLM.

Same mix as bench_layer_server_sim:
  50% search (name LIKE only — no tier/agent)
  30% read random payload
  15% write small append-as-new-id (or update name)
  5%  list COUNT(*)

  python3.12 scripts/bench_flat_server_sim.py --seconds 60 --workers 8
"""

from __future__ import annotations

import argparse
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


def connect(path: Path) -> sqlite3.Connection:
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
    n_items: int,
    stop_at: float,
    stats: Stats,
    wid: int,
    allow_write: bool,
) -> None:
    rng = random.Random(2000 + wid)
    conn = connect(path)
    blob = bytearray(4096)
    for i in range(0, 4096, 8):
        struct.pack_into("<Q", blob, i, rng.getrandbits(64))
    write_blob = bytes(blob)
    next_id_base = 10_000_000 + wid * 10_000_000
    local_seq = 0

    while time.perf_counter() < stop_at:
        r = rng.random()
        try:
            if r < 0.50:
                # SEARCH — only flat tools (LIKE / full count)
                kind = rng.choice(["like", "like2", "count_all"])
                t0 = time.perf_counter()
                if kind == "like":
                    pref = f"item-{rng.randint(0, 9)}"
                    conn.execute(
                        "SELECT id, name FROM items WHERE name LIKE ? LIMIT 100",
                        (pref + "%",),
                    ).fetchall()
                elif kind == "like2":
                    # mid-card search (harder without structured indexes)
                    frag = f"%{rng.randint(100, 999):03d}%"
                    conn.execute(
                        "SELECT id, name FROM items WHERE name LIKE ? LIMIT 50",
                        (frag,),
                    ).fetchall()
                else:
                    conn.execute("SELECT COUNT(*) FROM items").fetchone()
                stats.add("search", (time.perf_counter() - t0) * 1000)

            elif r < 0.80:
                iid = rng.randint(1, n_items)
                t0 = time.perf_counter()
                row = conn.execute(
                    "SELECT payload FROM items WHERE id=?",
                    (iid,),
                ).fetchone()
                br = len(row[0]) if row else 0
                stats.add("read", (time.perf_counter() - t0) * 1000, br=br)

            elif r < 0.95 and allow_write:
                local_seq += 1
                iid = next_id_base + local_seq
                t0 = time.perf_counter()
                try:
                    conn.execute(
                        "INSERT INTO items(id, name, nbytes, payload, created_at) VALUES (?,?,?,?,?)",
                        (
                            iid,
                            f"new-{wid}-{local_seq}",
                            len(write_blob),
                            write_blob,
                            time.time(),
                        ),
                    )
                    conn.commit()
                    stats.add(
                        "write",
                        (time.perf_counter() - t0) * 1000,
                        bw=len(write_blob),
                    )
                except sqlite3.IntegrityError:
                    conn.rollback()
                    stats.add("write_skip", (time.perf_counter() - t0) * 1000)
            else:
                t0 = time.perf_counter()
                conn.execute("SELECT COUNT(*) FROM items").fetchone()
                stats.add("list", (time.perf_counter() - t0) * 1000)
        except sqlite3.Error:
            stats.err()
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
    conn.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=None)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--read-only", action="store_true")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    db_path = args.db or (root / "bench_data" / "flat_10g.sqlite")

    print("=== Flat DB Server Simulation (NO layers, NO LLM) ===", flush=True)
    if not db_path.is_file():
        print("DB missing — run bench_flat_db.py first", flush=True)
        return 1

    conn = connect(db_path)
    n_items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    payload = conn.execute("SELECT SUM(nbytes) FROM items").fetchone()[0] or 0
    conn.close()

    print(f"db:       {db_path}", flush=True)
    print(f"items:    {n_items}", flush=True)
    print(f"filesize: {human_bytes(db_file_size(db_path))}", flush=True)
    print(f"payload:  {human_bytes(int(payload))}", flush=True)
    print(f"workers:  {args.workers}  duration: {args.seconds}s", flush=True)
    print("mix:      search 50% | read 30% | write 15% | list 5%", flush=True)

    stats = Stats()
    stop_at = time.perf_counter() + args.seconds
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [
            ex.submit(
                worker_loop,
                db_path,
                max(1, n_items),
                stop_at,
                stats,
                w,
                not args.read_only,
            )
            for w in range(args.workers)
        ]
        for f in as_completed(futs):
            f.result()
    wall = time.perf_counter() - t0
    total = sum(stats.n.values())

    print("\n-- RESULTS --", flush=True)
    print(f"wall time:     {wall:.2f} s", flush=True)
    print(f"total ops:     {total}", flush=True)
    print(f"throughput:    {total / wall:.1f} ops/s", flush=True)
    print(f"errors:        {stats.errors}", flush=True)
    print(f"bytes read:    {human_bytes(stats.bytes_r)}", flush=True)
    print(f"bytes written: {human_bytes(stats.bytes_w)}", flush=True)
    if wall > 0:
        print(f"read BW:       {stats.bytes_r / wall / (1024**2):.1f} MiB/s", flush=True)
        print(f"write BW:      {stats.bytes_w / wall / (1024**2):.1f} MiB/s", flush=True)

    print("\nper op:", flush=True)
    for op in sorted(stats.n.keys()):
        n = stats.n[op]
        avg = stats.ms[op] / n if n else 0
        print(f"  {op:12s}  n={n:7d}  avg={avg:7.2f} ms  rate={n / wall:7.1f} /s", flush=True)

    print("\n-- latency sample (1 thread, 500) --", flush=True)
    conn = connect(db_path)
    rng = random.Random(7)

    def sample(name, fn, n=500):
        s = []
        for _ in range(n):
            t0 = time.perf_counter()
            fn()
            s.append((time.perf_counter() - t0) * 1000)
        s.sort()
        print(
            f"  {name:12s}  p50={s[len(s) // 2]:6.2f}  p95={s[int(len(s) * 0.95)]:6.2f}  "
            f"p99={s[int(len(s) * 0.99)]:6.2f}  ms",
            flush=True,
        )

    sample(
        "search",
        lambda: conn.execute(
            "SELECT id FROM items WHERE name LIKE ? LIMIT 50",
            (f"item-{rng.randint(0, 9)}%",),
        ).fetchall(),
    )
    sample(
        "read",
        lambda: conn.execute(
            "SELECT payload FROM items WHERE id=?",
            (rng.randint(1, max(1, n_items)),),
        ).fetchone(),
    )
    sample("list", lambda: conn.execute("SELECT COUNT(*) FROM items").fetchone())
    conn.close()

    report = db_path.with_name(db_path.stem + ".server_sim.txt")
    with report.open("w", encoding="utf-8") as f:
        f.write(f"wall={wall}\nops={total}\nops_s={total / wall}\n")
        f.write(f"bytes_r={stats.bytes_r}\nbytes_w={stats.bytes_w}\n")
        f.write(f"n={dict(stats.n)}\n")
    print(f"\nreport: {report}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
