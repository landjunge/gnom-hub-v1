#!/usr/bin/env python3
"""Poll open `teilaufgabe` issues and start the Builder once per issue."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

CLAIM_MARKER = "<!-- gnom-builder-poll:started -->"
DEFAULT_REPO = "landjunge/gnom-hub-v1"
DEFAULT_INTERVAL = 45
DEFAULT_STATE = Path("data/agent_poll_state.json")
BUILDER_PROMPT = Path("agents/builder.md")
IN_PROGRESS = "in-bearbeitung"
MISSING_CMD = "missing-cmd"


class MissingBuilderCmd(RuntimeError):
    """Raised when GNOM_BUILDER_CMD is unset."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(action: str, issue: int | None = None, detail: str = "") -> None:
    parts = [utc_now(), action]
    if issue is not None:
        parts.append(f"issue=#{issue}")
    if detail:
        parts.append(detail)
    print(" ".join(parts), flush=True)


def repo_from_env() -> str:
    return (
        os.environ.get("GNOM_GITHUB_REPO")
        or os.environ.get("GITHUB_REPOSITORY")
        or DEFAULT_REPO
    ).strip()


def token_from_env() -> str:
    return (os.environ.get("GNOM_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()


def builder_cmd() -> str:
    return (os.environ.get("GNOM_BUILDER_CMD") or "").strip()


def require_builder_cmd() -> str:
    cmd = builder_cmd()
    if not cmd:
        raise MissingBuilderCmd(
            "GNOM_BUILDER_CMD is not set; refusing to start a Builder. "
            "Export GNOM_BUILDER_CMD to an executable command."
        )
    return cmd


def load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"started": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"started": {}}
    started = raw.get("started") if isinstance(raw, dict) else {}
    if not isinstance(started, dict):
        started = {}
    return {"started": {str(k): v for k, v in started.items()}}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def issue_labels(issue: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for item in issue.get("labels") or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(item).strip()
        if name:
            names.add(name)
    return names


def already_started(
    issue: dict[str, Any],
    state: dict[str, Any],
    comments: list[dict[str, Any]] | None = None,
) -> bool:
    number = str(issue.get("number") or "")
    if number and number in (state.get("started") or {}):
        return True
    if IN_PROGRESS in issue_labels(issue):
        return True
    for comment in comments or []:
        body = str(comment.get("body") or "")
        if CLAIM_MARKER in body:
            return True
    return False


def builder_prompt(issue_number: int, prompt_path: Path = BUILDER_PROMPT) -> str:
    text = ""
    if prompt_path.is_file():
        text = prompt_path.read_text(encoding="utf-8").strip()
    hint = (
        f"Offene Teilaufgabe: Issue #{issue_number}. "
        "Nimm nur diese Issue. Branch von baseline, PR gegen baseline, Issue verlinken."
    )
    if text:
        return f"{text}\n\n{hint}\n"
    return hint + "\n"


def github_request(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "gnom-hub-teilaufgabe-poll")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"GitHub {method} {url} -> {exc.code}: {detail}") from exc
    return json.loads(raw) if raw.strip() else None


def list_open_teilaufgaben(repo: str, token: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"state": "open", "labels": "teilaufgabe", "per_page": "100"})
    url = f"https://api.github.com/repos/{repo}/issues?{query}"
    items = github_request("GET", url, token) or []
    if not isinstance(items, list):
        return []
    return [it for it in items if isinstance(it, dict) and not it.get("pull_request")]


def list_issue_comments(repo: str, number: int, token: str) -> list[dict[str, Any]]:
    url = f"https://api.github.com/repos/{repo}/issues/{number}/comments?per_page=100"
    items = github_request("GET", url, token) or []
    return [it for it in items if isinstance(it, dict)] if isinstance(items, list) else []


def claim_issue(repo: str, number: int, token: str) -> None:
    body = f"{CLAIM_MARKER}\nBuilder-Poll claimt Issue #{number}.\n"
    github_request(
        "POST",
        f"https://api.github.com/repos/{repo}/issues/{number}/comments",
        token,
        {"body": body},
    )
    github_request(
        "POST",
        f"https://api.github.com/repos/{repo}/issues/{number}/labels",
        token,
        {"labels": [IN_PROGRESS]},
    )


