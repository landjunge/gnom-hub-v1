"""Q8 tab rule executed, not only grepped: collapse + when tabs are wanted."""

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
const cases = {
  none: collapseSharedErrors([]),
  one: collapseSharedErrors(rows([HTML_A])),
  four_key: collapseSharedErrors(rows([KEY, KEY2, KEY, KEY])),
  four_same_html: collapseSharedErrors(rows([HTML_A, HTML_A, HTML_A, HTML_A])),
  two_html: collapseSharedErrors(rows([HTML_A, HTML_B])),
  mixed: collapseSharedErrors(rows([HTML_A, KEY])),
  two_fail_diff: collapseSharedErrors(rows([KEY, TO])),
};
const out = {};
Object.keys(cases).forEach(function (k) {
  const r = cases[k];
  out[k] = {
    n: r.length,
    workers: r.map(function (x) { return x.worker; }),
    tabs: box3TabsWanted(r),
  };
});
console.log(JSON.stringify(out));
"""


def test_q8_tab_cases_run_in_node():
    src = _fn("box3TabsWanted") + "\n" + _fn("collapseSharedErrors") + "\n" + SCRIPT
    proc = subprocess.run(
        ["node", "-e", src],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)

    assert data["none"] == {"n": 0, "workers": [], "tabs": False}
    assert data["one"]["n"] == 1 and data["one"]["tabs"] is False
    assert data["four_key"]["n"] == 1
    assert data["four_key"]["workers"] == ["desk"]
    assert data["four_key"]["tabs"] is False
    assert data["four_same_html"]["n"] == 4
    assert data["four_same_html"]["tabs"] is True
    assert data["two_html"]["n"] == 2 and data["two_html"]["tabs"] is True
    assert data["mixed"]["n"] == 2 and data["mixed"]["tabs"] is True
    assert data["two_fail_diff"]["n"] == 2 and data["two_fail_diff"]["tabs"] is True


def test_q8_source_uses_shared_rule():
    render = BOX.split("function renderBox3WorkerTabs", 1)[1].split(
        "function focusBox3WorkerResult", 1
    )[0]
    assert "box3TabsWanted" in render
    box2 = BOX.split("function renderBox2ReplyTabs", 1)[1].split(
        "function renderDynamicContent", 1
    )[0]
    assert "answers.length < 2" in box2
