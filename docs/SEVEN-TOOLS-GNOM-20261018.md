# Gnom-Hub-V1: GH-C01/02/03 foundation and GH-R01

Order `seven-tools-build-20261018-1833`. Base main
`8108c64563694e46e813a807174b238d7e2c5b6c`, version 3.10.1.
Worker: Codex `/root/fourallpass_protected`, exclusive worktree
`.worktrees/seven-tools-20261018`, branch `feat/seven-tools-20261018`.
Foreign dirty root/worktrees, live services, credentials and user databases were
not changed. No native build, release, deployment, provider call or new account.

## Integration review: strict observation receipt

The observation path now uses the same exact-True host-receipt check and sanitized
failure handling as attach/stop. Previously a truthy nonboolean could pass this
one observation check, and host exception text could escape. Six new negative
cases plus the existing volatile-job-loss case passed (seven checks). No provider,
live job or user data was used. This is a source defect found during review, not
evidence of a previous production incident.

Der Leseweg prüft jetzt dieselbe echte boolesche Hostquittung wie Zuordnung und
Stopp. Fremde Fehlertexte werden durch job_receipt_unavailable ersetzt; andere
wahrheitsähnliche Werte bleiben abgewiesen. Keine Statusabfrage startet Arbeit.

## Current start/control map

| Path | Actual boundary | Result of this slice |
|---|---|---|
| Send/chat | Existing chat route and pipeline | No new auto-execute; unchanged |
| Execute / explicit start confirmation | Existing JobsMixin + pipeline lock | No second queue/start path added |
| Existing cloud provider | LLMManager → TollGate by default | Missing forced gate never falls through to direct provider |
| Explicit legacy standalone opt-out | Operator `GNOM_TOLLGATE_LLM=0` | Still separate, no whole-workflow budget/stop guarantee |
| Controlled profile | Operator `GNOM_EXECUTION_PROFILE=controlled` | Blocks model starts before key/route/provider selection until actual integration prerequisites exist |
| Handoff import | New local ExternalWork, host authorization + fixed issued lookup | Bounded metadata only; accepted/unverified, never execution |
| Existing own job mapping | Actual TD run lookup plus host-observed Gnom receipt | Original IDs preserved, durable mapping; no caller boolean grants ownership |
| Stop | Real local TG barrier, then existing bound cancel_job | EFFECTIVE/PENDING kept; cancelling is not local finalization |
| Return | Existing TD return builder, explicit caller strict import | Prepared/unverified/unsent; never automatic acceptance |
| Keep/Peek | Existing threaddesk_ops.py memory packet | Preserved, not relabeled as a working return protocol |
| Browser | Existing global `_SESSION` and debug/eval path | Not a protected account boundary; no shared-session account work enabled |

## Local adapter contract

`ExternalWork(database, hub, authorize=..., issued_lookup=...,
verify_job_receipt=..., workflow_control=...)` is a trusted **in-process host**
assembly. No unauthenticated HTTP endpoint or model-supplied callback/config is
added. Standalone Gnom does not require ThreadDesk/KiraBridge to operate.

The host must supply actual configured operator authorization, a fixed ThreadDesk
issued-record lookup and an independently observed own Gnom job receipt check.
Default missing callbacks fail closed. Imported `confirmed`/`source_authenticated`
booleans, principal strings, hashes or matching IDs are not authority proofs.
The source contains no active production assembly of these callbacks.

`RunBinding` retains project/workflow, handoff ID/revision, thread, original task ID
(including colon), separate Bridge task/run, actor/consumer/attempt/hash and local
operator/principal references. Handoff/source/thread revisions remain distinct.
`accept(packet,binding)` checks the exact issued payload, stores only mapping,
source refs and hash metadata, and returns
`binding_verification=unverified_pending_fixed_issuer`, `ran:false`.

`attach_job` requires exact current TD saved run fields and a host-observed job
receipt. It binds an already started job; it does not start one. A durable job
ownership entry prevents assigning that job to a different handoff. No broad
`cancel_busy`/foreign-session control is used. New KV updates use SQLite
BEGIN IMMEDIATE and compare/exchange in the **existing** kv table: max 1000 run
and 1000 job mappings, 64KiB record bound, max 32 delivery fingerprints per run.
Capacity/corruption/conflict fail closed; no historical records are pruned.
Prompts, credential material, result text or complete files are not persisted.

