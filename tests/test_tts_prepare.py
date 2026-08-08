"""TTS prepare: English thoughts → German before speech."""

from __future__ import annotations

from gnom_hub.llm.types import LLMResult
from gnom_hub.tts_ops import looks_mostly_german


class _FakeLLM:
    def has_provider(self, name: str) -> bool:
        return True

    def chat(self, messages, **kwargs):
        return LLMResult(
            content="Kurzer deutscher Gedanke zur Anfrage des Users.",
            model="fake",
            prompt_tokens=10,
            completion_tokens=10,
        )


class _HubStub:
    ui_lang = "de"
    llm = _FakeLLM()

    # mix in method
    from gnom_hub.tts_ops import TtsOpsMixin

    prepare_tts_text = TtsOpsMixin.prepare_tts_text
    _llm_translate_to_german = TtsOpsMixin._llm_translate_to_german


def test_looks_mostly_german():
    assert looks_mostly_german("Ich priorisiere die Anfrage und bleibe knapp.")
    assert not looks_mostly_german(
        "I should build a landing page for the user with three features."
    )


def test_prepare_tts_translates_english():
    hub = _HubStub()
    out = hub.prepare_tts_text(
        "I will prioritize a simple landing page with a hero and CTA.",
        lang="de",
    )
    assert out["translated"] is True
    assert out["lang"] == "de"
    assert (
        "deutsch" in out["text"].lower()
        or "deutscher" in out["text"].lower()
        or "anfrage" in out["text"].lower()
    )


def test_prepare_tts_keeps_german():
    hub = _HubStub()
    out = hub.prepare_tts_text(
        "Ich baue eine kurze Landingpage mit Hero und Footer.",
        lang="de",
    )
    assert out["translated"] is False
    assert "Landingpage" in out["text"] or "Hero" in out["text"]
