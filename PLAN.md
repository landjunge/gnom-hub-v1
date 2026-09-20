# Plan — GNOME Hub V1 (autonomes Agenten-Team)

## Phasen (zyklisch)
1. **Einfrieren** — Baseline-Branch prüfen, Haupt-Issue als Anker.
2. **Zerlegung** — Planer legt Teilaufgaben an (Label `teilaufgabe`).
3. **Bau** — Builder setzt eine Teilaufgabe um, öffnet PR.
4. **Prüfung** — Reviewer (Blind + Adversarial) merged oder fordert Änderungen.
5. **Test** — Test-Agent prüft nach Merge, meldet Fakten, öffnet Bug-Issues.

Dann zurück zu Phase 2, bis das Haupt-Issue erledigt ist.

Der Koordinator läuft durchgehend im Hintergrund.

## Agenten-Prompts
Siehe `agents/*.md`.