# Worker stands / getrennte Arbeitsstände (GH-C04)

## Umfang / scope

Additiver **trusted in-process host**-Anschluss `gnom_hub.worker_stands.WorkerStands`
an `ExternalWork`, dessen bestehende SQLite-CAS-Auftragsquittung und den vorhandenen
`WorkspaceStore`. Kein neuer Scheduler, keine Queue, kein Netzwerkendpunkt und
kein automatischer Start durch Import, Registrierung oder Statusabfrage. Legacy-
Pipeline und Modell-/TollGate-Wege bleiben unverändert. Der Host muss diese
optionale kontrollierte Funktion ausdrücklich anschließen; sie läuft nicht bereits
in der installierten Benutzeranwendung.

Trusted operator configuration supplies distinct **already prepared Git worktrees**
and concrete worker callables. Requests/handoffs cannot choose commands, paths,
processes, credentials, Git operations or arbitrary adapters. No repository is
cloned, installed, merged or executed merely because it is referenced. Worktrees
separate accidental writes; they are **not a security sandbox** against hostile
same-user code. Real coding/WorkerAgent adapters still need their own scoped tools,
provider authorization, budgets and cancellation. This packet proves local dummy
workers, not those external execution boundaries.

## Vertrag / contract

`WorkerEndpoint(worktree: Path, execute: Callable[[WorkerContext], str])` wird nur
im vertrauenswürdigen Host konfiguriert. Maximal vier Endpoints mit unterschiedlichen
Git-Arbeitswurzeln; keine im Auftrag übermittelten Dateisystemwurzeln. Ein optionaler,
separater `integration_worktree` gehört ebenfalls zur Hostkonfiguration.

`Assignment(subtask_id, worker_id, role, base_commit, request_hash, depends_on=(),
review_target=None)` enthält ausschließlich gebundene Metadaten:

- IDs: `[A-Za-z0-9_-]{1,64}`, maximal vier Unteraufträge, ein Endpoint pro Unterauftrag.
- Rollen: `plan`, `develop`, `review`. Review braucht genau benannten Entwickler-
  Unterauftrag als vorhandene Abhängigkeit. Keine zyklischen/fremden Abhängigkeiten.
- Vollständiger Ausgangscommit (40/64 Hexzeichen) und SHA256 des konkreten Auftrags
  nach bestehendem `external_work.digest(task)`; Quellidentität und Inhalt getrennt.
- Gleicher registrierter Plan ist idempotent. Rollen-, Quellen-, Auftrags- oder
  Abhängigkeitsänderungen am selben Auftragsrecord sind `worker_assignment_conflict`.
  Für Revisionen ist ein neuer ausdrücklich ausgestellter Elternauftrag nötig.

`register(binding, assignments)` schreibt nur Metadaten in `workers` des bestehenden
ExternalWork-Records. `run(binding, subtask_id, task=...)` prüft Hostautorisierung,
aktuellen ausgestellten Run, beobachteten eigenen laufenden Job, Stoppstatus,
Abhängigkeiten und echten sauberen Git-HEAD. Es persistiert den Claim **vor** dem
konkreten Workeraufruf. Die Methode ruft genau den konfigurierten Endpoint synchron
auf, niemals selbst einen Scheduler oder zweiten Ausführungsweg. Tasktext wird nicht
im Quittungsrecord gespeichert. Endpoint-Ergebnisse bleiben untrusted Daten.

`WorkerContext` enthält Assignment, unveränderte Eltern-Task-ID/Run-ID, feste
Worktree-Wurzel, tatsächlich beobachteten Startcommit, gegebenenfalls exakten
`reviewed_commit` und den gebundenen Tasktext. Ein Reviewer muss beim Start und
Abschluss exakt auf dem tatsächlich gelieferten Entwicklercommit stehen; ein
behaupteter Commit im Modelltext reicht nicht. Git-Prüfungen sind begrenzt
(5s/4096 Ausgabebytes) und melden nur stabile Fehlercodes.

Lieferung: höchstens64KiB UTF-8; sauberer beobachteter Ergebniscommit muss vom
Startcommit abstammen. Jedes Artefakt erhält einen opaken Namen aus Elternbindung,
Run, Unterauftrag und einmaliger Claimkennung. Exklusiver Dateianlageweg mit
`O_EXCL/O_NOFOLLOW`,0600,fsync in bestehendem `temp`; keine globale `result.txt`,
kein stilles Überschreiben und keine automatische Kopie nach `selected`.
Quittung speichert Artefaktname/Hash und echte Git-Stände, keine Modellantwort.
Worker-Fehlertexte werden nicht in die Quittung übernommen.

