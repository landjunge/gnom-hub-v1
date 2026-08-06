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
                        "You are the Brainstorm partner in Gnom-Hub.\n"
                        "Your job is FREE brainstorming with the user — a real dialogue, "
                        "not a one-shot idea dump and not execution.\n"
                        "Rules:\n"
                        "- Match the user language (DE/EN).\n"
                        "- Use the full prior dialogue; never restart from zero if history exists.\n"
                        "- React to THIS message; build on earlier ideas.\n"
                        "- For creative tasks: 3–6 concrete ideas/angles — not a finished plan.\n"
                        "- For diagnosis/analysis of Gnom-Hub or 'wo hakt es': give a DIRECT "
                        "numbered list of real failure modes (UI freeze, keys, Execute, workers, "
                        "thinking/empty output, job lock/cancel, prompt override). "
                        "Do NOT invent unrelated apps (todo/kanban/CSS drafts). "
                        "Do NOT only ask the user where they think it breaks — state findings.\n"
                        "- Ask at most ONE short follow-up if something is unclear.\n"
                        "- Do NOT start implementing full code or running the pipeline.\n"
                        "- No corporate fluff. Be direct and useful.\n"
                        "- If the user only refines (e.g. 'more on X'), go deeper on that."
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
                        max_tokens=900 if is_diag else 700,
                        temperature=0.35 if is_diag else 0.9,
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
    Personal companion for the human operator.

    Remembers what the user writes (preferences, people, sites, habits) into
    durable memory, and briefs the pipeline with “what I know about you”.
    Optional presets only add a light lens (security/research/neutral).
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

    def run(self, user_text: str, requirements: list[str], memory_ctx: str = "") -> str:
        if not self.enabled:
            return ""
        preset = (self.state.preset or "personal").lower()
        self.emit_active(True)
        try:
            # Always learn from this turn first
            self._extract_and_emit(user_text, memory_ctx)

            system = (
                "You are Flex — the user's personal companion inside Gnom-Hub.\n"
                "You ONLY care about the human operator: their preferences, people they "
                "mention, sites/tools they use, habits, language, constraints.\n"
                "Output in the user's language (DE/EN).\n"
                "Structure:\n"
                "1) Was ich über dich weiß (relevant jetzt) — short bullets from context\n"
                "2) Neu gemerkt — 0–3 new personal facts from THIS message\n"
                "3) Für die Worker — 1–3 practical hints so workers respect the user\n"
                "Do NOT write generic security essays unless preset is security.\n"
                "Do NOT invent people/sites the user never mentioned.\n"
            )
            if preset == "security":
                system += "Extra lens: flag personal-data / privacy risks in one short line.\n"
            elif preset == "researcher":
                system += "Extra lens: one open question about the user's intent.\n"
            elif preset == "neutral":
                system += "Extra lens: one trade-off for the user.\n"

            body = (
                f"User now says:\n{user_text}\n\n"
                f"Requirements:\n"
                + "\n".join(f"- {r}" for r in requirements[:6])
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
            # Stub without LLM: echo what we can store
            facts = self._heuristic_facts(user_text)
            if facts:
                self.bus.emit("pipeline.flex_facts", {"facts": facts, "user_text": user_text[:200]})
            return (
                "Was ich über dich weiß:\n"
                + (
                    "\n".join(f"• {f}" for f in facts)
                    if facts
                    else "• (noch wenig — schreib weiter)"
                )
                + "\nNeu gemerkt: siehe oben.\n"
                "Für die Worker: User-Kontext in WARM beachten."
            )
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
