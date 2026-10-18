"""Trusted-host worker stands on ExternalWork's existing CAS record; no queue/API.

Endpoints and worktrees are operator configuration, never imported instructions.
Separate worktrees prevent accidental writes, not hostile same-user processes.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from gnom_hub.external_work import BindingError, ExternalWork, RunBinding, digest
from gnom_hub.memory.workspace import WorkspaceStore

ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
COMMIT = re.compile(r"(?:[a-f0-9]{40}|[a-f0-9]{64})\Z")


@dataclass(frozen=True)
class Assignment:
    subtask_id: str
    worker_id: str
    role: str
    base_commit: str
    request_hash: str
    depends_on: tuple[str, ...] = ()
    review_target: str | None = None

    def payload(self):
        value = asdict(self)
        value["depends_on"] = list(self.depends_on)
        return value


@dataclass(frozen=True)
class WorkerContext:
    assignment: Assignment
    parent_task_id: str
    run_id: str
    worktree: Path
    starting_commit: str
    reviewed_commit: str | None
    task: str


@dataclass(frozen=True)
class WorkerEndpoint:
    # A real configured worker adapter, not a caller-selectable command/process.
    worktree: Path
    execute: Callable[[WorkerContext], str]


def git(path: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            timeout=5,
            check=True,
        )
        if len(result.stdout) > 4096:
            raise BindingError("worker_git_output_limit")
        return result.stdout.decode("utf-8").strip()
    except (OSError, subprocess.SubprocessError, UnicodeError):
        raise BindingError("worker_git_unavailable") from None


def observed_commit(path: Path) -> str:
    head = git(path, "rev-parse", "HEAD")
    if not COMMIT.fullmatch(head):
        raise BindingError("worker_git_invalid_commit")
    if git(path, "status", "--porcelain", "--untracked-files=normal"):
        raise BindingError("worker_worktree_dirty")
    return head


def configured_root(path: Path) -> Path:
    try:
        return Path(path).resolve(strict=True)
    except (OSError, ValueError):
        raise BindingError("worker_worktree_unavailable") from None


class WorkerStands:
    """Synchronous explicit invocation, never scheduling, merging or retrying work."""

    def __init__(
        self,
        external: ExternalWork,
        workspace: WorkspaceStore,
        endpoints: dict[str, WorkerEndpoint],
        *,
        integration_worktree: Path | None = None,
    ):
        self.external, self.workspace = external, workspace
        if not 1 <= len(endpoints) <= 4:
            raise BindingError("worker_endpoint_limit")
        self.endpoints = dict(endpoints)
        roots = set()
        for worker_id, endpoint in self.endpoints.items():
            if not ID.fullmatch(worker_id) or not callable(endpoint.execute):
                raise BindingError("worker_endpoint_invalid")
            root = configured_root(endpoint.worktree)
            if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root or root in roots:
                raise BindingError("worker_worktree_not_distinct")
            roots.add(root)
            self.endpoints[worker_id] = WorkerEndpoint(root, endpoint.execute)
        self.integration_worktree = integration_worktree
        if integration_worktree is not None:
            target = configured_root(integration_worktree)
            if (
                target in roots
                or Path(git(target, "rev-parse", "--show-toplevel")).resolve() != target
            ):
                raise BindingError("worker_integration_worktree_invalid")
            self.integration_worktree = target
        self._active: set[str] = set()
        self._lock = threading.Lock()

    def _authorized(self, binding, operation):
        self.external._authorize(binding, operation)
        self.external._require_verified_run(binding)
        observed = self.external.observe(binding)
        if (
            observed.get("status") != "running"
            or observed.get("finished")
            or observed.get("cancel_requested")
        ):
            raise BindingError("worker_parent_not_running")

    def register(self, binding: RunBinding, assignments: list[Assignment]):
        self._authorized(binding, "register_workers")
        if not isinstance(assignments, list) or not 1 <= len(assignments) <= 4:
            raise BindingError("worker_assignment_limit")
        specs = {}
        used = set()
        for item in assignments:
            if (
                not isinstance(item, Assignment)
                or not isinstance(item.subtask_id, str)
                or not ID.fullmatch(item.subtask_id)
                or not isinstance(item.worker_id, str)
                or item.worker_id not in self.endpoints
                or item.worker_id in used
                or not isinstance(item.role, str)
                or item.role not in {"plan", "develop", "review"}
                or not isinstance(item.base_commit, str)
                or not COMMIT.fullmatch(item.base_commit)
                or not isinstance(item.request_hash, str)
                or not re.fullmatch(r"[a-f0-9]{64}", item.request_hash)
                or not isinstance(item.depends_on, tuple)
                or len(item.depends_on) > 3
                or any(not isinstance(x, str) or not ID.fullmatch(x) for x in item.depends_on)
                or len(set(item.depends_on)) != len(item.depends_on)
                or (item.review_target is not None and not isinstance(item.review_target, str))
                or item.subtask_id in specs
            ):
                raise BindingError("worker_assignment_invalid")
            specs[item.subtask_id] = item.payload()
            used.add(item.worker_id)
        visited = set()

        def visit(key, stack):
            if key not in specs or key in stack:
                raise BindingError("worker_dependency_invalid")
            if key in visited:
                return
            spec = specs[key]
            if (spec["role"] == "review") != (spec["review_target"] is not None):
                raise BindingError("worker_review_target_required")
            if spec["role"] == "review" and (
                spec["review_target"] not in spec["depends_on"]
                or specs.get(spec["review_target"], {}).get("role") != "develop"
            ):
                raise BindingError("worker_review_target_invalid")
            for parent in spec["depends_on"]:
                visit(parent, stack | {key})
            visited.add(key)

        for key in specs:
            visit(key, set())

        def mutate(record):
            prior = record.get("workers")
            if prior is not None:
                if {key: value["assignment"] for key, value in prior.items()} != specs:
                    raise BindingError("worker_assignment_conflict")
                return
            record["workers"] = {
                key: {"assignment": value, "state": "pending"} for key, value in specs.items()
            }

        self.external._change(binding, mutate)
        return {"registered": list(specs), "ran": False}

    def status(self, binding: RunBinding):
        self.external._authorize(binding, "worker_status")
        _, record = self.external._read(binding)
        workers = record.get("workers", {})
        result = {}
        for key, item in workers.items():
            state = item["state"]
            if state == "pending":
                deps = [workers[x]["state"] for x in item["assignment"]["depends_on"]]
                state = (
                    "blocked"
                    if any(x in {"failed", "unknown"} for x in deps)
                    else "ready"
                    if all(x == "delivered" for x in deps)
                    else "waiting"
                )
            if state == "running" and item.get("attempt_id") not in self._active:
                state = "unknown"
            result[key] = {**item, "observed_state": state, "restart_allowed": False}
        return result

    def run(self, binding: RunBinding, subtask_id: str, *, task: str):
        """Claim before calling one configured adapter; no implicit start/retry."""
        self._authorized(binding, "run_worker")
        if not isinstance(task, str) or not task.strip() or len(task.encode()) > 65536:
            raise BindingError("worker_task_limit")
        _, record = self.external._read(binding)
        item = record.get("workers", {}).get(subtask_id)
        if item is None:
            raise BindingError("worker_assignment_missing")
        if item["state"] != "pending":
            raise BindingError("worker_already_claimed")
        if any(
            record["workers"][dep]["state"] != "delivered"
            for dep in item["assignment"]["depends_on"]
        ):
            raise BindingError("worker_dependencies_not_delivered")
        assignment = Assignment(
            **{**item["assignment"], "depends_on": tuple(item["assignment"]["depends_on"])}
        )
        if digest(task) != assignment.request_hash:
            raise BindingError("worker_request_conflict")
        endpoint = self.endpoints[assignment.worker_id]
        base = observed_commit(endpoint.worktree)
        reviewed = None
        if assignment.review_target:
            reviewed = record["workers"][assignment.review_target].get("result_commit")
        expected = reviewed if assignment.role == "review" else assignment.base_commit
        if base != expected:
            raise BindingError("worker_source_conflict")
        attempt = uuid4().hex

        def claim(record):
            worker = record["workers"][subtask_id]
            if worker["state"] != "pending":
                raise BindingError("worker_already_claimed")
            if any(record["workers"][dep]["state"] != "delivered" for dep in assignment.depends_on):
                raise BindingError("worker_dependencies_not_delivered")
            worker.update(
                state="running", attempt_id=attempt, starting_commit=base, reviewed_commit=reviewed
            )

        with self._lock:
            self._active.add(attempt)
        try:
            self.external._change(binding, claim)
        except BaseException:
            self._active.discard(attempt)
            raise
        try:
            self._authorized(binding, "run_worker")
            context = WorkerContext(
                assignment,
                binding.original_task_id,
                binding.run_id,
                endpoint.worktree,
                base,
                reviewed,
                task,
            )
            result = endpoint.execute(context)
            if not isinstance(result, str) or not result.strip() or len(result.encode()) > 65536:
                raise BindingError("worker_result_limit")
            final = observed_commit(endpoint.worktree)
            if assignment.role == "review" and final != reviewed:
                raise BindingError("worker_review_source_changed")
            git(endpoint.worktree, "merge-base", "--is-ancestor", base, final)
            name = "worker-" + digest([binding.key, binding.run_id, subtask_id, attempt]) + ".txt"
            self.workspace.write_worker_result(name, result)
            receipt = {
                "state": "delivered",
                "result_commit": final,
                "artifact": name,
                "artifact_sha256": hashlib.sha256(result.encode()).hexdigest(),
                "review_status": "unverified",
            }
        except Exception:  # noqa: BLE001 -- preserve only a stable error, not secret worker text
            receipt = {"state": "failed", "error": "worker_execution_failed"}
        finally:
            self._active.discard(attempt)

        def finish(record):
            worker = record["workers"][subtask_id]
            if worker.get("attempt_id") != attempt or worker["state"] != "running":
                raise BindingError("worker_receipt_conflict")
            worker.update(receipt)

        self.external._change(binding, finish)
        return self.status(binding)[subtask_id]

    def prepare_return(self, binding: RunBinding, subtask_id: str):
        """Prepare this exact worker artifact through the existing return builder."""
        self.external._authorize(binding, "prepare_worker_return")
        _, record = self.external._read(binding)
        item = record.get("workers", {}).get(subtask_id)
        if not item or item["state"] != "delivered":
            raise BindingError("worker_delivery_required")
        try:
            result = self.workspace.read_worker_result(item["artifact"], item["artifact_sha256"])
        except ValueError:
            raise BindingError("worker_artifact_changed") from None
        checks = [
            "Observed starting commit: " + item["starting_commit"],
            "Observed result commit: " + item["result_commit"],
        ]
        if item.get("reviewed_commit"):
            checks.append("Observed reviewed commit: " + item["reviewed_commit"])
        return self.external.prepare_return(
            binding,
            "worker-" + digest([subtask_id, item["attempt_id"]]),
            result=result,
            files=[item["artifact"]],
            test_results=checks,
            open_issues=[
                "Worker delivery is unverified; commit observation is not a functional test or project acceptance."
            ],
        )

    def merge_proposal(self, binding: RunBinding, subtask_id: str, *, expected_base: str):
        """Explicit conflict-checking proposal only; never git merge/cherry-pick."""
        self.external._authorize(binding, "worker_merge_proposal")
        self.external._require_verified_run(binding)
        _, record = self.external._read(binding)
        item = record.get("workers", {}).get(subtask_id)
        if not item or item["state"] != "delivered" or item["assignment"]["role"] != "develop":
            raise BindingError("worker_delivery_required")
        if expected_base != item["starting_commit"]:
            raise BindingError("worker_merge_base_conflict")
        if self.integration_worktree is None:
            raise BindingError("worker_integration_worktree_required")
        if observed_commit(self.integration_worktree) != expected_base:
            raise BindingError("worker_merge_base_conflict")
        reviewers = [
            x
            for x in record["workers"].values()
            if x["assignment"]["review_target"] == subtask_id
            and x["state"] == "delivered"
            and x.get("reviewed_commit") == item["result_commit"]
        ]
        if not reviewers:
            raise BindingError("worker_exact_review_required")
        for evidence in [item, *reviewers]:
            if not self.workspace.check_worker_result(
                evidence["artifact"], evidence["artifact_sha256"]
            ):
                raise BindingError("worker_artifact_changed")
        return {
            "base_commit": expected_base,
            "result_commit": item["result_commit"],
            "reviewed_commit": item["result_commit"],
            "merge_performed": False,
            "review_status": "unverified",
            "operator_merge_required": True,
        }
