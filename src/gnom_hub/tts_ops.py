"""TTS helpers: translate agent thoughts to German before speech."""

from __future__ import annotations

import hashlib
import re
from typing import Any

_DE_MARKERS = re.compile(
    r"[äöüÄÖÜß]|\b(der|die|das|und|ich|nicht|eine|für|mit|soll|wird|auch|noch|nur|wenn|dann)\b",
    re.IGNORECASE,
)
_EN_MARKERS = re.compile(
    r"\b(the|and|with|for|this|that|should|would|could|build|page|user|about|from|have|will)\b",
    re.IGNORECASE,
)


def looks_mostly_german(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if _DE_MARKERS.search(t):
        return True
    en = len(_EN_MARKERS.findall(t))
    # Mostly English function words → not German
    if en >= 3:
        return False
    return en == 0


class TtsOpsMixin:
    """Mixin: expects Hub.llm, ui_lang, optional cache."""

    def prepare_tts_text(self, text: str, *, lang: str = "de") -> dict[str, Any]:
        """
        Prepare text for speech: if lang=de and text is English, translate first.

        Returns {text, translated, lang, source_chars}.
        """
        raw = " ".join(str(text or "").split()).strip()
        if not raw:
            return {"text": "", "translated": False, "lang": lang, "source_chars": 0}

        target = (lang or self.ui_lang or "de").strip().lower()
        if target not in ("de", "en"):
            target = "de"

        # English UI: pass through
        if target == "en":
            return {
                "text": raw[:1200],
                "translated": False,
                "lang": "en",
                "source_chars": len(raw),
            }

        # Already German enough
        if looks_mostly_german(raw):
            return {
                "text": raw[:1200],
                "translated": False,
                "lang": "de",
                "source_chars": len(raw),
            }

        # Cache by hash
        if not hasattr(self, "_tts_translate_cache"):
            self._tts_translate_cache: dict[str, str] = {}
        key = hashlib.sha256(raw[:800].encode("utf-8")).hexdigest()[:24]
        cached = self._tts_translate_cache.get(key)
        if cached:
            return {
                "text": cached,
                "translated": True,
                "lang": "de",
                "source_chars": len(raw),
                "cached": True,
            }

        de = self._llm_translate_to_german(raw)
        if de and de.strip():
            out = de.strip()[:1200]
            self._tts_translate_cache[key] = out
            # ring cache
            if len(self._tts_translate_cache) > 80:
                for k in list(self._tts_translate_cache.keys())[:20]:
                    self._tts_translate_cache.pop(k, None)
            return {
                "text": out,
                "translated": True,
                "lang": "de",
                "source_chars": len(raw),
            }

        # Fallback: short German shell so TTS is never English monologue
        fallback = (
            "Kurzer Gedanke auf Deutsch: ich priorisiere die Anfrage des Users "
            "und bleibe knapp. Details stehen in Box 2 und Box 3."
        )
        return {
            "text": fallback,
            "translated": True,
            "lang": "de",
            "source_chars": len(raw),
            "fallback": True,
        }

    def _llm_translate_to_german(self, text: str) -> str:
        """Best-effort LLM translation for TTS only (not box content)."""
        llm = getattr(self, "llm", None)
        if llm is None or not getattr(llm, "has_provider", lambda *_: False)("any"):
            # try deepseek/ollama flags
            has = getattr(llm, "has_provider", None)
            if not callable(has):
                return ""
            if not (has("deepseek") or has("ollama")):
                return ""
        try:
            from gnom_hub.llm.types import LLMMessage

            result = llm.chat(
                [
                    LLMMessage(
                        role="system",
                        content=(
                            "Du übersetzt Agenten-Gedanken für Sprachausgabe (TTS).\n"
                            "Regeln:\n"
                            "- Nur flüssiges Deutsch ausgeben.\n"
                            "- Keine Einleitung, keine Anführungszeichen, keine Meta-Kommentare.\n"
                            "- Kurz und gesprochen (max. ~60 Wörter).\n"
                            "- Inhalt sinngemäß behalten."
                        ),
                    ),
                    LLMMessage(role="user", content=text[:1400]),
                ],
                max_tokens=220,
                temperature=0.15,
                thinking=False,
                agent="tts_translate",
            )
            return (getattr(result, "content", None) or "").strip()
        except Exception:  # noqa: BLE001
            return ""
