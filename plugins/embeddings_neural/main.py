"""Optional neural embeddings — only if extra packages installed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gnom_hub.plugins.sdk import fail, ok


def _vectors():
    try:
        from gnom_hub.hub import get_hub

        return getattr(get_hub(), "vectors", None)
    except Exception:  # noqa: BLE001
        return None


def status() -> dict[str, Any]:
    from gnom_hub.memory.neural_embed import probe_neural

    probe = probe_neural()
    vs = _vectors()
    active = getattr(vs, "embedder_name", "bow") if vs else "n/a"
    return ok(
        available=probe,
        active=active,
        install_hint="pip install fastembed  OR  pip install sentence-transformers",
    )


def use_neural(backend: str = "fastembed", reindex: bool = False) -> dict[str, Any]:
    vs = _vectors()
    if vs is None or not hasattr(vs, "set_embedder"):
        return fail("vector store not available")
    try:
        from gnom_hub.hub import get_hub
        from gnom_hub.memory.neural_embed import make_neural_embedder, probe_neural

        name, fn = make_neural_embedder(backend)
        out = vs.set_embedder(name, fn=fn, reindex=bool(reindex))
        try:
            root = get_hub().root
            path = Path(root) / "data" / "hot" / "vector_embedder.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"embedder": name}, indent=2) + chr(10), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        return ok(**out, available=probe_neural())
    except Exception as exc:  # noqa: BLE001
        return fail(f"neural embedder failed: {exc}")


def install_pkg() -> dict[str, Any]:
    """pip install fastembed into current env — one simple path."""
    import subprocess
    import sys

    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "fastembed>=0.4.0"],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "pip failed")[-800:]
            return fail(f"pip install failed: {err}")
        from gnom_hub.memory.neural_embed import probe_neural

        p = probe_neural()
        if not p.get("fastembed"):
            return fail("fastembed still not importable after pip")
        return ok(
            installed=True,
            available=p,
            next="Call embeddings_neural_use backend=fastembed reindex=true, or Vector modal.",
        )
    except Exception as exc:  # noqa: BLE001
        return fail(str(exc))
