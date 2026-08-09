"""V1 role agents — Brainstorm & Flex; others in roles_ext."""

from __future__ import annotations

from gnom_hub.agents.base import BaseAgent
from gnom_hub.agents.roles_ext import (  # noqa: F401
    CoordinatorAgent,
    MemoryAgent,
    WorkerAgent,
)
from gnom_hub.agents.roles_helpers import (  # noqa: F401
    _brainstorm_user_payload,
    _format_brainstorm_history,
    _is_garbage_fact,
    _lines,
    _needs_clarify,
    _sanitize_memory_ctx,
    _stub_brainstorm,
    _with_memory,
)


class BrainstormAgent(BaseAgent):
    """Free brainstorm partner — dialogue, not a one-shot idea dump."""

    def run(
        self,
        user_text: str,
        memory_ctx: str = "",
        history: list[dict] | None = None,
    ) -> str:
        if not self.enabled:
            return ""
        self.emit_active(True)
        try:
            hist = history or []
            if self.has_llm():
                try:
                    # True multi-turn: prior user/assistant messages, not a flat dump only
                    prior = [
                        {
                            "role": str(t.get("role") or "user"),
                            "content": str(t.get("text") or t.get("content") or ""),
                        }
                        for t in hist[-16:]
                        if isinstance(t, dict)
                        and str(t.get("text") or t.get("content") or "").strip()
                    ]
                    system = (
                        "Du bist der Brainstorm-Partner in Gnom-Hub — knapper Denkpartner, "
                        "KEIN Essay-Bot und KEIN Code-Dumper.\n"
                        "Workers bauen erst nach klarer Bau-Anweisung oder nach ja/ok/mach das.\n"
                        "Antwort-Länge (hart):\n"
                        "- Max. ~100 Wörter ODER 6–8 kurze Zeilen (Box 2 muss scannbar bleiben).\n"
                        "- Max. 4 Aufzählungspunkte. Keine langen Absätze.\n"
                        "Regeln:\n"
                        "- Immer auf Deutsch antworten, wenn der User Deutsch schreibt "
                        "(sonst Sprache des Users). Direkt, ohne Floskeln.\n"
                        "- Vorherigen Dialog nutzen; nicht von null neu starten.\n"
                        "- Auf DIESE Nachricht reagieren: schärfen, wählen, eine Richtung priorisieren.\n"
                        "- Kreative Tasks: 2–4 konkrete Richtungen mit je 1 Satz WARUM — kein fertiger Code.\n"
                        "- Diagnose Gnom-Hub: max. 4 nummerierte Punkte (UI, Keys, Workers, RESULT).\n"
                        "- Bau-Idee ohne harte Order → am Ende GENAU eine kurze Frage: "
                        "„Soll ich das jetzt umsetzen?“\n"
                        "- Harte Bau-Anweisung schon da → keine Frage (Hub startet Workers).\n"
                        "- Keine volle HTML/CSS/JS-Implementierung hier.\n"
                    )
                    # Diagnosis questions need lower temperature / less invention
                    ut_low = (user_text or "").lower()
                    is_diag = any(
                        k in ut_low
                        for k in (
                            "analy",
                            "hakt",
                            "bug",
                            "fehler",
                            "debug",
                            "wo es",
                            "kaputt",
                            "diagnos",
                        )
                    )
                    return self.ask(
                        system=system,
                        user=_with_memory(f"USER MESSAGE:\n{user_text}", memory_ctx),
                        prior=prior if not is_diag else prior[-4:],
                        max_tokens=420 if is_diag else 320,
                        temperature=0.35 if is_diag else 0.75,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": "brainstorm", "error": str(exc)},
                    )
            return _stub_brainstorm(user_text, hist)
        finally:
            self.emit_active(False)


