#!/usr/bin/env python3
"""Surgical UI gates for #106. Run after restoring 08-chat-jobs.js from baseline."""
from pathlib import Path

CORE = Path("src/gnom_hub/ui/static/parts/00-core.js")
JOBS = Path("src/gnom_hub/ui/static/parts/08-chat-jobs.js")

OLD_CORE = """      if (
        mine ||
        (isSend && (result === "GELIEFERT" || result === "UNGEPRÜFT" || result))
      ) {"""
NEW_CORE = """      if (pipe.deliverable_ok === true && (mine || isSend)) {"""

OLD_RERUN = """      if (stage === "done") {
        appendChat("system", "Nochmal fertig: " + wid);
        toast(wid + " re-run done", "ok");"""
NEW_RERUN = """      if (stage === "done") {
        const okDeliverable = snap.pipeline && snap.pipeline.deliverable_ok;
        if (okDeliverable) {
          appendChat("system", "Nochmal fertig: " + wid);
          toast(wid + " re-run done", "ok");
        } else {
          appendChat("system", "Nochmal fertig ohne Deliverable: " + wid);
          toast(wid + " re-run ohne Deliverable", "error");
        }"""

OLD_REEXEC = """      if (snap.pipeline && snap.pipeline.stage === "done") {
        appendChat("system", "Nochmal fertig — siehe Box 3.");
        toast("Nochmal fertig", "ok");"""
NEW_REEXEC = """      if (snap.pipeline && snap.pipeline.stage === "done") {
        const okDeliverable = snap.pipeline && snap.pipeline.deliverable_ok;
        if (okDeliverable) {
          appendChat("system", "Nochmal fertig — siehe Box 3.");
          toast("Nochmal fertig", "ok");
        } else {
          appendChat("system", "Nochmal fertig ohne Deliverable — siehe Box 3.");
          toast("Kein Deliverable", "error");
        }"""


def must_replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            print(f"{path}: already gated")
            return
        raise SystemExit(f"{path}: expected block missing")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{path}: patched")


def main() -> None:
    must_replace(CORE, OLD_CORE, NEW_CORE)
    must_replace(JOBS, OLD_RERUN, NEW_RERUN)
    must_replace(JOBS, OLD_REEXEC, NEW_REEXEC)
    jobs = JOBS.read_text(encoding="utf-8")
    if jobs.count("okDeliverable") < 8:
        raise SystemExit(f"okDeliverable count={jobs.count('okDeliverable')}")


if __name__ == "__main__":
    main()
