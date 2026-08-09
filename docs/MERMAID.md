# Mermaid in Gnom-Hub docs

How we draw architecture diagrams so they render on **GitHub** and stay maintainable.

## Where diagrams live

| File | Content |
|------|---------|
| [README.md](../README.md) / [README_DE.md](../README_DE.md) | Product-facing overview |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full system map + execute sequence |
| This file | Syntax + **styling classes** |

---

## Shared styling classes (source of truth)

Use **only** these `classDef` names across README / ARCHITECTURE. Same hex values everywhere so dark GitHub UI stays readable.

### Palette

| Class | Role | Fill | Stroke | Text |
|-------|------|------|--------|------|
| `ui` | Browser SPA, REST, badges, API edge | `#1a1f2e` | `#5b8def` | `#e6edf3` |
| `core` | Orchestrator, agents, LLM, tools, registry | `#1e2a1e` | `#3a8f6e` | `#e6edf3` |
| `locked` | Memory / Flex (non-toggleable) | `#2a2218` | `#c9a227` | `#f5f0e6` |
| `work` | Workers W1–W4 | `#141c2a` | `#6ea8fe` | `#e6edf3` |
| `hot` | HOT session memory | `#2a2218` | `#c9a227` | `#f5f0e6` |
| `warm` | WARM durable / Flex wishes | `#1e2a1e` | `#3a8f6e` | `#e6edf3` |
| `cold` | COLD archive | `#1a1f2e` | `#6b7280` | `#c9cdd4` |
| `store` | Vector / SQLite-like stores | `#1a2433` | `#7c9cbf` | `#e6edf3` |
| `plugin` | Plugin packs | `#221a2e` | `#9b7ed9` | `#efe6f5` |
| `danger` | God-Mode / elevated risk | `#2a1818` | `#c45c5c` | `#f5e6e6` |
| `gate` | Decisions / clarify / quality branch | `#2a2418` | `#d4a017` | `#f5f0e6` |
| `terminal` | Pipeline start/end | `#12151c` | `#8b929e` | `#c9cdd4` |

### Canonical `classDef` block (copy into every styled diagram)

```text
classDef ui fill:#1a1f2e,stroke:#5b8def,color:#e6edf3,stroke-width:1px
classDef core fill:#1e2a1e,stroke:#3a8f6e,color:#e6edf3,stroke-width:1px
classDef locked fill:#2a2218,stroke:#c9a227,color:#f5f0e6,stroke-width:2px
classDef work fill:#141c2a,stroke:#6ea8fe,color:#e6edf3,stroke-width:1px
classDef hot fill:#2a2218,stroke:#c9a227,color:#f5f0e6,stroke-width:1px
classDef warm fill:#1e2a1e,stroke:#3a8f6e,color:#e6edf3,stroke-width:1px
classDef cold fill:#1a1f2e,stroke:#6b7280,color:#c9cdd4,stroke-width:1px
classDef store fill:#1a2433,stroke:#7c9cbf,color:#e6edf3,stroke-width:1px
classDef plugin fill:#221a2e,stroke:#9b7ed9,color:#efe6f5,stroke-width:1px
classDef danger fill:#2a1818,stroke:#c45c5c,color:#f5e6e6,stroke-width:2px
classDef gate fill:#2a2418,stroke:#d4a017,color:#f5f0e6,stroke-width:1px
classDef terminal fill:#12151c,stroke:#8b929e,color:#c9cdd4,stroke-width:1px
```

**Do not invent** one-off colors (`edge`, `reg`, …). Map them:

| Old / wrong | Use instead |
|-------------|-------------|
| `edge` | `ui` |
| `reg` | `core` |
| random purple for tools | `core` or `plugin` |

### Applying classes (two equivalent forms)

**A — `class` statement (batch):**

