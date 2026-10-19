"""GH-C04: real temporary Git worktrees, explicit dummy adapters, no provider."""

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace

import pytest
import test_external_work as bindings

from gnom_hub.external_work import BindingError, digest
from gnom_hub.memory.workspace import WorkspaceStore
from gnom_hub.worker_stands import Assignment, WorkerEndpoint, WorkerStands, git

setup = bindings.setup


@pytest.fixture
def stands(setup, tmp_path, monkeypatch):
    monkeypatch.setenv("GNOM_WS", str(tmp_path / "personal"))
    adapter, binding, packet, issued, jobs, _ = setup
    adapter.accept(packet, binding)
    bindings.trust_run(issued, binding)
    adapter.attach_job(binding, "aaaaaaaaaaaa")
    repo = tmp_path / "source"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.name", "Synthetic Worker")
    git(repo, "config", "user.email", "dummy@invalid.invalid")
    git(repo, "config", "core.hooksPath", "/dev/null")
    (repo / "shared.txt").write_text("original\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "synthetic base")
    base = git(repo, "rev-parse", "HEAD")
    trees = {}
    calls = []
    for worker in ("worker1", "worker2", "worker3", "worker4"):
        trees[worker] = tmp_path / worker
        git(repo, "worktree", "add", "--detach", str(trees[worker]), base)

    def develop(context):
        # Receipt is durable before any worker code runs.
        recorded = adapter._read(binding)[1]["workers"][context.assignment.subtask_id]
        assert recorded["state"] == "running" and recorded["starting_commit"] == base
        calls.append(context.assignment.subtask_id)
        (context.worktree / "shared.txt").write_text(context.task + "\n")
        git(context.worktree, "add", "shared.txt")
        git(context.worktree, "commit", "-m", context.task)
        return "Synthetic output " + context.task

    endpoints = {key: WorkerEndpoint(path, develop) for key, path in trees.items()}
    workspace = WorkspaceStore(tmp_path / "isolated-hub")
    service = WorkerStands(adapter, workspace, endpoints, integration_worktree=repo)
    return SimpleNamespace(
        service=service,
        adapter=adapter,
        binding=binding,
        jobs=jobs,
        calls=calls,
        base=base,
        trees=trees,
        repo=repo,
        workspace=workspace,
        endpoints=endpoints,
    )


def assignment(s, key, worker, *, role="develop", depends=(), review=None):
    return Assignment(key, worker, role, s.base, digest(key), depends, review)


def test_two_actual_dummy_workers_isolate_same_filename_and_exact_review(stands):
    s = stands
    s.service.register(
        s.binding,
        [
            assignment(s, "a", "worker1"),
            assignment(s, "b", "worker2"),
            assignment(s, "review-a", "worker3", role="review", depends=("a",), review="a"),
        ],
    )
    with ThreadPoolExecutor(2) as pool:
        a, b = list(pool.map(lambda key: s.service.run(s.binding, key, task=key), ["a", "b"]))
    assert a["state"] == b["state"] == "delivered"
    assert a["artifact"] != b["artifact"] and a["result_commit"] != b["result_commit"]
    assert s.workspace.read_text("temp", a["artifact"]) == "Synthetic output a"
    assert s.workspace.read_text("temp", b["artifact"]) == "Synthetic output b"
    assert (s.trees["worker1"] / "shared.txt").read_text() == "a\n"
    assert (s.trees["worker2"] / "shared.txt").read_text() == "b\n"
    assert (s.repo / "shared.txt").read_text() == "original\n"
    assert git(s.repo, "rev-parse", "HEAD") == s.base
    with pytest.raises(BindingError, match="worker_source_conflict"):
        s.service.run(s.binding, "review-a", task="review-a")
    # Explicit host checkout, never a model-provided claim or automatic merge.
    git(s.trees["worker3"], "checkout", "--detach", a["result_commit"])

    def review(context):
        assert context.reviewed_commit == a["result_commit"]
        return "Looked at exact commit " + context.reviewed_commit

    s.service.endpoints["worker3"] = WorkerEndpoint(s.trees["worker3"], review)
    reviewed = s.service.run(s.binding, "review-a", task="review-a")
    assert reviewed["reviewed_commit"] == a["result_commit"]
    assert reviewed["review_status"] == "unverified"
    proposal = s.service.merge_proposal(s.binding, "a", expected_base=s.base)
    assert proposal["merge_performed"] is False
    assert proposal["reviewed_commit"] == a["result_commit"]
    assert git(s.repo, "rev-parse", "HEAD") == s.base
    artifact = s.workspace.temp / reviewed["artifact"]
    original = artifact.read_bytes()
    artifact.write_text("changed after delivery")
    with pytest.raises(BindingError, match="worker_artifact_changed"):
        s.service.merge_proposal(s.binding, "a", expected_base=s.base)
    artifact.write_bytes(original)
    # An independently changed destination is a real conflict, not caller attestation.
    (s.repo / "later.txt").write_text("independent\n")
    git(s.repo, "add", ".")
    git(s.repo, "commit", "-m", "independent target change")
    with pytest.raises(BindingError, match="worker_merge_base_conflict"):
        s.service.merge_proposal(s.binding, "a", expected_base=s.base)


def test_failed_worker_blocks_only_dependents_and_never_repeats(stands):
    s = stands

    def fail(_):
        raise RuntimeError("SYNTHETIC_PRIVATE_ERROR_NOT_TO_PERSIST")

    s.service.endpoints["worker1"] = WorkerEndpoint(s.trees["worker1"], fail)
    plan = [
        assignment(s, "a", "worker1"),
        assignment(s, "b", "worker2", depends=("a",)),
        assignment(s, "c", "worker3", depends=("b",)),
        assignment(s, "independent", "worker4"),
    ]
    s.service.register(s.binding, plan)
    assert s.service.status(s.binding)["b"]["observed_state"] == "waiting"
    with pytest.raises(BindingError, match="worker_dependencies_not_delivered"):
        s.service.run(s.binding, "b", task="b")
    assert s.service.run(s.binding, "a", task="a")["state"] == "failed"
    assert s.service.status(s.binding)["b"]["observed_state"] == "blocked"
    assert s.service.status(s.binding)["c"]["observed_state"] == "blocked"
    assert s.service.run(s.binding, "independent", task="independent")["state"] == "delivered"
    with pytest.raises(BindingError, match="worker_already_claimed"):
        s.service.run(s.binding, "a", task="a")
    assert "SYNTHETIC_PRIVATE_ERROR" not in s.adapter._read(s.binding)[0]
    assert s.calls == ["independent"]


def test_restart_reads_uncertain_claim_without_duplicate_worker(stands):
    s = stands

    class SimulatedCrash(BaseException):
        pass

    def crash(_):
        s.calls.append("before-crash")
        raise SimulatedCrash()

    s.service.endpoints["worker1"] = WorkerEndpoint(s.trees["worker1"], crash)
    plan = [
        assignment(s, "c", "worker3", depends=("b",)),
        assignment(s, "b", "worker2", depends=("a",)),
        assignment(s, "a", "worker1"),
        assignment(s, "independent", "worker4"),
    ]
    s.service.register(s.binding, plan)
    with pytest.raises(SimulatedCrash):
        s.service.run(s.binding, "a", task="a")
    recovered = WorkerStands(s.adapter, s.workspace, s.endpoints, integration_worktree=s.repo)
    recovered.register(s.binding, plan)
    before_observation = s.adapter._read(s.binding)[0]
    observed = recovered.status(s.binding)
    assert s.adapter._read(s.binding)[0] == before_observation
    status = observed["a"]
    assert status["state"] == "running" and status["observed_state"] == "unknown"
    assert status["restart_allowed"] is False
    for key in ("b", "c"):
        assert observed[key]["state"] == "pending"
        assert observed[key]["observed_state"] == "blocked"
        assert observed[key]["restart_allowed"] is False
        with pytest.raises(BindingError, match="worker_dependencies_not_delivered"):
            recovered.run(s.binding, key, task=key)
    assert observed["independent"]["observed_state"] == "ready"
    with pytest.raises(BindingError, match="worker_already_claimed"):
        recovered.run(s.binding, "a", task="a")
    assert s.calls == ["before-crash"]


def test_duplicate_concurrent_claim_has_one_actual_start(stands):
    s = stands
    entered = threading.Event()
    release = threading.Event()

    def waiting(_):
        s.calls.append("one")
        entered.set()
        assert release.wait(3)
        return "result"

    s.service.endpoints["worker1"] = WorkerEndpoint(s.trees["worker1"], waiting)
    s.service.register(
        s.binding,
        [assignment(s, "b", "worker2", depends=("a",)), assignment(s, "a", "worker1")],
    )
    with ThreadPoolExecutor(2) as pool:
        future = pool.submit(s.service.run, s.binding, "a", task="a")
        assert entered.wait(2)
        observed = s.service.status(s.binding)
        assert observed["a"]["observed_state"] == "running"
        assert observed["b"]["observed_state"] == "waiting"
        with pytest.raises(BindingError, match="worker_already_claimed"):
            s.service.run(s.binding, "a", task="a")
        release.set()
        assert future.result(3)["state"] == "delivered"
    assert s.service.status(s.binding)["b"]["observed_state"] == "ready"
    assert s.calls == ["one"]


def test_role_dependencies_source_request_and_cancellation_fail_closed(stands):
    s = stands
    a = assignment(s, "a", "worker1")
    for changes in [
        {"subtask_id": 3},
        {"worker_id": []},
        {"role": []},
        {"base_commit": 3},
        {"request_hash": 3},
        {"depends_on": ([],)},
        {"review_target": []},
    ]:
        with pytest.raises(BindingError, match="worker_assignment_invalid"):
            s.service.register(s.binding, [replace(a, **changes)])
    with pytest.raises(BindingError, match="worker_dependency_invalid"):
        s.service.register(s.binding, [replace(a, depends_on=("a",))])
    with pytest.raises(BindingError, match="worker_review_target_required"):
        s.service.register(s.binding, [replace(a, role="review")])
    s.service.register(s.binding, [a])
    for changed in [
        replace(a, role="plan"),
        replace(a, base_commit="f" * 40),
        replace(a, request_hash="f" * 64),
    ]:
        with pytest.raises(BindingError, match="worker_assignment_conflict"):
            s.service.register(s.binding, [changed])
    with pytest.raises(BindingError, match="worker_request_conflict"):
        s.service.run(s.binding, "a", task="caller changed text")
    (s.trees["worker1"] / "shared.txt").write_text("uncommitted")
    with pytest.raises(BindingError, match="worker_worktree_dirty"):
        s.service.run(s.binding, "a", task="a")
    s.jobs["aaaaaaaaaaaa"]["cancel"] = True
    with pytest.raises(BindingError, match="worker_parent_not_running"):
        s.service.run(s.binding, "a", task="a")
    assert not s.calls


def test_immutable_artifact_and_worktree_alias_no_global_overwrite(stands):
    s = stands
    name = "worker-" + "a" * 64 + ".txt"
    s.workspace.write_worker_result(name, "one")
    with pytest.raises(FileExistsError):
        s.workspace.write_worker_result(name, "two")
    assert s.workspace.read_text("temp", name) == "one"
    import hashlib

    sha = hashlib.sha256(b"one").hexdigest()
    assert s.workspace.check_worker_result(name, sha)
    assert not s.workspace.check_worker_result(name, "0" * 64)
    (s.workspace.temp / name).unlink()
    (s.workspace.temp / name).symlink_to(s.repo / "shared.txt")
    assert not s.workspace.check_worker_result(name, sha)
    with pytest.raises(ValueError, match="worker_artifact_name"):
        s.workspace.write_worker_result("../foreign", "bad")
    with pytest.raises(BindingError, match="worker_worktree_not_distinct"):
        WorkerStands(
            s.adapter, s.workspace, {"a": s.endpoints["worker1"], "b": s.endpoints["worker1"]}
        )


def test_missing_host_authorization_or_issuer_never_starts_worker(stands):
    s = stands
    s.service.register(s.binding, [assignment(s, "a", "worker1")])
    s.adapter.authorize = None
    with pytest.raises(BindingError, match="operator_authorization_required"):
        s.service.run(s.binding, "a", task="a")
    s.adapter.authorize = lambda *_: True
    s.adapter.issued_lookup = None
    with pytest.raises(BindingError, match="run_binding_unverified"):
        s.service.run(s.binding, "a", task="a")
    assert not s.calls


def test_two_deliveries_use_existing_exact_return_builder_without_send(stands):
    pytest.importorskip("threaddesk.services.return_contract")
    s = stands
    s.service.register(s.binding, [assignment(s, "a", "worker1"), assignment(s, "b", "worker2")])
    s.service.run(s.binding, "a", task="a")
    s.service.run(s.binding, "b", task="b")
    with pytest.raises(BindingError, match="delivery_not_observed"):
        s.service.prepare_return(s.binding, "a")
    s.jobs["aaaaaaaaaaaa"].update(status="done", finished=True)
    a = s.service.prepare_return(s.binding, "a")
    b = s.service.prepare_return(s.binding, "b")
    assert a == s.service.prepare_return(s.binding, "a")
    assert a["payload"]["return_id"] != b["payload"]["return_id"]
    assert a["payload"]["task_id"] == b["payload"]["task_id"] == s.binding.original_task_id
    assert a["payload"]["result"] == "Synthetic output a"
    assert b["payload"]["result"] == "Synthetic output b"
    assert a["sent"] is b["sent"] is False
    assert a["review_status"] == b["review_status"] == "unverified"
    assert a["project_completion_verified"] is False
