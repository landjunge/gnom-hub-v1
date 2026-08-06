#!/usr/bin/env python3
"""
Flat DB stress bench (NO layers / tiers / agents) — fair size twin of bench_layer_db.

Default: 40_000 items × 256 KiB ≈ 9.77 GiB (same payload as 10k-layer bench).

  python3.12 scripts/bench_flat_db.py
  python3.12 scripts/bench_flat_db.py --skip-fill
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import struct
import sys
import time
from pathlib import Path


def ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000.0


def human_bytes(n: int) -> str:
    x = float(n)
    for u in ("B", "KiB", "MiB", "GiB", "TiB"):
        if x < 1024 or u == "TiB":
            return f"{x:.2f} {u}"
        x /= 1024.0
    return f"{n} B"


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-200000")
    conn.execute("PRAGMA mmap_size=268435456")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        -- flat: one bag of blobs, no layer_id / tier / agent
        CREATE TABLE IF NOT EXISTS items (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          nbytes INTEGER NOT NULL,
          payload BLOB NOT NULL,
          created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
        """
    )
    conn.commit()


def make_blob(nbytes: int, seed: int) -> bytes:
    rng = random.Random(seed)
    block = bytearray(4096)
    for i in range(0, 4096, 8):
        struct.pack_into("<Q", block, i, rng.getrandbits(64))
    out = bytearray()
    while len(out) < nbytes:
        out.extend(block)
    return bytes(out[:nbytes])


def fill_db(
    conn: sqlite3.Connection,
    *,
    n_items: int,
    item_bytes: int,
) -> dict:
    conn.execute("DELETE FROM items")
    conn.execute("DELETE FROM meta")
    conn.commit()

    t0 = time.perf_counter()
    now = time.time()
    written = 0
    batch: list[tuple] = []
    for i in range(1, n_items + 1):
        blob = make_blob(item_bytes, seed=i * 17)
        batch.append((i, f"item-{i:06d}", item_bytes, blob, now))
        written += item_bytes
        if len(batch) >= 50:
            conn.executemany(
                "INSERT INTO items(id, name, nbytes, payload, created_at) VALUES (?,?,?,?,?)",
                batch,
            )
            conn.commit()
            batch.clear()
        if i % 2000 == 0 or i == n_items:
            elapsed = time.perf_counter() - t0
            rate = written / elapsed / (1024 * 1024) if elapsed > 0 else 0
            print(
                f"  fill {i}/{n_items}  {human_bytes(written)}  {rate:.1f} MiB/s",
                flush=True,
            )
    if batch:
        conn.executemany(
            "INSERT INTO items(id, name, nbytes, payload, created_at) VALUES (?,?,?,?,?)",
            batch,
        )
        conn.commit()

    conn.execute(
        "INSERT OR REPLACE INTO meta(key,value) VALUES ('n_items', ?)",
        (str(n_items),),
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key,value) VALUES ('item_bytes', ?)",
        (str(item_bytes),),
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key,value) VALUES ('written_bytes', ?)",
        (str(written),),
    )
    conn.commit()
    return {
        "n_items": n_items,
        "item_bytes": item_bytes,
        "written_bytes": written,
        "ms_fill": ms(t0),
    }


def db_file_size(path: Path) -> int:
    n = path.stat().st_size if path.is_file() else 0
    for suf in ("-wal", "-shm"):
        p = Path(str(path) + suf)
        if p.is_file():
            n += p.stat().st_size
    return n