```mermaid
flowchart LR
  A[Orch] --> B[Worker]
  classDef core fill:#1e2a1e,stroke:#3a8f6e,color:#e6edf3,stroke-width:1px
  classDef work fill:#141c2a,stroke:#6ea8fe,color:#e6edf3,stroke-width:1px
  class A core
  class B work
```

**B — `:::` shorthand (per node, preferred for small graphs):**

```mermaid
flowchart LR
  A[Orch]:::core --> B[Worker]:::work
  classDef core fill:#1e2a1e,stroke:#3a8f6e,color:#e6edf3,stroke-width:1px
  classDef work fill:#141c2a,stroke:#6ea8fe,color:#e6edf3,stroke-width:1px
```

Rules:

1. Define `classDef` **after** nodes (or at end of diagram) — GH Mermaid is happiest that way.
2. Multiple classes on one node are **not** reliable on GitHub → one class per node.
3. Subgraphs **cannot** take `classDef` reliably → style **nodes inside**, not the subgraph frame.
4. Meaning must survive without color (labels + structure first).
5. `stroke-width:2px` only for **locked** and **danger** (attention).

### Optional edge styling

GitHub support is uneven; use sparingly:

```text
linkStyle default stroke:#4b5563,stroke-width:1px
linkStyle 0 stroke:#3a8f6e,stroke-width:2px
```

`linkStyle N` indexes edges in **declaration order** (0-based). Prefer labeled edges over colored ones.

### Sequence diagrams

`classDef` / `:::` do **not** apply to sequence participants. Style with **`rect`**, **`Note`**, and control blocks.

#### Rect colors (= flowchart palette)

| rgb | Class token | Use |
|-----|-------------|-----|
| `rgb(26, 31, 46)` | **ui** | SPA · REST · badges · modal |
| `rgb(30, 42, 30)` | **core** | Orchestrator · distill · prefetch · registry |
| `rgb(42, 34, 24)` | **locked / hot** | Flex wishes · Memory absorb |
| `rgb(34, 26, 46)` | **plugin** | Plugin handler body |
| `rgb(42, 24, 24)` | **danger** | God-Mode risk · auth FEHLER · no stub |

#### Participants

```text
actor U as User              preferred for human
participant SPA as SPA
participant O as Orchestrator
```

- Short **id**, readable **label** (`as …`)
- Keep count ≤ ~10 per diagram (split Send vs Execute vs Tools)
- Order left→right ≈ call stack depth (User → SPA → API → Hub …)

#### Messages

| Arrow | Meaning |
|-------|---------|
| `A->>B: text` | Sync request |
| `A-->>B: text` | Response / async reply |
| `A-)B: text` | Async fire-and-forget (rare here) |

#### Activation

```text
activate O
O->>W: run
deactivate O
```

Shows who is “busy”. Pair every `activate` with `deactivate`.

#### Control blocks (GitHub-safe)

| Block | Use in Gnom |
|-------|-------------|
| `opt` | URL prefetch, optional tool, auto-Execute |
| `alt` / `else` | usable key vs FEHLER; fixable vs auth |
| `loop` | workers · soft retries |
| `par` | avoid unless truly parallel (workers are sequential in V1) |
| `critical` | avoid — poor GH support |
| `break` | avoid — uneven support |

#### Notes

```text
Note over O,T: core · prefetch
Note left of U: user sees Box 3
Note right of F: locked wishes
```

Prefix notes with palette token when helpful: `ui ·` / `core ·` / `danger ·`.

#### Canonical Execute skeleton

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant O as Orchestrator
  participant W as Worker
  participant L as LLM

  U->>O: Execute
  activate O
  rect rgb(30, 42, 30)
    Note over O: core · distill + plan
    O->>O: plan
  end
  alt usable key
    O->>W: run
    W->>L: chat
    L-->>W: draft
    W-->>O: draft
  else auth fail
    rect rgb(42, 24, 24)
      Note over W,U: danger · FEHLER
      W-->>O: FEHLER
      O-->>U: no stub
    end
  end
  deactivate O
