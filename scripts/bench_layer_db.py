#!/usr/bin/env python3
"""
Layer-DB stress bench: N layers, ~target_gb payload, timed ops.

Default: 10_000 layers, ~10 GiB under ./bench_data/ (gitignored path).

  python3 scripts/bench_layer_db.py
  python3 scripts/bench_layer_db.py --layers 1000 --gb 0.5   # smoke
  python3 scripts/bench_layer_db.py --skip-fill              # re-bench existing

Schema (conceptual Y×X×Z cell store):
  layers(id, name, agent, module, tier, created_at)
  chunks(id, layer_id, seq, payload BLOB, nbytes)
"""

from __future__ import annotations

import argparse
import os
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
    conn.execute("PRAGMA cache_size=-200000")  # ~200MB page cache
    conn.execute("PRAGMA mmap_size=268435456")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS layers (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          agent TEXT NOT NULL,
          module TEXT NOT NULL,
          tier TEXT NOT NULL,
          created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chunks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          layer_id INTEGER NOT NULL,
          seq INTEGER NOT NULL,
          nbytes INTEGER NOT NULL,
          payload BLOB NOT NULL,
          FOREIGN KEY(layer_id) REFERENCES layers(id)
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_layer ON chunks(layer_id);
        CREATE INDEX IF NOT EXISTS idx_layers_tier ON layers(tier);
        CREATE INDEX IF NOT EXISTS idx_layers_agent ON layers(agent);
        """
    )
    conn.commit()


AGENTS = [
    "brainstorm",
    "memory",
    "flex",
    "coordinator",
    "worker1",
    "worker2",
    "worker3",
    "worker4",
]
MODULES = ["chat", "box1-info", "box2-content", "box3-worker", "box3-regler"]
TIERS = ["HOT", "WARM", "COLD", "WS"]


def make_blob(nbytes: int, seed: int) -> bytes:
    """Pseudo-random but deterministic blob (not highly compressible)."""
    rng = random.Random(seed)
    # 4KB pattern repeated + noise for speed of generation
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
    n_layers: int,
    target_bytes: int,
    chunk_bytes: int,
) -> dict:
    conn.execute("DELETE FROM chunks")
    conn.execute("DELETE FROM layers")
    conn.execute("DELETE FROM meta")
    conn.commit()

    bytes_per_layer = max(chunk_bytes, target_bytes // n_layers)
    chunks_per_layer = max(1, bytes_per_layer // chunk_bytes)
    # adjust so total ≈ target
    total_planned = n_layers * chunks_per_layer * chunk_bytes

    t0 = time.perf_counter()
    now = time.time()
    layers_rows = []
    for i in range(1, n_layers + 1):
        agent = AGENTS[(i - 1) % len(AGENTS)]
        module = MODULES[(i - 1) % len(MODULES)]
        # deeper id → colder tier bias
        if i <= n_layers * 0.1:
            tier = "HOT"
        elif i <= n_layers * 0.4:
            tier = "WARM"
        elif i <= n_layers * 0.8:
            tier = "COLD"
        else:
            tier = "WS"
        layers_rows.append(
            (i, f"layer-{i:05d}", agent, module, tier, now)
        )
    conn.executemany(
        "INSERT INTO layers(id, name, agent, module, tier, created_at) VALUES (?,?,?,?,?,?)",
        layers_rows,
    )
    conn.commit()
    t_layers = ms(t0)

    t1 = time.perf_counter()
    written = 0
    batch: list[tuple] = []
    batch_n = 0
    for lid in range(1, n_layers + 1):
        for seq in range(chunks_per_layer):
            blob = make_blob(chunk_bytes, seed=lid * 1_000_003 + seq)
            batch.append((lid, seq, chunk_bytes, blob))
            written += chunk_bytes
            batch_n += 1
            if batch_n >= 50:
                conn.executemany(
                    "INSERT INTO chunks(layer_id, seq, nbytes, payload) VALUES (?,?,?,?)",
                    batch,
                )
                conn.commit()
                batch.clear()
                batch_n = 0
        if lid % 500 == 0 or lid == n_layers:
            elapsed = time.perf_counter() - t1
            rate = written / elapsed / (1024 * 1024) if elapsed > 0 else 0
            print(
                f"  fill {lid}/{n_layers} layers  {human_bytes(written)}  "
                f"{rate:.1f} MiB/s",
                flush=True,
            )
    if batch:
        conn.executemany(
            "INSERT INTO chunks(layer_id, seq, nbytes, payload) VALUES (?,?,?,?)",
            batch,
        )
        conn.commit()
    t_chunks = ms(t1)

    conn.execute(
        "INSERT OR REPLACE INTO meta(key,value) VALUES ('n_layers', ?)",
        (str(n_layers),),
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key,value) VALUES ('chunk_bytes', ?)",
        (str(chunk_bytes),),
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key,value) VALUES ('written_bytes', ?)",
        (str(written),),
    )
    conn.commit()

    return {
        "n_layers": n_layers,
        "chunks_per_layer": chunks_per_layer,
        "chunk_bytes": chunk_bytes,
        "written_bytes": written,
        "planned_bytes": total_planned,
        "ms_insert_layers": t_layers,
        "ms_insert_chunks": t_chunks,
    }


def db_file_size(path: Path) -> int:
    n = path.stat().st_size if path.is_file() else 0
    for suf in ("-wal", "-shm"):
        p = Path(str(path) + suf)
        if p.is_file():
            n += p.stat().st_size
    return n


def bench_ops(conn: sqlite3.Connection, n_layers: int) -> dict:
    out: dict = {}
    rng = random.Random(42)

    # count
    t0 = time.perf_counter()
    n = conn.execute("SELECT COUNT(*) FROM layers").fetchone()[0]
    out["ms_count_layers"] = ms(t0)
    out["n_layers_db"] = n

    t0 = time.perf_counter()
    nc = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    out["ms_count_chunks"] = ms(t0)
    out["n_chunks"] = nc

    # sum nbytes
    t0 = time.perf_counter()
    total = conn.execute("SELECT SUM(nbytes) FROM chunks").fetchone()[0] or 0
    out["ms_sum_nbytes"] = ms(t0)
    out["sum_nbytes"] = int(total)

    # point: one layer meta
    lid = rng.randint(1, max(1, n_layers))
    t0 = time.perf_counter()
    for _ in range(1000):
        conn.execute(
            "SELECT id, name, agent, module, tier FROM layers WHERE id=?",
            (lid,),
        ).fetchone()
    out["ms_point_layer_x1000"] = ms(t0)

    # random layer first chunk payload (cold cache-ish)
    ids = [rng.randint(1, n_layers) for _ in range(50)]
    t0 = time.perf_counter()
    got = 0
    for i in ids:
        row = conn.execute(
            "SELECT payload FROM chunks WHERE layer_id=? AND seq=0",
            (i,),
        ).fetchone()
        if row:
            got += len(row[0])
    out["ms_random_50_chunk0"] = ms(t0)
    out["bytes_random_50"] = got

    # sequential scan one tier
    t0 = time.perf_counter()
    rows = conn.execute(
        "SELECT id, agent, module FROM layers WHERE tier='WARM'"
    ).fetchall()
    out["ms_filter_tier_warm"] = ms(t0)
    out["n_warm_layers"] = len(rows)

    # join: all chunk headers for 20 random layers (no full payload)
    lids = [rng.randint(1, n_layers) for _ in range(20)]
    t0 = time.perf_counter()
    nhead = 0
    for i in lids:
        cur = conn.execute(
            "SELECT id, seq, nbytes FROM chunks WHERE layer_id=? ORDER BY seq",
            (i,),
        ).fetchall()
        nhead += len(cur)
    out["ms_headers_20_layers"] = ms(t0)
    out["n_headers"] = nhead

    # full payload read 5 layers (all chunks)
    lids5 = [rng.randint(1, n_layers) for _ in range(5)]
    t0 = time.perf_counter()
    bread = 0
    for i in lids5:
        for (payload,) in conn.execute(
            "SELECT payload FROM chunks WHERE layer_id=? ORDER BY seq",
            (i,),
        ):
            bread += len(payload)
    out["ms_full_read_5_layers"] = ms(t0)
    out["bytes_full_5"] = bread

    # tier walk simulation (search path): HOT then WARM then COLD ids only
    t0 = time.perf_counter()
    for tier in ("HOT", "WARM", "COLD", "WS"):
        conn.execute(
            "SELECT COUNT(*) FROM layers WHERE tier=?",
            (tier,),
        ).fetchone()
    out["ms_tier_walk_counts"] = ms(t0)

    # agent filter
    t0 = time.perf_counter()
    conn.execute(
        "SELECT COUNT(*) FROM layers WHERE agent='worker1'"
    ).fetchone()
    out["ms_count_agent_worker1"] = ms(t0)

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="10k-layer / multi-GB SQLite bench")
    ap.add_argument("--layers", type=int, default=10_000)
    ap.add_argument("--gb", type=float, default=10.0, help="target payload GiB")
    ap.add_argument(
        "--chunk-kb",
        type=int,
        default=256,
        help="chunk size KiB (default 256)",
    )
    ap.add_argument(
        "--db",
        type=Path,
        default=None,
        help="db path (default: <hub>/bench_data/layer_10k.sqlite)",
    )
    ap.add_argument("--skip-fill", action="store_true")
    ap.add_argument("--vacuum", action="store_true")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    db_path = args.db or (root / "bench_data" / "layer_10k.sqlite")
    target = int(args.gb * 1024**3)
    chunk_bytes = max(4096, args.chunk_kb * 1024)

    print("=== Layer DB Bench ===", flush=True)
    print(f"db:      {db_path}", flush=True)
    print(f"layers:  {args.layers}", flush=True)
    print(f"target:  {human_bytes(target)} payload", flush=True)
    print(f"chunk:   {human_bytes(chunk_bytes)}", flush=True)

    conn = connect(db_path)
    init_schema(conn)

    fill_info = None
    if not args.skip_fill:
        print("\n-- FILL --", flush=True)
        t_all = time.perf_counter()
        fill_info = fill_db(
            conn,
            n_layers=args.layers,
            target_bytes=target,
            chunk_bytes=chunk_bytes,
        )
        fill_info["ms_fill_total"] = ms(t_all)
        print(
            f"written payload: {human_bytes(fill_info['written_bytes'])}  "
            f"layers_insert={fill_info['ms_insert_layers']:.0f}ms  "
            f"chunks_insert={fill_info['ms_insert_chunks']:.0f}ms",
            flush=True,
        )
    else:
        print("\n-- SKIP FILL (existing db) --", flush=True)

    if args.vacuum:
        print("VACUUM...", flush=True)
        t0 = time.perf_counter()
        conn.execute("VACUUM")
        print(f"VACUUM {ms(t0):.0f} ms", flush=True)

    fsize = db_file_size(db_path)
    print(f"\nfile size (db+wal+shm): {human_bytes(fsize)}", flush=True)

    print("\n-- BENCH --", flush=True)
    # drop page cache is not possible portable; run twice
    b1 = bench_ops(conn, args.layers)
    b2 = bench_ops(conn, args.layers)

    def line(k: str, cold: float, hot: float, extra: str = "") -> None:
        print(f"  {k:28s}  cold={cold:9.1f} ms  warm={hot:9.1f} ms{extra}")

    print("\nResults (1st pass ~cold cache, 2nd ~warm):", flush=True)
    line("COUNT layers", b1["ms_count_layers"], b2["ms_count_layers"], f"  n={b1['n_layers_db']}")
    line("COUNT chunks", b1["ms_count_chunks"], b2["ms_count_chunks"], f"  n={b1['n_chunks']}")
    line("SUM nbytes", b1["ms_sum_nbytes"], b2["ms_sum_nbytes"], f"  {human_bytes(b1['sum_nbytes'])}")
    line("point layer ×1000", b1["ms_point_layer_x1000"], b2["ms_point_layer_x1000"])
    line("random 50 × chunk0", b1["ms_random_50_chunk0"], b2["ms_random_50_chunk0"], f"  {human_bytes(b1['bytes_random_50'])}")
    line("filter tier=WARM", b1["ms_filter_tier_warm"], b2["ms_filter_tier_warm"], f"  n={b1['n_warm_layers']}")
    line("headers 20 layers", b1["ms_headers_20_layers"], b2["ms_headers_20_layers"])
    line("FULL read 5 layers", b1["ms_full_read_5_layers"], b2["ms_full_read_5_layers"], f"  {human_bytes(b1['bytes_full_5'])}")
    line("tier walk counts×4", b1["ms_tier_walk_counts"], b2["ms_tier_walk_counts"])
    line("count agent=worker1", b1["ms_count_agent_worker1"], b2["ms_count_agent_worker1"])

    # throughput estimate for full 5-layer read
    if b2["ms_full_read_5_layers"] > 0:
        thr = b2["bytes_full_5"] / (b2["ms_full_read_5_layers"] / 1000.0) / (1024**2)
        print(f"\n  ~read throughput (warm 5 layers): {thr:.1f} MiB/s", flush=True)

    print("\n-- vs LLM (1s call) --", flush=True)
    for label, m in [
        ("tier walk", b2["ms_tier_walk_counts"]),
        ("point×1000", b2["ms_point_layer_x1000"]),
        ("50 random chunks", b2["ms_random_50_chunk0"]),
    ]:
        if m > 0:
            print(f"  {label}: {1000.0/m:.0f}× faster than 1s LLM", flush=True)

    # write report next to db
    report = db_path.with_suffix(".bench.txt")
    with report.open("w", encoding="utf-8") as f:
        f.write(f"db={db_path}\nfile={human_bytes(fsize)}\n")
        if fill_info:
            f.write(f"fill={fill_info}\n")
        f.write(f"cold={b1}\nwarm={b2}\n")
    print(f"\nreport: {report}", flush=True)

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
