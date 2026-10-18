"""Setup explains blocked capabilities; a configured key is not readiness."""

from __future__ import annotations

import builtins
from types import SimpleNamespace

import pytest

from gnom_hub.system_ops import SystemOpsMixin


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("profile", ["standalone", "controlled"])
def test_setup_explains_actual_profile_and_forced_missing_gate(monkeypatch, lang, profile):
    from gnom_hub import stack
    from gnom_hub.config import user_workspace

    monkeypatch.setattr(
        user_workspace,
        "inspect_user_workspace",
        lambda _root: SimpleNamespace(key_has_deepseek=True, personal_ws="synthetic-workspace"),
    )
    monkeypatch.setattr(stack, "via_tollgate", lambda: True)
    real_import = builtins.__import__

    def missing_gate(name, *args, **kwargs):
        if name == "tollgate":
            raise ImportError("synthetic missing package")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_gate)
    hub = SimpleNamespace(ui_lang=lang, llm=SimpleNamespace(execution_profile=profile))
    setup = SystemOpsMixin._setup_dict(hub)
    assert setup["key_ok"] is True
    assert setup["tollgate_ok"] is False
    assert ("blocked" if lang == "en" else "gesperrt") in setup["tollgate_note"]
    assert "direkt" not in setup["tollgate_note"]
    if profile == "controlled":
        assert ("protected access" if lang == "en" else "Zugangsanbindung") in setup[
            "controlled_execution_note"
        ]
    else:
        assert setup["controlled_execution_note"] == ""