```

Full diagrams: [ARCHITECTURE.md](ARCHITECTURE.md) (Send · Execute · Tools API).

### State diagrams

Limited styling. Prefer notes + clear transition labels over `classDef`.

---

## Diagram types we use

| Type | Keyword | Use for |
|------|---------|---------|
| Flowchart | `flowchart TB` / `LR` | Runtime, memory, tools |
| State machine | `stateDiagram-v2` | Pipeline stages |
| Sequence | `sequenceDiagram` | Send · Execute · Tools API (see ARCHITECTURE) |

Avoid: `gitGraph`, `journey`, `gantt`, `pie`, `mindmap`, click handlers, heavy `init` themes.

## Frontmatter (optional)

```mermaid
---
title: Short title
config:
  flowchart:
    curve: basis
    padding: 12
---
flowchart TB
  A --> B
```

## Flowchart building blocks

### Directions & subgraphs

```mermaid
flowchart TB
  subgraph Client["Browser SPA"]
    direction TB
    UI[UI]:::ui
  end
  classDef ui fill:#1a1f2e,stroke:#5b8def,color:#e6edf3,stroke-width:1px
```

- Subgraph: `subgraph Id["Label"]`
- `direction TB|LR` inside subgraph when layout fights you

### Node shapes

| Shape | Syntax | Use |
|-------|--------|-----|
| Rectangle | `A["text"]` | Component / stage |
| Stadium | `A(["pill"])` | Entry/exit · `terminal` |
| Circle | `A((EventBus))` | Bus |
| Diamond | `A{decision?}` | Branch · `gate` |
| Cylinder | `A[("store")]` | Vector / DB · `store` |
| Subroutine | `A[["Registry"]]` | Registry facade · `core` |

### Edges

```text
A --> B
A -.-> B
A <-.-> B
A -->|"label"| B
A & B --> C
```

### Line breaks

Use `<br/>`, never `\n`:

```text
LLM["LLM manager<br/>DeepSeek / Ollama"]:::core
```

## State diagrams

```mermaid
stateDiagram-v2
  [*] --> memory
  memory --> brainstorm
  brainstorm --> distill: Execute
  distill --> flex
  flex --> done
  done --> [*]
  note right of brainstorm: Send stays here
```

## Sequence diagrams

See **Sequence diagrams** above and full flows in [ARCHITECTURE.md](ARCHITECTURE.md#paths-over-time-sequence).

## Checklist before commit

1. Only **shared class names** from the palette above.
2. `classDef` includes `stroke-width`.
3. Fence balanced; labels use `<br/>`.
4. EN/DE README stay parallel (same classes, translated labels).
5. Diagram readable without color.
6. No `edge` / `reg` aliases — use `ui` / `core`.

## Common failures

| Symptom | Fix |
|---------|-----|
| Style ignored | `classDef` after nodes; one class per node |
| Wrong colors | Copied old `edge`/`reg` — remap to palette |
| Blank diagram | Unbalanced fence or bad frontmatter |
| Edge `linkStyle` paints wrong line | Edge index off-by-one — drop linkStyle |

## Minimal styled template

````markdown
```mermaid
---
title: Short name
---
flowchart TB
  A["Component A"]:::core --> B["Component B"]:::ui
  B --> C{branch?}:::gate
  C -->|yes| D[path]:::work
  C -->|no| E[other]:::terminal

  classDef ui fill:#1a1f2e,stroke:#5b8def,color:#e6edf3,stroke-width:1px
  classDef core fill:#1e2a1e,stroke:#3a8f6e,color:#e6edf3,stroke-width:1px
  classDef work fill:#141c2a,stroke:#6ea8fe,color:#e6edf3,stroke-width:1px
  classDef gate fill:#2a2418,stroke:#d4a017,color:#f5f0e6,stroke-width:1px
  classDef terminal fill:#12151c,stroke:#8b929e,color:#c9cdd4,stroke-width:1px
```
````
