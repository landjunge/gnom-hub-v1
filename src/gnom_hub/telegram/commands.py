"""Telegram slash-command handlers (extracted from Hub — pure move)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TelegramCommandMixin:
    """Mixin: expects Hub attributes (pipeline, warm, hot, tools, …)."""

    def _telegram_command(self, cmd: str, arg: str, meta: dict[str, Any]) -> str:
        if cmd == "help":
            return (
                "Gnom-Hub Telegram\n"
                "/status — hub state\n"
                "plain text or /bs <idea> — brainstorm turn\n"
                "/exec — Execute from brainstorm notes\n"
                "/do <task> — full one-shot pipeline\n"
                "/pack list | save [label] | load <n|name>\n"
                "/warm list | add <fact> | del <n|text> | clear\n"
                "/cold list | load <n|id> | del <n|id>\n"
                "/cancel — soft-cancel running job\n"
                "/last — last worker results\n"
                "/reset — clear HOT (WARM kept)\n"
                "/yes /no /whatever /later — clarify\n"
                "/skills — list playbook skills\n"
                "/skill_on <id> · /skill_off <id>"
            )
        if cmd in ("skills", "skill"):
            skills = getattr(self, "skills", None)
            if skills is None:
                return "skills unavailable"
            lines = ["Skills (playbooks):"]
            for s in skills.skills:
                mark = "on" if s.enabled else "off"
                lines.append(f"  [{mark}] {s.id} — {s.name} ({s.source})")
            if not skills.skills:
                lines.append("  (none)")
            return "\n".join(lines)
        if cmd in ("skill_on", "skill_off"):
            skills = getattr(self, "skills", None)
            if skills is None:
                return "skills unavailable"
            sid = (arg or "").strip()
            if not sid:
                return "Usage: /skill_on <id> or /skill_off <id>"
            out = skills.set_enabled(sid, cmd == "skill_on")
            return str(out)
        if cmd == "status":
            st = self.pipeline.state
            packs_n = len(self.list_session_packs())
            return (
                f"stage={st.stage.value} mode={getattr(st, 'mode', '')}\n"
                f"can_execute={bool((st.brainstorm_notes or '').strip())}\n"
                f"agents={sum(1 for a in self.agents.list_agents() if a.enabled)}/6\n"
                f"deepseek={'yes' if self.llm.has_provider('deepseek') else 'no'}\n"
                f"hot={self.hot.get_context_summary()}\n"
                f"warm_facts={len(self.warm.all_facts())}\n"
                f"packs={packs_n}"
                + chr(10)
                + f"cold={len(self.cold.list_archives(200))}"
                + chr(10)
                + f"vectors={self.vectors.count()}"
            )
        if cmd in ("bs", "brainstorm", "idea"):
            if not arg.strip():
                return "Usage: /bs <idea text> (or send plain text)"
            snap = self.chat(arg.strip(), full=False)
            p = snap["pipeline"]
            notes = (p.get("brainstorm_notes") or "")[-500:]
            return (
                f"brainstorm ok · stage={p.get('stage')}\nSend more ideas, then /exec\n---\n{notes}"
            )
        if cmd in ("exec", "execute", "go"):
            try:
                snap = self.execute_sync()
            except Exception as exc:  # noqa: BLE001
                return f"Execute failed: {exc}"
            p = snap["pipeline"]
            if p.get("stage") == "clarify" and p.get("pending_question"):
                q = p["pending_question"]["text"]
                return f"Clarify needed: {q}\nReply /yes /no /whatever /later"
            results = p.get("worker_results") or []
            head = (p.get("brainstorm_notes") or "")[:160]
            body = "\n".join(str(r)[:400] for r in results[:3])
            return f"stage={p.get('stage')}\n{head}\n{body}".strip()
        if cmd == "do":
            if not arg.strip():
                return "Usage: /do <task text> (one-shot full pipeline)"
            snap = self.chat(arg.strip(), full=True)
            p = snap["pipeline"]
            if p["stage"] == "clarify" and p.get("pending_question"):
                q = p["pending_question"]["text"]
                return f"Clarify needed: {q}\nReply /yes /no /whatever /later"
            results = p.get("worker_results") or []
            head = (p.get("brainstorm_notes") or "")[:200]
            return f"stage={p['stage']}\n{head}\n" + "\n".join(results[:3])
        if cmd == "pack":
            return self._telegram_pack(arg.strip())
        if cmd == "warm":
            return self._telegram_warm(arg.strip())
        if cmd == "cold":
            return self._telegram_cold(arg.strip())
        if cmd in ("vec", "vector", "search"):
            return self._telegram_vec(arg.strip())
        if cmd == "trace":
            return self._telegram_trace(arg.strip())
        if cmd == "backup":
            return self._telegram_backup(arg.strip())
        if cmd in ("jobs", "job"):
            return self._telegram_jobs(arg.strip())
        if cmd in ("usage", "cost", "spend"):
            return self._telegram_usage(arg.strip())
        if cmd in ("ws", "workspace", "files"):
            return self._telegram_workspace(arg.strip())
        if cmd in ("tools", "tool"):
            return self._telegram_tools(arg.strip(), cmd=cmd)
        if cmd in ("fetch", "web"):
            return self._telegram_fetch(arg.strip())
        if cmd == "hot":
            return self._telegram_hot(arg.strip())
        if cmd == "cancel":
            return self._telegram_cancel()
        if cmd == "last":
            st = self.pipeline.state
            if not st.worker_results and not getattr(st, "quality_notes", ""):
                return "No worker results yet."
            lines = [f"stage={st.stage.value}"]
            if st.user_text:
                lines.append(f"user: {st.user_text[:120]}")
            qn = getattr(st, "quality_notes", "") or ""
            if qn:
                lines.append(f"quality: {qn[:200]}")
            for r in (st.worker_results or [])[:5]:
                lines.append(str(r)[:500])
            return "\n".join(lines)
        if cmd == "reset":
            self.reset_session(keep_agents=True)
            return "HOT session reset (WARM facts kept)."
        if cmd in ("yes", "no", "whatever", "later"):
            opt = cmd.capitalize() if cmd != "yes" else "Yes"
            if cmd == "no":
                opt = "No"
            if cmd == "whatever":
                opt = "Whatever"
            if cmd == "later":
                opt = "Later"
            try:
                snap = self.clarify(opt)
            except ValueError as e:
                return str(e)
            p = snap["pipeline"]
            return f"stage={p['stage']}\n" + "\n".join((p.get("worker_results") or [])[:3])
        if cmd == "disable" and arg:
            try:
                en = self.agents.toggle(arg.strip().lower())
                return f"{arg} enabled={en}"
            except ValueError as e:
                return str(e)
        return f"Unknown /{cmd}. Try /help"

    def _telegram_pack(self, arg: str) -> str:
        """Telegram: /pack list | save [label] | load <n|name>."""
        parts = arg.split(maxsplit=1)
        sub = (parts[0] if parts else "list").lower()
        rest = parts[1].strip() if len(parts) > 1 else ""
        if sub in ("", "list", "ls"):
            packs = self.list_session_packs()[:10]
            if not packs:
                return "No packs yet. /pack save [label]"
            lines = ["Session packs:"]
            for i, p in enumerate(packs, start=1):
                note = f" — {p['notes'][:40]}" if p.get("notes") else ""
                lines.append(f"{i}. {p.get('label') or p['name']}{note}")
            lines.append("Load: /pack load <n|name>")
            return "\n".join(lines)
        if sub in ("save", "export", "store"):
            try:
                data = self.export_session_pack(
                    label=rest or None,
                    persist=True,
                )
            except Exception as exc:  # noqa: BLE001
                return f"Pack save failed: {exc}"
            return (
                f"Pack saved: {data.get('filename')}\n"
                f"label={data.get('pack', {}).get('label')}\n"
                f"chars={data.get('chars')}"
            )
        if sub in ("load", "import", "open"):
            if not rest:
                return "Usage: /pack load <number|filename|label>"
            packs = self.list_session_packs()
            if not packs:
                return "No packs on disk."
            target = None
            if rest.isdigit():
                idx = int(rest)
                if 1 <= idx <= len(packs):
                    target = packs[idx - 1]["name"]
            if target is None:
                low = rest.lower()
                for p in packs:
                    if p["name"].lower() == low or low in p["name"].lower():
                        target = p["name"]
                        break
                    if low in str(p.get("label") or "").lower():
                        target = p["name"]
                        break
            if not target:
                return f"Pack not found: {rest}"
            try:
                snap = self.import_session_pack_file(target)
            except Exception as exc:  # noqa: BLE001
                return f"Pack load failed: {exc}"
            p = snap.get("pipeline") or {}
            return (
                f"Loaded {target}\nstage={p.get('stage')} · user={(p.get('user_text') or '')[:80]}"
            )
        return "Usage: /pack list | save [label] | load <n|name>"

    def _telegram_warm(self, arg: str) -> str:
        """Telegram: /warm list | add <fact> | del <n|text> | clear."""
        parts = arg.split(maxsplit=1)
        sub = (parts[0] if parts else "list").lower()
        rest = parts[1].strip() if len(parts) > 1 else ""
        if sub in ("", "list", "ls"):
            facts = self.warm.all_facts()
            if not facts:
                return "WARM empty. /warm add <fact>"
            lines = [f"WARM facts ({len(facts)}):"]
            start_i = max(0, len(facts) - 12)
            for i, f in enumerate(facts[start_i:], start=start_i + 1):
                lines.append(f"{i}. {f[:160]}")
            return "\n".join(lines)
        if sub in ("add", "a", "+"):
            if not rest:
                return "Usage: /warm add <fact text>"
            ok = self.warm.add_fact(rest)
            return "WARM added." if ok else "WARM unchanged (empty or duplicate)."
        if sub in ("del", "rm", "delete", "remove"):
            if not rest:
                return "Usage: /warm del <n|exact text>"
            if rest.isdigit():
                removed = self.warm.remove_at(int(rest))
                if removed is None:
                    return f"No fact at index {rest}"
                return f"WARM removed: {removed[:120]}"
            ok = self.warm.remove_fact(rest)
            return "WARM removed." if ok else "Fact not found (use exact text or index)."
        if sub == "clear":
            n = len(self.warm.all_facts())
            self.warm.clear()
            return f"WARM cleared ({n} facts)."
        return "Usage: /warm list | add <fact> | del <n|text> | clear"

    def _telegram_cancel(self) -> str:
        """Soft-cancel the newest running job, if any."""
        jobs = getattr(self, "_jobs", {})
        running = [j for j in jobs.values() if isinstance(j, dict) and j.get("status") == "running"]
        if not running:
            return "No running job to cancel."
        running.sort(key=lambda j: str(j.get("id") or ""), reverse=True)
        job = running[0]
        try:
            self.cancel_job(str(job["id"]))
        except FileNotFoundError:
            return "Job vanished."
        return f"Cancel requested for job {job['id']} (soft)."

    def _telegram_cold(self, arg: str) -> str:
        """Telegram: /cold list | load <n|id> | del <n|id>."""
        parts = arg.split(maxsplit=1)
        sub = (parts[0] if parts else "list").lower()
        rest = parts[1].strip() if len(parts) > 1 else ""
        archives = self.cold.list_archives(30)
        if sub in ("", "list", "ls"):
            if not archives:
                return "COLD empty. Archive from UI or /reset."
            lines = ["COLD archives:"]
            for i, a in enumerate(archives[:12], start=1):
                lines.append(
                    f"{i}. {a.get('id')} · {a.get('label') or ''} · msg={a.get('messages')}"
                )
            lines.append("Load: /cold load <n|id>")
            return chr(10).join(lines)
        if sub in ("load", "restore", "open"):
            if not rest:
                return "Usage: /cold load <n|id>"
            target = self._resolve_cold_id(rest, archives)
            if not target:
                return f"COLD not found: {rest}"
            try:
                snap = self.restore_cold(target, archive_current=True)
            except FileNotFoundError:
                return f"COLD not found: {rest}"
            meta = snap.get("restored") or {}
            rid = meta.get("id") or target
            lab = meta.get("label") or ""
            return f"Restored COLD {rid}" + chr(10) + f"label={lab}"
        if sub in ("del", "rm", "delete"):
            if not rest:
                return "Usage: /cold del <n|id>"
            target = self._resolve_cold_id(rest, archives)
            if not target:
                return f"COLD not found: {rest}"
            try:
                self.delete_cold(target)
            except FileNotFoundError:
                return f"COLD not found: {rest}"
            return f"Deleted COLD {target}"
        return "Usage: /cold list | load <n|id> | del <n|id>"

    def _resolve_cold_id(self, token: str, archives: list[dict] | None = None) -> str | None:
        rows = archives if archives is not None else self.cold.list_archives(50)
        if not rows:
            return None
        if token.isdigit():
            idx = int(token)
            if 1 <= idx <= len(rows):
                return str(rows[idx - 1].get("id") or "") or None
        low = token.lower()
        for a in rows:
            aid = str(a.get("id") or "")
            if aid.lower() == low or low in aid.lower():
                return aid
            if low in str(a.get("label") or "").lower():
                return aid
        return None

    def _telegram_vec(self, arg: str) -> str:
        """Telegram: /vec search|add|list|del|clear."""
        parts = arg.split(maxsplit=1)
        sub = (parts[0] if parts else "list").lower()
        rest = parts[1].strip() if len(parts) > 1 else ""
        if sub in ("", "list", "ls"):
            docs = self.vectors.list_docs(12)
            if not docs:
                return "Vector store empty. /vec add <text>"
            lines = [f"Vectors ({self.vectors.count()}):"]
            for d in docs:
                lines.append(f"- {d.get('id')}: {str(d.get('text') or '')[:100]}")
            return chr(10).join(lines)
        if sub in ("search", "find", "q"):
            if not rest:
                return "Usage: /vec search <query>"
            hits = self.vectors.search(rest, limit=5)
            if not hits:
                return "No hits."
            lines = [f"Search: {rest[:60]}"]
            for h in hits:
                lines.append(f"{h.get('score')}: {h.get('id')} — {str(h.get('text') or '')[:120]}")
            return chr(10).join(lines)
        if sub in ("add", "a", "+"):
            if not rest:
                return "Usage: /vec add <text>"
            doc_id = self.vectors.add(rest, meta={"source": "telegram"})
            return f"Added {doc_id} (n={self.vectors.count()})"
        if sub in ("del", "rm", "delete"):
            if not rest:
                return "Usage: /vec del <id>"
            ok = self.vectors.delete(rest.strip())
            return f"Deleted {rest}." if ok else f"Not found: {rest}"
        if sub == "clear":
            n = self.vectors.count()
            self.vectors.clear()
            return f"Vector store cleared ({n} docs)."
        # bare query convenience: /vec something without subcommand word
        if arg.strip() and sub not in ("list", "ls"):
            # if first token isn't a known sub, treat full arg as search
            hits = self.vectors.search(arg.strip(), limit=5)
            if not hits:
                return "No hits. Try /vec add <text> first."
            lines = [f"Search: {arg.strip()[:60]}"]
            for h in hits:
                lines.append(f"{h.get('score')}: {h.get('id')} — {str(h.get('text') or '')[:120]}")
            return chr(10).join(lines)
        return "Usage: /vec search <q> | add <text> | list | del <id> | clear"

    def _telegram_trace(self, arg: str) -> str:
        """Telegram: /trace [n] | clear."""
        parts = arg.split(maxsplit=1)
        sub = (parts[0] if parts else "").lower()
        if sub == "clear":
            n = len(self.trace)
            self.trace = []
            return f"Trace cleared ({n} events)."
        limit = 15
        if sub.isdigit():
            limit = max(1, min(40, int(sub)))
        elif arg.strip().isdigit():
            limit = max(1, min(40, int(arg.strip())))
        events = list(self.trace[-limit:])
        if not events:
            return "Trace empty. Run /bs or /exec first."
        lines = [f"Trace (last {len(events)}/{len(self.trace)}):"]
        for e in events:
            d = e.get("data") if isinstance(e.get("data"), dict) else {}
            extra = ""
            if d.get("stage"):
                extra = f" stage={d.get('stage')}"
            elif d.get("error"):
                extra = f" err={str(d.get('error'))[:60]}"
            lines.append(f"{e.get('ts') or ''} {e.get('event') or ''}{extra}")
        return chr(10).join(lines)

    def _telegram_backup(self, arg: str) -> str:
        """Telegram: /backup list | save | load <n|name> | del <n|name>."""
        parts = arg.split(maxsplit=1)
        sub = (parts[0] if parts else "list").lower()
        rest = parts[1].strip() if len(parts) > 1 else ""
        if sub in ("", "list", "ls"):
            rows = self.list_backups()[:10]
            if not rows:
                return "No backups. /backup save"
            lines = ["Backups:"]
            for i, b in enumerate(rows, start=1):
                kb = (b.get("bytes") or 0) // 1024
                lines.append(f"{i}. {b.get('name')} · {kb} KB")
            lines.append("Load: /backup load <n|name>")
            return chr(10).join(lines)
        if sub in ("save", "create", "new"):
            try:
                data = self.create_backup()
            except Exception as exc:  # noqa: BLE001
                return f"Backup failed: {exc}"
            return f"Backup saved: {Path(data.get('path') or '').name} ({data.get('bytes')} B)"
        if sub in ("load", "restore", "open"):
            if not rest:
                return "Usage: /backup load <n|name>"
            target = self._resolve_backup_name(rest)
            if not target:
                return f"Backup not found: {rest}"
            try:
                snap = self.restore_backup(target, archive_current=True)
            except (FileNotFoundError, ValueError) as exc:
                return f"Restore failed: {exc}"
            return (
                f"Restored {snap.get('restored_backup')}"
                + chr(10)
                + f"checkpoint={snap.get('checkpoint_loaded')}"
            )
        if sub in ("del", "rm", "delete"):
            if not rest:
                return "Usage: /backup del <n|name>"
            target = self._resolve_backup_name(rest)
            if not target:
                return f"Backup not found: {rest}"
            try:
                self.delete_backup(target)
            except (FileNotFoundError, ValueError) as exc:
                return f"Delete failed: {exc}"
            return f"Deleted backup {target}"
        return "Usage: /backup list | save | load <n|name> | del <n|name>"

    def _resolve_backup_name(self, token: str) -> str | None:
        rows = self.list_backups()
        if not rows:
            return None
        if token.isdigit():
            idx = int(token)
            if 1 <= idx <= len(rows):
                return str(rows[idx - 1].get("name") or "") or None
        low = token.lower()
        for b in rows:
            name = str(b.get("name") or "")
            if name.lower() == low or low in name.lower():
                return name
        return None

    def _telegram_jobs(self, arg: str) -> str:
        """Telegram: /jobs [n] | cancel <id>."""
        parts = arg.split(maxsplit=1)
        sub = (parts[0] if parts else "").lower()
        rest = parts[1].strip() if len(parts) > 1 else ""
        if sub in ("cancel", "stop") and rest:
            try:
                out = self.cancel_job(rest)
            except FileNotFoundError:
                return f"Unknown job {rest}"
            return f"Job {out.get('id')}: {out.get('status')}"
        limit = 10
        if sub.isdigit():
            limit = max(1, min(20, int(sub)))
        rows = self.list_jobs(limit)
        if not rows:
            return "No jobs yet."
        lines = [f"Jobs (last {len(rows)}):"]
        for r in rows:
            err = f" · {r['error'][:40]}" if r.get("error") else ""
            lines.append(
                f"{r.get('id')} · {r.get('name')} · {r.get('status')}/{r.get('stage')}{err}"
            )
        lines.append("Cancel: /jobs cancel <id> or /cancel")
        return chr(10).join(lines)

    def _telegram_usage(self, arg: str) -> str:
        """Telegram: /usage [reset]."""
        sub = (arg or "").strip().lower()
        if sub in ("reset", "clear", "zero"):
            self.reset_usage()
            return "Usage counters reset."
        u = self.usage_dict()
        lines = [
            f"spent=${float(u.get('spent_usd') or 0):.4f}",
            f"tokens={int(u.get('prompt_tokens') or 0)}+{int(u.get('completion_tokens') or 0)}",
            f"budget={u.get('max_budget_usd') if u.get('max_budget_usd') is not None else 'none'}",
            f"free_only={u.get('free_only')}",
        ]
        by = u.get("by_agent") or {}
        if by:
            lines.append("by agent:")
            for aid, bucket in list(by.items())[:8]:
                cost = float(bucket.get("cost_usd") or 0)
                calls = int(bucket.get("calls") or 0)
                lines.append(f"  {aid}: ${cost:.4f} · calls={calls}")
        lines.append("Reset: /usage reset")
        return chr(10).join(lines)

    def _telegram_workspace(self, arg: str) -> str:
        """Telegram: /ws list | cat | promote | del | clear | write."""
        parts = arg.split(maxsplit=1)
        sub = (parts[0] if parts else "list").lower()
        rest = parts[1].strip() if len(parts) > 1 else ""
        if sub in ("", "list", "ls"):
            snap = self.workspace.snapshot()
            lines = ["Workspace:"]
            for zone in ("temp", "perm"):
                files = snap.get(zone) or []
                lines.append(f"[{zone}] {len(files)}")
                for f in files[:8]:
                    lines.append(f"  {f.get('name')} ({f.get('bytes')} B)")
                if len(files) > 8:
                    lines.append(f"  … +{len(files) - 8} more")
            return chr(10).join(lines)
        if sub in ("cat", "read", "show"):
            bits = rest.split(maxsplit=1)
            if len(bits) < 2:
                return "Usage: /ws cat <temp|perm> <name>"
            zone, name = bits[0], bits[1]
            try:
                text = self.workspace.read_text(zone, name, max_chars=1500)
            except (FileNotFoundError, ValueError) as exc:
                return f"Read failed: {exc}"
            return f"{zone}/{name}:" + chr(10) + text
        if sub in ("promote", "keep", "perm"):
            if not rest:
                return "Usage: /ws promote <temp-name>"
            try:
                path = self.workspace.promote(rest.strip())
            except FileNotFoundError as exc:
                return f"Promote failed: {exc}"
            return f"Promoted → {path.name}"
        if sub in ("del", "rm", "delete"):
            bits = rest.split(maxsplit=1)
            if len(bits) < 2:
                return "Usage: /ws del <temp|perm> <name>"
            zone, name = bits[0], bits[1]
            try:
                ok = self.workspace.delete(zone, name)
            except ValueError as exc:
                return str(exc)
            return f"Deleted {zone}/{name}." if ok else f"Not found: {zone}/{name}"
        if sub in ("clear", "clear-temp", "cleartemp"):
            n = self.workspace.clear_temp()
            return f"Cleared temp ({n} files)."
        if sub in ("write", "add", "put"):
            # /ws write temp name.txt content...
            bits = rest.split(maxsplit=2)
            if len(bits) < 3:
                return "Usage: /ws write <temp|perm> <name> <content>"
            zone, name, content = bits[0], bits[1], bits[2]
            try:
                path = self.workspace.write_text(zone, name, content)
            except ValueError as exc:
                return str(exc)
            return f"Wrote {zone}/{path.name} ({len(content)} chars)"
        return (
            "Usage: /ws list | cat <zone> <name> | promote <name> | "
            "del <zone> <name> | clear | write <zone> <name> <text>"
        )

    def _telegram_tools(self, arg: str, *, cmd: str = "tools") -> str:
        """Telegram: /tools | /tool <name> [json-args]."""
        # /tools alone → list; /tool name … → call
        if cmd == "tools" and not arg.strip():
            tools = self.tools.list_tools()
            if not tools:
                return "No tools registered."
            lines = [f"Tools ({len(tools)}):"]
            for tspec in tools[:20]:
                lines.append(
                    f"- {tspec.get('name')} [{tspec.get('plugin')}] "
                    f"— {str(tspec.get('description') or '')[:80]}"
                )
            lines.append('Call: /tool <name> {"key":"val"}')
            lines.append("Fetch: /fetch https://example.com")
            return chr(10).join(lines)
        # treat remaining as call
        parts = arg.split(maxsplit=1)
        if not parts or not parts[0]:
            return "Usage: /tool <name> [json-args]  or  /tools"
        name = parts[0].strip()
        raw_args = parts[1].strip() if len(parts) > 1 else ""
        arguments: dict = {}
        if raw_args:
            if raw_args.startswith("{"):
                try:
                    parsed = json.loads(raw_args)
                except json.JSONDecodeError as exc:
                    return f"Invalid JSON args: {exc}"
                if not isinstance(parsed, dict):
                    return "Args must be a JSON object"
                arguments = parsed
            else:
                # convenience: single string arg → text/url/query
                if name == "web_fetch":
                    arguments = {"url": raw_args}
                elif name == "memory_search":
                    arguments = {"query": raw_args}
                elif name == "pipeline_do":
                    arguments = {"text": raw_args}
                else:
                    arguments = {"text": raw_args}
        try:
            result = self.tools.call(name, arguments)
        except KeyError:
            return f"Unknown tool: {name}. Try /tools"
        except Exception as exc:  # noqa: BLE001
            return f"Tool error: {exc}"
        text = (
            result
            if isinstance(result, str)
            else json.dumps(result, ensure_ascii=False, default=str)
        )
        if len(text) > 2800:
            text = text[:2799] + "…"
        return f"{name} →" + chr(10) + text

    def _telegram_fetch(self, arg: str) -> str:
        """Telegram: /fetch <url>."""
        url = (arg or "").strip()
        if not url:
            return "Usage: /fetch https://example.com"
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            result = self.tools.call("web_fetch", {"url": url, "max_chars": 2000})
        except Exception as exc:  # noqa: BLE001
            return f"Fetch failed: {exc}"
        text = result if isinstance(result, str) else str(result)
        if len(text) > 2800:
            text = text[:2799] + "…"
        return f"fetch {url}" + chr(10) + text

    def _telegram_hot(self, arg: str) -> str:
        """Telegram: /hot list | add | del | clear | promote."""
        parts = arg.split(maxsplit=1)
        sub = (parts[0] if parts else "list").lower()
        rest = parts[1].strip() if len(parts) > 1 else ""
        if sub in ("", "list", "ls"):
            facts = self.hot.all_facts()
            if not facts:
                return "HOT facts empty. /hot add <fact>"
            lines = [f"HOT facts ({len(facts)}):"]
            start = max(0, len(facts) - 12)
            for i, f in enumerate(facts[start:], start=start + 1):
                lines.append(f"{i}. {f[:160]}")
            return chr(10).join(lines)
        if sub in ("add", "a", "+"):
            if not rest:
                return "Usage: /hot add <fact text>"
            data = self.add_hot_fact(rest)
            return "HOT added." if data.get("ok") else "HOT unchanged (empty or duplicate)."
        if sub in ("del", "rm", "delete", "remove"):
            if not rest:
                return "Usage: /hot del <n|exact text>"
            try:
                if rest.isdigit():
                    data = self.delete_hot_fact(index=int(rest))
                else:
                    data = self.delete_hot_fact(text=rest)
            except (FileNotFoundError, ValueError) as exc:
                return str(exc)
            return f"HOT removed: {str(data.get('removed') or '')[:120]}"
        if sub == "clear":
            data = self.clear_hot_facts()
            return f"HOT facts cleared ({data.get('cleared')})."
        if sub in ("promote", "warm", "keep"):
            if not rest:
                return "Usage: /hot promote <n|exact text>"
            facts = self.hot.all_facts()
            text = rest
            if rest.isdigit():
                idx = int(rest)
                if idx < 1 or idx > len(facts):
                    return f"No HOT fact at index {rest}"
                text = facts[idx - 1]
            try:
                data = self.promote_hot_fact(text)
            except (FileNotFoundError, ValueError) as exc:
                return str(exc)
            note = " (already in WARM)" if not data.get("warm_added") else ""
            return f"Promoted to WARM{note}: {text[:120]}"
        return "Usage: /hot list | add <fact> | del <n|text> | clear | promote <n|text>"

    # ── agent persistence ───────────────────────────────────────────
