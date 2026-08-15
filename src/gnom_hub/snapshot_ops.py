"""Pipeline/memory snapshot payloads for API/UI (extracted from Hub)."""

from __future__ import annotations

import os
from typing import Any

from gnom_hub import __version__
from gnom_hub.agents.models import FLEX_PRESETS


def _worst_validation(worker_outputs: list | None) -> dict[str, Any] | None:
    """Pick the most useful DoD gate for UI (failed first, then lowest score)."""
    worst: dict[str, Any] | None = None
    worst_rank = -1
    for o in worker_outputs or []:
        if not isinstance(o, dict):
            continue
        g = o.get("validation")
        if not isinstance(g, dict) or not g:
            continue
        ok = bool(g.get("ok", True))
        score = int(g.get("score") if g.get("score") is not None else (100 if ok else 0))
        issues = list(g.get("issues") or [])
        # higher rank = worse
        rank = (0 if ok else 1000) + (100 - max(0, min(100, score))) + min(len(issues), 20)
        if rank > worst_rank:
            worst_rank = rank
            worst = {
                "ok": ok,
                "score": score,
                "retryable": bool(g.get("retryable", False)),
                "issues": issues,
                "soft_issues": list(g.get("soft_issues") or []),
                "hints": list(g.get("hints") or [])[:8],
                "checklist": list(g.get("checklist") or [])[:24],
                "worker": o.get("worker") or o.get("name") or o.get("id"),
            }
    return worst


