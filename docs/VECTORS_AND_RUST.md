# Vector models · vector DBs · Rust app? (honest notes)

## 1. Modelle vergleichen ≠ Vektordatenbank

| Begriff | Was es ist | Bei Gnom heute |
|---------|------------|----------------|
| **Embedder / Modell** | Text → Zahlenvektor (bow, char_ngram, **fastembed**, sbert, …) | umschaltbar |
| **Vector store / DB** | Speichert Vektoren + sucht (cosine / ANN) | **lite** JSONL + BM25/cosine im Prozess |
| **ANN index** (HNSW etc.) | Schnelle Suche bei Millionen Docs | **nicht** nötig für Desk-Facts |

**Modell vergleichen** = Qualität der *Ähnlichkeit* (besserer Embedder → bessere Treffer).  
**Vektordatenbank** = wo/wie du *viele* Vektoren speicherst und abfragst.

### Braucht Gnom Qdrant / Chroma / LanceDB / pgvector?

**Meist nein** für V1/V4 Desk:

- Typische Last: Dutzende–Tausende Facts/Notes, nicht 10M Chunks
- USB + ein Python-Prozess = KISS
- bow/char_ngram/fastembed + lokaler Store deckt Recall ab

**Wann doch eine echte Vector-DB?**

- Sehr große Wissensbasis, multi-process workers, shared index
- Dann: **Plugin optional** (z.B. Chroma/Lance) — Core bleibt lite

**Modell-Vergleich sinnvoll:**

| Backend | Pro | Contra |
|---------|-----|--------|
| bow | zero install, USB | schwache Semantik |
| char_ngram / hashing | kein heavy dep | mittel |
| **fastembed** | gut/schnell, ONNX | ~pip + Modell-Download |
| sbert | klassisch stark | schwerer Stack |

Gnom: **Default bow**, optional fastembed — vergleichen im Vector-Modal, nicht parallel 5 DBs.

---

## 2. Neu bauen in Rust? (echte App)

Du hast nach **Rust als echte App** gefragt — Optionen:

### A) **Shell um den Hub** (empfohlen zuerst)

- **Tauri** (Rust UI-Shell) + bestehender Python-Hub als Side-Process  
- Vorteil: nativer Window-Rahmen, Tray, Auto-Start, ohne Rewrite der Pipeline  
- Aufwand: **mittel**, Risiko **niedrig**

### B) **Voll-Rewrite in Rust**

- Agents, Pipeline, LLM-HTTP, Plugins, UI neu  
- Vorteil: ein Binary, speichereffizient  
- Aufwand: **sehr hoch**, Risiko **hoch**, Freeze/Feature-Parität Monate

### C) **Hybrid**

- Hot path (Vector index, file watch) in Rust crate  
- Orchestrierung bleibt Python  
- Sinnvoll **erst** wenn Profiling einen echten Engpass zeigt

### Decision 2026-08-10 (product)

**Tauri = endgame only.**  
Do **not** start a desktop shell while the desk (pipeline, skills, embeddings install, quality) is still the focus.  
When the hub “runs reasonably” in daily use → then thin Tauri wrapper. Not before.

### Empfehlung für Gnom

1. **Jetzt:** Python-Desk + einfacher Install (dieses Repo)  
2. **Nächster sinnvoller App-Schritt:** Tauri wrapper (`apps/desktop/`) der `./scripts/start.sh` startet und WebView auf :8080 zeigt  
3. **Kein** Full-Rust-Rewrite, solange die 8-Agent-Pipeline und Plugins stabil wachsen  

Rust lohnt sich als **Verpackung**, nicht als kompletter Ersatz — außer du willst bewusst ein neues Produkt (Gnom-Hub-native) mit langer runway.

---

## 3. Install-Philosophie (Bindings)

- Maximal **ein** Befehl pro Stufe  
- Neural immer **optional**  
- Kein “install 12 extras or nothing works”
