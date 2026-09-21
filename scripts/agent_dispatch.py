#!/usr/bin/env python3
"""One-at-a-time dispatcher for the GitHub agent team on baseline."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_REPO = "landjunge/gnom-hub-v1"
DEFAULT_BASE = "baseline"
DEFAULT_INTERVAL = 45
DEFAULT_STATE = Path("data/agent_dispatch_state.json")
DEFAULT_AGENTS = Path("agents")
HAUPT_ISSUE = 105
IN_PROGRESS = "in-bearbeitung"
STALE_AFTER = timedelta(hours=2)
COORD_COOLDOWN = timedelta(hours=1)
STARTED_TTL = timedelta(hours=2)
MISSING_CMD = "missing-cmd"
# Supervisor: end the tick on GitHub-effect or idle, not after --max-turns.
DEFAULT_TICK_POLL_SEC = 2.0
DEFAULT_TICK_IDLE_SEC = 180.0
DEFAULT_TICK_START_GRACE_SEC = 600.0
CPU_IDLE_PCT = 1.0
STOP_GRACE_SEC = 2.0
DONE_COMMENT_GENERIC = (
    "squash-merge",
    "fast-forward",
    "gemerged",
    "geschlossen",
)
ROLE_DONE_MARKERS: dict[str, tuple[str, ...]] = {
    "reviewer": ("**reviewer**",),
    "test-agent": ("**test-agent**",),
    "planer": ("planer:",),
    "koordinator": ("**koordinator",),
    "builder": ("fixes #", "closes #"),
}

RoleLaunch = Callable[[str, str, dict[str, str]], str]
ReviewKey = int | tuple[str, int]


@dataclass(frozen=True)
class RepoSpec:
    repo: str
    bases: tuple[str, ...]


# Home repo watches baseline and main (they are the same line). Other products: default branch.
DEFAULT_REPOS: tuple[RepoSpec, ...] = (
    RepoSpec("landjunge/gnom-hub-v1", ("baseline", "main")),
    RepoSpec("landjunge/4AllPass", ("main",)),
    RepoSpec("landjunge/tollgate", ("main",)),
    RepoSpec("landjunge/threaddesk", ("main",)),
    RepoSpec("landjunge/agent-authority-lab", ("master",)),
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_stamp(now: datetime | None = None) -> str:
    return (now or utc_now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(action: str, *, role: str = "", target: str = "", detail: str = "") -> None:
    parts = [utc_stamp(), action]
    if role:
        parts.append(f"role={role}")
    if target:
        parts.append(target)
    if detail:
        parts.append(detail)
    print(" ".join(parts), flush=True)


def parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def repo_from_env() -> str:
    return (
        os.environ.get("GNOM_GITHUB_REPO") or os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO
    ).strip()


def _bases_for(repo: str, explicit: str | None = None) -> tuple[str, ...]:
    if explicit:
        parts = tuple(
            part.strip() for part in explicit.replace("|", "+").split("+") if part.strip()
        )
        if parts:
            return parts
    repo_l = repo.strip().lower()
    for spec in DEFAULT_REPOS:
        if spec.repo.lower() == repo_l:
            return spec.bases
    if repo_l == DEFAULT_REPO.lower():
        return (DEFAULT_BASE, "main")
    return ("main",)


def parse_repo_specs(raw: str | None) -> tuple[RepoSpec, ...]:
    text = (raw or "").strip()
    if not text:
        return DEFAULT_REPOS
    specs: list[RepoSpec] = []
    for chunk in text.replace(";", ",").replace("\n", ",").split(","):
        for token in chunk.split():
            token = token.strip()
            if not token:
                continue
            if ":" in token:
                repo, base_raw = token.split(":", 1)
                repo = repo.strip()
                bases = _bases_for(repo, base_raw.strip())
            else:
                repo = token
                bases = _bases_for(repo, None)
            if repo:
                specs.append(RepoSpec(repo, bases))
    return tuple(specs) or DEFAULT_REPOS


def repos_from_env() -> tuple[RepoSpec, ...]:
    return parse_repo_specs(os.environ.get("GNOM_GITHUB_REPOS"))


def token_from_env() -> str:
    return (os.environ.get("GNOM_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()


def dispatch_enabled() -> bool:
    raw = (os.environ.get("GNOM_AGENT_DISPATCH") or "1").strip().lower()
    return raw not in ("0", "false", "off", "no")


def default_agent_cmd(role: str) -> str:
    env_key = {
        "builder": "GNOM_BUILDER_CMD",
        "reviewer": "GNOM_REVIEWER_CMD",
        "planer": "GNOM_PLANER_CMD",
        "koordinator": "GNOM_KOORDINATOR_CMD",
        "test-agent": "GNOM_TEST_AGENT_CMD",
    }.get(role, "")
    if env_key:
        override = (os.environ.get(env_key) or "").strip()
        if override:
            return override
    return f"scripts/run_agent.sh {role}"


@dataclass(frozen=True)
class Job:
    role: str
    reason: str
    issue: int | None = None
    pr: int | None = None
    sha: str | None = None
    extra: str = ""
    repo: str = DEFAULT_REPO
    base: str = DEFAULT_BASE

    def target(self) -> str:
        if self.pr is not None:
            return f"{self.repo}#{self.pr}" if self.repo else f"pr=#{self.pr}"
        if self.issue is not None:
            return f"issue=#{self.issue}"
        if self.sha:
            return f"sha={self.sha[:12]}"
        return "none"

    def key(self) -> str:
        parts = [self.role]
        if self.repo:
            parts.append(f"repo:{self.repo}")
        if self.pr is not None:
            parts.append(f"pr:{self.pr}")
        if self.issue is not None:
            parts.append(f"issue:{self.issue}")
        if self.sha:
            parts.append(f"sha:{self.sha[:12]}")
        parts.append(self.reason)
        return ":".join(parts)


@dataclass
class Snapshot:
    teilaufgaben: list[dict[str, Any]]
    pulls: list[dict[str, Any]]
    reviews: dict[ReviewKey, list[dict[str, Any]]]
    haupt: dict[str, Any] | None
    baseline_sha: str
    now: datetime
    home_repo: str = DEFAULT_REPO


def load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"started": {}, "last_test_sha": ""}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"started": {}, "last_test_sha": ""}
    if not isinstance(raw, dict):
        return {"started": {}, "last_test_sha": ""}
    started = raw.get("started") if isinstance(raw.get("started"), dict) else {}
    return {
        "started": {str(k): v for k, v in started.items()},
        "last_test_sha": str(raw.get("last_test_sha") or ""),
        "last_koordinator_at": str(raw.get("last_koordinator_at") or ""),
    }


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def started_fresh(state: dict[str, Any], key: str, now: datetime) -> bool:
    item = (state.get("started") or {}).get(key)
    if not isinstance(item, dict):
        return False
    at = parse_dt(str(item.get("at") or ""))
    if at is None:
        return True
    return now - at < STARTED_TTL


def mark_started(state: dict[str, Any], job: Job, how: str, now: datetime) -> None:
    state.setdefault("started", {})[job.key()] = {
        "at": utc_stamp(now),
        "how": how,
        "role": job.role,
        "reason": job.reason,
    }
    if job.role == "test-agent" and job.sha:
        state["last_test_sha"] = job.sha
    if job.role == "koordinator":
        state["last_koordinator_at"] = utc_stamp(now)


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


def latest_review(reviews: list[dict[str, Any]]) -> dict[str, Any] | None:
    dated: list[tuple[datetime, dict[str, Any]]] = []
    undated: list[dict[str, Any]] = []
    for item in reviews:
        if not isinstance(item, dict):
            continue
        at = parse_dt(str(item.get("submitted_at") or item.get("submittedAt") or ""))
        if at is None:
            undated.append(item)
        else:
            dated.append((at, item))
    if dated:
        dated.sort(key=lambda pair: pair[0])
        return dated[-1][1]
    return undated[-1] if undated else None


def review_state(review: dict[str, Any] | None) -> str:
    if not review:
        return ""
    return str(review.get("state") or "").upper().replace(" ", "_")


def linked_issue(pr: dict[str, Any]) -> int | None:
    title = str(pr.get("title") or "")
    body = str(pr.get("body") or "")
    text = f"{title}\n{body}"
    for token in text.replace("(", " ").replace(")", " ").split():
        if token.startswith("#") and token[1:].isdigit():
            return int(token[1:])
    return None


def pr_repo(pr: dict[str, Any], default: str = "") -> str:
    tagged = str(pr.get("_repo") or "").strip()
    if tagged:
        return tagged
    base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
    repo_obj = base.get("repo") if isinstance((base or {}).get("repo"), dict) else {}
    name = str((repo_obj or {}).get("full_name") or "").strip()
    if name:
        return name
    html = str(pr.get("html_url") or pr.get("url") or "")
    marker = "/repos/"
    if marker in html:
        rest = html.split(marker, 1)[1]
        parts = rest.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    if "github.com/" in html:
        rest = html.split("github.com/", 1)[1]
        parts = rest.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    return default


def pr_base(pr: dict[str, Any], default: str = DEFAULT_BASE) -> str:
    tagged = str(pr.get("_base") or "").strip()
    if tagged:
        return tagged
    base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
    ref = str((base or {}).get("ref") or "").strip()
    return ref or default


def pr_ci(pr: dict[str, Any]) -> str:
    tagged = str(pr.get("_ci") or "").strip()
    if tagged:
        return tagged.lower()
    rollup = pr.get("statusCheckRollup")
    if isinstance(rollup, list) and rollup:
        states = [
            str(item.get("state") or item.get("conclusion") or "").upper()
            for item in rollup
            if isinstance(item, dict)
        ]
        if states and all(s in ("SUCCESS", "SKIPPED", "NEUTRAL") for s in states):
            return "success"
        if any(s in ("FAILURE", "ERROR", "CANCELLED", "TIMED_OUT") for s in states):
            return "failure"
        if any(s in ("PENDING", "QUEUED", "IN_PROGRESS") for s in states):
            return "pending"
    return ""


def pr_is_draft(pr: dict[str, Any]) -> bool:
    if "draft" in pr:
        return bool(pr.get("draft"))
    return bool(pr.get("isDraft"))


def pr_merge_conflict(pr: dict[str, Any]) -> bool:
    mergeable = pr.get("mergeable")
    if mergeable is False:
        return True
    token = str(mergeable or "").strip().upper()
    if token in ("CONFLICTING", "DIRTY"):
        return True
    state = str(pr.get("mergeable_state") or "").strip().lower()
    return state in ("dirty", "conflicting")


def pr_has_blocker(pr: dict[str, Any]) -> bool:
    """CI red, draft, or merge conflict — the three review-fix blockers."""
    if pr_is_draft(pr) or pr_merge_conflict(pr):
        return True
    return pr_ci(pr) in ("failure", "error")


def review_is_comment(state: str) -> bool:
    # GitHub REST/GraphQL: COMMENTED. Issue text and some payloads: COMMENT.
    return state in ("COMMENTED", "COMMENT")


def needs_review_fixes(pr: dict[str, Any], latest: dict[str, Any] | None) -> bool:
    """CHANGES_REQUESTED, or COMMENT plus a blocker, means Builder on this PR."""
    state = review_state(latest)
    if state == "CHANGES_REQUESTED":
        return True
    return review_is_comment(state) and pr_has_blocker(pr)


def reviews_for(snapshot: Snapshot, pr: dict[str, Any]) -> list[dict[str, Any]]:
    number = int(pr.get("number") or 0)
    repo = pr_repo(pr, default="")
    table = snapshot.reviews
    if repo:
        found = table.get((repo, number))
        if found is not None:
            return found
    found = table.get(number)
    return found if isinstance(found, list) else []


def github_request(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "gnom-hub-agent-dispatch")
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


def _list_pulls(
    call: Callable[[str, str, str, dict[str, Any] | None], Any],
    repo: str,
    base: str,
    token: str,
) -> list[dict[str, Any]]:
    url = (
        f"https://api.github.com/repos/{repo}/pulls?"
        f"{urllib.parse.urlencode({'state': 'open', 'base': base, 'per_page': '100'})}"
    )
    try:
        raw = call("GET", url, token, None) or []
    except RuntimeError as exc:
        log("watch-failed", target=repo, detail=f"base={base} {str(exc)[:180]}")
        return []
    if not isinstance(raw, list):
        return []
    return [pr for pr in raw if isinstance(pr, dict)]


def _list_reviews(
    call: Callable[[str, str, str, dict[str, Any] | None], Any],
    repo: str,
    number: int,
    token: str,
) -> list[dict[str, Any]]:
    url = f"https://api.github.com/repos/{repo}/pulls/{number}/reviews"
    try:
        raw = call("GET", url, token, None) or []
    except RuntimeError as exc:
        log("watch-failed", target=f"{repo}#{number}", detail=str(exc)[:180])
        return []
    if not isinstance(raw, list):
        return []
    return [it for it in raw if isinstance(it, dict)]


def collect_snapshot(
    *,
    repo: str,
    token: str,
    base: str = DEFAULT_BASE,
    now: datetime | None = None,
    github: Callable[[str, str, str, dict[str, Any] | None], Any] | None = None,
    repos: Sequence[RepoSpec] | None = None,
) -> Snapshot:
    call = github or github_request
    watch = list(repos) if repos is not None else [RepoSpec(repo, (base,))]
    issues = (
        call(
            "GET",
            f"https://api.github.com/repos/{repo}/issues?{urllib.parse.urlencode({'state': 'open', 'labels': 'teilaufgabe', 'per_page': '100'})}",
            token,
            None,
        )
        or []
    )
    if not isinstance(issues, list):
        issues = []
    teilaufgaben = [it for it in issues if isinstance(it, dict) and not it.get("pull_request")]
    pulls: list[dict[str, Any]] = []
    reviews: dict[ReviewKey, list[dict[str, Any]]] = {}
    seen: set[tuple[str, int]] = set()
    for spec in watch:
        for watch_base in spec.bases:
            for pr in _list_pulls(call, spec.repo, watch_base, token):
                number = int(pr.get("number") or 0)
                if number <= 0:
                    continue
                key = (spec.repo, number)
                if key in seen:
                    continue
                seen.add(key)
                pr["_repo"] = spec.repo
                pr["_base"] = pr_base(pr, watch_base)
                _enrich_pull(call, spec.repo, pr, token)
                pulls.append(pr)
                reviews[key] = _list_reviews(call, spec.repo, number, token)
    try:
        haupt = call(
            "GET", f"https://api.github.com/repos/{repo}/issues/{HAUPT_ISSUE}", token, None
        )
    except RuntimeError:
        haupt = None
    if not isinstance(haupt, dict):
        haupt = None
    ref = (
        call("GET", f"https://api.github.com/repos/{repo}/git/ref/heads/{base}", token, None) or {}
    )
    sha = ""
    if isinstance(ref, dict):
        obj = ref.get("object") if isinstance(ref.get("object"), dict) else {}
        sha = str((obj or {}).get("sha") or "")
    return Snapshot(
        teilaufgaben=teilaufgaben,
        pulls=pulls,
        reviews=reviews,
        haupt=haupt,
        baseline_sha=sha,
        now=now or utc_now(),
        home_repo=repo,
    )


def _pr_head_sha(pr: dict[str, Any]) -> str:
    head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
    return str((head or {}).get("sha") or "")


def _enrich_pull(
    call: Callable[[str, str, str, dict[str, Any] | None], Any],
    repo: str,
    pr: dict[str, Any],
    token: str,
) -> None:
    """REST list omits mergeable and Actions checks. Fill both for pick_job."""
    number = int(pr.get("number") or 0)
    if number <= 0:
        return
    if pr.get("mergeable") is None:
        url = f"https://api.github.com/repos/{repo}/pulls/{number}"
        try:
            detail = call("GET", url, token, None)
        except RuntimeError as exc:
            log("watch-failed", target=f"{repo}#{number}", detail=str(exc)[:180])
            detail = None
        if isinstance(detail, dict):
            for key in ("draft", "mergeable", "mergeable_state"):
                if key in detail:
                    pr[key] = detail[key]
    if pr_ci(pr):
        return
    sha = _pr_head_sha(pr)
    if not sha:
        return
    url = f"https://api.github.com/repos/{repo}/commits/{sha}/check-runs"
    try:
        raw = call("GET", url, token, None)
    except RuntimeError as exc:
        log("watch-failed", target=f"{repo}#{number}", detail=str(exc)[:180])
        return
    runs: list[Any] = []
    if isinstance(raw, dict):
        maybe = raw.get("check_runs")
        if isinstance(maybe, list):
            runs = maybe
    elif isinstance(raw, list):
        runs = raw
    rollup: list[dict[str, Any]] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        conclusion = str(run.get("conclusion") or "").upper()
        status = str(run.get("status") or "").upper()
        rollup.append(
            {
                "state": conclusion or status,
                "conclusion": conclusion,
                "status": status,
                "name": run.get("name"),
            }
        )
    if rollup:
        pr["statusCheckRollup"] = rollup


# Strict one-job-per-tick order. Do not reorder these steps.
PRIORITY = (
    "review-fixes",  # 1 builder on CHANGES_REQUESTED or COMMENT+blocker
    "reviewer",  # 2 needs-review or merge-approved
    "test-agent",  # 3 baseline moved
    "builder",  # 4 open teilaufgabe
    "planer",  # 5 haupt open, no teilaufgaben
    "koordinator",  # 6 stale or waiting
)


def pick_job(snapshot: Snapshot, state: dict[str, Any]) -> Job | None:
    now = snapshot.now
    pulls = list(snapshot.pulls)
    home = snapshot.home_repo or DEFAULT_REPO

    def accept(job: Job) -> Job | None:
        if started_fresh(state, job.key(), now):
            return None
        return job

    for pr in pulls:
        number = int(pr.get("number") or 0)
        latest = latest_review(reviews_for(snapshot, pr))
        if needs_review_fixes(pr, latest):
            repo = pr_repo(pr, home)
            job = Job(
                role="builder",
                reason="changes-requested",
                pr=number,
                issue=linked_issue(pr),
                sha=_pr_head_sha(pr) or None,
                extra=(
                    f"arbeite die Review-Kommentare zu PR #{number} in {repo} ab. "
                    "Branch nicht neu anlegen."
                ),
                repo=repo,
                base=pr_base(pr),
            )
            taken = accept(job)
            if taken:
                return taken

    for pr in pulls:
        number = int(pr.get("number") or 0)
        sha = _pr_head_sha(pr)
        latest = latest_review(reviews_for(snapshot, pr))
        if needs_review_fixes(pr, latest):
            continue
        state_name = review_state(latest)
        if state_name == "APPROVED":
            reason = "merge-approved"
        else:
            reason = "needs-review"
        repo = pr_repo(pr, home)
        base = pr_base(pr)
        job = Job(
            role="reviewer",
            reason=reason,
            pr=number,
            issue=linked_issue(pr),
            sha=sha or None,
            extra=f"Prüfe PR #{number} in {repo} gegen {base}. Merge nur ohne Blocker.",
            repo=repo,
            base=base,
        )
        taken = accept(job)
        if taken:
            return taken

    if snapshot.baseline_sha and snapshot.baseline_sha != str(state.get("last_test_sha") or ""):
        job = Job(
            role="test-agent",
            reason="baseline-moved",
            issue=HAUPT_ISSUE,
            sha=snapshot.baseline_sha,
            extra=f"baseline HEAD {snapshot.baseline_sha[:12]}. Tests ausführen, Fakten in #{HAUPT_ISSUE}.",
            repo=home,
        )
        taken = accept(job)
        if taken:
            return taken

    home_pulls = [pr for pr in pulls if pr_repo(pr, home) == home]
    pr_issues = {linked_issue(pr) for pr in home_pulls}
    for issue in snapshot.teilaufgaben:
        number = int(issue.get("number") or 0)
        if number <= 0:
            continue
        if number in pr_issues:
            continue
        labels = issue_labels(issue)
        updated = parse_dt(str(issue.get("updated_at") or ""))
        stale = IN_PROGRESS in labels and updated is not None and now - updated >= STALE_AFTER
        if IN_PROGRESS in labels and not stale:
            continue
        job = Job(
            role="builder",
            reason="stale-retry" if stale else "open-teilaufgabe",
            issue=number,
            extra=f"Offene Teilaufgabe: Issue #{number}. Branch von baseline, PR gegen baseline.",
            repo=home,
        )
        taken = accept(job)
        if taken:
            return taken

    haupt_open = bool(snapshot.haupt) and str(snapshot.haupt.get("state") or "").lower() == "open"
    if haupt_open and not snapshot.teilaufgaben:
        job = Job(
            role="planer",
            reason="no-teilaufgaben",
            issue=HAUPT_ISSUE,
            extra=f"Lies Issue #{HAUPT_ISSUE}. Zerlege in 2–4 Teilaufgaben. Keine Umsetzung.",
            repo=home,
        )
        taken = accept(job)
        if taken:
            return taken

    last_coord = parse_dt(str(state.get("last_koordinator_at") or ""))
    if last_coord is not None and now - last_coord < COORD_COOLDOWN:
        return None
    stale_issues = []
    for issue in snapshot.teilaufgaben:
        labels = issue_labels(issue)
        updated = parse_dt(str(issue.get("updated_at") or ""))
        if IN_PROGRESS in labels and updated is not None and now - updated >= STALE_AFTER:
            stale_issues.append(int(issue.get("number") or 0))
    waiting_prs = bool(pulls)
    if stale_issues or waiting_prs:
        extra = "Blockaden: " + ", ".join(
            [f"stale #{n}" for n in stale_issues if n] + (["offene PRs"] if waiting_prs else [])
        )
        job = Job(
            role="koordinator",
            reason="stale-or-waiting",
            issue=HAUPT_ISSUE,
            extra=extra,
            repo=home,
        )
        return accept(job)
    return None


def build_prompt(job: Job, agents_dir: Path) -> str:
    name = "test-agent.md" if job.role == "test-agent" else f"{job.role}.md"
    path = agents_dir / name
    text = path.read_text(encoding="utf-8").strip() if path.is_file() else ""
    hint = job.extra.strip()
    parts = [text] if text else []
    if hint:
        parts.append(hint)
    return "\n\n".join(parts) + "\n"


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def tick_poll_sec() -> float:
    return max(0.2, min(30.0, _env_float("GNOM_TICK_POLL_SEC", DEFAULT_TICK_POLL_SEC)))


def tick_idle_sec() -> float:
    return max(30.0, min(600.0, _env_float("GNOM_TICK_IDLE_SEC", DEFAULT_TICK_IDLE_SEC)))


def tick_start_grace_sec() -> float:
    """No idle halt until grok has printed, unless this grace expires."""
    return max(
        60.0, min(1800.0, _env_float("GNOM_TICK_START_GRACE_SEC", DEFAULT_TICK_START_GRACE_SEC))
    )


def is_done_comment(body: str, role: str = "", *, strict_role: bool = False) -> bool:
    """True when a GitHub comment looks like this role finished the tick."""
    text = (body or "").lower()
    if any(marker in text for marker in ROLE_DONE_MARKERS.get(role, ())):
        return True
    if strict_role:
        return False
    return any(marker in text for marker in DONE_COMMENT_GENERIC)


def _comment_after(item: dict[str, Any], started_at: datetime) -> bool:
    at = parse_dt(str(item.get("created_at") or item.get("createdAt") or ""))
    if at is None:
        return False
    return at >= started_at


def _list_issue_comments(
    call: Callable[[str, str, str, dict[str, Any] | None], Any],
    repo: str,
    number: int,
    token: str,
    started_at: datetime,
) -> list[dict[str, Any]]:
    url = (
        f"https://api.github.com/repos/{repo}/issues/{number}/comments?"
        f"{urllib.parse.urlencode({'since': utc_stamp(started_at), 'per_page': '30'})}"
    )
    try:
        raw = call("GET", url, token, None) or []
    except RuntimeError as exc:
        log("watch-failed", target=f"{repo}#{number}", detail=str(exc)[:180])
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def github_effect_done(
    job: Job,
    token: str,
    started_at: datetime,
    *,
    github: Callable[[str, str, str, dict[str, Any] | None], Any] | None = None,
) -> bool:
    """PR merged/closed, issue closed, or a completion comment after start."""
    if not token:
        return False
    call = github or github_request
    repo = job.repo or DEFAULT_REPO

    if job.pr is not None:
        url = f"https://api.github.com/repos/{repo}/pulls/{job.pr}"
        try:
            pr = call("GET", url, token, None) or {}
        except RuntimeError as exc:
            log("watch-failed", target=f"{repo}#{job.pr}", detail=str(exc)[:180])
            pr = {}
        if isinstance(pr, dict):
            if bool(pr.get("merged")) or str(pr.get("state") or "").lower() == "closed":
                return True
        for item in _list_issue_comments(call, repo, job.pr, token, started_at):
            if _comment_after(item, started_at) and is_done_comment(
                str(item.get("body") or ""), job.role
            ):
                return True
        if job.role == "reviewer":
            rev_url = f"https://api.github.com/repos/{repo}/pulls/{job.pr}/reviews"
            try:
                reviews = call("GET", rev_url, token, None) or []
            except RuntimeError as exc:
                log("watch-failed", target=f"{repo}#{job.pr}", detail=str(exc)[:180])
                reviews = []
            if isinstance(reviews, list):
                for rev in reviews:
                    if not isinstance(rev, dict):
                        continue
                    if review_state(rev) != "CHANGES_REQUESTED":
                        continue
                    at = parse_dt(str(rev.get("submitted_at") or rev.get("submittedAt") or ""))
                    if at is None or at >= started_at:
                        return True

    if job.issue is not None and job.issue != job.pr:
        url = f"https://api.github.com/repos/{repo}/issues/{job.issue}"
        try:
            issue = call("GET", url, token, None) or {}
        except RuntimeError as exc:
            log("watch-failed", target=f"issue=#{job.issue}", detail=str(exc)[:180])
            issue = {}
        closed = isinstance(issue, dict) and str(issue.get("state") or "").lower() == "closed"
        # #105 stays closed; test-agent/planer/koordinator still write there.
        if closed and job.issue != HAUPT_ISSUE:
            return True
        strict = job.issue == HAUPT_ISSUE
        for item in _list_issue_comments(call, repo, job.issue, token, started_at):
            if _comment_after(item, started_at) and is_done_comment(
                str(item.get("body") or ""), job.role, strict_role=strict
            ):
                return True
    return False


def process_cpu_percent(pid: int) -> float:
    """Sum %CPU for pid and descendants. Unknown-but-unreadable → busy."""
    if pid <= 0:
        return 0.0
    try:
        out = subprocess.check_output(
            ["ps", "-axo", "pid=,ppid=,%cpu="],
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return 100.0
    kids: dict[int, list[int]] = {}
    cpu: dict[int, float] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            proc_id = int(parts[0])
            parent = int(parts[1])
            pct = float(parts[2])
        except ValueError:
            continue
        cpu[proc_id] = pct
        kids.setdefault(parent, []).append(proc_id)
    if pid not in cpu:
        return 0.0
    total = 0.0
    stack = [pid]
    seen: set[int] = set()
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        total += cpu.get(cur, 0.0)
        stack.extend(kids.get(cur, []))
    return total


def stop_agent_process(proc: subprocess.Popen[Any], *, grace: float = STOP_GRACE_SEC) -> None:
    """SIGTERM the process group, then SIGKILL if it ignores the first signal."""
    if proc.poll() is not None:
        return
    pid = proc.pid
    pgid: int | None = None
    if isinstance(pid, int) and pid > 0:
        try:
            pgid = os.getpgid(pid)
        except OSError:
            pgid = None
    if pgid is not None and pgid == pid:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except OSError:
            try:
                proc.terminate()
            except OSError:
                pass
    else:
        try:
            proc.terminate()
        except OSError:
            pass
    try:
        proc.wait(timeout=grace)
        return
    except subprocess.TimeoutExpired:
        pass
    if pgid is not None and pgid == pid:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            try:
                proc.kill()
            except OSError:
                pass
    else:
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=grace)
    except (subprocess.TimeoutExpired, OSError):
        pass


def _drain_stdout(proc: subprocess.Popen[Any]) -> bool:
    stream = proc.stdout
    if stream is None:
        return False
    got = False
    try:
        fd = stream.fileno()
    except (OSError, AttributeError):
        return False
    while True:
        try:
            chunk = os.read(fd, 65536)
        except BlockingIOError:
            break
        except OSError:
            break
        if not chunk:
            break
        got = True
        try:
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
        except OSError:
            pass
    return got


def _write_prompt(proc: subprocess.Popen[Any], prompt: str) -> None:
    if proc.stdin is None:
        return
    try:
        proc.stdin.write(prompt.encode("utf-8"))
        proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass


def run_agent(
    job: Job,
    prompt: str,
    *,
    cmd: str | None = None,
    cwd: Path | None = None,
    token: str | None = None,
    github: Callable[[str, str, str, dict[str, Any] | None], Any] | None = None,
    popen: Callable[..., subprocess.Popen[Any]] | None = None,
    cpu_of: Callable[[int], float] | None = None,
    stop: Callable[[subprocess.Popen[Any]], None] | None = None,
    sleep: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
    poll_sec: float | None = None,
    idle_sec: float | None = None,
    now: datetime | None = None,
) -> str:
    """Launch one role and return as soon as GitHub is done or grok is idle.

    Does not wait for ``grok --max-turns``. A tick with stdout events or
    descendant CPU stays alive until it exits on its own.
    """
    raw = (cmd if cmd is not None else default_agent_cmd(job.role)).strip()
    argv = shlex.split(raw)
    if not argv:
        raise RuntimeError(MISSING_CMD)
    env = os.environ.copy()
    env["GNOM_AGENT_ROLE"] = job.role
    if job.repo:
        env["GNOM_GITHUB_REPO"] = job.repo
    if job.base:
        env["GNOM_JOB_BASE"] = job.base
    if job.issue is not None:
        env["ISSUE_NUMBER"] = str(job.issue)
    if job.pr is not None:
        env["PR_NUMBER"] = str(job.pr)
    if job.sha:
        env["GNOM_JOB_SHA"] = job.sha
    env["GNOM_JOB_REASON"] = job.reason
    start = now or utc_now()
    auth = (token if token is not None else token_from_env()).strip()
    spawn = popen or subprocess.Popen
    cpu = cpu_of or process_cpu_percent
    halt = stop or stop_agent_process
    pause = sleep or time.sleep
    clock = monotonic or time.monotonic
    interval = tick_poll_sec() if poll_sec is None else max(0.0, float(poll_sec))
    idle_limit = tick_idle_sec() if idle_sec is None else max(0.0, float(idle_sec))
    start_grace = tick_start_grace_sec() if idle_sec is None else max(0.0, float(idle_sec))
    proc = spawn(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=str(cwd) if cwd else None,
        start_new_session=True,
        bufsize=0,
    )
    _write_prompt(proc, prompt)
    if proc.stdout is not None:
        try:
            os.set_blocking(proc.stdout.fileno(), False)
        except (OSError, AttributeError):
            pass
    spawned = clock()
    last_event = spawned
    seen_event = False
    supervised = False
    reason = ""
    try:
        while True:
            rc = proc.poll()
            had_event = _drain_stdout(proc)
            if had_event:
                seen_event = True
                last_event = clock()
            if rc is not None:
                if rc != 0 and not supervised:
                    raise subprocess.CalledProcessError(rc, argv)
                return f"cmd:{argv[0]}"
            if github_effect_done(job, auth, start, github=github):
                supervised = True
                reason = "github-effect"
                log("tick-done", role=job.role, target=job.target(), detail=reason)
                halt(proc)
                _drain_stdout(proc)
                return f"cmd:{argv[0]}"
            busy_cpu = cpu(proc.pid) >= CPU_IDLE_PCT
            if busy_cpu or had_event:
                last_event = clock()
            elif seen_event and clock() - last_event >= idle_limit:
                supervised = True
                reason = "idle"
                log("tick-done", role=job.role, target=job.target(), detail=reason)
                halt(proc)
                _drain_stdout(proc)
                return f"cmd:{argv[0]}"
            elif (not seen_event) and clock() - spawned >= start_grace:
                supervised = True
                reason = "idle"
                log("tick-done", role=job.role, target=job.target(), detail=reason)
                halt(proc)
                _drain_stdout(proc)
                return f"cmd:{argv[0]}"
            if interval:
                pause(interval)
    finally:
        if proc.poll() is None:
            halt(proc)


def launch_role(
    job: Job,
    prompt: str,
    cmd: str | None = None,
    cwd: Path | None = None,
    token: str | None = None,
    github: Callable[[str, str, str, dict[str, Any] | None], Any] | None = None,
) -> str:
    return run_agent(job, prompt, cmd=cmd, cwd=cwd, token=token, github=github)


def log_seen_pulls(snapshot: Snapshot) -> None:
    home = snapshot.home_repo or DEFAULT_REPO
    for pr in snapshot.pulls:
        number = int(pr.get("number") or 0)
        if number <= 0:
            continue
        repo = pr_repo(pr, home)
        base = pr_base(pr)
        ci = pr_ci(pr)
        detail = " ".join(
            part
            for part in (
                f"base={base}" if base else "",
                f"ci={ci}" if ci else "",
            )
            if part
        )
        log("seen-pr", target=f"{repo}#{number}", detail=detail)


def dispatch_once(
    *,
    repo: str,
    token: str,
    state_path: Path,
    agents_dir: Path,
    base: str = DEFAULT_BASE,
    dry_run: bool = False,
    cwd: Path | None = None,
    snapshot: Snapshot | None = None,
    launch: RoleLaunch | None = None,
    github: Callable[[str, str, str, dict[str, Any] | None], Any] | None = None,
    now: datetime | None = None,
    repos: Sequence[RepoSpec] | None = None,
) -> str:
    if not dispatch_enabled():
        log("disabled", detail="GNOM_AGENT_DISPATCH=0")
        return "disabled"
    if not token:
        log("no-token", detail="set GITHUB_TOKEN or GNOM_GITHUB_TOKEN")
        return "no-token"
    watch = tuple(repos) if repos is not None else repos_from_env()
    snap = snapshot or collect_snapshot(
        repo=repo, token=token, base=base, now=now, github=github, repos=watch
    )
    if dry_run:
        for spec in watch:
            log("watch", target=spec.repo, detail="bases=" + "+".join(spec.bases))
        log_seen_pulls(snap)
    state = load_state(state_path)
    job = pick_job(snap, state)
    if job is None:
        log("idle")
        return "idle"
    log("pick", role=job.role, target=job.target(), detail=job.reason)
    if dry_run:
        log("dry-run", role=job.role, target=job.target())
        return "dry-run"
    prompt = build_prompt(job, agents_dir)
    run = launch or (
        lambda role, text, _env: launch_role(job, text, cwd=cwd, token=token, github=github)
    )
    try:
        how = run(job.role, prompt, {})
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        log("launch-failed", role=job.role, target=job.target(), detail=str(exc)[:200])
        return "launch-failed"
    mark_started(state, job, how, snap.now)
    save_state(state_path, state)
    log("start", role=job.role, target=job.target(), detail=how)
    return "started"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo", default=repo_from_env())
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--agents", type=Path, default=DEFAULT_AGENTS)
    parser.add_argument("--cwd", type=Path, default=None)
    args = parser.parse_args(argv)
    interval = max(30, min(60, int(args.interval)))
    cwd = args.cwd or Path((os.environ.get("GNOM_AGENT_WORKDIR") or "").strip() or ".")
    while True:
        try:
            dispatch_once(
                repo=args.repo,
                token=token_from_env(),
                state_path=args.state,
                agents_dir=args.agents,
                base=args.base,
                dry_run=args.dry_run,
                cwd=cwd,
            )
        except Exception as exc:
            log("error", detail=str(exc)[:240])
        if args.once:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
