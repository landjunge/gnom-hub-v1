"""Demo plugin tool."""


def run(text: str = "") -> dict:
    return {"echo": text, "plugin": "echo"}
