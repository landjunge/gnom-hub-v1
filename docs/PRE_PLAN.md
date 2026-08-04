# Gnom-Hub – Pre-Plan (Stand: 04.08.2026)

Vollständige Zusammenfassung aus dem gesamten Brainstorming.
Nichts Wichtiges soll verloren gehen.

---

## 1. Grundidee

Ein lokales, portables Multi-Agenten-System mit klarem Ablauf:

**Erst freies Brainstorming → dann automatische Ausführung**

Das System soll vom USB-Stick laufen können und sowohl schlank lokal als auch mit Cloud-LLMs arbeiten.

---

## 2. Architektur

### Feste Agenten (4)
- **Brainstorm-Moderator** – führt die ungestörte Ideensammlung mit dem User
- **Memory-Agent** – verwaltet Kurz- und Langzeitgedächtnis
- **Security-Guard** – prüft hauptsächlich eingehende Daten (Prompt-Injection etc.)
- **Coordinator** – analysiert das Brainstorming, entscheidet wie viele Worker nötig sind und steuert sie

### Dynamische Worker (bis zu 4)
- Werden vom Coordinator bei Bedarf erzeugt
- Können als Presets gespeichert und wiederverwendet werden
- Haben Skills und können bei Bedarf Tools/Plugins nachladen

### Besondere Modi
- **God-Mode**: Volle Rechnerrechte (bewusst aktivierbar, inkl. Kernel-Änderungen möglich)
- Normal-Modus mit sinnvollen Grenzen

---

## 3. Gedächtnis

- **Symbolisches Kurzzeitgedächtnis** (Mermaid-Canvas + Context-Offload mit node_id)
- **Geschichtetes Langzeitgedächtnis** (HOT / WARM / COLD)
- Permanentes Archiv
- Wichtige Brainstorming-Ergebnisse werden persistent gespeichert
- Kontext-Kompression bei langen Sessions

---

## 4. Benutzeroberfläche

### Oben
- Header
- 8 Agenten als **Visitenkarten** (horizontal, feste Breite)
  - Zeigt: Tokenverbrauch, aktuelle LLM, Online/Offline-Status
  - TTS-Checkbox (wenn aktiv → Gedanken des Agenten werden vorgelesen)
  - 1-Pixel-Rahmen, der bei Aktivität in Echtzeit pulsiert
  - Jeder Agent hat eine eigene feste Rahmenfarbe

### Drei Boxen (ca. 300–400 × 300–400 px)
- Alle mit 1-Pixel-Rahmen
- Rahmenfarbe wechselt zur Farbe des Agenten, der die Box gerade benutzt
- Pre-Rendering für Inhalte

**Box 1 – Arounder (interaktive Kontext-Box)**
- Hover-Erklärungen über Buttons, Regler, Elemente
- Agenten können hier Vorschläge machen und kommunizieren
- Zeigt live Auswirkungen von Schiebereglern
- Mehrsprachig (DE/EN, erweiterbar)

**Box 2 – Brainstorm-Gedanken**
- Nur die destillierten, wichtigen Gedanken und Zusammenfassungen
- Persistent (verschwindet nicht im Chat)

**Box 3 – Worker-Ergebnisse**
- Live-Preview der Ergebnisse der Worker

### Darunter
- **Chatfenster** (ca. 150 px hoch, volle Breite)
  - Mit Spracheingabe (Speech-to-Text)
  - Als eigenes Modul

### Weitere UI-Elemente
- System-Button
- Hilfe-Button
- Globaler Speicher-Button (speichert alles – einziger zentraler Save)
- Agent-Tuning-Seite (beim Klick auf Agent):
  - Prompt anzeigen & bearbeiten (ca. 300×300, scrollbar)
  - 5 Schieberegler daneben (ca. 300×300):
    1. Temperature
    2. Top-P
    3. Max Tokens
    4. Frequency Penalty
    5. Presence/Repetition Penalty
  - Live-Erklärung der Regler in Box 1

---

## 5. Workspace-Konzept

**Zwei Workspaces:**

1. **Temporärer Workspace** (Sammelplatz)
   - Alles, was Agenten erzeugen, landet zuerst hier
   - Vorschau als kleine Kästchen (Seiten-Preview + Code-Preview)
   - Checkbox + „Übertragen/Speichern“ → verschiebt ins permanente System
   - Button „Temporären Workspace löschen“

2. **Permanenter Workspace**
   - Nur bewusst übernommene Ergebnisse

---

## 6. Computer-Use / UI-Automation Modul