`observe` reads the existing volatile job. Missing RAM state returns `unknown`,
`restart_allowed:false`; it never restarts, resumes or creates another task.
`stop` requires a previously checked own mapping and current host authorization.
That recorded ownership remains stoppable if TD disconnects. It invokes the real
TG scope barrier and then only the bound Gnom cooperative cancel route. A pending
TG lock is PENDING, never EFFECTIVE; local abort is confirmed only after observed
cancelled+finished state. Provider/browser rest effects remain unknown.

`prepare_return` uses the actual optional ThreadDesk return builder and stable
bounded delivery IDs/hashes. It requires a finished observed job and fresh TD
run lookup. It returns the `threaddesk.return.v1` payload plus
`strict_binding:true`, `sent:false`, `review_status:unverified`.
The caller explicitly imports/reviews it through TD. No callback retry queue,
TD database write or auto-send was added. Same-ID changed content conflicts.

## Abnahme / evidence

Compatible source dependencies used only in isolated synthetic tests:

- ThreadDesk `05403916e549e1060f839ccbaf36a5cb90413776` (PR76): real
  issued/run lookup, existing builder and strict receive; delivered remains
  unverified and original colon task ID is retained.
- TollGate `c3a062d89cd3be449cb61976149ee5d455d67b8a`: actual local workflow
  control; EFFECTIVE/PENDING and cooperative cancellation are separate.

No adapter uses a fabricated Allow token or a submitted boolean as proof.
No actual accepted Bridge run or real provider identity is claimed by these
synthetic fixture IDs. Model work/paid calls/personal vaults were not used.

Targeted tests cover no-start import, duplicate/content/owner conflicts, missing
operator/issuer/run/job receipt/gate, bounded storage/corrupt data, lost volatile
jobs, real TG pending/effective stop, only-own cancellation, strict TD return
and stable repeated delivery. Route tests exercise the **actual** missing-package
import path without mocking admission; opt-out cannot activate controlled mode.
Full unit gate was run once; exact totals/follow-up below. No repeated unchanged
broad suites. Ruff format/check and Mermaid/docs-index gates apply before commit.

## Remaining prerequisites / no completion overclaim

| Package | This source | Remaining requirement |
|---|---|---|
| GH-C01 | Import/run/job/return foundation + synthetic actual TD contracts | Trusted installed issuer/Bridge start receipt assembly; full question/answer/team/Inbox roundtrip and user decision |
| GH-C02 | Real TG stop + bound cooperative Gnom cancel adapter | Actual provider/browser abort connection and KB-C04 operator profile; no arbitrary process kill guarantee |
| GH-C03 | Forced gate failure fixed; controlled mode fail closed, no worker→system-key fallback | Enforced per-action provider quote/whole-workflow money reservation + protected FP secret boundary at actual dispatch |
| GH-C04 | Additive trusted ExternalWork host adapter: two isolated dummy workers, exact Git/reviewer commits, immutable outputs and dependency/unknown/merge checks ([contract](WORKER_STANDS.md), [evidence](GH-C04-20261018.md)) | Installed host/real worker and controlled provider connection; full team/Inbox/user acceptance remains separate |
| GH-C05 | No protected account use enabled | FP-C03 isolated login/cookie/debug boundary; current global session does not qualify |
| GH-D01 | Exact shared np CSS retained; /v4 clarification/answer and controlled denial visibly checked DE/EN with isolated synthetic API | Full DE/EN conversation/team/Inbox acceptance across separate legacy and /v4 UIs, not inferred from synthetic tooltips/status tests |
| GH-R01 | DE/EN profile/start/update/return/stop claims reconciled | Runtime/provider/package acceptance remains separately scoped |

Technical releases exist (e.g. v3.10.1); current updates.check reads metadata and
updates.apply still returns not_published. This source change does not turn them
into a newly approved installer/release. Existing license/marks remain unchanged.


### Actual check results

- Route/binding/stop/return tests: 26 passed with matching actual TD/TG source
  directories on PYTHONPATH (synthetic fixtures only).