class FlexAgent(BaseAgent):
    """
    Fixed system agent — personal companion + wish memory + pipeline driver.

    Jobs (immutable):
      1) absorb user wishes into WARM (source=flex)
      2) co-talk in brainstorm + request Execute when clear
      3) brief workers on Execute; nudge gaps after workers
    Preset/toggle/UI role edits are ignored (always personal, always on).
    """

    def absorb(self, user_text: str, memory_ctx: str = "") -> list[str]:
        """Extract personal facts from a user line; emit for WARM storage."""
        if not self.enabled:
            return []
        text = (user_text or "").strip()
        if len(text) < 4:
            return []
        self.emit_active(True)
        try:
            facts = self._extract_personal_facts(text, memory_ctx)
            if facts:
                self.bus.emit(
                    "pipeline.flex_facts",
                    {"facts": facts[:5], "user_text": text[:200]},
                )
            return facts
        finally:
            self.emit_active(False)

    def maybe_request_execute(
        self,
        user_text: str,
        turns: list[dict] | None = None,
        memory_ctx: str = "",
    ) -> dict | None:
        """
        Decide whether Flex should trigger Execute for the user.

        Returns {"execute": True, "reason": str, "message": str} or None.
        Never auto-fires on pure chat/diagnosis — only clear task + intent.
        """
        if not self.enabled:
            return None
        text = (user_text or "").strip()
        if not text:
            return None

        # Import shared heuristic (context / ja after offer / hard build order)
        from gnom_hub.pipeline.orchestrator import _wants_auto_execute

        low = text.lower().strip(" !.。")
        reason = ""
        # Explicit execute command (Flex presses the button for the user)
        execute_cmds = {
            "execute",
            "ausführen",
            "ausfuehren",
            "run it",
            "run execute",
            "flex execute",
            "jetzt ausführen",
            "jetzt ausfuehren",
            "pipeline starten",
            "starte execute",
            "start execute",
        }
        if low in execute_cmds or low.startswith(
            ("execute ", "ausführen ", "ausfuehren ", "run it")
        ):
            reason = "explicit_execute"

        if not reason and _wants_auto_execute(text, turns):
            reason = "context_intent"

        # Standing wish: always execute on clear build orders
        if not reason and memory_ctx:
            mlow = memory_ctx.lower()
            wish_auto = any(
                k in mlow
                for k in (
                    "always execute",
                    "immer execute",
                    "immer ausführen",
                    "auto-execute",
                    "auto execute",
                    "automatisch ausführen",
                )
            )
            if wish_auto and _wants_auto_execute(text, turns):
                reason = "standing_wish"

        if not reason:
            return None

        # Need something to execute (prior brainstorm or this turn is a task)
        turns = turns or []
        has_task = bool(text) and (
            len(text) >= 12
            or any(str(x.get("text") or "").strip() for x in turns if x.get("role") == "user")
        )
        if not has_task:
            return None

        # Pure execute word alone still OK if history has a real task
        if reason == "explicit_execute":
            users = [
                str(x.get("text") or "").strip()
                for x in turns
                if x.get("role") == "user" and str(x.get("text") or "").strip()
            ]
            # If only "execute" and no prior user task → refuse
            substantive = [u for u in users if u.lower().strip(" !.。") not in execute_cmds]
            if not substantive and low in execute_cmds:
                return None

        msg = {
            "explicit_execute": "Flex: Execute — Auftrag wird ausgeführt.",
            "context_intent": "Flex: klarer Bau-Auftrag — starte Execute.",
            "standing_wish": "Flex: stehender Wunsch Auto-Execute — starte Execute.",
        }.get(reason, "Flex: Execute.")

        decision = {"execute": True, "reason": reason, "message": msg}
        self.bus.emit(
            "pipeline.flex_execute",
            {"reason": reason, "message": msg, "user_text": text[:200]},
        )
        return decision

    def brainstorm_contribute(
        self,
        user_text: str,
        brainstorm_reply: str = "",
        memory_ctx: str = "",
        *,
        absorbed: list[str] | None = None,
    ) -> str | None:
        """
        Short chat line each brainstorm turn — Flex as user proxy.

        Not a full essay (that is Flex.run on Execute). One to three short lines:
        what was remembered, standing wishes to keep, gentle steer toward next step.
        """
        if not self.enabled:
            return None
        text = (user_text or "").strip()
        if not text:
            return None
        low = text.lower().strip(" !.。")
        # Bare execute tokens: maybe_request_execute speaks instead
        if low in {
            "execute",
            "ausführen",
            "ausfuehren",
            "run it",
            "run execute",
            "flex execute",
            "jetzt ausführen",
            "jetzt ausfuehren",
            "pipeline starten",
            "starte execute",
            "start execute",
        }:
            return None

        parts: list[str] = []
        facts = list(absorbed or [])
        if facts:
            show = facts[:2]
            parts.append("gemerkt: " + "; ".join(s.replace("User: ", "", 1) for s in show))

        # Standing wishes from memory (User: lines)
        wishes: list[str] = []
        for ln in (memory_ctx or "").splitlines():
            s = ln.strip().lstrip("-•* ")
            if s.lower().startswith("user:") or s.lower().startswith("wish:"):
                wishes.append(s)
            if len(wishes) >= 2:
                break
        if wishes and not facts:
            w = wishes[0].replace("User: ", "").replace("Wish: ", "")[:120]
            parts.append("bleibend: " + w)

        br = (brainstorm_reply or "").lower()
        # Brainstorm offered to implement → Flex steers toward Execute
        if any(
            k in br
            for k in (
                "soll ich",
                "umsetzen",
                "plan erstellen",
                "shall i",
                "ready to",
            )
        ):
            parts.append("wenn der Auftrag klar ist: Execute sagen / Button drücken.")

        # User is pure diagnosis → Flex stays quiet-ish
        diagnose = (
            "warum",
            "wo hakt",
            "was ist mit",
            "erklär",
            "analys",
            "only brainstorm",
            "nur brainstorm",
            "nur ideen",
        )
        if any(d in low for d in diagnose) and not parts:
            parts.append("Brainstorm zuerst — Execute erst bei klarem Auftrag.")

        if not parts:
            # Minimal presence so Flex is visible as co-pilot
            if len(text) >= 12:
                parts.append("dabei — speichere Wünsche und halte die Linie.")
            else:
                return None

        msg = "Flex: " + " · ".join(parts)
        if len(msg) > 280:
            msg = msg[:279] + "…"
        self.bus.emit(
            "pipeline.flex_chat",
            {"message": msg, "user_text": text[:200]},
        )
        return msg

    def nudge_gaps(
        self,
        user_text: str,
        requirements: list[str],
        outputs: list[dict],
        quality_notes: str = "",
        memory_ctx: str = "",
    ) -> list[dict]:
        """
        Before the user has to repeat themselves: find unfulfilled bits and
        tell the responsible agent (worker/coordinator) what to fix.

        Returns list of {agent, message, reason}.
        """
        if not self.enabled:
            return []
        self.emit_active(True)
        try:
            nudges = self._heuristic_nudges(user_text, requirements, outputs, quality_notes)
            if self.has_llm() and (quality_notes or outputs):
                try:
                    pack = (
                        f"User task:\n{user_text}\n\n"
                        f"Requirements:\n"
                        + "\n".join(f"- {r}" for r in (requirements or [])[:8])
                        + f"\n\nQuality notes:\n{(quality_notes or '')[:800]}\n\n"
                        "Worker results (head):\n"
                        + "\n---\n".join(
                            f"{o.get('worker')}: {str(o.get('result') or '')[:280]}"
                            for o in (outputs or [])[:3]
                        )
                        + f"\n\nUser context:\n{(memory_ctx or '')[:400]}"
                    )
                    raw = self.ask(
                        system=(
                            "You are Flex protecting the user from having to nag agents.\n"
                            "If something the user asked for is MISSING or WRONG in worker output, "
                            "emit 1–4 correction lines:\n"
                            "  agent_id | short mandatory fix for that agent\n"
                            "agent_id is one of: worker1 worker2 worker3 worker4 coordinator brainstorm\n"
                            "If everything is fine: (none)\n"
                            "No fluff. Match user language."
                        ),
                        user=pack,
                        max_tokens=280,
                        temperature=0.15,
                    )
                    for ln in (raw or "").splitlines():
                        if "|" not in ln:
                            continue
                        left, right = ln.split("|", 1)
                        aid = left.strip().lower().replace(" ", "")
                        msg = right.strip()
                        if (
                            aid
                            in (
                                "worker1",
                                "worker2",
                                "worker3",
                                "worker4",
                                "coordinator",
                                "brainstorm",
                            )
                            and len(msg) >= 8
                        ):
                            nudges.append(
                                {
                                    "agent": aid,
                                    "message": msg[:400],
                                    "reason": "flex_gap",
                                }
                            )
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": "flex_nudge", "error": str(exc)},
                    )
            # de-dupe by agent keep last
            by: dict[str, dict] = {}
            for n in nudges:
                by[str(n.get("agent"))] = n
            out = list(by.values())[:4]
            if out:
                self.bus.emit("pipeline.agent_nudges", {"nudges": out})
            return out
        finally:
            self.emit_active(False)

    def _heuristic_nudges(
        self,
        user_text: str,
        requirements: list[str],
        outputs: list[dict],
        quality_notes: str,
    ) -> list[dict]:
        nudges: list[dict] = []
        qlow = (quality_notes or "").lower()
        for o in outputs or []:
            wid = str(o.get("worker") or "worker1")
            body = str(o.get("result") or "")
            gate = o.get("validation") if isinstance(o.get("validation"), dict) else {}
            issues = list(gate.get("issues") or [])
            msgs: list[str] = []
            if "worker_error" in issues or ("FEHLER" in body and "Deliverable" in body):
                msgs.append(
                    "Kein Deliverable (LLM/Key). Echten DEEPSEEK_API_KEY setzen; "
                    "kein Platzhalter sk-your-…. Danach Execute erneut."
                )
            if "stub" in issues or "Stub —" in body:
                msgs.append(
                    "Kein Stub-Output: echten Worker-Lauf mit LLM liefern, User-Auftrag voll erfuellen."
                )
            if "incomplete_html" in issues or "html incomplete" in qlow:
                msgs.append("Pflicht: komplette HTML-Datei bis </html>, nichts abschneiden.")
            if "missing_required_interaction" in issues or "no_interaction" in issues:
                msgs.append(
                    "Pflicht: mindestens eine echte Interaktion (onclick oder addEventListener)."
                )
            if "too short" in issues or "too_short" in issues or len(body) < 200:
                msgs.append(
                    "Output zu dünn — erfülle die User-Anforderungen vollständig, nicht als Skizze."
                )
            if "weak task match" in issues or "weak task match" in qlow:
                msgs.append(f"Am User-Auftrag bleiben: {(user_text or '')[:120]}")
            if not gate.get("ok", True) and not msgs:
                msgs.append(
                    "Quality-Gate fail: "
                    + ", ".join(issues[:4] or ["unspecified"])
                    + " — jetzt korrigieren, User soll das nicht wiederholen müssen."
                )
            if msgs:
                nudges.append(
                    {
                        "agent": wid,
                        "message": " ".join(msgs)[:400],
                        "reason": "quality_gap",
                    }
                )
        # Standing user rules often in requirements / warm context lines
        for r in requirements or []:
            rl = str(r).lower()
            looks_standing = any(
                k in rl
                for k in (
                    "immer",
                    "always",
                    "vor dem push",
                    "before push",
                    "agents.md",
                    "nicht vergessen",
                )
            )
            if not looks_standing or not outputs:
                continue
            if "agents.md" not in rl and "push" not in rl:
                continue
            # Remind if quality notes don't show compliance
            ok_hint = "push" in qlow or "agents.md" in qlow or "ruff" in qlow
            if ok_hint:
                continue
            nudges.append(
                {
                    "agent": str(outputs[0].get("worker") or "worker1"),
                    "message": (
                        "User-Regel beachten: "
                        + str(r)[:200]
                        + " — erledigen BEVOR der User es nochmal sagen muss."
                    ),
                    "reason": "standing_rule",
                }
            )
        return nudges

    def binding_wishes(self, memory_ctx: str = "", *, limit: int = 12) -> list[str]:
        """Standing User:/Wish: lines from memory — for requirement injection."""
        from gnom_hub.memory.dedupe import core_key, prefer_canonical_wish

        out: list[str] = []
        seen: set[str] = set()
        for ln in (memory_ctx or "").splitlines():
            s = " ".join(str(ln).split()).strip().lstrip("-•* ")
            if not s:
                continue
            low = s.lower()
            if not low.startswith(("user:", "wish:", "flex-wish:")):
                continue
            canon = prefer_canonical_wish(s)
            if not canon:
                continue
            key = core_key(canon)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(canon[:200])
            if len(out) >= limit:
                break
        return out

    def run(self, user_text: str, requirements: list[str], memory_ctx: str = "") -> str:
        if not self.enabled:
            return ""
        self.state.preset = "personal"
        self.emit_active(True)
        try:
            # Always learn from this turn first
            self._extract_and_emit(user_text, memory_ctx)

            system = (
                "You are Flex — FIXED personal companion in Gnom-Hub (not a free preset).\n"
                "You ONLY represent the human operator: preferences, people, tools, habits, "
                "standing rules. Never invent facts the user did not state.\n"
                "STANDING WISHES are absolute orders for workers — never call a wish\n"
                "optional; always demand full compliance on Execute.\n"
                "Output in the user's language (DE/EN).\n"
                "Structure:\n"
                "1) Was ich über dich weiß (relevant jetzt) — short bullets from context\n"
                "2) Neu gemerkt — 0–3 new personal facts from THIS message\n"
                "3) Für die Worker — 1–3 practical hints so workers respect the user\n"
                "4) Binding wishes — restate any User:/Wish: lines that workers must obey\n"
            )
            wishes = self.binding_wishes(memory_ctx)
            wish_block = "\n".join(f"- {w}" for w in wishes) if wishes else "(none in context)"
            body = (
                f"User now says:\n{user_text}\n\n"
                f"Requirements:\n"
                + "\n".join(f"- {r}" for r in requirements[:6])
                + f"\n\nBinding wishes from memory:\n{wish_block}"
                + f"\n\nKnown context (WARM/HOT):\n{(memory_ctx or '')[:900]}"
            )
            if self.has_llm():
                try:
                    return self.ask(
                        system=system,
                        user=body,
                        max_tokens=450,
                        temperature=0.35,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": "flex", "error": str(exc)},
                    )
            # Stub without LLM: echo facts + binding wishes for workers
            facts = self._heuristic_facts(user_text)
            if facts:
                self.bus.emit("pipeline.flex_facts", {"facts": facts, "user_text": user_text[:200]})
            know_bits = facts or wishes
            know = (
                "\n".join(f"• {f}" for f in know_bits)
                if know_bits
                else "• (noch wenig — schreib weiter)"
            )
            worker_hint = (
                "Für die Worker: " + "; ".join(wishes[:3])
                if wishes
                else "Für die Worker: User-Kontext in WARM beachten."
            )
            return "Was ich über dich weiß:\n" + know + "\nNeu gemerkt: siehe oben.\n" + worker_hint
        finally:
            self.emit_active(False)

    def _extract_and_emit(self, user_text: str, memory_ctx: str) -> list[str]:
        facts = self._extract_personal_facts(user_text, memory_ctx)
        if facts:
            self.bus.emit(
                "pipeline.flex_facts",
                {"facts": facts[:5], "user_text": (user_text or "")[:200]},
            )
        return facts

    def _extract_personal_facts(self, user_text: str, memory_ctx: str = "") -> list[str]:
        text = (user_text or "").strip()
        if not text:
            return []
        if self.has_llm():
            try:
                raw = self.ask(
                    system=(
                        "Extract 0–5 DURABLE personal facts about the USER only.\n"
                        "Examples: preferred language, names of people/bots they talk to "
                        "(e.g. Eve), sites they visit (e.g. grok.com), tools, habits, "
                        "standing instructions (always browse X, chat as Y).\n"
                        "One fact per line. Prefix each with 'User: '.\n"
                        "No HTML, no code, no task requirements lists.\n"
                        "If nothing personal: (none)"
                    ),
                    user=f"Message:\n{text}\n\nPrior context:\n{(memory_ctx or '')[:500]}",
                    max_tokens=220,
                    temperature=0.15,
                )
                facts: list[str] = []
                for ln in (raw or "").splitlines():
                    s = ln.strip().lstrip("-•* ")
                    if not s or s.lower() in ("(none)", "none", "n/a"):
                        continue
                    if not s.lower().startswith("user:"):
                        s = "User: " + s
                    if 12 <= len(s) <= 200 and not _is_garbage_fact(s):
                        facts.append(s[:200])
                return facts[:5]
            except Exception as exc:  # noqa: BLE001
                self.bus.emit(
                    "pipeline.warning",
                    {"stage": "flex_absorb", "error": str(exc)},
                )
        return self._heuristic_facts(text)

    def _heuristic_facts(self, text: str) -> list[str]:
        """No-LLM fallback: catch obvious personal instructions."""
        import re

        t = " ".join(text.split()).strip()
        if len(t) < 8:
            return []
        low = t.lower()
        facts: list[str] = []
        # browse / visit site
        m = re.search(
            r"\b(?:browse|besuche|öffne|open|geh(?:e)?\s+zu)\s+(?:zu\s+)?([a-z0-9.-]+\.[a-z]{2,}\S*)",
            low,
            re.IGNORECASE,
        )
        if m:
            facts.append(f"User: wants to browse/open {m.group(1)}")
        # chat with name
        m2 = re.search(
            r"\b(?:chat(?:te)?|sprich|rede)\s+(?:mit|with)\s+(\w+)",
            t,
            re.IGNORECASE,
        )
        if m2:
            facts.append(f"User: chats with {m2.group(1)}")
        # name is eve / called
        m3 = re.search(r"\b(?:mit|with|namens?|called)\s+([A-ZÄÖÜ][a-zäöüß]{1,20})\b", t)
        if m3 and m3.group(1).lower() not in ("user", "html", "css", "http"):
            facts.append(f"User: refers to person/bot {m3.group(1)}")
        if (
            not facts
            and len(t) >= 20
            and any(k in low for k in ("immer", "always", "merke", "remember", "präfer", "prefer"))
        ):
            facts.append("User: " + t[:160])
        return [f for f in facts if not _is_garbage_fact(f)][:5]