## Zustand, Rückgabe und Zusammenführung

`status(binding)` unterscheidet persistente `pending/running/delivered/failed` und
beobachtete `ready/waiting/blocked/unknown`. Ein laufender Claim ohne lokale aktive
Aufrufbeobachtung bleibt **unknown**, mit `restart_allowed=false`. Auch eine erneute
Hostinstanz startet nichts nach; unklarer Ausgang verlangt manuellen Belegabgleich.
Ein abgebrochener Aufruf kann bereits Wirkungen erzeugt haben. `failed` garantiert
keine Wirkungslosigkeit. Es gibt hier weder automatische Wiederholung noch Recovery-
Fortsetzung. Ein fehlgeschlagener Worker sperrt nur seine abhängigen Unteraufträge;
unabhängige werden bei ihrem nächsten ausdrücklichen Aufruf weiter zugelassen.

`prepare_return(binding, subtask_id)` liest genau das hashgebundene eigene Artefakt
und benutzt den bestehenden `ExternalWork.prepare_return`/ThreadDesk-Rückgabebauer.
Jeder Unterauftrag erhält eine stabile eigene delivery-/return-ID. Gleiche Lieferung
ist wiederholbar, abweichender Inhalt bleibt Konflikt. Der bestehende Elternjob muss
beobachtet `done/finished` sein. Ausgabe ist **prepared, unsent, unverified**; keine
Inbox-Zustellung oder Nutzerannahme wird erfunden. Git-Beobachtungen in `test_results`
sind ausdrücklich Quellenbelege, **keine Funktionsprüfung**.

`merge_proposal(binding, subtask_id, expected_base=...)` ist ein ausdrücklich
angeforderter **Vorschlag**, kein Merge. Er braucht gelieferte Entwicklung und
separaten gelieferten Reviewer auf exakt demselben Ergebniscommit, unveränderte
hashgebundene Artefakte und einen tatsächlich sauberen Integrations-HEAD auf dem
vereinbarten Ausgangscommit. Er nennt base/result/reviewed commit und liefert
`merge_performed=false`, `review_status=unverified`, `operator_merge_required=true`.
Auch dies ist keine Aussage über Qualität oder Projektabnahme. Danach muss der
Operator den Zielstand erneut prüfen und bewusst zusammenführen.

Fehlende Berechtigung/Issuer/Job, bereits angenommener Unterauftrag, falscher
Request-/Quellpin, fremde/zyklische Abhängigkeit, schmutziger Worktree, unpassender
Reviewer, geändertes Artefakt oder abweichender Integrationsstand führen zu konkreten
stabilen Fehlercodes. Keine Fehlermeldung enthält Tasktexte, Pfade oder Secrets.

## Bedienbeispiel für einen vorhandenen Host / host example

```python
from gnom_hub.external_work import digest
from gnom_hub.worker_stands import Assignment, WorkerEndpoint, WorkerStands

# external is already authorized, issued/run-bound, with an observed own job.
# workspace is the existing WorkspaceStore. These paths/callables are host config.
stands = WorkerStands(external, workspace, {
    "worker1": WorkerEndpoint(developer_worktree, configured_developer),
    "worker2": WorkerEndpoint(reviewer_worktree, configured_reviewer),
}, integration_worktree=operator_target)
stands.register(binding, [
    Assignment("code", "worker1", "develop", base, digest(code_task)),
    Assignment("review", "worker2", "review", base, digest(review_task),
               depends_on=("code",), review_target="code"),
])
code = stands.run(binding, "code", task=code_task)
# Operator deliberately prepares reviewer_worktree at code["result_commit"].
review = stands.run(binding, "review", task=review_task)
proposal = stands.merge_proposal(binding, "code", expected_base=base)
# No merge/start/send occurs here. Existing host finalizes the parent job.
packet = stands.prepare_return(binding, "code")  # only after done/finished
# Caller may explicitly submit packet using the existing strict TD import.
```

## Grenzen / remaining acceptance

No real provider, account, user repository or installed runtime was used. No UI-
quality improvement, full team/Inbox roundtrip, protected tool execution or external
review identity is claimed. Role names express configured local responsibilities,
not authenticated human identities. Existing host-authorized job and issued-run
checks are required; caller labels cannot create that authority. Real endpoints,
actual cancellation/provider control and a deliberate operator merge remain separate
integration requirements. Current evidence: [GH-C04 source record](GH-C04-20261018.md).