def bench_ops(conn: sqlite3.Connection, n_items: int) -> dict:
    out: dict = {}
    rng = random.Random(42)

    t0 = time.perf_counter()
    n = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    out["ms_count"] = ms(t0)
    out["n_items"] = n

    t0 = time.perf_counter()
    total = conn.execute("SELECT SUM(nbytes) FROM items").fetchone()[0] or 0
    out["ms_sum_nbytes"] = ms(t0)
    out["sum_nbytes"] = int(total)

    iid = rng.randint(1, max(1, n_items))
    t0 = time.perf_counter()
    for _ in range(1000):
        conn.execute(
            "SELECT id, name, nbytes FROM items WHERE id=?",
            (iid,),
        ).fetchone()
    out["ms_point_meta_x1000"] = ms(t0)

    ids = [rng.randint(1, n_items) for _ in range(50)]
    t0 = time.perf_counter()
    got = 0
    for i in ids:
        row = conn.execute(
            "SELECT payload FROM items WHERE id=?",
            (i,),
        ).fetchone()
        if row:
            got += len(row[0])
    out["ms_random_50_payload"] = ms(t0)
    out["bytes_random_50"] = got

    # "search" without tier: name prefix LIKE (only flat tool)
    t0 = time.perf_counter()
    rows = conn.execute(
        "SELECT id, name FROM items WHERE name LIKE ? LIMIT 100",
        ("item-000%",),
    ).fetchall()
    out["ms_name_like"] = ms(t0)
    out["n_like"] = len(rows)

    # no tier — full table scan count (expensive, shows flat cost)
    t0 = time.perf_counter()
    conn.execute("SELECT COUNT(*) FROM items WHERE name LIKE 'item-%'").fetchone()
    out["ms_count_like_all"] = ms(t0)

    # headers 20 items
    lids = [rng.randint(1, n_items) for _ in range(20)]
    t0 = time.perf_counter()
    for i in lids:
        conn.execute(
            "SELECT id, name, nbytes FROM items WHERE id=?",
            (i,),
        ).fetchone()
    out["ms_headers_20"] = ms(t0)

    # full read 5 items (same 5×256KiB ≈ 1.25 MiB — layer bench did 5 layers × 1MiB)
    # For fair payload: read 20 items of 256KiB = 5 MiB
    lids20 = [rng.randint(1, n_items) for _ in range(20)]
    t0 = time.perf_counter()
    bread = 0
    for i in lids20:
        row = conn.execute(
            "SELECT payload FROM items WHERE id=?",
            (i,),
        ).fetchone()
        if row:
            bread += len(row[0])
    out["ms_full_read_20_items"] = ms(t0)
    out["bytes_full_20"] = bread

    # "tier walk" equivalent: 4 full-table aggregates (no index differentiation)
    t0 = time.perf_counter()
    for _ in range(4):
        conn.execute("SELECT COUNT(*) FROM items").fetchone()
    out["ms_four_full_counts"] = ms(t0)

    # agent filter equivalent: cannot — use random name scans
    t0 = time.perf_counter()
    conn.execute(
        "SELECT COUNT(*) FROM items WHERE name LIKE ?",
        (f"item-{rng.randint(0, 9)}%",),
    ).fetchone()
    out["ms_name_prefix_count"] = ms(t0)

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", type=int, default=40_000, help="default 40k = same as layer chunks")
    ap.add_argument("--chunk-kb", type=int, default=256)
    ap.add_argument("--gb", type=float, default=None, help="if set, derive items from target GiB")
    ap.add_argument("--db", type=Path, default=None)
    ap.add_argument("--skip-fill", action="store_true")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    db_path = args.db or (root / "bench_data" / "flat_10g.sqlite")
    item_bytes = max(4096, args.chunk_kb * 1024)
    n_items = args.items
    if args.gb is not None:
        n_items = max(1, int(args.gb * 1024**3) // item_bytes)

    print("=== Flat DB Bench (NO layers) ===", flush=True)
    print(f"db:     {db_path}", flush=True)
    print(f"items:  {n_items}", flush=True)
    print(f"each:   {human_bytes(item_bytes)}", flush=True)
    print(f"target: {human_bytes(n_items * item_bytes)}", flush=True)

    conn = connect(db_path)
    init_schema(conn)

    if not args.skip_fill:
        print("\n-- FILL --", flush=True)
        info = fill_db(conn, n_items=n_items, item_bytes=item_bytes)
        print(
            f"written {human_bytes(info['written_bytes'])} in {info['ms_fill']:.0f} ms",
            flush=True,
        )
    else:
        print("\n-- SKIP FILL --", flush=True)
        n_items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    fsize = db_file_size(db_path)
    print(f"\nfile size: {human_bytes(fsize)}", flush=True)

    print("\n-- BENCH --", flush=True)
    b1 = bench_ops(conn, n_items)
    b2 = bench_ops(conn, n_items)

    def line(k: str, c: float, w: float, extra: str = "") -> None:
        print(f"  {k:28s}  cold={c:9.1f} ms  warm={w:9.1f} ms{extra}")

    print("\nResults:", flush=True)
    line("COUNT items", b1["ms_count"], b2["ms_count"], f"  n={b1['n_items']}")
    line("SUM nbytes", b1["ms_sum_nbytes"], b2["ms_sum_nbytes"], f"  {human_bytes(b1['sum_nbytes'])}")
    line("point meta ×1000", b1["ms_point_meta_x1000"], b2["ms_point_meta_x1000"])
    line("random 50 payload", b1["ms_random_50_payload"], b2["ms_random_50_payload"], f"  {human_bytes(b1['bytes_random_50'])}")
    line("name LIKE limit 100", b1["ms_name_like"], b2["ms_name_like"], f"  n={b1['n_like']}")
    line("COUNT name LIKE all", b1["ms_count_like_all"], b2["ms_count_like_all"])
    line("headers 20", b1["ms_headers_20"], b2["ms_headers_20"])
    line("FULL read 20 items", b1["ms_full_read_20_items"], b2["ms_full_read_20_items"], f"  {human_bytes(b1['bytes_full_20'])}")
    line("4× COUNT(*)", b1["ms_four_full_counts"], b2["ms_four_full_counts"])
    line("prefix COUNT", b1["ms_name_prefix_count"], b2["ms_name_prefix_count"])

    if b2["ms_full_read_20_items"] > 0:
        thr = b2["bytes_full_20"] / (b2["ms_full_read_20_items"] / 1000.0) / (1024**2)
        print(f"\n  ~read throughput (warm): {thr:.1f} MiB/s", flush=True)

    report = db_path.with_suffix(".bench.txt")
    with report.open("w", encoding="utf-8") as f:
        f.write(f"db={db_path}\nfile={human_bytes(fsize)}\ncold={b1}\nwarm={b2}\n")
    print(f"\nreport: {report}", flush=True)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
