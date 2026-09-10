"""_action_to_dict must keep dry_run so workers do not label a no-op as live."""

from __future__ import annotations

from gnom_hub.computer_use.action import ActionResult
from gnom_hub.tools.agent_bridge import label_tool_result
from gnom_hub.tools_ops import _action_to_dict


def test_action_to_dict_keeps_dry_run_and_detail() -> None:
    raw = ActionResult(True, True, "dry-run click (1,2) — enable God-Mode to execute")
    out = _action_to_dict(raw)
    assert out["ok"] is True
    assert out["dry_run"] is True
    assert "dry-run" in out["detail"]
    assert label_tool_result(out) == "dry-run"


def test_action_to_dict_live_result_is_not_dry_run() -> None:
    raw = ActionResult(True, False, "clicked (1,2)", stdout="")
    out = _action_to_dict(raw)
    assert out["dry_run"] is False
    assert label_tool_result(out) == "live"