Eigenständiges Fähigkeitspaket, damit Agenten Programme und Webseiten bedienen können.

Enthält:
- Screen-, Fenster-, Element- und Scrolling-Capture
- Seiten-Capture (Web)
- Video- und Audio-Capture
- OCR (Text aus Bildern erkennen)
- UI-Element-Erkennung
- Maus- und Tastatursteuerung
- Aufnahme von Abläufen (Recording)
- Speichern von Abläufen als wiederverwendbare Skills

Ziel: Agenten können lernen, Programme und Formulare zu bedienen und diese Fähigkeit später wiederverwenden.

---

## 7. Installation & Betrieb

- Wirklich einfache Installation
- Erkennt automatisch:
  - Betriebssystem
  - Ob auf USB-Stick installiert wird
  - Welches lokale LLM geeignet ist
- Vorschläge: Schlank / Etwas größer / Empfohlen
- Update-System
- Backup-System
- API-Keys:
  - User legt `Key.txt` auf dem Desktop ab
  - System liest sie und schreibt sie in private `.env` (nicht öffentlich)

---

## 8. Weitere wichtige Features

- TTS von Anfang an
- Spracheingabe (API-Key oder Mac-System-Fallback)
- Jeder Agent kann eigenen API-Key nutzen
- Übersichtliches LLM-Zuweisungssystem
- MCP (Model Context Protocol) Unterstützung
- Plugin-System
- Skills für Agenten
- Agenten können bei Bedarf Tools selbst nachladen
- Internet-Surfen
- Vollständige Rechner- + Maussteuerung (im God-Mode uneingeschränkt)
- Ein-Klick „Sauberer Zustand“ (setzt temporäre Dinge zurück, ohne Langzeitgedächtnis)
- Mehrsprachigkeit (Deutsch + Englisch, erweiterbar)

---

## 9. Technische Verbesserungen (explizit eingebaut)

1. Starkes Checkpointing / Resume
2. Leichte Nachvollziehbarkeit (Light Tracing)
3. Automatische Qualitätsprüfung der Worker-Ergebnisse
4. Kontext-Kompression für lange Sessions
5. Ein-Klick „Sauberer Zustand“

---

## 10. Modul-Struktur (Vorschlag)

- Core / EventBus
- AgentManager
- MemoryModule
- BrainstormModule
- WorkerModule
- UI Module (Karten + Boxen + Chat)
- TTS Module
- ResetModule
- Plugin / MCP Module
- Workspace Module
- Computer-Use / UI-Automation Module
- Install / Update / Backup Module

Kommunikation über EventBus + klare, schmale Interfaces.

---

## 11. Vorgeschlagene Umsetzungs-Reihenfolge (Pre-Plan Phasen)

**Phase 0 – Fundament**
- Modulare Projektstruktur
- EventBus + Schnittstellen
- Einfache Installation + USB-Erkennung
- Key.txt → .env System

**Phase 1 – Kern-UI**
- Header + Agenten-Visitenkarten
- 3 Boxen inkl. Pre-Rendering und farbigem Rahmen
- Chatfenster mit Spracheingabe
- Globale Buttons

**Phase 2 – Agenten-Grundgerüst**
- 4 feste Agenten (Brainstorm-Moderator zuerst)
- Agent-Tuning-Seite + 5 Schieberegler
- TTS + Checkboxen
- God-Mode

**Phase 3 – Memory & Workspace**
- Mermaid-Gedächtnis + Langzeitgedächtnis
- Temporärer + permanenter Workspace
- Kontext-Kompression
- Ein-Klick Sauberer Zustand

**Phase 4 – Dynamik & Qualität**
- Dynamische Worker + Presets
- Checkpointing / Resume
- Light Tracing
- Automatische Qualitätsprüfung der Worker-Ergebnisse

**Phase 5 – Erweiterungen**
- Plugin-System + MCP
- Skills + Tool-Nachladen
- Computer-Use / UI-Automation Modul
- Update- + Backup-System
- Mehrsprachigkeit

---

## 12. Offene / später zu klärende Punkte

- Genaue Farbzuordnung der 8 Agenten
- Genaues Verhalten des Arounders bei komplexen Hover-Situationen
- Konkrete lokale LLM-Empfehlungen für 4-Kern-Systeme
- Wie aggressiv die automatische Qualitätsprüfung sein soll

---

**Ende des Pre-Plans**
Stand: 04.08.2026 – aus dem vollständigen Brainstorming extrahiert.
