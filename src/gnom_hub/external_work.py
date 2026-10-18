"""Local trusted adapter: handoff/job association, not a second execution queue.

No network route, import-time execution, callback auto-send or secret store.
Operator authorization and issued-source lookup must be supplied by the trusted
host. Request metadata is never treated as its own authorization proof.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from gnom_hub.db.sqlite_store import GnomDatabase

PREFIX = "external-run:"


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class BindingError(ValueError):
    """Stable code only; no prompts, provider responses or exception details."""


@dataclass(frozen=True)
class RunBinding:
    project_id: str
    workflow_id: str
    handoff_id: str
    handoff_revision: int
    thread_id: str
    original_task_id: str
    bridge_task_id: str
    run_id: str
    actor_id: str
    consumer_id: str
    attempt_id: str
    request_hash: str
    operator_scope: str
    principal_ref: str

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key == "handoff_revision":
                if type(value) is not int or value < 1:
                    raise BindingError("invalid_revision")
            elif (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > 512
                or any(ord(char) < 32 for char in value)
            ):
                raise BindingError("invalid_binding_id")
        for key in ("project_id", "workflow_id", "actor_id", "consumer_id", "attempt_id"):
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", getattr(self, key)):
                raise BindingError("invalid_control_id")
        if not re.fullmatch(r"[a-f0-9]{64}", self.request_hash):
            raise BindingError("invalid_request_hash")

    @property
    def key(self) -> str:
        # Preserve colon-containing source IDs. Never strip/replace punctuation.
        return PREFIX + digest(self.handoff_id)


class ExternalWork:
    def __init__(
        self,
        database: GnomDatabase,
        hub: Any,
        *,
        authorize: Callable[[RunBinding, str], bool] | None = None,
        issued_lookup: Callable[[str], dict] | None = None,
        verify_job_receipt: Callable[[RunBinding, str], bool] | None = None,
        workflow_control: Any = None,
    ):
        self.db, self.hub = database, hub
        self.authorize, self.issued_lookup = authorize, issued_lookup
        self.verify_job_receipt = verify_job_receipt
        self.workflow_control = workflow_control

    def _authorize(self, binding: RunBinding, operation: str):
        try:
            allowed = self.authorize is not None and self.authorize(binding, operation) is True
        except Exception:  # noqa: BLE001 -- host errors must not leak private configuration
            raise BindingError("operator_authorization_unavailable") from None
        if not allowed:
            raise BindingError("operator_authorization_required")

    def _verify_job(self, binding: RunBinding, job_id: str):
        try:
            verified = (
                self.verify_job_receipt is not None
                and self.verify_job_receipt(binding, job_id) is True
            )
        except Exception:  # noqa: BLE001 -- never echo host receipt/transport error material
            raise BindingError("job_receipt_unavailable") from None
        if not verified:
            raise BindingError("job_receipt_unverified")

    def _read(self, binding: RunBinding):
        raw = self.db.kv_get(binding.key)
        if raw is None:
            raise BindingError("binding_missing")
        try:
            record = json.loads(raw)
        except (ValueError, TypeError):
            raise BindingError("binding_corrupt") from None
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("deliveries"), dict)
            or not isinstance(record.get("packet_hash"), str)
        ):
            raise BindingError("binding_corrupt")
        if record.get("binding") != asdict(binding):
            raise BindingError("binding_conflict")
        return raw, record

    def _issued(self, binding: RunBinding):
        if self.issued_lookup is None:
            raise BindingError("issued_source_lookup_required")
        try:
            checked = self.issued_lookup(binding.handoff_id)
            issued = checked.get("issued") if checked.get("found") is True else None
        except Exception:  # noqa: BLE001 -- never expose transport error material
            raise BindingError("issued_lookup_unavailable") from None
        if not isinstance(issued, dict) or not isinstance(issued.get("handoff"), dict):
            raise BindingError("issued_source_missing")
        return issued

    def _require_verified_run(self, binding: RunBinding):
        _, record = self._read(binding)
        if self.issued_lookup is None:
            raise BindingError("run_binding_unverified")
        issued = self._issued(binding)
        run = issued.get("binding")
        expected = {
            "handoff_id": binding.handoff_id,
            "handoff_revision": binding.handoff_revision,
            "task_id": binding.original_task_id,
            "bridge_task_id": binding.bridge_task_id,
            "run_id": binding.run_id,
            "worker": "gnom-hub-v1",
            "operator_scope": binding.operator_scope,
            "principal_ref": binding.principal_ref,
            "request_hash": binding.request_hash,
        }
        if not isinstance(run, dict) or any(run.get(key) != val for key, val in expected.items()):
            raise BindingError("run_binding_unverified")
        if digest(issued.get("handoff")) != record["packet_hash"]:
            raise BindingError("issued_source_conflict")
        return record

    def _change(self, binding: RunBinding, mutate):
        for _ in range(4):
            raw, record = self._read(binding)
            mutate(record)
            encoded = json.dumps(record, sort_keys=True, separators=(",", ":"))
            if self.db.kv_compare_exchange(binding.key, raw, encoded, prefix=PREFIX):
                return record
        raise BindingError("binding_busy")

    def accept(self, packet: dict, binding: RunBinding) -> dict:
        """Import metadata only; cannot start a job, model, tool or delivery."""
        self._authorize(binding, "accept")
        issued = self._issued(binding)
        actual = issued["handoff"]
        # Lookup is from configured ThreadDesk, not a submitted self-attestation.
        if actual != packet:
            raise BindingError("issued_source_conflict")
        if (
            packet.get("format") != "threaddesk.handoff.v1"
            or packet.get("target_system") != "gnom-hub-v1"
            or packet.get("ran") is not False
            or packet.get("sent") is not False
        ):
            raise BindingError("invalid_handoff")
        expected = {
            "handoff_id": binding.handoff_id,
            "revision": binding.handoff_revision,
            "thread_id": binding.thread_id,
            "task_id": binding.original_task_id,
        }
        if any(packet.get(key) != value for key, value in expected.items()):
            raise BindingError("handoff_binding_mismatch")
        record = {
            "binding": asdict(binding),
            "packet_hash": digest(packet),
            "source": {
                key: (issued.get("source") or {}).get(key)
                for key in ("thread_revision", "snapshot_id", "content_hash")
            },
            "job_id": None,
            "deliveries": {},
            "binding_verification": "unverified_pending_fixed_issuer",
        }
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":"))
        created = self.db.kv_compare_exchange(binding.key, None, encoded, prefix=PREFIX)
        if not created:
            _, prior = self._read(binding)
            if prior["packet_hash"] != record["packet_hash"]:
                raise BindingError("handoff_content_conflict")
        return {
            "status": "accepted",
            "duplicate": not created,
            "ran": False,
            "project_completion_verified": False,
            "binding_verification": "unverified_pending_fixed_issuer",
        }

    def attach_job(self, binding: RunBinding, job_id: str):
        """Associate an already explicitly started job; never create one here."""
        self._authorize(binding, "attach_job")
        self._require_verified_run(binding)
        if not isinstance(job_id, str) or not re.fullmatch(r"[a-f0-9]{12}", job_id):
            raise BindingError("invalid_job_id")
        self._verify_job(binding, job_id)
        if self.hub.get_job(job_id) is None:
            raise BindingError("job_not_observed")
        owner_key = "external-job:" + job_id
        owner = self.db.kv_get(owner_key)
        if owner is None:
            self.db.kv_compare_exchange(owner_key, None, binding.key, prefix="external-job:")
            owner = self.db.kv_get(owner_key)
        if owner != binding.key:
            raise BindingError("job_owned_by_other_binding")

        def mutate(record):
            if record["job_id"] not in (None, job_id):
                raise BindingError("job_binding_conflict")
            record["job_id"] = job_id
            record["binding_verification"] = "checked_configured_issuer_run"

        self._change(binding, mutate)
        return {"job_id": job_id, "status": "bound", "ran": False}

    def observe(self, binding: RunBinding) -> dict:
        self._authorize(binding, "observe")
        _, record = self._read(binding)
        if record["job_id"] is None:
            return {"status": "accepted", "job_id": None, "ran": False}
        job = self.hub.get_job(record["job_id"])
        if job is None:
            return {
                "status": "unknown",
                "job_id": record["job_id"],
                "restart_allowed": False,
                "reason": "volatile_job_not_observed",
                "project_completion_verified": False,
            }
        self._verify_job(binding, record["job_id"])
        return {
            "status": job["status"],
            "stage": job.get("stage"),
            "finished": bool(job.get("finished")),
            "cancel_requested": bool(job.get("cancel")),
            "job_id": record["job_id"],
            "project_completion_verified": False,
        }

    def stop(self, binding: RunBinding, stop_id: str) -> dict:
        self._authorize(binding, "stop")
        # A previously checked own job remains stoppable when TD goes offline.
        # This local record is written only after issuer/run + job-receipt checks;
        # imported booleans never set it. Host authorization is checked above.
        _, record = self._read(binding)
        if record.get("binding_verification") != "checked_configured_issuer_run":
            raise BindingError("run_binding_unverified")
        if record["job_id"] and self.db.kv_get("external-job:" + record["job_id"]) != binding.key:
            raise BindingError("job_ownership_conflict")
        if self.workflow_control is None:
            raise BindingError("workflow_control_required")
        try:
            from tollgate.workflow_control import WorkflowScope

            barrier = self.workflow_control.stop(
                WorkflowScope(binding.project_id, binding.workflow_id), stop_id
            )
        except ImportError:
            raise BindingError("workflow_control_required") from None
        job = self.hub.get_job(record["job_id"]) if record["job_id"] else None
        if job:
            self._verify_job(binding, record["job_id"])
        cancel = self.hub.cancel_job(record["job_id"]) if job and not job.get("finished") else None
        return {
            "barrier": barrier,
            "cancel_requested": cancel is not None,
            "abort_confirmed": bool(
                job and job.get("finished") and job.get("status") == "cancelled"
            ),
            "external_effect": "unknown",
            "job_id": record["job_id"],
        }

    def prepare_return(
        self,
        binding: RunBinding,
        delivery_id: str,
        *,
        result: str,
        files: list[str],
        test_results: list[str],
        open_issues: list[str],
    ) -> dict:
        """Explicit packet build only; caller uses TD strict import, never auto-send."""
        self._authorize(binding, "prepare_return")
        self._require_verified_run(binding)
        observed = self.observe(binding)
        if observed["status"] != "done" or observed.get("finished") is not True:
            raise BindingError("delivery_not_observed")
        if not isinstance(delivery_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,128}", delivery_id
        ):
            raise BindingError("invalid_delivery_id")
        if not isinstance(result, str) or not result.strip() or len(result.encode()) > 65536:
            raise BindingError("delivery_result_limit")
        for items in (files, test_results, open_issues):
            if (
                not isinstance(items, list)
                or len(items) > 32
                or any(not isinstance(item, str) or len(item) > 512 for item in items)
            ):
                raise BindingError("delivery_list_limit")
        try:
            from threaddesk.services.return_contract import build
        except ImportError:
            raise BindingError("return_contract_unavailable") from None
        payload = build(
            handoff_id=binding.handoff_id,
            handoff_revision=binding.handoff_revision,
            thread_id=binding.thread_id,
            task_id=binding.original_task_id,
            worker="gnom-hub-v1",
            run_id=binding.run_id,
            result=result,
            files=files,
            test_results=test_results,
            open_issues=open_issues,
            return_id="gnom-" + digest([binding.key, delivery_id]),
        )
        # Store stable minimal return metadata. No prompt/result/file contents.
        body_hash = digest({key: value for key, value in payload.items() if key != "created_at"})

        def mutate(record):
            prior = record["deliveries"].get(delivery_id)
            if prior and prior["hash"] != body_hash:
                raise BindingError("delivery_conflict")
            if not prior and len(record["deliveries"]) >= 32:
                raise BindingError("delivery_capacity_reached")
            record["deliveries"].setdefault(
                delivery_id, {"hash": body_hash, "created_at": payload["created_at"]}
            )
            payload["created_at"] = record["deliveries"][delivery_id]["created_at"]

        self._change(binding, mutate)
        return {
            "payload": payload,
            "strict_binding": True,
            "sent": False,
            "review_status": "unverified",
            "project_completion_verified": False,
        }
