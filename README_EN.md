# Gnom-Hub-V1 — English

Gnom-Hub-V1 is an independent local multi-agent desk. **Send** is conversation;
**Start work** explicitly starts the existing coordinator/worker pipeline.
Direct KiraBridge→Codex work does not require Gnom. This is not an unattended
computer-control service. See [German guide](README.md).

## Install and start

The existing terminal quick start is:

```sh
curl -fsSL https://raw.githubusercontent.com/landjunge/gnom-hub-v1/main/scripts/get.sh | sh
```

For an existing checkout, use `./scripts/install.sh`, then `./scripts/start.sh`
and open `http://127.0.0.1:8080/` (legacy desk) or `/v4`. Git and Python 3.10+
are required. macOS/Linux use this source/terminal path; no new native package
or fresh-device acceptance is claimed here. Existing `.venv` and personal data
are preserved by the documented installer. Personal data belongs in the sibling
`WS-gnom-hub-v1` or an explicitly configured `GNOM_WS`, not in Git. Never commit
Key.txt, .env, credentials or personal user.db. No Docker/sudo step is added.

The existing developer installation adds the `.[dev]` extras; this change does
not rebuild or reinstall a healthy user runtime. Source version is 3.10.1.

## Providers and profiles

The default `standalone` desk keeps `GNOM_TOLLGATE_LLM=1`: cloud requests require
the TollGate package/connection. Missing or denying TollGate never causes a direct
paid fallback. An operator may explicitly choose the existing legacy opt-out
`GNOM_TOLLGATE_LLM=0`; that path does not enforce a durable whole-workflow dollar
budget or stop guarantee. Explicit `ollama/*` routing is local. Configure actual
provider access through the existing Key/System path, never through chat.

The new operator-selected `GNOM_EXECUTION_PROFILE=controlled` currently **blocks
model starts** until verified workflow binding, an enforceably bounded provider
adapter and protected access are connected. No request boolean, imported prompt
or matching ID can activate it. A worker does not fall back to the system key in
that profile. No existing runtime setting was changed by this source work.

## Handoff, return and cancellation

The new local adapter stores only bounded mapping metadata in the existing
SQLite kv store; it is not a second execution queue. Import never starts a job.
Original ThreadDesk IDs (including colons), separate Bridge task/run/attempt,
actor/consumer and content references remain distinct. Host authorization, fixed
issued/run lookup and an observed own job receipt are required for active use.
Metadata alone is `unverified_pending_fixed_issuer`. A lost volatile job becomes
`unknown`; reconnect never automatically repeats it.

A prepared `threaddesk.return.v1` remains delivered/unverified and unsent. The
caller must use ThreadDesk strict import and a separate review/user decision.
Existing Keep/Peek memory packets are not this working return protocol. This
foundation is not yet an installed ChatGPT→Gnom→ThreadDesk roundtrip.

A stop response separates TollGate's persistent EFFECTIVE/PENDING barrier, Gnom's
cooperative cancellation request, observed local finalization and unknown
external effects. It does not prove provider rollback or kill arbitrary processes.
Protected account/browser work remains unavailable: the existing global browser
session/debug path is not an isolated credential boundary.

## Updates and limits

Technical GitHub tags/releases exist, including v3.10.1. They are not evidence of
new installation, provider-budget or user acceptance for this integration. The
current updater only checks metadata; `updates.apply()` still returns
`not_published`. It does not install main or a new release. Back up before an
actual version switch and use the existing System backup/restore path.

The shared NetzwerkPunkt grey CSS foundation is retained unchanged. Legacy and
/v4 are separate surfaces; /v4 still contains German UI strings, so complete
English UI coverage is not claimed. See the exact tests, pins and remaining
prerequisites in [the source integration record](docs/SEVEN-TOOLS-GNOM-20261018.md).
The existing repository LICENSE remains authoritative; no license or release was
changed by this work.
