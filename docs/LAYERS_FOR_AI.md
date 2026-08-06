# Layers — map for AI (and humans)

Mental model only. **UI = visibility + modules. DB = tiered store. Search = walk tiers outward.**

## 1. Three axes (3D map, not 3D UI)

```mermaid
flowchart TB
  subgraph Z["Z · Tiefe / Haltbarkeit"]
    HOT["HOT · Session now"]
    WARM["WARM · user.db facts"]
    COLD["COLD · archives"]
    WS["WS files · HTML / keep"]
    HOT --> WARM --> COLD
    HOT -.-> WS
  end

  subgraph X["X · Modul / Filmstreifen"]
    CHAT["Chat Crux"]
    INFO["Box1 Info"]
    CONTENT["Box2 Content"]
    REGLER["Box3 Regler / Worker"]
  end

  subgraph Y["Y · Agent"]
    A1["brainstorm"]
    A2["memory"]
    A3["flex / coord"]
    A4["worker1…4"]
  end
```

**Cell address (concept):** `agent × module × tier`  
Example: `memory × facts × WARM` · `worker1 × result × HOT/WS`

---

## 2. UI desk layers (what the human sees)

```mermaid
flowchart TB
  subgraph MOD["Box module · 1px agent frame color only"]
    direction LR
    B1["Box1 · Info explain params"]
    B2["Box2 · content layers"]
    B3["Box3 · worker / Regler"]
  end

  CARDS["Agent cards A·P·A"]
  CHAT["Chat module · per-agent chat layer = Crux"]

  CARDS -->|click| MOD
  CARDS -->|click| CHAT
  CARDS -->|frame color| MOD
  CARDS -->|frame color| CHAT
```

**Rules (do not invent opposite):**

- Agent click → module frame color **only** (not individual box borders).
- Box1 = agent explain + params · Box3 = tune/Regler · Chat = crux layer.
- Agent layers in boxes 1/2/3; chat has own per-agent layer.

---

## 3. Navigation (Clown Lab / film idea)

```mermaid
flowchart LR
  subgraph NAV["4-way"]
    UD["↑↓ · visibility only · opacity of layers"]
    LR["←→ · film strip · each frame = one module"]
  end

  UD --> STACK["Layers stay stacked · never delete data"]
  LR --> FRAMES["Modules side by side"]
```

---

## 4. Data tiers (where truth lives)

```mermaid
flowchart TB
  UI["UI layers / film"] -.->|display only| UI

  subgraph STORE["Stores"]
    HOT2["HOT · session / pipeline"]
    WARM2["WARM · SQLite user.db"]
    COLD2["COLD · archives"]
    FILES["Workspace files selected/"]
    VEC["Vector optional"]
  end

  PIPE["Pipeline Send / Execute"] --> HOT2
  MEM["Memory agent"] --> WARM2
  ARCH["Archive / reset"] --> COLD2
  KEEP["Copy / keep HTML"] --> FILES
  HOT2 -->|durable facts only| WARM2
```

| Tier | Write | Clear-safe? |
|------|--------|-------------|
| HOT | session, jobs | yes often |
| WARM | durable facts | no (keep) |
| COLD | archived HOT | restore/delete explicit |
| Files | HTML artifacts | Clear temp ≠ keep selected |

---

## 5. Search over large data (when layers matter)

```mermaid
flowchart TB
  Q["Query"] --> S1["1 · HOT"]
  S1 -->|enough?| DONE["Return"]
  S1 -->|thin| S2["2 · WARM user.db"]
  S2 -->|enough?| DONE
  S2 -->|thin| S3["3 · COLD archives"]
  S3 -->|thin| S4["4 · WS files + optional vector"]
  S4 --> DONE
```

**AI rule:** prefer inner tiers first; escalate depth only if needed. Do not dump COLD+WS into every prompt.

---

## 6. One diagram for “what am I looking at?”

```mermaid
stateDiagram-v2
  [*] --> Desk
  Desk --> AgentClick: card click
  AgentClick --> Box1Info: explain + params
  AgentClick --> ChatLayer: that agent log
  AgentClick --> ContentLayer: box2/3 agent layer
  AgentClick --> FrameColor: module 1px color

  Desk --> FilmNav: experiment only
  FilmNav --> Vis: up down opacity
  FilmNav --> Modules: left right frames
```

---

## 7. Do / Don’t (for agents editing the hub)

**Do**

- Keep HOT / WARM / COLD semantics when touching memory.
- Route agent explain to Box1; Regler to Box3; chat to active agent layer.
- Treat layer UI as visibility/navigation, not as deleting stores.

**Don’t**

- Put full HTML into WARM.
- Paint individual box borders with agent color (module frame only).
- Build literal 3D database UI unless user asks for experiment.

---

*Source of product truth remains code + user.db + WS. This file is the shared map.*
