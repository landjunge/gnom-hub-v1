# Autonomes Agenten-Team — Pipeline & Rollen

**Repo:** `landjunge/gnom-hub-v1`  
**Baseline-Branch:** `baseline` (eingefrorener Stand)  
**Haupt-Issue (Anker):** #105  
**Kommunikation:** GitHub Issues + Pull Requests  
**Ziel:** GNOME Hub V1 fertigstellen, prüfen, iterativ verbessern.

---

## 1. Überblick

Fünf Agenten arbeiten parallel, aber synchronisiert über GitHub.  
Jeder Agent hat eine eigene Rolle, einen eigenen Prompt (`agents/*.md`) und reagiert auf Trigger (offene Issues, PRs, Commits).

Der **Koordinator** läuft durchgehend im Hintergrund und greift nur ein, wenn etwas hängt.

---

## 2. Die Pipeline (zyklisch)

1. **Einfrieren** — Baseline-Branch + Haupt-Issue #105 als Anker.
2. **Zerlegung** — Planer liest #105, legt Teilaufgaben an (Label `teilaufgabe`).
3. **Bau** — Builder nimmt eine offene Teilaufgabe, schreibt Code, öffnet PR gegen `baseline`.
4. **Prüfung** — Reviewer (Blind + Adversarial) prüft den PR: merged oder fordert Änderungen.
5. **Test** — Test-Agent prüft nach dem Merge, ob das Tool wirklich läuft. Meldet Fakten, öffnet Bug-Issues.

Dann zurück zu Phase 2, bis #105 als erledigt markiert ist.

### Wichtige Regeln
- Builder arbeitet **nacheinander** an Teilaufgaben (nie parallel an zwei).
- Reviewer sieht **nicht**, wer den Code geschrieben hat (Blind-Review).
- Reviewer ist im **Adversarial-Modus**: aktiv Fehler suchen, nicht bestätigen.
- Test-Agent ist **neutral** — lobt/kritisiert niemanden, berichtet nur Fakten.
- Koordinator stört die anderen nicht unnötig; meldet sich nur bei Blockaden.

---

## 3. Die Rollen

### Planer
- **Prompt:** `agents/planer.md`
- **Aufgabe:** Haupt-Issue lesen, in 2–4 konkrete Teilaufgaben zerlegen, als Issues mit Label `teilaufgabe` anlegen, mit #105 verknüpfen.
- **Trigger:** Start des Zyklus / neues Haupt-Issue.
- **Nicht:** Umsetzen, bewerten.

### Builder
- **Prompt:** `agents/builder.md`
- **Aufgabe:** Offene Teilaufgabe (`teilaufgabe`, offen) nehmen → Code schreiben → Branch von `baseline` → PR gegen `baseline` → PR mit Teilaufgabe verknüpfen → Status „in Bearbeitung".
- **Trigger:** Neue/offene Teilaufgabe.
- **Nicht:** Zwei Aufgaben gleichzeitig.

### Reviewer
- **Prompt:** `agents/reviewer.md`
- **Modus:** Blind-Review + Adversarial.
- **Aufgabe:** Offene PRs prüfen (Qualität, Lesbarkeit, Tests, Plan-Treue). Mindestens 3 Probleme pro PR suchen. Bei Problemen: Kommentar + „Änderungen angefordert". Bei OK: Merge, Teilaufgabe schließen, #105 aktualisieren.
- **Trigger:** Neuer offener PR.
- **Nicht:** Zwei PRs gleichzeitig.

### Koordinator
- **Prompt:** `agents/koordinator.md`
- **Aufgabe:** Überblick über Issues, PRs, Agenten-Aktivität. Bei Blockade: neu zuweisen, eskalieren, Plan anpassen. Haupt-Issue als lebendiges Dokument halten.
- **Trigger:** Dauerhaft im Hintergrund.
- **Nicht:** Unnötig stören; bei „alles läuft“ still bleiben.

### Test-Agent
- **Prompt:** `agents/test-agent.md`
- **Aufgabe:** Nach jedem Merge Tests ausführen (oder schreiben, falls keine existieren). Ergebnis als Kommentar in #105. Bei Fehlern: neues Issue mit Label `bug` + Verweis auf Merge-Commit.
- **Trigger:** Neuer Merge.
- **Nicht:** Bewerten, loben, kritisieren — nur Fakten.

---

## 4. Gegenmaßnahmen gegen Stillstand

**Problem:** Builder läuft nur bei manuellem Anstupsen → Zyklus bricht ab.

**Lösung (Zwischenaufgabe #108):**  
Builder baut zuerst ein **Polling-/Webhook-Skript**, das auf neue Issues mit Label `teilaufgabe` reagiert und den Builder automatisch startet. Danach arbeitet er #106, dann #107 ab.

---

## 5. Start-Prompts (Beispiele)

### Planer (Kickoff)
```
Du bist der Planer-Agent im autonomen Team für Repo landjunge/gnom-hub-v1.

Lies Issue #105 (Haupt-Issue, Label agenten-team). Das ist dein einziger Anker und der aktuelle Projektstand.

Deine Aufgabe:
- Verstehe das Ziel: GNOME Hub V1 fertigstellen, prüfen, iterativ verbessern.
- Zerlege es in 2–4 konkrete, umsetzbare Teilaufgaben.
- Lege jede als eigenes Issue an mit Label "teilaufgabe", verknüpfe sie mit #105.
- Markiere sie als offen. Keine Bewertung, keine Umsetzung — nur saubere Zerlegung.

Arbeite nur auf dem Branch baseline oder davon abgezweigten Arbeits-Branches. Wenn du fertig bist, melde dich kurz im Haupt-Issue.
```

### Builder (Beispiel für #106)
```
Starte jetzt. Issue #106 ist offen, Label "teilaufgabe". Nimm sie, setze um, öffne einen PR gegen baseline.
```

---

## 6. Datei-Karte

| Was | Pfad |
|-----|------|
| Pipeline-Übersicht | `docs/AUTONOMOUS_AGENT_PIPELINE.md` (dieses File) |
| Kurzer Plan | `PLAN.md` |
| Planer-Prompt | `agents/planer.md` |
| Builder-Prompt | `agents/builder.md` |
| Reviewer-Prompt | `agents/reviewer.md` |
| Koordinator-Prompt | `agents/koordinator.md` |
| Test-Agent-Prompt | `agents/test-agent.md` |
| Haupt-Issue | #105 |
| Automatisierungs-Issue | #108 |

---

*Stand: Baseline-Branch. Bei Änderungen an Rollen oder Pipeline dieses Dokument aktualisieren.*