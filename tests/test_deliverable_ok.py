"""Stage done with FEHLER must not look like a successful deliverable."""

from pathlib import Path
from types import SimpleNamespace

from gnom_hub.pipeline.dod_gate import run_dod_check
from gnom_hub.snapshot_ops import _deliverable_ok

_REPO = Path(__file__).resolve().parents[1]


def _fehler_body(*, reason: str) -> str:
    return (
        "Worker 1 FEHLER - kein Deliverable\n"
        f"{reason}\n"
        "Kein Stub-Ersatz. Key pruefen, Budget pruefen, dann erneut ausfuehren.\n"
        + ("Hinweis: Worker liefert erst mit tigem Provider. " * 8)
    )
