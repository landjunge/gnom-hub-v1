"""Box 3 core rules executed in Node — collapse, keep, tabs, labels, normalize."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOX = (ROOT / "src/gnom_hub/ui/static/parts/09-boxes.js").read_text(encoding="utf-8")


def _brace_block(src: str, brace: int) -> str:
    depth = 0
    for i, ch in enumerate(src[brace:], brace):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[brace : i + 1]
    raise AssertionError("unclosed")


def _fn(name: str) -> str:
    idx = BOX.find("function " + name)
    if idx < 0:
        raise AssertionError("missing " + name)
    brace = BOX.index("{", idx)
    return BOX[idx:brace] + _brace_block(BOX, brace)


SCRIPT = r"""
const KEY = "Worker 1 FEHLER - kein Deliverable\nllm/key missing";
const KEY2 = "Worker 2 FEHLER - kein Deliverable\nllm/key missing";
const TO = "Worker 3 FEHLER - timeout nach 30s";
const HTML_A = "<!DOCTYPE html><html><body><h1>A</h1></body></html>";
const HTML_B = "<!DOCTYPE html><html><body><h1>B</h1></body></html>";
function rows(texts) {
  return texts.map(function (t, i) {
    return { worker: "worker" + (i + 1), name: "Worker " + (i + 1), result: t };
  });
}
function pack(r) {
  return {
    n: r.length,
    workers: r.map(function (x) { return x.worker; }),
    tabs: box3TabsWanted(r),
  };
}
const prev = rows([HTML_A, HTML_B]);
const out = {
  collapse: {
    none: pack(collapseSharedErrors([])),
    one: pack(collapseSharedErrors(rows([HTML_A]))),
    four_key: pack(collapseSharedErrors(rows([KEY, KEY2, KEY, KEY]))),
    four_same_html: pack(collapseSharedErrors(rows([HTML_A, HTML_A, HTML_A, HTML_A]))),
    two_html: pack(collapseSharedErrors(rows([HTML_A, HTML_B]))),
    mixed: pack(collapseSharedErrors(rows([HTML_A, KEY]))),
    two_fail_diff: pack(collapseSharedErrors(rows([KEY, TO]))),
    blanks: pack(collapseSharedErrors(rows(["", "  ", ""]))),
    one_blank_one_html: pack(collapseSharedErrors(rows(["", HTML_A]))),
  },
  keep: {
    send_idle: box3KeepLast([], prev, "idle"),
    send_brain: box3KeepLast([], prev, "brainstorm"),
    done_empty: box3KeepLast([], prev, "done"),
    error_empty: box3KeepLast([], prev, "error"),
    work_empty: box3KeepLast([], prev, "work"),
    idle_fresh: box3KeepLast([], [], "idle"),
    idle_new: box3KeepLast(rows([HTML_B]), prev, "idle"),
  },
  normalize: {
    empty: normalizeWorkerOutputs({}).length,
    outputs: normalizeWorkerOutputs({
      worker_outputs: [{ worker: "worker2", result: HTML_A, validation: { ok: true } }],
    }),
    results: normalizeWorkerOutputs({ worker_results: ["alpha", "beta"] }),
  },
  labels: {
    w1: box3WorkerTabLabel({ worker: "worker1" }, 0),
    w2name: box3WorkerTabLabel({ name: "Worker 2" }, 1),
    desk: box3WorkerTabLabel({ worker: "desk", name: "Ergebnis" }, 0),
    variant: box3WorkerTabLabel({ worker: "worker1", variant_of: 1 }, 0),
    title1: box3WorkerTabTitle({ worker: "worker1", name: "Worker 1" }, 0),
    titleDesk: box3WorkerTabTitle({ worker: "desk", name: "Ergebnis" }, 0),
  },
};
console.log(JSON.stringify(out));
"""


def _run() -> dict:
    src = "\n".join(
        [
            _fn("box3TabsWanted"),
            _fn("box3KeepLast"),
            _fn("collapseSharedErrors"),
            _fn("normalizeWorkerOutputs"),
            _fn("box3WorkerTabLabel"),
            _fn("box3WorkerTabTitle"),
            SCRIPT,
        ]
    )
    proc = subprocess.run(
        ["node", "-e", src],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_q8_collapse_and_tabs():
    data = _run()["collapse"]
    assert data["none"] == {"n": 0, "workers": [], "tabs": False}
    assert data["one"]["n"] == 1 and data["one"]["tabs"] is False
    assert data["four_key"] == {"n": 1, "workers": ["desk"], "tabs": False}
    assert data["four_same_html"]["n"] == 4 and data["four_same_html"]["tabs"] is True
    assert data["two_html"]["n"] == 2 and data["two_html"]["tabs"] is True
    assert data["mixed"]["n"] == 2 and data["mixed"]["tabs"] is True
    assert data["two_fail_diff"]["n"] == 2 and data["two_fail_diff"]["tabs"] is True
    assert data["blanks"]["n"] == 3 and data["blanks"]["tabs"] is True
    assert data["one_blank_one_html"]["n"] == 2


def test_q5_keep_last_only_on_talk():
    k = _run()["keep"]
    assert k["send_idle"] is True
    assert k["send_brain"] is True
    assert k["done_empty"] is False
    assert k["error_empty"] is False
    assert k["work_empty"] is False
    assert k["idle_fresh"] is False
    assert k["idle_new"] is False


def test_normalize_outputs_and_results():
    n = _run()["normalize"]
    assert n["empty"] == 0
    assert n["outputs"][0]["worker"] == "worker2"
    assert n["outputs"][0]["validation"]["ok"] is True
    assert [x["worker"] for x in n["results"]] == ["worker1", "worker2"]
    assert n["results"][0]["result"] == "alpha"


def test_box3_tab_labels():
    lab = _run()["labels"]
    assert lab["w1"] == "1"
    assert lab["w2name"] == "2"
    assert lab["desk"] == "1"
    assert lab["variant"] == "1v"
    assert lab["title1"] == "Arbeiter 1"
    assert lab["titleDesk"] == "Ergebnis"


def test_q8_source_uses_shared_rule():
    render = BOX.split("function renderBox3WorkerTabs", 1)[1].split(
        "function focusBox3WorkerResult", 1
    )[0]
    assert "box3TabsWanted" in render
    keep = BOX.split("function renderBox3Workers", 1)[1].split("function stageResultsRecovery", 1)[
        0
    ]
    assert "box3KeepLast" in keep
    nav = BOX.split("function paintBox3Nav", 1)[1].split("function renderBox3WorkerTabs", 1)[0]
    assert "box3TabsWanted" in nav
    box2 = BOX.split("function renderBox2ReplyTabs", 1)[1].split(
        "function renderDynamicContent", 1
    )[0]
    assert "answers.length < 2" in box2
