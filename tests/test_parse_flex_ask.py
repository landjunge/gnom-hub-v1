"""parse_flex_ask: first FLEX_ASK block, even after preamble or fences."""

from gnom_hub.flex_desk import parse_flex_ask


def test_parse_flex_ask_plain_block():
    parsed = parse_flex_ask("FLEX_ASK yes_no task=hero\nSoll der Kopfbereich kürzer sein?")
    assert parsed is not None
    assert parsed["component"] == "yes_no"
    assert parsed["task_id"] == "hero"
    assert "Kopfbereich" in parsed["text"]


def test_parse_flex_ask_after_short_preamble():
    raw = (
        "Ich brauche eine Entscheidung, bevor ich den Kopfbereich baue.\n"
        "\n"
        "FLEX_ASK yes_no task=hero\n"
        "Soll der Kopfbereich kürzer sein?"
    )
    parsed = parse_flex_ask(raw)
    assert parsed is not None
    assert parsed["component"] == "yes_no"
    assert parsed["task_id"] == "hero"
    assert "Kopfbereich" in parsed["text"]
    assert "Entscheidung" not in parsed["text"]


def test_parse_flex_ask_inside_markdown_fences():
    raw = (
        "Kurze Rückfrage:\n"
        "```\n"
        "FLEX_ASK yes_no task=hero\n"
        "Soll der Kopfbereich kürzer sein?\n"
        "```\n"
        "<!DOCTYPE html><html>draft</html>"
    )
    parsed = parse_flex_ask(raw)
    assert parsed is not None
    assert parsed["component"] == "yes_no"
    assert parsed["task_id"] == "hero"
    assert "Kopfbereich" in parsed["text"]
    assert "DOCTYPE" not in parsed["text"]
    assert "```" not in parsed["text"]


def test_parse_flex_ask_fence_glued_to_token():
    raw = "```text FLEX_ASK yes_no task=nav\nSoll das Menü links bleiben?\n```"
    parsed = parse_flex_ask(raw)
    assert parsed is not None
    assert parsed["component"] == "yes_no"
    assert parsed["task_id"] == "nav"
    assert "Menü" in parsed["text"]


def test_parse_flex_ask_tool_loop_preamble_case_insensitive():
    raw = (
        "TOOL_CALL web_fetch url=https://example.com\n"
        "TOOL_RESULT: title=Example\n"
        "Ich kann die Farbe nicht raten.\n"
        "flex_ask yes_no task=color\n"
        "Soll der Hintergrund dunkel sein?"
    )
    parsed = parse_flex_ask(raw)
    assert parsed is not None
    assert parsed["component"] == "yes_no"
    assert parsed["task_id"] == "color"
    assert "Hintergrund" in parsed["text"]
    assert "TOOL_" not in parsed["text"]


def test_parse_flex_ask_applies_plain_german():
    parsed = parse_flex_ask("FLEX_ASK yes_no task=hero\nSoll der Hero kürzer sein?")
    assert parsed is not None
    assert "Kopfbereich" in parsed["text"]
    assert "Hero" not in parsed["text"]


def test_parse_flex_ask_none_without_token():
    assert parse_flex_ask("") is None
    assert parse_flex_ask(None) is None  # type: ignore[arg-type]
    assert parse_flex_ask("<html>page</html>") is None
    assert parse_flex_ask("Hier ist der fertige Entwurf ohne Rückfrage.") is None
    assert parse_flex_ask("I considered asking flex, but here is the HTML.") is None
