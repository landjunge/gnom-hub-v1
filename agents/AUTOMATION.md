# Agenten-Runtime

Ein Dispatcher liest GitHub und startet genau eine Rolle pro Tick über Headless Grok. Polling und der PR-Webhook bleiben optional; sie sind nicht der Hauptdienst.

## Pflicht

```bash
export GITHUB_TOKEN="$(gh auth token)"   # oder GNOM_GITHUB_TOKEN
export GNOM_GITHUB_REPO=landjunge/gnom-hub-v1   # Home: Issues, #105, baseline-SHA
# Kill-Switch: GNOM_AGENT_DISPATCH=0
```

`pick_job` läuft über alle Produkt-Repos, nicht pro Repo. Höchste Priorität gewinnt global (eine Rolle, ein Tick). Offene PRs kommen aus:

| Repo | Base |
|---|---|
| `landjunge/gnom-hub-v1` | `baseline` und `main` (`main` = baseline) |
| `landjunge/4AllPass` | `main` |
| `landjunge/tollgate` | `main` |
| `landjunge/threaddesk` | `main` |
| `landjunge/agent-authority-lab` | `master` |

Override der Watch-Liste:

```bash
export GNOM_GITHUB_REPOS="landjunge/gnom-hub-v1:baseline+main,landjunge/4AllPass:main"
```

Format: `owner/repo` oder `owner/repo:base` (mehrere Bases mit `+` oder `|`). Komma oder Whitespace. Ohne Env: die fünf Defaults. Dry-Run listet gefundene PRs als `seen-pr`.

`scripts/run_agent.sh` ruft `grok --prompt-file … --yolo --max-turns 80` auf. Der Prompt liegt in `agents/<rolle>.md`. Zusätzlicher Text (Poll/Webhook) kommt über stdin in dieselbe Datei, nicht als `grok -p "$(cat)"`.

Override pro Rolle (sonst `scripts/run_agent.sh <rolle>`):

```bash
export GNOM_BUILDER_CMD="scripts/run_agent.sh builder"
export GNOM_REVIEWER_CMD="scripts/run_agent.sh reviewer"
export GNOM_GROK_BIN=grok
export GNOM_AGENT_WORKDIR=/Users/landjunge/.grok/worktrees/gnom-hub-agents
```

## Start

```bash
# Worktree nur für Agenten (nicht den Desk-Clone)
git fetch origin baseline
git worktree add ~/.grok/worktrees/gnom-hub-agents origin/baseline

cd ~/.grok/worktrees/gnom-hub-agents
python3 scripts/agent_dispatch.py --once --dry-run
python3 scripts/agent_dispatch.py --once
python3 scripts/agent_dispatch.py --interval 45
```

macOS-Dienst: `deploy/gnom-agent-dispatch.plist` nach `~/Library/LaunchAgents/` kopieren, Pfade prüfen, `launchctl load`.

Stop: Prozess beenden, oder `GNOM_AGENT_DISPATCH=0`, oder `launchctl unload`.

State: `data/agent_dispatch_state.json` (gitignored unter `data/`). Einträge gelten 2 Stunden.

## Reihenfolge pro Tick

1. Offener PR mit Review *changes requested*, oder *comment* plus Blocker (CI rot, Draft, Merge-Konflikt) → Builder (Fixes auf demselben Branch)
2. Offener PR ohne Review oder Approve ohne Merge → Reviewer (jedes Watch-Repo)
3. `baseline` HEAD neu seit letztem Test → Test-Agent
4. Offene `teilaufgabe` ohne PR (stale `in-bearbeitung` nach 2h nochmal) → Builder
5. #105 offen, keine Teilaufgaben → Planer
6. sonst Stale/Warteschlange → Koordinator (Cooldown 1h)

Genau eine Rolle, ein Prozess. Launch-Fehler speichert keinen Start.

## Alt: nur Builder-Poll / Webhook

```bash
export GNOM_BUILDER_CMD="scripts/run_agent.sh builder"
python3 scripts/poll_teilaufgaben.py --once --dry-run
python3 scripts/github_pr_webhook.py --host 127.0.0.1 --port 8088
```

GitHub-Event für Review-Fixes ist `pull_request_review` mit `state=changes_requested` (nicht `pull_request` / Action `changes_requested`). Claim: bei Launch-Fehler wird `in-bearbeitung` wieder entfernt.
