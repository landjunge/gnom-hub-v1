"""Chat → Brainstorm → Distill → Flex → Coordinator → Worker(s) pipeline."""

from __future__ import annotations

from typing import Any

from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline.models import DistillQuestion, PipelineStage, PipelineState

_FLEX_PROMPTS = {
    "security": (
        "You are a security reviewer for a multi-agent product plan. "
        "List 3–5 concrete risks (auth, data leak, abuse, secrets, paths). "
        "Each risk: one line. German or English matching the user language."
    ),
    "researcher": (
        "You are a researcher. List 3–5 missing facts or open questions. "
        "One line each. Match user language."
    ),
    "neutral": (
        "You are a neutral reviewer. List 3–5 trade-offs or decisions. "
        "One line each. Match user language."
    ),
}


class Pipeline:
    """
    Synchronous pipeline driven by EventBus.

    Without a live LLM key, stages use useful deterministic stubs.
    Disabled agents are skipped (Memory always on via memory_hint).
    """

    def __init__(
        self,
        bus: EventBus,
        llm_manager: Any | None = None,
        agent_manager: Any | None = None,
        memory: Any | None = None,
    ) -> None:
        self._bus = bus
        self._llm = llm_manager
        self._agents = agent_manager
        self._memory = memory
        self._state = PipelineState()
        self._clarified_once = False
        self._tasks: list[tuple[str, str]] = []

    @property
    def state(self) -> PipelineState:
        return self._state

    def start(self, user_text: str) -> PipelineState:
        mem_ctx = self._load_memory_context()
        self._state = PipelineState(user_text=user_text.strip(), memory_context=mem_ctx)
        self._clarified_once = False
        self._tasks = []
        if mem_ctx:
            self._bus.emit("pipeline.memory_context", {"context": mem_ctx})
        try:
            self._run_from_brainstorm()
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state

    def _load_memory_context(self) -> str:
        if self._memory is None:
            return ""
        fn = getattr(self._memory, "pipeline_context", None)
        if callable(fn):
            try:
                return str(fn() or "").strip()
            except Exception:  # noqa: BLE001
                return ""
        return ""

    def answer_clarify(self, option: str) -> PipelineState:
        if self._state.stage != PipelineStage.clarify or self._state.pending_question is None:
            raise ValueError("No pending clarification question")

        answer = option.strip()
        q = self._state.pending_question
        self._state.distilled_requirements.append(f"User clarified ({q.id}): {answer}")
        self._state.pending_question = None
        self._clarified_once = True

        try:
            self._run_flex_then_work()
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state

    # ── stages ───────────────────────────────────────────────────────

    def _run_from_brainstorm(self) -> None:
        text = self._state.user_text
        if not text:
            self._fail("Empty user text")
            return

        if self._agent_enabled("brainstorm"):
            self._set_stage(PipelineStage.brainstorm)
            notes = self._safe_stage(
                "brainstorm",
                lambda: self._llm_brainstorm(text),
                lambda: self._stub_brainstorm(text),
            )
            self._state.brainstorm_notes = notes
            self._bus.emit("pipeline.brainstorm", {"notes": notes})

        self._set_stage(PipelineStage.distill)
        requirements, question = self._safe_stage(
            "distill",
            lambda: self._llm_distill(text),
            lambda: self._stub_distill(text),
        )
        self._state.distilled_requirements = requirements
        self._bus.emit("pipeline.distill", {"requirements": list(requirements)})

        if question is not None and not self._clarified_once:
            self._state.pending_question = question
            self._set_stage(PipelineStage.clarify)
            self._bus.emit(
                "pipeline.question",
                {
                    "id": question.id,
                    "text": question.text,
                    "options": list(question.options),
                },
            )
            return

        self._run_flex_then_work()

    def _run_flex_then_work(self) -> None:
        if self._agent_enabled("flex"):
            self._set_stage(PipelineStage.flex)
            notes = self._safe_stage("flex", self._llm_flex, self._stub_flex)
            self._state.flex_notes = notes
            self._bus.emit(
                "pipeline.flex",
                {"notes": notes, "preset": self._flex_preset()},
            )
            # One short constraint line only — never dump whole flex essay into reqs
            if notes:
                first = notes.strip().splitlines()[0][:160]
                self._state.distilled_requirements.append(f"Flex/{self._flex_preset()}: {first}")

        self._run_coordinate_and_work()

    def _run_coordinate_and_work(self) -> None:
        if not self._agent_enabled("coordinator"):
            self._bus.emit(
                "pipeline.coordinate",
                {"tasks": [], "skipped": True, "reason": "coordinator disabled"},
            )
            self._state.worker_results = []
            self._finish_with_memory([])
            return

        self._set_stage(PipelineStage.coordinate)
        tasks = self._safe_stage(
            "coordinate",
            self._llm_coordinate,
            self._stub_coordinate,
        )
        # ensure list of tuples
        if not isinstance(tasks, list):
            tasks = self._stub_coordinate()
        self._tasks = tasks
        self._bus.emit(
            "pipeline.coordinate",
            {"tasks": [{"worker": w, "task": t} for w, t in tasks]},
        )

        self._set_stage(PipelineStage.work)
        results: list[str] = []
        for i, (worker_id, task) in enumerate(tasks, start=1):
            result = self._safe_stage(
                worker_id,
                lambda w=worker_id, tt=task: self._llm_worker(w, tt),
                lambda n=i, tt=task: self._stub_worker(n, tt),
            )
            results.append(result)
            self._bus.emit(
                "pipeline.worker",
                {"worker": worker_id, "index": i, "result": result, "task": task},
            )
        self._state.worker_results = results
        self._finish_with_memory(results)

    def _finish_with_memory(self, results: list[str]) -> None:
        # Only promote clean short requirements (not flex dumps)
        clean_reqs = [
            r
            for r in self._state.distilled_requirements
            if not r.startswith("Flex/") and len(r) < 200
        ]
        self._bus.emit(
            "pipeline.memory_hint",
            {
                "user_text": self._state.user_text,
                "requirements": clean_reqs[:6],
                "results": list(results),
                "brainstorm_notes": self._state.brainstorm_notes,
                "flex_notes": self._state.flex_notes,
            },
        )
        self._set_stage(PipelineStage.done)
        self._bus.emit(
            "pipeline.done",
            {
                "requirements": list(self._state.distilled_requirements),
                "results": list(results),
                "flex_notes": self._state.flex_notes,
            },
        )

    # ── stubs (useful demo output) ───────────────────────────────────

    def _stub_brainstorm(self, text: str) -> str:
        return (
            f"Ideen zu: {text}\n"
            f"• Ziel klar formulieren und Nutzerwert in 1 Satz\n"
            f"• 3 Kernfunktionen priorisieren (MVP)\n"
            f"• UI: 1 Hauptscene + klare nächste Aktion\n"
            f"• Daten: lokal speichern, keine unnötigen Secrets\n"
            f"• Risiken: Scope-Creep, leere States, Fehlerfälle"
        )

    def _stub_distill(self, text: str) -> tuple[list[str], DistillQuestion | None]:
        requirements = [
            f"Ziel: {text}",
            "MVP mit 3 Kernfunktionen liefern",
            "Einfache Desktop-UI, lesbare Ausgaben",
            "Fehler- und Leerzustände anzeigen",
        ]
        question: DistillQuestion | None = None
        notes = getattr(self._state, "brainstorm_notes", "") or ""
        if self._needs_clarify(text, notes) and not self._clarified_once:
            question = DistillQuestion(
                id="q1",
                text="Soll das eher schnell/MVP oder gründlich/robust werden?",
                options=["MVP/schnell", "Gründlich/robust", "Egal", "Später"],
            )
        return requirements, question

    def _stub_flex(self) -> str:
        preset = self._flex_preset()
        if preset == "security":
            return (
                "• Keine Secrets im Frontend speichern\n"
                "• Eingaben validieren (Länge, Pfade)\n"
                "• Schreibzugriffe auf data/ begrenzen"
            )
        if preset == "researcher":
            return "• Welche Zielgruppe?\n• Welche Datenquellen?\n• Erfolgsmetrik in 1 Satz?"
        return (
            "• Geschwindigkeit vs. Qualität abwägen\n"
            "• Manuell vs. Automatisierung\n"
            "• Lokal vs. Cloud"
        )

    def _stub_coordinate(self) -> list[tuple[str, str]]:
        workers = self._enabled_worker_ids()
        reqs = [r for r in self._state.distilled_requirements if not r.startswith("Flex/")]
        if not workers:
            return []
        goal = self._state.user_text
        plans = [
            f"Erstelle einen konkreten Umsetzungsplan (Schritte) für: {goal}",
            f"Liefere ein knappes Ergebnis-Artefakt (Text/Struktur) für: {goal}",
        ]
        if reqs:
            plans[0] += "\nAnforderungen:\n- " + "\n- ".join(reqs[:4])
            plans[1] += "\nFokus: " + reqs[min(1, len(reqs) - 1)]
        tasks: list[tuple[str, str]] = []
        for i, wid in enumerate(workers[:2]):
            tasks.append((wid, plans[i] if i < len(plans) else plans[0]))
        return tasks

    @staticmethod
    def _stub_worker(n: int, task: str) -> str:
        return (
            f"Worker {n} Ergebnis\n"
            f"Aufgabe: {task.splitlines()[0][:120]}\n"
            f"• Schritt 1: Anforderungen lesen\n"
            f"• Schritt 2: MVP skizzieren\n"
            f"• Schritt 3: Nächster sinnvoller Schritt vorschlagen\n"
            f"(Stub-Modus — mit DeepSeek-Key kommt hier echte LLM-Ausgabe.)"
        )

    # ── LLM ──────────────────────────────────────────────────────────

    def _agent_llm_kwargs(self, agent_id: str) -> dict[str, str]:
        out: dict[str, str] = {"agent": agent_id}
        if self._agents is None:
            return out
        try:
            agent = self._agents.get(agent_id)
        except (KeyError, ValueError):
            return out
        model = getattr(agent, "model", None)
        key = getattr(agent, "api_key", None)
        if model:
            out["model"] = str(model)
        if key:
            out["api_key"] = str(key)
        return out

    def _memory_block(self) -> str:
        ctx = self._state.memory_context.strip()
        if not ctx:
            return ""
        # cap noise
        return f"\n\nBekannter Kontext (kurz halten, nicht widersprechen):\n{ctx[:700]}"

    def _llm_brainstorm(self, text: str) -> str:
        from gnom_hub.llm.types import LLMMessage

        result = self._llm.chat(
            [
                LLMMessage(
                    role="system",
                    content=(
                        "Du bist Brainstorm-Partner in Gnom-Hub — Dialog, kein Bullet-Bot. "
                        "Sprache wie der User (DE/EN). Baue auf Kontext auf; "
                        "3–6 konkrete Richtungen mit Warum; kein fertiger Code; "
                        "ohne klare Bau-Order eine kurze Frage: Soll ich umsetzen?"
                    ),
                ),
                LLMMessage(role="user", content=text + self._memory_block()),
            ],
            max_tokens=500,
            temperature=0.8,
            **self._agent_llm_kwargs("brainstorm"),
        )
        return (result.content or "").strip()

    def _llm_distill(self, text: str) -> tuple[list[str], DistillQuestion | None]:
        from gnom_hub.llm.types import LLMMessage

        context = text
        if self._state.brainstorm_notes:
            context = f"{text}\n\nBrainstorm:\n{self._state.brainstorm_notes[:1200]}"
        context += self._memory_block()
        result = self._llm.chat(
            [
                LLMMessage(
                    role="system",
                    content=(
                        "Du destillierst Aufträge in klare Anforderungen. "
                        "Antworte NUR mit 4–7 Anforderungs-Zeilen, je eine Anforderung, "
                        "ohne Nummerierungsideologie, ohne Einleitung. "
                        "Sprache wie der User."
                    ),
                ),
                LLMMessage(role="user", content=context),
            ],
            max_tokens=400,
            temperature=0.3,
            **self._agent_llm_kwargs("coordinator"),
        )
        lines = [
            ln.strip().lstrip("-•*0123456789. \t")
            for ln in (result.content or "").splitlines()
            if ln.strip()
        ]
        requirements = [ln for ln in lines if len(ln) > 3][:8] or [f"Ziel: {text}"]
        question: DistillQuestion | None = None
        notes = getattr(self._state, "brainstorm_notes", "") or ""
        if self._needs_clarify(text, notes) and not self._clarified_once:
            question = DistillQuestion(
                id="q1",
                text="MVP/schnell oder gründlich/robust?",
                options=["MVP/schnell", "Gründlich/robust", "Egal", "Später"],
            )
        return requirements, question

    def _llm_flex(self) -> str:
        from gnom_hub.llm.types import LLMMessage

        preset = self._flex_preset()
        system = _FLEX_PROMPTS.get(preset, _FLEX_PROMPTS["neutral"])
        body = "Auftrag: " + self._state.user_text + "\n\nAnforderungen:\n"
        body += "\n".join(f"- {r}" for r in self._state.distilled_requirements[:6])
        body += self._memory_block()
        result = self._llm.chat(
            [
                LLMMessage(role="system", content=system),
                LLMMessage(role="user", content=body),
            ],
            max_tokens=350,
            temperature=0.4,
            **self._agent_llm_kwargs("flex"),
        )
        return (result.content or "").strip()

    def _llm_coordinate(self) -> list[tuple[str, str]]:
        """Ask LLM for 1–2 concrete worker tasks; fall back to stub parse."""
        from gnom_hub.llm.types import LLMMessage

        workers = self._enabled_worker_ids()
        if not workers:
            return []
        body = (
            f"User: {self._state.user_text}\n"
            f"Requirements:\n"
            + "\n".join(f"- {r}" for r in self._state.distilled_requirements[:6])
            + f"\nWorkers available: {', '.join(workers)}\n"
            "Output EXACTLY one line per worker as: WORKER_ID | task text\n"
            "Example: worker1 | Write a step plan for the MVP"
        )
        result = self._llm.chat(
            [
                LLMMessage(
                    role="system",
                    content=(
                        "You are the Coordinator. Assign clear executable tasks. "
                        "Only lines 'workerN | task'. No other text."
                    ),
                ),
                LLMMessage(role="user", content=body),
            ],
            max_tokens=300,
            temperature=0.3,
            **self._agent_llm_kwargs("coordinator"),
        )
        tasks: list[tuple[str, str]] = []
        for ln in (result.content or "").splitlines():
            if "|" not in ln:
                continue
            left, right = ln.split("|", 1)
            wid = left.strip().lower().replace(" ", "")
            task = right.strip()
            if wid in workers and task:
                tasks.append((wid, task))
        if not tasks:
            return self._stub_coordinate()
        return tasks[:2]

    def _llm_worker(self, worker_id: str, task: str) -> str:
        from gnom_hub.llm.types import LLMMessage

        body = (
            f"Aufgabe: {task}\n"
            f"Original-Auftrag: {self._state.user_text}\n"
            f"Anforderungen:\n"
            + "\n".join(f"- {r}" for r in self._state.distilled_requirements[:5])
            + self._memory_block()
        )
        result = self._llm.chat(
            [
                LLMMessage(
                    role="system",
                    content=(
                        "Du bist ein Worker. Liefere ein konkretes, nützliches Ergebnis "
                        "(Plan, Text, Struktur, Checkliste). "
                        "Keine Meta-Floskeln wie 'als KI'. Sprache wie der User. "
                        "Max. ca. 250 Wörter."
                    ),
                ),
                LLMMessage(role="user", content=body),
            ],
            max_tokens=700,
            temperature=0.5,
            **self._agent_llm_kwargs(worker_id),
        )
        return (result.content or "").strip()

    # ── helpers ──────────────────────────────────────────────────────

    def _safe_stage(self, name: str, llm_fn, stub_fn):
        if self._use_stubs():
            return stub_fn()
        try:
            return llm_fn()
        except Exception as exc:  # noqa: BLE001
            msg = f"{name}: LLM failed ({exc}); used stub"
            self._state.warnings.append(msg)
            self._bus.emit("pipeline.warning", {"stage": name, "error": str(exc)})
            return stub_fn()

    def _flex_preset(self) -> str:
        if self._agents is None:
            return "security"
        try:
            agent = self._agents.get("flex")
            return str(getattr(agent, "preset", None) or "security")
        except (KeyError, ValueError):
            return "security"

    def _use_stubs(self) -> bool:
        if self._llm is None:
            return True
        has = getattr(self._llm, "has_provider", None)
        if callable(has):
            return not bool(has("deepseek"))
        return True

    def _agent_enabled(self, agent_id: str) -> bool:
        if self._agents is None:
            return True
        get = getattr(self._agents, "get", None)
        if callable(get):
            try:
                agent = get(agent_id)
                return bool(getattr(agent, "enabled", True))
            except (KeyError, ValueError):
                return True
        return True

    def _enabled_worker_ids(self) -> list[str]:
        if self._agents is None:
            return ["worker1", "worker2"]
        enabled_workers = getattr(self._agents, "enabled_workers", None)
        if callable(enabled_workers):
            out: list[str] = []
            for w in enabled_workers():
                wid = getattr(w, "id", w)
                out.append(wid.value if hasattr(wid, "value") else str(wid))
            return out
        return [i for i in ("worker1", "worker2") if self._agent_enabled(i)]

    @staticmethod
    def _needs_clarify(text: str, brainstorm: str = "") -> bool:
        from gnom_hub.agents.roles_helpers import _needs_clarify as _nc

        return _nc(text, brainstorm)

    def _set_stage(self, stage: PipelineStage) -> None:
        self._state.stage = stage
        self._bus.emit("pipeline.stage", {"stage": stage.value})

    def _fail(self, message: str) -> None:
        self._state.stage = PipelineStage.error
        self._state.error = message
        self._bus.emit("pipeline.stage", {"stage": PipelineStage.error.value})
        self._bus.emit("pipeline.error", {"error": message})
