"""GH-C01/02: synthetic local source/run bindings, no model or personal data."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from gnom_hub.db.sqlite_store import GnomDatabase
from gnom_hub.external_work import BindingError, ExternalWork, RunBinding


@pytest.fixture
def setup(tmp_path):
    binding = RunBinding(
        "p",
        "workflow",
        "handoff-1",
        1,
        "thread-1",
        "thread-1:task",
        "bridge-1",
        "run-1",
        "worker1",
        "lane-1",
        "attempt-1",
        "a" * 64,
        "operator-project",
        "configured-principal",
    )
    packet = {
        "format": "threaddesk.handoff.v1",
        "handoff_id": "handoff-1",
        "revision": 1,
        "thread_id": "thread-1",
        "task_id": "thread-1:task",
        "target_system": "gnom-hub-v1",
        "ran": False,
        "sent": False,
        "task": "synthetic task",
    }
    issued = {
        "handoff": packet,
        "binding": None,
        "source": {"thread_revision": 3, "snapshot_id": "snap-1", "content_hash": "b" * 64},
    }
    jobs = {
        "aaaaaaaaaaaa": {"status": "running", "stage": "running", "finished": False},
        "bbbbbbbbbbbb": {"status": "running", "stage": "running", "finished": False},
    }
    cancelled = []

    def cancel(jid):
        jobs[jid]["cancel"] = True
        jobs[jid]["stage"] = "cancelling"
        cancelled.append(jid)
        return dict(jobs[jid])

    hub = SimpleNamespace(get_job=lambda jid: jobs.get(jid), cancel_job=cancel)
    database = GnomDatabase(tmp_path, db_path=tmp_path / "isolated.db")
    adapter = ExternalWork(
        database,
        hub,
        authorize=lambda *_: True,
        issued_lookup=lambda _: {"found": True, "issued": issued},
        verify_job_receipt=lambda _binding, job_id: job_id in jobs,
    )
    yield adapter, binding, packet, issued, jobs, cancelled
    database.close()


def trust_run(issued, binding):
    issued["binding"] = {
        "handoff_id": binding.handoff_id,
        "handoff_revision": 1,
        "task_id": binding.original_task_id,
        "bridge_task_id": binding.bridge_task_id,
        "run_id": binding.run_id,
        "worker": "gnom-hub-v1",
        "operator_scope": binding.operator_scope,
        "principal_ref": binding.principal_ref,
        "request_hash": binding.request_hash,
    }


def test_import_is_idempotent_nonexecuting_and_claims_are_unverified(setup):
    adapter, binding, packet, _, jobs, cancelled = setup
    assert adapter.accept(packet, binding)["ran"] is False
    assert adapter.accept(packet, binding)["duplicate"] is True
    assert (
        adapter.accept(packet, binding)["binding_verification"] == "unverified_pending_fixed_issuer"
    )
    assert adapter.observe(binding)["status"] == "accepted"
    assert not cancelled and len(jobs) == 2
    with pytest.raises(BindingError, match="run_binding_unverified"):
        adapter.attach_job(binding, "aaaaaaaaaaaa")


def test_authorization_and_issuer_lookup_fail_closed(setup):
    adapter, binding, packet, *_ = setup
    no_auth = ExternalWork(adapter.db, adapter.hub, issued_lookup=adapter.issued_lookup)
    with pytest.raises(BindingError, match="operator_authorization_required"):
        no_auth.accept(packet, binding)
    with pytest.raises(BindingError, match="issued_source_lookup_required"):
        ExternalWork(adapter.db, adapter.hub, authorize=lambda *_: True).accept(packet, binding)
    with pytest.raises(BindingError, match="issued_source_conflict"):
        adapter.accept({**packet, "confirmed": True, "source_authenticated": True}, binding)


@pytest.mark.parametrize(
    "changes",
    [
        {"run_id": "foreign"},
        {"request_hash": "c" * 64},
        {"principal_ref": "foreign"},
        {"original_task_id": "thread1task"},
    ],
)
def test_binding_changes_cannot_reuse_prior_acceptance(setup, changes):
    adapter, binding, packet, *_ = setup
    adapter.accept(packet, binding)
    with pytest.raises(BindingError):
        adapter.accept(packet, replace(binding, **changes))


def test_job_loss_is_unknown_not_a_new_execution(setup):
    adapter, binding, packet, issued, jobs, cancelled = setup
    adapter.accept(packet, binding)
    trust_run(issued, binding)
    adapter.attach_job(binding, "aaaaaaaaaaaa")
    assert adapter.observe(binding)["status"] == "running"
    jobs.clear()
    observed = adapter.observe(binding)
    assert observed["status"] == "unknown" and observed["restart_allowed"] is False
    assert adapter.accept(packet, binding)["duplicate"] is True
    assert not jobs and not cancelled


def test_missing_gate_cannot_claim_stop_or_cancel_foreign_job(setup):
    adapter, binding, packet, issued, jobs, cancelled = setup
    adapter.accept(packet, binding)
    trust_run(issued, binding)
    adapter.attach_job(binding, "aaaaaaaaaaaa")
    with pytest.raises(BindingError, match="workflow_control_required"):
        adapter.stop(binding, "stop-1")
    assert not cancelled and not jobs["bbbbbbbbbbbb"].get("cancel")


def test_same_job_cannot_belong_to_two_handoffs(setup):
    adapter, binding, packet, issued, _, _ = setup
    adapter.accept(packet, binding)
    trust_run(issued, binding)
    adapter.attach_job(binding, "aaaaaaaaaaaa")
    other = replace(binding, handoff_id="handoff-2")
    packet.update(handoff_id="handoff-2")
    issued["handoff"] = packet
    adapter.accept(packet, other)
    trust_run(issued, other)
    with pytest.raises(BindingError, match="job_owned_by_other_binding"):
        adapter.attach_job(other, "aaaaaaaaaaaa")


def test_atomic_binding_capacity_and_corrupt_record_fail_closed(setup):
    adapter, binding, packet, *_ = setup
    adapter.accept(packet, binding)
    adapter.db.kv_set(binding.key, "{broken")
    with pytest.raises(BindingError, match="binding_corrupt"):
        adapter.observe(binding)
    with pytest.raises(ValueError, match="binding_capacity"):
        adapter.db.kv_compare_exchange("bounded:a", None, "{}", prefix="bounded:", limit=0)


def test_matching_ids_do_not_replace_observed_job_receipt(setup):
    adapter, binding, packet, issued, _, cancelled = setup
    adapter.accept(packet, binding)
    trust_run(issued, binding)
    adapter.verify_job_receipt = None
    with pytest.raises(BindingError, match="job_receipt_unverified"):
        adapter.attach_job(binding, "aaaaaaaaaaaa")
    assert not cancelled


@pytest.mark.parametrize("reported", [None, False, 1, "verified", {"verified": True}])
def test_observation_requires_exact_host_receipt_true(setup, reported):
    adapter, binding, packet, issued, _, cancelled = setup
    adapter.accept(packet, binding)
    trust_run(issued, binding)
    adapter.attach_job(binding, "aaaaaaaaaaaa")
    adapter.verify_job_receipt = lambda *_: reported
    with pytest.raises(BindingError, match=r"^job_receipt_unverified$"):
        adapter.observe(binding)
    assert not cancelled


def test_observation_sanitizes_host_failure_without_side_effects(setup):
    adapter, binding, packet, issued, _, cancelled = setup
    adapter.accept(packet, binding)
    trust_run(issued, binding)
    adapter.attach_job(binding, "aaaaaaaaaaaa")

    def unavailable(*_):
        raise OSError("synthetic-private-host-detail-must-not-escape")

    adapter.verify_job_receipt = unavailable
    with pytest.raises(BindingError, match=r"^job_receipt_unavailable$") as error:
        adapter.observe(binding)
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__ is True
    assert not cancelled
