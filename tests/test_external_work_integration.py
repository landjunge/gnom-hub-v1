"""Optional actual TD/TG source tests; no network, account or provider execution."""

from __future__ import annotations

import pytest
import test_external_work as cases

from gnom_hub.external_work import ExternalWork, RunBinding

setup = cases.setup


def test_actual_tollgate_barrier_then_only_bound_cooperative_cancel(setup, tmp_path):
    control_module = pytest.importorskip("tollgate.workflow_control")
    adapter, binding, packet, issued, jobs, cancelled = setup
    control = control_module.WorkflowControl(root=tmp_path / "tg")
    controlled = ExternalWork(
        adapter.db,
        adapter.hub,
        authorize=adapter.authorize,
        issued_lookup=adapter.issued_lookup,
        verify_job_receipt=adapter.verify_job_receipt,
        workflow_control=control,
    )
    controlled.accept(packet, binding)
    cases.trust_run(issued, binding)
    controlled.attach_job(binding, "aaaaaaaaaaaa")
    # Previously checked local ownership survives loss of the issuer connection.
    controlled.issued_lookup = lambda _: (_ for _ in ()).throw(OSError("synthetic disconnect"))
    reply = controlled.stop(binding, "stop-1")
    assert reply["barrier"]["status"] == "EFFECTIVE"
    assert reply["cancel_requested"] is True and reply["abort_confirmed"] is False
    assert reply["external_effect"] == "unknown"
    assert cancelled == ["aaaaaaaaaaaa"]
    assert jobs["aaaaaaaaaaaa"]["stage"] == "cancelling"
    assert not jobs["bbbbbbbbbbbb"].get("cancel")
    # Only actual cooperative finalization permits an abort confirmation.
    jobs["aaaaaaaaaaaa"].update(status="cancelled", finished=True)
    assert controlled.stop(binding, "stop-1")["abort_confirmed"] is True


def test_actual_threaddesk_issued_run_and_strict_unverified_return(setup, tmp_path):
    pytest.importorskip("threaddesk.services.issued_handoffs")
    from threaddesk.api.service import ThreadService
    from threaddesk.storage.sqlite_store import SQLiteStore

    adapter, _, _, _, jobs, _ = setup
    service = ThreadService(SQLiteStore(tmp_path / "td"))
    service.gate_set(cooldown_seconds=0)
    thread = service.create("Synthetic Gnom task", "No provider execution")
    issued_payload = service.issue_handoff(
        {
            "operation_id": "issue-gnom-1",
            "id": thread.id,
            "expected_revision": thread.revision,
            "target": "gnom-hub-v1",
        }
    )
    record = service.get_issued_handoff(handoff_id=issued_payload["handoff_id"])["issued"]
    handoff = record["handoff"]
    binding = RunBinding(
        "p",
        "workflow",
        handoff["handoff_id"],
        handoff["revision"],
        thread.id,
        handoff["task_id"],
        "bridge-1",
        "run-1",
        "worker1",
        "lane-1",
        "attempt-1",
        "a" * 64,
        "operator-project",
        "configured-principal",
    )
    service.bind_handoff_run(
        {
            "handoff_id": binding.handoff_id,
            "handoff_revision": binding.handoff_revision,
            "task_id": binding.original_task_id,
            "bridge_task_id": binding.bridge_task_id,
            "run_id": binding.run_id,
            "worker": "gnom-hub-v1",
            "expected_thread_revision": record["source"]["thread_revision"],
            "principal_ref": binding.principal_ref,
            "operator_scope": binding.operator_scope,
            "request_hash": binding.request_hash,
        }
    )
    integrated = ExternalWork(
        adapter.db,
        adapter.hub,
        authorize=adapter.authorize,
        issued_lookup=lambda hid: service.get_issued_handoff(handoff_id=hid),
        verify_job_receipt=adapter.verify_job_receipt,
    )
    assert integrated.accept(handoff, binding)["ran"] is False
    integrated.attach_job(binding, "aaaaaaaaaaaa")
    jobs["aaaaaaaaaaaa"].update(status="done", finished=True)
    first = integrated.prepare_return(
        binding,
        "delivery-1",
        result="Synthetic result",
        files=[],
        test_results=["synthetic check passed"],
        open_issues=[],
    )
    again = integrated.prepare_return(
        binding,
        "delivery-1",
        result="Synthetic result",
        files=[],
        test_results=["synthetic check passed"],
        open_issues=[],
    )
    assert again == first and first["sent"] is False
    assert first["payload"]["task_id"] == handoff["task_id"]
    assert first["payload"]["review_status"] == "unverified"
    # Actual strict TD receive is called by the test, never by import/observe.
    received = service.receive_return(first["payload"], strict_binding=True)
    assert received["return"]["review_status"] == "unverified"


def test_actual_pending_stop_is_not_effective_or_abort_confirmation(setup, tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    m = pytest.importorskip("tollgate.workflow_control")
    adapter, binding, packet, issued, _, cancelled = setup
    quote = m.Quote("dummy-gnom", "dummy", "synthetic-send", "dummy-target", 0, "fixed-zero-v1")
    control = m.WorkflowControl(
        root=tmp_path / "tg",
        lock_timeout_s=0.02,
        registered_quotes={quote.adapter_id: quote},
        admission=lambda *_: True,
    )
    scope = m.WorkflowScope(binding.project_id, binding.workflow_id)
    control.configure_budget(scope, binding.actor_id, binding.consumer_id, 0)
    identity = m.AttemptIdentity(
        scope,
        binding.original_task_id,
        binding.actor_id,
        binding.consumer_id,
        binding.attempt_id,
        binding.request_hash,
    )
    control.reserve(identity, quote)
    adapter.workflow_control = control
    adapter.accept(packet, binding)
    cases.trust_run(issued, binding)
    adapter.attach_job(binding, "aaaaaaaaaaaa")
    entered, release = threading.Event(), threading.Event()

    def send():
        entered.set()
        assert release.wait(3)

    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(control.dispatch, identity, send)
        assert entered.wait(2)
        result = adapter.stop(binding, "stop-pending")
        assert result["barrier"]["status"] == "PENDING"
        assert result["abort_confirmed"] is False
        assert cancelled == ["aaaaaaaaaaaa"]
        release.set()
        pending.result(3)
    assert adapter.stop(binding, "stop-pending")["barrier"]["status"] == "EFFECTIVE"
