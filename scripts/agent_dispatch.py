#!/usr/bin/env python3
"""One-at-a-time dispatcher for the GitHub agent team on baseline."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
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


# Strict one-job-per-tick order. Do not reorder these steps.
PRIORITY = (
    "review-fixes",  # 1 builder on CHANGES_REQUESTED
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
        if review_state(latest) == "CHANGES_REQUESTED":
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
        state_name = review_state(latest)
        if state_name == "CHANGES_REQUESTED":
            continue
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


def launch_role(
    job: Job,
    prompt: str,
    cmd: str | None = None,
    cwd: Path | None = None,
) -> str:
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
    subprocess.run(
        argv,
        check=True,
        input=prompt,
        text=True,
        env=env,
        cwd=str(cwd) if cwd else None,
        shell=False,
    )
    return f"cmd:{argv[0]}"


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
    run = launch or (lambda role, text, _env: launch_role(job, text, cwd=cwd))
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