class SnapshotOpsMixin:
    """Mixin extracted from Hub — pure move."""

    def _tollgate_snapshot(self) -> dict[str, Any]:
        """Compact Tollgate status for UI (no secrets)."""
        out: dict[str, Any] = {
            "home": (os.getenv("TOLLGATE_HOME") or os.getenv("GNOM_WS") or "").strip() or None,
            "url": (os.getenv("TOLLGATE_URL") or "").strip() or None,
            "llm_via": os.getenv("GNOM_TOLLGATE_LLM", "1").strip().lower()
            not in ("0", "false", "no", "off"),
            "ok": False,
        }
        try:
            from tollgate import get_keys_service
            from tollgate.paths import path_snapshot

            snap = path_snapshot()
            out["portable"] = snap
            out["home"] = snap.get("data_home") or out["home"]
            st = get_keys_service().app_status()
            out["ok"] = bool(st.get("ok", True))
            out["app"] = {
                "prefer_free": (st.get("config") or {}).get("prefer_free")
                if isinstance(st.get("config"), dict)
                else None,
            }
            # usage totals if available
            try:
                from tollgate.usage_ledger import usage_summary

                u = usage_summary()
                out["usage_day"] = u.get("day")
                out["usage_totals"] = u.get("totals")
            except Exception:  # noqa: BLE001
                pass
        except Exception as e:  # noqa: BLE001
            out["error"] = str(e)[:160]
        return out

    def _stack_snapshot(self) -> dict[str, Any]:
        from gnom_hub.stack import stack_snapshot

        return stack_snapshot()

    def pipeline_dict(self) -> dict[str, Any]:
        st = self.pipeline.state
        q = None
        if st.pending_question is not None:
            q = {
                "id": st.pending_question.id,
                "text": st.pending_question.text,
                "options": list(st.pending_question.options),
            }
        can_execute = bool((st.brainstorm_notes or "").strip()) and st.stage.value in (
            "brainstorm",
            "idle",
            "done",
            "error",
        )
        if st.stage.value in ("distill", "flex", "coordinate", "work", "clarify"):
            can_execute = False
        return {
            "stage": st.stage.value,
            "mode": getattr(st, "mode", "brainstorm") or "brainstorm",
            "user_text": st.user_text,
            "memory_context": st.memory_context,
            "brainstorm_notes": st.brainstorm_notes,
            "brainstorm_turns": list(getattr(st, "brainstorm_turns", None) or []),
            "can_execute": can_execute,
            "distilled_requirements": list(st.distilled_requirements),
            "flex_notes": st.flex_notes,
            "pending_question": q,
            "deferred_clarifies": list(getattr(st, "deferred_clarifies", None) or [])[-8:],
            "worker_results": list(st.worker_results),
            "tool_calls": list(getattr(st, "tool_calls", None) or []),
            "worker_outputs": list(st.worker_outputs or []),
            "quality_notes": getattr(st, "quality_notes", "") or "",
            "agent_nudges": list(getattr(st, "agent_nudges", None) or []),
            "warnings": list(st.warnings),
            "error": st.error,
            "tool_log": list(getattr(st, "tool_log", None) or [])[-40:],
            "resolved_plan_mode": getattr(st, "resolved_plan_mode", "") or "",
            "plan_html_score": getattr(st, "plan_html_score", None),
            "validation": _worst_validation(list(st.worker_outputs or [])),
        }

    def memory_dict(self) -> dict[str, Any]:
        db_info: dict[str, Any] = {}
        try:
            from gnom_hub.db.sqlite_store import get_db

            db_info = get_db(self.root).snapshot_info()
        except Exception:  # noqa: BLE001
            db_info = {}
        return {
            "summary": self.hot.get_context_summary(),
            "facts": self.hot.all_facts()[-30:],
            "hot_count": len(self.hot.all_facts()),
            "warm_facts": self.warm.all_facts()[-30:],
            "warm_count": len(self.warm.all_facts()),
            "recent_messages": self.hot.recent_messages(6),
            "context": self.memory.pipeline_context(),
            "canvas_nodes": len(self.hot.canvas.nodes),
            "user_db": db_info,
        }

    def snapshot(self) -> dict[str, Any]:
        usage = self.llm.usage_snapshot()
        uw = getattr(self, "user_workspace", None)
        user_ws = uw.to_dict() if uw is not None and hasattr(uw, "to_dict") else {}
        return {
            "agents": [self._agent_dict(a) for a in self.agents.list_agents()],
            "pipeline": self.pipeline_dict(),
            "memory_summary": self.hot.get_context_summary(),
            "memory": self.memory_dict(),
            "user_workspace": user_ws,
            "workspace": self.workspace.snapshot(),
            "telegram": {
                "configured": self.telegram.enabled,
                "running": self.telegram.running,
                "allowlist_size": len(getattr(self.telegram, "allowed_chat_ids", ()) or ()),
                "allowlist_configured": bool(getattr(self.telegram, "allowed_chat_ids", None)),
            },
            "god_mode": self.god_mode.snapshot(),
            "vectors": {
                "count": self.vectors.count(),
                "embedder": getattr(self.vectors, "embedder_name", "bow"),
            },
            "skills": {
                "count": len(
                    getattr(self, "skill_list", None)
                    or getattr(getattr(self, "skills", None), "skills", [])
                    or []
                ),
                "enabled": sum(
                    1
                    for s in (getattr(getattr(self, "skills", None), "skills", None) or [])
                    if getattr(s, "enabled", True)
                ),
            },
            "cold": {"count": len(self.cold.list_archives(200))},
            "plugins": self.plugin_list,
            "tools": self.tools.list_tools(),
            "computer_use": self.computer.snapshot(),
            "canvas": {
                "mermaid": self.hot.canvas.to_mermaid(),
                "nodes": len(self.hot.canvas.nodes),
            },
            "llm": {
                "deepseek": self.llm.has_provider("deepseek"),
                "ollama": self.llm.has_provider("ollama"),
                "auth": (self.llm.auth_snapshot() if hasattr(self.llm, "auth_snapshot") else {}),
                "free_only": self.llm.free_only,
                "max_budget_usd": self.llm.max_budget_usd,
                "spent_usd": usage["spent_usd"],
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "default_model": self.llm.default_model,
                "providers": self.llm.providers_snapshot(),
                "via_tollgate": os.getenv("GNOM_TOLLGATE_LLM", "1").strip().lower()
                not in ("0", "false", "no", "off"),
                "tollgate_url": (os.getenv("TOLLGATE_URL") or "").strip() or None,
                "last_route": usage.get("last_route"),
            },
            "tollgate": self._tollgate_snapshot(),
            "stack": self._stack_snapshot(),
            "version": __version__,
            "flex_presets": list(FLEX_PRESETS),
            "plan_mode": getattr(self, "plan_mode", "default") or "default",
            "team_presets": self.list_team_presets(),
            "last_error": self.last_error,
            # Reasoning streams for TTS (Gedanken) — not the written Box 2/3 text
            "agent_thoughts": dict(getattr(self, "_agent_thoughts", {}) or {}),
            "flex_review": (
                self.flex_review_panel()
                if hasattr(self, "flex_review_panel")
                else {"active": False, "buttons": []}
            ),
            "trace": list(self.trace[-40:]),
            "ui_lang": self.ui_lang,
            "checkpoint": {
                "exists": self._checkpoint_path.is_file(),
                "path": str(self._checkpoint_path),
            },
            "features": {
                "phase3": self.feature_phase3,
                "workers_max": 4,
            },
            "worker_presets": self.list_worker_presets(),
        }