- Repository unit gate run once: 1058 passed; two newly added optional integration
  tests initially had a fixture registration error. That fixture defect was
  corrected and those paths passed in the targeted run; unchanged 1058 tests
  were not rerun as busywork. CI supplies a fresh complete gate at the PR pin.
- The independent /v4 polling defect was corrected: a finished `clarify` job
  releases polling for the user's question, matching legacy behavior. Actual
  JavaScript function execution plus existing /v4 route/assets: 9 passed.
- Ruff check/format, existing generated JS/CSS checks, docs index and Mermaid
  gates passed. Portable np CSS blob remains unchanged.
- At the initial source pin, configured real-user Chrome CDP default9222 was not reachable. No existing
  foreign Chrome tab/runtime was redirected, and no paid live-model quality run
  was started. The bounded JS probe is not a full visible /v4 conversation/team
  or complete DE/EN acceptance. The existing German /v4 copy remains explicit.

### Isolated visible follow-up / sichtbare Folgeprüfung

Parent source `8b8fb4313fbef0fbc5388c980ebb20544f684ee0`; follow-up source is
the commit containing this section and the versioned browser proof. Actual
served asset SHA256 values are recorded in
[`evidence/seven-tools-20261018/browser-proof.json`](evidence/seven-tools-20261018/browser-proof.json).
The harness is [`../scripts/seven_tools_ui_probe.py`](../scripts/seven_tools_ui_probe.py).

The existing real-user suite's headed **real Google Chrome** fallback was reused
with a fresh temporary profile because CDP was unavailable. Only an ephemeral
loopback synthetic API served this worktree's actual HTML/JS/CSS. Outbound
requests outside that fixture origin were blocked. No existing browser tab,
Gnom runtime, credentials, user workspace, provider or model was used. The
fixture's legacy bootstrap enable-all response only returns dummy agent records;
it does not change any real agent setting.

- Both DE and EN: click Start → actual V4 polling receives finished `clarify` →
  question becomes answerable → focus/Tab/Shift+Tab → answer → explicitly
  **synthetic, unverified** delivery. Exactly one synthetic start, two job polls
  and one answer per language; no hidden retry or real execution.
- Visual inspection exposed a half-width question card with truncated answer
  options. An active question now occupies the available grid width; answer
  labels wrap and remain keyboard reachable. Ordinary offered-choice grids keep
  their existing layout. Screenshots include the long question and focus ring.
- Controlled profile: V4 Start/Send stay disabled and the header explains the
  missing integration, including the accessible title/label. Both V4 and legacy
  cards now show blocked rather than a misleading working animation. Legacy LLM
  badge and System explanation agree, even with a configured-key claim.
- Small viewport 1024×700 and 125% zoom were inspected with the existing desktop
  scroll policy. No new responsive composition or complete translation is claimed.
  Navigation and other existing copy still contain German.
- Setup notes no longer claim that a forced missing TollGate uses the direct
  key. Targeted DE/EN unit cases verify missing-gate and controlled-profile
  explanations without reading a real workspace or secret.
- Follow-up setup, actual JavaScript polling, agent-status/detail and existing
  quiet-card tests: **43 passed**. No unchanged full local suite was repeated.

Six PNG screenshots and the timestamped structured report are stored beside the
proof JSON. This establishes the tested **UI/API-fixture behavior** only. It is
not a model-quality score, trusted issuer/Bridge/provider/OS acceptance, real
controlled execution or deployment. The open prerequisites above remain open.

The first PR CI passed all three complete Python matrices (3.10/3.11/3.12).
Its lint failure was the generated Mermaid inventory's shifted README line,
not a runtime failure; that inventory is corrected in this follow-up. No broad
unchanged local suite was repeated merely to increase the test total.

Local full quality_check.sh was not used against another running :8080 service:
its existing live branches would exercise that service. In-process unit/static
checks above are scoped to this source and isolated data. No pipeline-quality
improvement, user acceptance or deployment is inferred from the test totals.

### Cause qualification

The old missing-package branch attempted to fall through to the legacy route.
Its later real `_tollgate_admit` was itself fail-closed when forced; the old
positive fallback test mocked that admission away. This work does **not** claim
an observed successful paid bypass in the previous running product. It removes
the inconsistent fallback branch and tests the actual import-failure path without
mocking admission. No regression or real provider charge is invented.
