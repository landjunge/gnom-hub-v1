# Tests abgeleitet aus Gnom-Daten (HOT / WARM / COLD / E2E)

**Stand:** 2026-08-06 · Quelle: `data/hot`, `data/warm`, `data/cold`, `data/vector`, `data/e2e-*`, `data/workspace`

Nicht spekuliert — aus **echten User-Zeilen und Fakten** im Hub.

---

## 1. Was die Daten sagen (Häufigkeit)

| Thema | Hits (rough) | Typische User-Zeilen / Fakten |
|-------|--------------|-------------------------------|
| **Landing / HTML** | ~91 | `baue moderne landingpage`, Bean & Bloom full HTML, `landingpage` |
| **Todo / minimal** | ~59 | B1 tiny todo app, plain-text `tasks.txt`, 3-Spalten |
| **Execute / UI** | ~43 | Execute nach Brainstorm, Worker, Box 3 |
| **Flex / personal** | ~15 | Prefs in WARM, später Eve/Grok-Absicht |
| **Memory** | ~11 | WARM/HOT, „erinnerungen mit zeit“ |
| **TTS** | ~5 | `was ist mit tts`, Gedanken |
| **Tools / computer** | ~3 | Tools portfolio, inspect |
| **Push / Agents.md** | ~3 | Qualität vor Push (Coding-Gate, nicht nur UI) |
| **Chat-History** | ~2 | Terminal ↑/↓ (UI) |

**Diagnose-Wiederholungen (Schmerz):**  
`wo ist der fehler` · `prüfe die pipeline brainstorming` · `führe eine detaillierte Analyse… wo es hakt` · `mann nicht du die worker`

---

## 2. Was du wirklich wolltest (Produkt-Intents)

Aus den wiederholten User-Messages, nicht aus Roadmap-Marketing:

1. **Eine fertige HTML-Landing** (modern, hero, features, footer) — sichtbar in Box 3 / Datei  
2. **Brainstorm → Execute** muss laufen; **ein Worker** für die Page, keine 4× Müll  
3. **UI nicht einfrieren** (Send/Execute wieder bedienbar)  
4. **Memory** hält Präferenzen (Brand, Layout, todo-Ideen) — und soll **nicht** mit Test-Müll vollaufen  
5. **TTS / Gedanken** (selten, aber klar)  
6. **Tools/Computer-use** existieren und sind nutzbar  
7. **Flex merkt sich den Menschen** (Prefs, später Personen/Sites)  
8. **Wenn etwas fehlt:** System korrigiert Agenten, **du musst es nicht 100× sagen**  
9. **Chat-History wie Terminal** (↑/↓)  

---

## 3. Test-Matrix (was wir deshalb testen)

| ID | Intent aus Daten | Wie testen | Gate |
|----|------------------|------------|------|
| **T1** | Bean & Bloom / moderne Landing | Playwright S1: keyboard → brainstorm → execute → **RESULT.html ≥800** | hard |
| **T2** | Execute nach Brainstorm / UI unfreeze | B2 + B3 + S1 `can_execute` / free input | hard |
| **T3** | Ein Worker, volle HTML | S1: `workers_api==1` bei full_page + `html complete` / gates | hard |
| **T4** | Tools nicht tot | S5: tools/call + computer-use + Tools-Modal | hard |
| **T5** | Todo minimal (B1 history) | API B1 brainstorm/execute ideas path (kein full landing) | soft/API |
| **T6** | Topic switch / „nicht die worker“ | S2: TTS-Chat → todo/page task, Execute-Task = letzter echter Task | full suite |
| **T7** | Memory Prefs | Unit/API: WARM `User:` / Bean&Bloom facts survive clean | unit |
| **T8** | Flex personal absorb | Unit: `browse grok.com + Eve` → flex_facts | unit (done) |
| **T9** | Flex nudge bei Lücken | Unit: incomplete HTML → nudge worker1 | unit (done) |
| **T10** | TTS = Gedanken | Unit/mock: reasoning ≠ content; UI speaks thoughts | unit/integration |
| **T11** | Chat ↑/↓ History | Manual / light Playwright (localStorage hist) | soft |
| **T12** | Diagnose „wo hakt es“ | Optional: brainstorm diagnosis path no product-hallucination | soft |

**Default quality_check (Server an):** T1+T2+T3+T4 ≈ **S1 + S5** + B1–B3.  
**Full:** `--all` → S1–S5 deckt T1,T2,T3,T4,T6 + Soft-T5.

---

## 4. Was die Daten **nicht** fordern

- Multi-Workflow-Engine  
- 4 parallele HTML-Worker als Normalfall  
- Generische Security-Flex-Essays ohne Bezug zu dir  
- Tests ohne sichtbares Deliverable (panel-only PASS)

---

## 5. Abgleich Suite ↔ Daten

| Scenario-Script | Deckt Intent |
|-----------------|---------------|
| `user_scenarios_e2e.py` S1 | Landing Bean & Bloom (häufigster User-Task) |
| S2 | Topic-Switch / „mann nicht du die worker“ |
| S3 | Unklare Anfrage (seltener, aber Pipeline-Schmerz) |
| S4 | Clean + neuer Task (Reset-lastige Session-Historie) |
| S5 | Tools/Computer-use |
| `basic_tests` B1 | Todo brainstorm (viele cold entries) |
| B2/B3 | can_execute / UI unfreeze |
| Flex unit tests | personal absorb + nudge |

---

## 6. Regenerieren

```bash
# Daten ansehen (lokal)
python3 -c "..."  # or re-run miner in agent session
# Suite
python scripts/user_scenarios_e2e.py          # T1+T4
python scripts/user_scenarios_e2e.py --all    # +T2/T6/S3/S4
```

Wenn sich `data/warm` / cold User-Zeilen stark ändern: dieses Doc + Scenario-Prompts anpassen — **Tests folgen deinen Daten, nicht umgekehrt.**