def launch_builder(issue_number: int, prompt: str, cmd: str | None = None) -> str:
    raw = cmd if cmd is not None else require_builder_cmd()
    args = shlex.split(raw)
    if not args:
        raise MissingBuilderCmd("GNOM_BUILDER_CMD is empty after parse; refusing to start.")
    env = os.environ.copy()
    env["ISSUE_NUMBER"] = str(issue_number)
    subprocess.run(args, check=True, input=prompt, text=True, env=env, shell=False)
    return f"cmd:{raw}"


def process_issue(
    issue: dict[str, Any],
    *,
    repo: str,
    token: str,
    state: dict[str, Any],
    state_path: Path,
    prompt_path: Path,
    dry_run: bool = False,
    cmd: str | None = None,
    claim: Callable[[str, int, str], None] | None = None,
    comments: list[dict[str, Any]] | None = None,
) -> str:
    number = int(issue["number"])
    if comments is None and token and not dry_run:
        comments = list_issue_comments(repo, number, token)
    if already_started(issue, state, comments):
        log("skip-already-started", number)
        return "skipped"
    if dry_run:
        log("dry-run-start", number)
        return "dry-run"
    try:
        raw_cmd = cmd if cmd is not None else require_builder_cmd()
    except MissingBuilderCmd as exc:
        log("error", number, f"{MISSING_CMD} {exc}")
        return MISSING_CMD
    if token:
        (claim or claim_issue)(repo, number, token)
        labels = issue.setdefault("labels", [])
        if isinstance(labels, list):
            labels.append({"name": IN_PROGRESS})
    try:
        how = launch_builder(number, builder_prompt(number, prompt_path), cmd=raw_cmd)
    except (MissingBuilderCmd, OSError, subprocess.CalledProcessError) as exc:
        log("launch-failed", number, str(exc)[:200])
        return "launch-failed"
    state.setdefault("started", {})[str(number)] = {"at": utc_now(), "how": how}
    save_state(state_path, state)
    log("start-builder", number, how)
    return "started"


def poll_once(
    *,
    repo: str,
    token: str,
    state_path: Path,
    prompt_path: Path,
    dry_run: bool = False,
    cmd: str | None = None,
    list_issues: Callable[[str, str], list[dict[str, Any]]] | None = None,
    claim: Callable[[str, int, str], None] | None = None,
) -> list[str]:
    if not dry_run:
        try:
            raw_cmd = cmd if cmd is not None else require_builder_cmd()
        except MissingBuilderCmd as exc:
            log("error", detail=f"{MISSING_CMD} {exc}")
            return [MISSING_CMD]
    else:
        raw_cmd = cmd or ""
    if not token:
        log("no-token", detail="set GITHUB_TOKEN or GNOM_GITHUB_TOKEN")
        return []
    fetch = list_issues or list_open_teilaufgaben
    issues = fetch(repo, token)
    if not issues:
        log("empty-repo", detail="no open teilaufgabe issues")
        return []
    state = load_state(state_path)
    actions: list[str] = []
    for issue in issues:
        action = process_issue(
            issue,
            repo=repo,
            token=token,
            state=state,
            state_path=state_path,
            prompt_path=prompt_path,
            dry_run=dry_run,
            cmd=raw_cmd,
            claim=claim,
        )
        actions.append(action)
        if action != "skipped":
            break
    return actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo", default=repo_from_env())
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--prompt", type=Path, default=BUILDER_PROMPT)
    args = parser.parse_args(argv)
    interval = max(30, min(60, int(args.interval)))
    while True:
        try:
            poll_once(
                repo=args.repo,
                token=token_from_env(),
                state_path=args.state,
                prompt_path=args.prompt,
                dry_run=args.dry_run,
            )
        except Exception as exc:  # noqa: BLE001
            log("error", detail=str(exc)[:240])
        if args.once:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
