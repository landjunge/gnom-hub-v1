# Gnom-Hub – V1 Scope (harte Schnittmenge)

Stand: 05.08.2026

Nur das, was wirklich im ersten Wurf gebaut wird.
Alles andere bleibt im PRE_PLAN.md als Zielbild dokumentiert und wird später aktiviert.

---

## Ziel von v1

Ein lauffähiges, debuggbares System, mit dem man:

1. Frei brainstormen kann
2. Das Ergebnis destillieren lässt
3. Den Coordinator 1–2 Worker steuern lässt
4. Alles über eine klare Desktop-UI sieht und steuert

---

## Was in v1 **rein** kommt

### Agenten
- 4 feste Agenten: Brainstorm, Memory, Flex, Coordinator
- Bis zu 2 Worker (dynamisch)
- Doppelklick-Toggle für alle außer Memory
- Flex mit Presets (Standard: Security, weitere: Neutral / Researcher …)
- Live-Status über EventBus (active / disabled)

### LLM
- LLM-Manager
- Erster Test-Provider: **DeepSeek**
- Jeder Agent kann eigenes Modell + Key haben
- Free-Modelle nur wenn explizit aktiviert
- Budget-Schutz

### UI (Desktop-only, 13″ optimiert)
- 8 Agentenkarten: **140 × 100 px**, Abstand **5 px**
- 3 Boxen: **380 × 380 px**, Abstand **5 px**
- Box 1 = reiche Tooltip-/Erklärungsfläche (Titel + How-to + Beispiel)
- Box 2 = Brainstorm-Gedanken
- Box 3 = Worker-Ergebnisse
- Chatfenster (~150 px)
- Globaler Speicher-Button
- UI-Sprache: Basic English
- Box-1-Texte: mehrsprachig vorbereitet

### Memory
- HOT-Layer (session.json + mermaid_canvas.mmd)
- Einfaches Mermaid-Canvas + node_id Offload
- Memory-Agent immer aktiv

### Technik
- EventBus
- Schmale Interfaces / Facade
- Atomic Writes
- Relative Pfade (USB-fähig)
- Einfache Installation + Key.txt → .env

---

## Was in v1 **draußen** bleibt (geparkt)

- WARM / COLD Persistenz
- Vektor-Plugin + Hybrid Ranking
- Computer-Use / UI-Automation
- Volles Plugin-System + MCP
- God-Mode
- Workspace-Previews + temporärer/permanenter Workspace
- Self-Explaining Videos
- Volle Accessibility-Profile
- Mehr als 2 Worker
- Update-/Backup-System (nur Basis)
- Responsive / Mobile / Remote-Zugriff von Handy

---

## Design-Entscheidung Layout

Festes Desktop-Layout, optimiert für 13-Zoll und größer.
Keine Mobile-Responsive-Anforderungen.

Gesamtbreite Agentenkarten ≈ Gesamtbreite der drei Boxen (≈ 1150–1155 px).

---

**Ende V1 Scope**
