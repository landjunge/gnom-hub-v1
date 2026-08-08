"""Session pack export/import (extracted from Hub — pure move)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gnom_hub.memory.atomic import atomic_write_text
from gnom_hub.pipeline.models import PipelineStage, PipelineState


class SessionPackMixin:
    """Mixin: expects Hub attributes (root, hot, warm, pipeline, workspace, …)."""

    @staticmethod
    def _sanitize_ui_chat_log(raw: Any) -> list[dict[str, str]]:
        """Cap chat lines for pack portability."""
        if not isinstance(raw, list):
            return []
        out: list[dict[str, str]] = []
        for item in raw[-80:]:
            if isinstance(item, str):
                text = item.strip()[:4000]
                if text:
                    out.append({"who": "system", "text": text, "ts": ""})
                continue
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()[:4000]
            if not text:
                continue
            out.append(
                {
                    "who": str(item.get("who") or "system")[:40],
                    "text": text,
                    "ts": str(item.get("ts") or "")[:32],
                }
            )
        return out

    @staticmethod
    def _sanitize_ui_result_history(raw: Any) -> list[dict[str, Any]]:
        """Cap result-history entries for pack portability."""
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw[:12]:
            if not isinstance(item, dict):
                continue
            outputs: list[dict[str, Any]] = []
            for o in (item.get("outputs") or [])[:8]:
                if not isinstance(o, dict):
                    continue
                outputs.append(
                    {
                        "worker": str(o.get("worker") or "")[:40],
                        "name": str(o.get("name") or "")[:80],
                        "task": str(o.get("task") or "")[:2000],
                        "result": str(o.get("result") or "")[:50000],
                        "index": o.get("index"),
                    }
                )
            turns: list[dict[str, str]] = []
            for tr in (item.get("brainstorm_turns") or [])[:40]:
                if not isinstance(tr, dict):
                    continue
                turns.append(
                    {
                        "role": str(tr.get("role") or "")[:40],
                        "text": str(tr.get("text") or "")[:4000],
                    }
                )
            out.append(
                {
                    "id": str(item.get("id") or "")[:40],
                    "ts": str(item.get("ts") or "")[:40],
                    "label": str(item.get("label") or "")[:80],
                    "user_text": str(item.get("user_text") or "")[:4000],
                    "brainstorm_notes": str(item.get("brainstorm_notes") or "")[:20000],
                    "brainstorm_turns": turns,
                    "can_reexec": bool(item.get("can_reexec")),
                    "outputs": outputs,
                }
            )
        return out

    def _collect_workspace_for_pack(
        self,
        *,
        max_files_per_zone: int = 20,
        max_chars_per_file: int = 100_000,
        max_total_chars: int = 500_000,
    ) -> dict[str, list[dict[str, str]]]:
        """Read temp/perm text files for pack (size-capped)."""
        out: dict[str, list[dict[str, str]]] = {"temp": [], "perm": []}
        total = 0
        for zone in ("temp", "perm"):
            try:
                files = self.workspace.list_files(zone)
            except OSError:
                continue
            for meta in files[:max_files_per_zone]:
                if total >= max_total_chars:
                    break
                name = str(meta.get("name") or "")
                if not name:
                    continue
                try:
                    # read full then cap (read_text already caps with ellipsis)
                    text = self.workspace.read_text(zone, name, max_chars=max_chars_per_file)
                except (OSError, FileNotFoundError, ValueError):
                    continue
                if total + len(text) > max_total_chars:
                    remain = max_total_chars - total
                    if remain < 64:
                        break
                    text = text[: remain - 1] + "…"
                out[zone].append({"name": name, "content": text})
                total += len(text)
        return out

    def _restore_workspace_from_pack(self, raw: Any) -> dict[str, int]:
        """Write pack workspace files into temp/perm. Returns counts."""
        if not isinstance(raw, dict):
            return {"temp": 0, "perm": 0}
        counts = {"temp": 0, "perm": 0}
        for zone in ("temp", "perm"):
            items = raw.get(zone)
            if not isinstance(items, list):
                continue
            for item in items[:20]:
                if not isinstance(item, dict):
                    continue
                name = Path(str(item.get("name") or "")).name
                content = item.get("content")
                if not name or content is None:
                    continue
                text = str(content)[:100_000]
                try:
                    self.workspace.write_text(zone, name, text)
                    counts[zone] += 1
                except (OSError, ValueError):
                    continue
        return counts

    @staticmethod
    def _sanitize_ui_prefs(raw: Any) -> dict[str, Any]:
        """compact + ui_lang only."""
        if not isinstance(raw, dict):
            return {}
        out: dict[str, Any] = {}
        if "compact" in raw:
            out["compact"] = bool(raw.get("compact"))
        lang = str(raw.get("ui_lang") or "").strip().lower()
        if lang in ("en", "de"):
            out["ui_lang"] = lang
        return out

    def export_session_pack(
        self,
        label: str | None = None,
        *,
        persist: bool = True,
        ui_chat_log: list | None = None,
        ui_result_history: list | None = None,
        include_workspace: bool = True,
        ui_prefs: dict | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Portable JSON pack: HOT + WARM + agents + pipeline + workspace (+ UI)."""

        self.hot.save()
        self.warm.save()
        agents_path = self._save_agent_state()
        agents_payload: dict[str, Any] = {"agents": []}
        try:
            agents_payload = json.loads(agents_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            agents_payload = {
                "agents": [
                    {
                        "id": a.id.value,
                        "enabled": a.enabled,
                        "preset": a.preset,
                        "model": a.model,
                        "tts": a.tts,
                        "system_prompt": a.system_prompt,
                        "temperature": a.temperature,
                        "top_p": a.top_p,
                        "max_tokens": a.max_tokens,
                        "frequency_penalty": a.frequency_penalty,
                        "presence_penalty": a.presence_penalty,
                    }
                    for a in self.agents.list_agents()
                ]
            }
        st = self.pipeline.state
        pipeline = {
            "stage": st.stage.value,
            "mode": st.mode,
            "user_text": st.user_text,
            "memory_context": st.memory_context,
            "brainstorm_notes": st.brainstorm_notes,
            "brainstorm_turns": list(st.brainstorm_turns or []),
            "distilled_requirements": list(st.distilled_requirements),
            "flex_notes": st.flex_notes,
            "worker_results": list(st.worker_results),
            "worker_outputs": list(st.worker_outputs or []),
            "quality_notes": getattr(st, "quality_notes", "") or "",
            "warnings": list(st.warnings),
            "error": st.error,
            "pending_question": (
                {
                    "id": st.pending_question.id,
                    "text": st.pending_question.text,
                    "options": list(st.pending_question.options),
                }
                if st.pending_question
                else None
            ),
        }
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        pack_label = (label or st.user_text or "session").strip()[:80] or "session"
        pack = {
            "format": "gnom-hub-session-pack",
            "format_version": 1,
            "app_version": "3.7.1",
            "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "label": pack_label,
            "notes": (str(notes).strip()[:200] if notes else ""),
            "hot": dict(self.hot.session),
            "canvas_mmd": self.hot.canvas.to_mermaid(),
            "warm_facts": self.warm.all_facts(),
            "agents": agents_payload.get("agents") or [],
            "pipeline": pipeline,
        }
        if ui_chat_log is not None:
            pack["ui_chat_log"] = self._sanitize_ui_chat_log(ui_chat_log)
        if ui_result_history is not None:
            pack["ui_result_history"] = self._sanitize_ui_result_history(ui_result_history)
        if include_workspace:
            pack["workspace"] = self._collect_workspace_for_pack()
        # Always embed server ui_lang; merge client prefs when provided
        prefs = {"ui_lang": self.ui_lang if self.ui_lang in ("en", "de") else "en"}
        if ui_prefs is not None:
            prefs.update(self._sanitize_ui_prefs(ui_prefs))
        pack["ui_prefs"] = prefs
        filename = f"gnom-hub-session-{stamp}.json"
        saved_path: str | None = None
        pruned: list[str] = []
        if persist:
            self._packs_dir.mkdir(parents=True, exist_ok=True)
            path = self._packs_dir / filename
            atomic_write_text(path, json.dumps(pack, ensure_ascii=False, indent=2) + "\n")
            saved_path = str(path)
            pruned = self.prune_session_packs()
        self._append_trace(
            "session.pack.export",
            {"label": pack["label"], "path": saved_path or "", "pruned": len(pruned)},
        )
        return {
            "ok": True,
            "filename": filename,
            "path": saved_path,
            "pack": pack,
            "chars": len(json.dumps(pack, ensure_ascii=False)),
            "packs": self.list_session_packs()[:12],
            "pruned": pruned,
        }

    def prune_session_packs(self, max_keep: int | None = None) -> list[str]:
        """Delete oldest packs beyond max_keep (default: self.pack_max). Newest first by name."""
        keep = self.pack_max if max_keep is None else int(max_keep)
        keep = max(5, min(100, keep))
        if not self._packs_dir.is_dir():
            return []
        files = sorted(self._packs_dir.glob("gnom-hub-session-*.json"), reverse=True)
        deleted: list[str] = []
        for p in files[keep:]:
            try:
                p.unlink()
                deleted.append(p.name)
            except OSError:
                continue
        if deleted:
            self._append_trace(
                "session.pack.prune",
                {"deleted": len(deleted), "keep": keep},
            )
        return deleted

    def store_session_pack(
        self,
        pack: dict[str, Any],
        *,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """Write a pack JSON under data/packs/ (e.g. after USB import)."""
        if not isinstance(pack, dict):
            raise TypeError("pack must be an object")
        if pack.get("format") != "gnom-hub-session-pack":
            raise ValueError("not a gnom-hub-session-pack")

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        name = Path(filename or f"gnom-hub-session-{stamp}.json").name
        if not name.startswith("gnom-hub-session-") or not name.endswith(".json"):
            name = f"gnom-hub-session-{stamp}.json"
        self._packs_dir.mkdir(parents=True, exist_ok=True)
        path = self._packs_dir / name
        atomic_write_text(path, json.dumps(pack, ensure_ascii=False, indent=2) + "\n")
        pruned = self.prune_session_packs()
        self._append_trace("session.pack.store", {"name": path.name})
        return {
            "ok": True,
            "name": path.name,
            "path": str(path),
            "pruned": pruned,
            "packs": self.list_session_packs()[:12],
        }

    def list_session_packs(self) -> list[dict[str, Any]]:
        """List packs under data/packs/ (newest first)."""

        if not self._packs_dir.is_dir():
            return []
        out: list[dict[str, Any]] = []
        for p in sorted(self._packs_dir.glob("gnom-hub-session-*.json"), reverse=True):
            try:
                label = p.stem
                exported_at = ""
                notes = ""
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        if data.get("label"):
                            label = str(data["label"])[:80]
                        exported_at = str(data.get("exported_at") or "")
                        notes = str(data.get("notes") or "")[:200]
                except (OSError, json.JSONDecodeError):
                    pass
                st = p.stat()
                mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
                out.append(
                    {
                        "name": p.name,
                        "path": str(p),
                        "bytes": st.st_size,
                        "label": label,
                        "notes": notes,
                        "exported_at": exported_at,
                        "mtime": mtime.replace(microsecond=0).isoformat(),
                    }
                )
            except OSError:
                continue
        return out[:30]

    def _pack_path(self, name: str) -> Path:
        safe = Path(name).name
        if not safe.startswith("gnom-hub-session-") or not safe.endswith(".json"):
            raise ValueError("invalid pack name")
        path = (self._packs_dir / safe).resolve()
        base = self._packs_dir.resolve()
        if not str(path).startswith(str(base)) or not path.is_file():
            raise FileNotFoundError(safe)
        return path

    def load_session_pack_file(self, name: str) -> dict[str, Any]:
        """Load pack JSON from data/packs/{name} (does not import)."""
        path = self._pack_path(name)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("pack file is not an object")
        return {"ok": True, "name": path.name, "pack": data}

    def import_session_pack_file(
        self,
        name: str,
        *,
        include_warm: bool = True,
        include_agents: bool = True,
    ) -> dict[str, Any]:
        """Import a pack stored under data/packs/."""
        data = self.load_session_pack_file(name)
        return self.import_session_pack(
            data["pack"],
            include_warm=include_warm,
            include_agents=include_agents,
        )

    def rename_session_pack(
        self,
        name: str,
        label: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Update label and/or notes inside a stored pack (filename unchanged)."""
        path = self._pack_path(name)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("pack file is not an object")
        if data.get("format") != "gnom-hub-session-pack":
            raise ValueError("not a gnom-hub-session-pack")
        if label is None and notes is None:
            raise ValueError("label or notes required")
        if label is not None:
            new_label = (label or "").strip()[:80]
            if not new_label:
                raise ValueError("label required")
            data["label"] = new_label
        if notes is not None:
            data["notes"] = str(notes).strip()[:200]
        atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        self._append_trace(
            "session.pack.rename",
            {
                "name": path.name,
                "label": data.get("label"),
                "notes": bool(data.get("notes")),
            },
        )
        return {
            "ok": True,
            "name": path.name,
            "label": data.get("label"),
            "notes": data.get("notes") or "",
            "packs": self.list_session_packs(),
        }

    def delete_session_pack(self, name: str) -> dict[str, Any]:
        path = self._pack_path(name)
        path.unlink()
        self._append_trace("session.pack.delete", {"name": path.name})
        return {"ok": True, "deleted": path.name, "packs": self.list_session_packs()}

    def maybe_auto_pack(self) -> dict[str, Any] | None:
        """If auto_pack is on, persist a pack after successful Execute."""
        if not self.auto_pack_after_execute:
            return None
        try:
            return self.export_session_pack(persist=True)
        except Exception as exc:  # noqa: BLE001
            self._append_trace("session.pack.auto_fail", {"error": str(exc)})
            return None

    def import_session_pack(
        self,
        pack: dict[str, Any],
        *,
        include_warm: bool = True,
        include_agents: bool = True,
        store: bool = False,
    ) -> dict[str, Any]:
        """Restore a portable session pack into this hub."""
        from gnom_hub.pipeline.models import DistillQuestion

        if not isinstance(pack, dict):
            raise TypeError("pack must be an object")
        if pack.get("format") != "gnom-hub-session-pack":
            raise ValueError("not a gnom-hub-session-pack")
        if store:
            self.store_session_pack(pack)

        # H6: pack import mutates pipeline + memory — hold pipeline lock
        with self._pipeline_lock_obj():
            hot = pack.get("hot") if isinstance(pack.get("hot"), dict) else {}
            self.hot.session = {
                "messages": list(hot.get("messages") or []),
                "facts": list(hot.get("facts") or []),
                "updated_at": hot.get("updated_at") or "",
            }
            canvas_mmd = str(pack.get("canvas_mmd") or "")
            if canvas_mmd.strip():
                self.hot.canvas_path.parent.mkdir(parents=True, exist_ok=True)
                if not canvas_mmd.endswith("\n"):
                    canvas_mmd = canvas_mmd + "\n"
                atomic_write_text(self.hot.canvas_path, canvas_mmd)
                self.hot.canvas.load(self.hot.canvas_path)
            else:
                self.hot.canvas.clear()
            self.hot.save()

            if isinstance(pack.get("workspace"), dict):
                self._restore_workspace_from_pack(pack.get("workspace"))

            if include_warm:
                for fact in pack.get("warm_facts") or []:
                    text = str(fact).strip()
                    if text:
                        self.warm.add_fact(text)

            if include_agents and isinstance(pack.get("agents"), list):
                for item in pack["agents"]:
                    if not isinstance(item, dict) or not item.get("id"):
                        continue
                    try:
                        agent = self.agents.get(str(item["id"]))
                    except ValueError:
                        continue
                    if agent.toggleable and "enabled" in item:
                        agent.enabled = bool(item["enabled"])
                    if str(getattr(agent.id, "value", agent.id)) == "flex" and item.get("preset"):
                        try:
                            self.agents.set_flex_preset(str(item["preset"]))
                        except ValueError:
                            pass
                    if item.get("model"):
                        agent.model = str(item["model"])
                    if "tts" in item:
                        agent.tts = bool(item["tts"])
                    if item.get("system_prompt") is not None:
                        agent.system_prompt = str(item["system_prompt"]) or None
                    for key in ("temperature", "top_p", "frequency_penalty", "presence_penalty"):
                        if item.get(key) is not None:
                            try:
                                setattr(agent, key, float(item[key]))
                            except (TypeError, ValueError):
                                pass
                    if item.get("max_tokens") is not None:
                        try:
                            agent.max_tokens = int(item["max_tokens"])
                        except (TypeError, ValueError):
                            pass
                self._save_agent_state()

            data = pack.get("pipeline") if isinstance(pack.get("pipeline"), dict) else {}
            q = None
            pq = data.get("pending_question")
            if isinstance(pq, dict) and pq.get("text"):
                q = DistillQuestion(
                    id=str(pq.get("id") or "q1"),
                    text=str(pq["text"]),
                    options=list(pq.get("options") or ["Yes", "No", "Whatever", "Later"]),
                )
            stage_raw = str(data.get("stage") or "brainstorm")
            try:
                stage = PipelineStage(stage_raw)
            except ValueError:
                stage = PipelineStage.brainstorm
            self.pipeline._state = PipelineState(
                stage=stage,
                user_text=str(data.get("user_text") or ""),
                memory_context=str(data.get("memory_context") or ""),
                brainstorm_notes=str(data.get("brainstorm_notes") or ""),
                brainstorm_turns=list(data.get("brainstorm_turns") or []),
                mode=str(data.get("mode") or "brainstorm"),
                distilled_requirements=list(data.get("distilled_requirements") or []),
                flex_notes=str(data.get("flex_notes") or ""),
                pending_question=q,
                worker_results=list(data.get("worker_results") or []),
                worker_outputs=list(data.get("worker_outputs") or []),
                quality_notes=str(data.get("quality_notes") or ""),
                warnings=list(data.get("warnings") or []),
                error=data.get("error"),
            )
            self.last_error = None
            self._append_trace(
                "session.pack.import",
                {"label": pack.get("label"), "stage": stage.value},
            )
            if isinstance(pack.get("ui_prefs"), dict):
                prefs = self._sanitize_ui_prefs(pack.get("ui_prefs"))
                lang = prefs.get("ui_lang")
                if lang in ("en", "de"):
                    self.ui_lang = lang
            snap = self.snapshot()
            if "ui_chat_log" in pack:
                snap["ui_chat_log"] = self._sanitize_ui_chat_log(pack.get("ui_chat_log"))
            if "ui_result_history" in pack:
                snap["ui_result_history"] = self._sanitize_ui_result_history(
                    pack.get("ui_result_history")
                )
            if isinstance(pack.get("ui_prefs"), dict):
                snap["ui_prefs"] = self._sanitize_ui_prefs(pack.get("ui_prefs"))
            if pack.get("notes") is not None:
                snap["pack_notes"] = str(pack.get("notes") or "")[:200]
            return snap
