/* part: 00-preamble.js  lines 1-323 of app.js — edit parts, run scripts/build_ui_js.py */
/**
 * Gnom-Hub v1 – desktop UI wired to /api/*
 * Hooks still available: window.GnomHub.onSend / onSave / onToggle / onClarify
 */
(function () {
  "use strict";

  /** @type {Window & { GnomHub?: Record<string, unknown> }} */
  const w = window;
  w.GnomHub = w.GnomHub || {};

  const API = "";

  /** Loaded from /api/tooltips?lang=… (en/de) */
  let TOOLTIPS = {};
  let uiLang = "de";

  const _FLEX_PRESETS = ["personal", "security", "neutral", "researcher"]; // kept for desk docs/export

  const COLOR_HEX = {
    brainstorm: "#ef5350",
    memory: "#42a5f5",
    flex: "#f0c000",
    coordinator: "#26c281",
    worker1: "#29b6f6",
    worker2: "#8b6cf6",
    worker3: "#ec5f9b",
    worker4: "#ff8a3d",
  };

  function ownerColorFor(agentId) {
    const k = String(agentId || "").toLowerCase();
    return (typeof COLOR_HEX !== "undefined" && COLOR_HEX[k]) || "";
  }

  function markOwner(el, agentId) {
    if (!el) return;
    const aid = String(agentId || "").toLowerCase();
    if (aid) el.dataset.agent = aid;
    const hex = ownerColorFor(aid);
    if (hex) el.style.setProperty("--owner-color", hex);
  }

  const SLIDER_DEFAULTS = {
    temperature: 0.5,
    top_p: 1,
    max_tokens: 800,
    frequency: 0,
    presence: 0,
  };
  const SLIDER_TIPS = {
    temperature:
      "Temperature steuert Zufall. Niedrig = gleichmäßiger und vorsichtiger. Hoch = kreativer, aber unberechenbarer. Empfehlung 0.3–0.8. Standard 0.50.",
    top_p:
      "Top-P begrenzt die Wortauswahl. Klein = engere Auswahl. Groß = breitere Auswahl. Empfehlung 0.8–1.0. Standard 1.00.",
    max_tokens:
      "Max Tokens ist die Längengrenze. Klein = kürzere Antworten. Groß = ausführlicher, langsamer, teurer. Standard 800.",
    frequency:
      "Frequency Penalty mindert Wiederholungen. Höher = weniger Repeats, kann wichtige Begriffe meiden. Standard 0.00.",
    presence:
      "Presence Penalty fördert neue Aspekte. Höher = eher neue Themen, kann vom Kern wegführen. Standard 0.00.",
  };

  // Display hints only (role prompts live in Python). Empty = code default.
  // Never treat these as the real system prompt unless the user edits Extra tuning.
  const DEFAULT_PROMPTS = {
    brainstorm:
      "(code default) Dialogue partner in Box 2 — riff, ask where it pulls, no code, no Execute.",
    memory:
      "(code default) Extract durable personal/project facts only — no HTML garbage.",
    flex:
      "(code default) Personal companion: remember user facts, spot gaps, brief workers.",
    coordinator:
      "(code default) Distill requirements + worker plan from brainstorm dialogue.",
    worker1: "(code default) Deliver the assigned artifact (HTML/page when asked).",
    worker2: "(code default) Deliver the assigned artifact.",
    worker3: "(code default) Reserved worker.",
    worker4: "(code default) Reserved worker.",
  };

  /** 8 slots – Worker3/4 UI-reserved (shown on; pipeline uses Worker 1+2) */
  const AGENTS = [
    { id: "brainstorm", label: "Brainstorm", color: "brainstorm", enabled: true, toggleable: true, parked: false, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
    { id: "memory", label: "Memory", color: "memory", enabled: true, toggleable: false, parked: false, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
    { id: "flex", label: "Flex", color: "flex", enabled: true, toggleable: true, parked: false, model: "—", preset: "personal", tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
    { id: "coordinator", label: "Coordinator", color: "coordinator", enabled: true, toggleable: true, parked: false, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
    { id: "worker1", label: "Worker 1", color: "worker1", enabled: true, toggleable: true, parked: false, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
    { id: "worker2", label: "Worker 2", color: "worker2", enabled: true, toggleable: true, parked: false, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
    { id: "worker3", label: "Worker 3", color: "worker3", enabled: true, toggleable: true, parked: false, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
    { id: "worker4", label: "Worker 4", color: "worker4", enabled: true, toggleable: true, parked: false, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
  ];

  const els = {
    cards: document.getElementById("agent-cards"),
    tipRoot: document.getElementById("box1-tooltip"),
    tipTitle: document.getElementById("tip-title"),
    tipHow: document.getElementById("tip-how"),
    tipExample: document.getElementById("tip-example"),
    placeholder: document.querySelector(".box1-placeholder"),
    clarify: document.getElementById("clarify"),
    clarifyQ: document.getElementById("clarify-question"),
    chatInput: document.getElementById("chat-input"),
    chatLog: null, /* set by syncActiveChatLog after buildChatLayers */
    btnSend: document.getElementById("btn-send"),
    btnExecute: document.getElementById("btn-execute"),
    btnMic: document.getElementById("btn-mic"),
    btnTd: document.getElementById("btn-td"),
    btnSave: document.getElementById("btn-save"),
    btnHelp: document.getElementById("btn-help"),
    btnSystem: document.getElementById("btn-system"),
    btnReset: document.getElementById("btn-reset"),
    stageBadge: document.getElementById("stage-badge"),
    llmBadge: document.getElementById("llm-badge"),
    toolsBadge: document.getElementById("tools-badge"),
    skillsBadge: document.getElementById("skills-badge"),
    docsBadge: document.getElementById("docs-badge"),
    costBadge: document.getElementById("cost-badge"),
    usageModal: document.getElementById("usage-modal"),
    memBadge: document.getElementById("mem-badge"),
    vecBadge: document.getElementById("vec-badge"),
    godBadge: document.getElementById("god-badge"),
    coldBadge: document.getElementById("cold-badge"),
    btnArchive: document.getElementById("btn-archive"),
    coldBrowser: document.getElementById("cold-browser"),
    coldList: document.getElementById("cold-list"),
    coldDetail: document.getElementById("cold-detail"),
    btnColdClose: document.getElementById("btn-cold-close"),
    tuneModal: document.getElementById("tune-layer"),
    systemModal: document.getElementById("system-modal"),
    workspaceModal: document.getElementById("workspace-modal"),
    btnWorkspace: document.getElementById("btn-workspace"),
    btnTools: document.getElementById("btn-tools"),
    toolsModal: document.getElementById("tools-modal"),
    flexSelect: document.getElementById("flex-preset-select"),
    vectorModal: document.getElementById("vector-modal"),
    skillsModal: document.getElementById("skills-modal"),
    docsModal: document.getElementById("docs-modal"),
  };

  let activeStage = "idle";
  let tuneAgentId = null;
  /** Agent id last clicked — box module 1px border color */
  let lastClickedAgentId = null;
  /** Recipient of the next Send — independent of card click / layer. */
  let sendTarget = "brainstorm";
  let clickTimer = null;
  let recognition = null;
  let listening = false;
  let lastSpokenKey = "";
  let _pendingSpeech = ""; // spoken on next click if browser blocked autoplay
  let ttsUnlocked = false; // true after speak started from a real click
  /** Sequential TTS queue — one utterance fully finishes before the next (no cut-off). */
  let ttsQueue = [];
  let ttsPumping = false;
  let lastAgentThoughts = {}; // reasoning streams for TTS (not Box text)
  let lastNudgeKey = ""; // avoid re-spamming Flex corrections in chat
  let lastToolsKey = ""; // avoid re-toasting tool_calls
  let lastSnapshot = null; // latest hub snapshot (tools history etc.)
  let lastToolCalls = []; // pipeline.tool_calls for Tools modal history
  let manualToolCalls = []; // this browser session (Tools Run / Fetch)
  let toolsResultMode = "preview";
  let lastToolsSicht = "";
  let lastToolsCode = "";
  let wsPreviewMode = "preview";
  let wsPreviewCode = "";
  let wsPreviewIsHtml = false;
  let lastDryRunKey = ""; // avoid re-toasting dry-run God hint
  let lastPlanKey = ""; // avoid re-toasting resolved plan mode
  let currentJobId = null;
  let lastWorkerOutputs = [];
  let jobTimerStart = null;
  let jobTimerInterval = null;
  let lastJobElapsedSec = 0;
  let lastReportedPipelineError = null;
  let lastDeferredClarifyKey = "";
  let chatBusy = false;
  let lastCanExecute = false;
  /** Per-agent chat logs: { brainstorm: [...], worker1: [...], ... } */
  const CHAT_STORAGE_KEY = "gnom-hub-chat-logs-by-agent-v1";
  const CHAT_STORAGE_LEGACY = "gnom-hub-chat-log-v1";
  const HISTORY_KEY = "gnom-hub-result-history-v1";
  const CHAT_HIST_KEY = "gnom-hub-chat-input-hist-v1";
  const CHAT_HIST_MAX = 50;
  const HISTORY_MAX = 12;
  let resultHistory = [];
  const resultTrash = [];
  let selectedColdId = null;
  /** Terminal-style input history (ArrowUp/Down). idx -1 = live draft. */
  let chatHist = [];
  let chatHistIdx = -1;
  let chatDraft = "";

  function statusLabel(agent) {
    if (agent.parked) return agent.enabled ? "on · later" : "off / parked";
    return agent.enabled ? "on" : "off";
  }

  function agentIsActive(agent) {
    if (!agent || !agent.enabled) return false;
    const s = activeStage || "";
    // Exact id match (worker1…, brainstorm, …) — only the agent that is running
    if (s === agent.id) return true;
    if (s === "memory" && agent.id === "memory") return true;
    if (s === "brainstorm" && agent.id === "brainstorm") return true;
    if (
      (s === "distill" || s === "clarify" || s === "coordinate") &&
      agent.id === "coordinator"
    ) {
      return true;
    }
    if (s === "flex" && agent.id === "flex") return true;
    // Generic "work" without a worker id: pulse no worker (avoid fake all-worker pulse)
    // done/error/idle: no pulse
    return false;
  }

  function agentLiveStatusToken(label) {
    const s = String(label || "");
    if (s === "fragt nach" || s === "fragt") return "fragt";
    if (s === "benutzt Werkzeug" || s === "denkt" || s === "aktiv") return "aktiv";
    if (s === "hat Ergebnis" || s === "fertig") return "fertig";
    if (s === "Fehler" || s === "fehler") return "fehler";
    if (s === "lädt" || s === "laedt") return "laedt";
    if (s === "offline") return "offline";
    if (s === "keine Daten" || s === "leer") return "leer";
    if (s === "blockiert" || s === "wartet") return s;
    return "wartet";
  }

  function agentLiveStatus(agentId) {
    const id = String(agentId || "");
    const agent = findAgent(id) || {};
    const snap = typeof lastSnapshot !== "undefined" ? lastSnapshot : null;
    const pipe = (snap && snap.pipeline) || {};
    const stage = String(pipe.stage || activeStage || "idle");
    const send = String(pipe.send_target || "");
    const isSend = send === id;
    const isWorker = id.indexOf("worker") === 0;
    const err = String(
      pipe.error || pipe.last_error || (snap && snap.last_error) || ""
    );
    const result = String(pipe.result_status || "");
    if (agent.parked) return "blockiert";

    const flexBox = (snap && snap.flex_box1) || {};
    const flexQs = Array.isArray(flexBox.questions)
      ? flexBox.questions
      : Array.isArray(pipe.flex_questions)
        ? pipe.flex_questions
        : [];
    const blockedQ = flexQs.some(function (q) {
      if (!q) return false;
      const qid = String(q.agent_id || q.agent || "").toLowerCase();
      if (qid && qid !== id) return false;
      return String(q.entry_type || "").toLowerCase() === "blockiert";
    });
    if (blockedQ) return "blockiert";

    const val = pipe.validation;
    if (
      val &&
      val.ok === false &&
      String(val.worker || "").toLowerCase() === id &&
      stage !== "error"
    ) {
      return "blockiert";
    }

    const involved =
      isSend ||
      (typeof agentIsActive === "function" && agentIsActive(agent)) ||
      stage === id;
    if (stage === "error" && (involved || (isWorker && result === "FEHLER"))) {
      return "Fehler";
    }
    if (err && stage === "error" && involved) return "Fehler";
    if (result === "FEHLER" && (isSend || involved)) return "Fehler";

    const pending = pipe.pending_question;
    const asking =
      stage === "clarify" ||
      (pending && pending.text) ||
      flexQs.some(function (q) {
        if (!q) return false;
        const qid = String(q.agent_id || q.agent || "").toLowerCase();
        if (qid && qid !== id) return false;
        return !!(q.text || q.question || q.prompt);
      });
    if (asking && (id === "flex" || id === "coordinator" || isSend)) {
      return "fragt nach";
    }

    const tools = [].concat(pipe.tool_log || [], pipe.tool_calls || []);
    const toolForMe = tools.some(function (t) {
      if (!t) return false;
      const a = String(t.agent || t.agent_id || "").toLowerCase();
      return !a || a === id;
    });
    const working = stage === "work" || stage === id;
    if (
      working &&
      toolForMe &&
      (involved || (isWorker && stage === "work"))
    ) {
      return "benutzt Werkzeug";
    }

    if (stage === "done") {
      const outs = pipe.worker_outputs || [];
      const mine = outs.some(function (o) {
        return _agentPageOutputMine(o, id);
      });
      if (
        mine ||
        (isSend && (result === "GELIEFERT" || result === "UNGEPRÜFT" || result))
      ) {
        return "hat Ergebnis";
      }
    }

    if (typeof agentIsActive === "function" && agentIsActive(agent)) {
      return "denkt";
    }
    if (
      isSend &&
      (stage === "brainstorm" ||
        stage === "distill" ||
        stage === "flex" ||
        stage === "coordinate" ||
        stage === "work" ||
        stage === "memory")
    ) {
      return "denkt";
    }
    if (typeof chatBusy !== "undefined" && chatBusy && isSend) return "denkt";
    return "wartet";
  }

  function _agentPageOutputMine(o, agentId) {
    const id = String(agentId || "").toLowerCase();
    const w = String((o && (o.worker || o.id || o.name)) || "").toLowerCase();
    if (!id || !w) return false;
    if (w === id) return true;
    if (id === "worker1" && /worker\s*1|\bw1\b/.test(w)) return true;
    if (id === "worker2" && /worker\s*2|\bw2\b/.test(w)) return true;
    if (id === "worker3" && /worker\s*3|\bw3\b/.test(w)) return true;
    if (id === "worker4" && /worker\s*4|\bw4\b/.test(w)) return true;
    return false;
  }

  /** Crux: one chat log layer per agent. */
  function buildChatLayers() {
    const stack = document.getElementById("chat-layers");
    if (!stack) return;
    stack.innerHTML = "";
    AGENTS.forEach(function (agent, idx) {
      const layer = document.createElement("div");
      layer.className = "chat-agent-layer";
      layer.dataset.agent = agent.id;
      layer.dataset.layerIndex = String(idx + 1);
      layer.setAttribute(
        "aria-label",
        "Chat layer " + (idx + 1) + " · " + agent.label
      );
      const log = document.createElement("div");
      log.className = "chat-log flex-1 min-h-0 space-y-0 overflow-y-auto px-2.5 py-2 text-xs text-gnom-muted";
      log.id = "chat-log-" + agent.id;
      if (agent.id === "brainstorm") log.id = "chat-log";
      log.dataset.agent = agent.id;
      layer.appendChild(log);
      stack.appendChild(layer);
    });
    syncActiveChatLog(lastClickedAgentId || "brainstorm");
  }

  function syncActiveChatLog(agentId) {
    const aid = agentId || lastClickedAgentId || "brainstorm";
    document.querySelectorAll(".chat-agent-layer").forEach(function (layer) {
      const on = layer.getAttribute("data-agent") === aid;
      layer.classList.toggle("is-active", on);
      layer.hidden = !on;
    });
    els.chatLog =
      document.getElementById(aid === "brainstorm" ? "chat-log" : "chat-log-" + aid) ||
      document.querySelector(
        '.chat-agent-layer[data-agent="' + aid + '"] .chat-log'
      ) ||
      document.getElementById("chat-log");
    if (els.chatLog) {
      try {
        els.chatLog.scrollTop = els.chatLog.scrollHeight;
      } catch (_e) {
        /* ignore */
      }
    }
    /* Crux frame color = same agent color as boxes module */
    const chatMod = document.getElementById("chat-mod");
    if (chatMod) {
      const hex = COLOR_HEX[aid] || null;
      chatMod.style.setProperty(
        "--chat-mod-color",
        hex || "var(--border)"
      );
    }
  }

  /** Build 8 agent layers per box (Agent N = Layer N). */
  function buildAgentLayers() {
    const hints = {
      brainstorm: "Brainstorm dialogue",
      memory: "Memory notes",
      flex: "Flex review",
      coordinator: "Coordinator / plan",
      worker1: "Worker 1 result",
      worker2: "Worker 2 result",
      worker3: "Worker 3 result",
      worker4: "Worker 4 result",
    };
    [1, 2, 3].forEach(function (n) {
      const stack = document.getElementById("box" + n + "-layers");
      if (!stack) return;
      stack.innerHTML = "";
      AGENTS.forEach(function (agent, idx) {
        const layer = document.createElement("div");
        layer.className = "agent-layer";
        layer.dataset.agent = agent.id;
        layer.dataset.layerIndex = String(idx + 1);
        layer.setAttribute("aria-label", "Layer " + (idx + 1) + " " + agent.label);
        const body = document.createElement("div");
        body.className = "agent-layer-body box-body";
        if (n === 3) body.classList.add("box3-dynamic");
        body.id = "box" + n + "-" + agent.id;
        /* box2 brainstorm alias only — box3-content stays on dual-layer slot in HTML */
        if (n === 2 && agent.id === "brainstorm") body.id = "box2-content";
        body.dataset.agentBody = agent.id;
        body.dataset.box = String(n);
        const empty = document.createElement("p");
        empty.className = "muted empty-hint";
        empty.textContent = hints[agent.id] || agent.label;
        body.appendChild(empty);
        layer.appendChild(body);
        stack.appendChild(layer);
      });
    });
    /* default: first agent layer visible until click */
    activateAgentLayer(lastClickedAgentId || "brainstorm", false);
  }

  function getAgentBoxBody(boxNum, agentId) {
    const aid = agentId || lastClickedAgentId || "brainstorm";
    if (boxNum === 2 && aid === "brainstorm") {
      const b = document.getElementById("box2-content");
      if (b) return b;
    }
    // Never use #box3-content here — that node is the dual-layer stage for previews
    return document.getElementById("box" + boxNum + "-" + aid) ||
      document.querySelector(
        "#box" + boxNum + "-layers .agent-layer[data-agent=\"" + aid + "\"] .agent-layer-body"
      );
  }

  /**
   * Agent click: show that agent's layer in Box 1/2/3 + 1px module frame color.
   * @param {string} agentId
   * @param {boolean} [paintOnly]
   */
  function activateAgentLayer(agentId, doPaint) {
    if (!agentId) return;
    if (!AGENTS.some(function (a) { return a.id === agentId; })) return;
    lastClickedAgentId = agentId;
    document.querySelectorAll(".agent-layer").forEach(function (layer) {
      const on = layer.getAttribute("data-agent") === agentId;
      layer.classList.toggle("is-active", on);
      layer.hidden = !on;
    });
    document.querySelectorAll(".agent-card").forEach(function (card) {
      card.classList.toggle(
        "is-layer-active",
        card.dataset.agentId === agentId
      );
    });
    /* Crux: chat layer switches with agent */
    syncActiveChatLog(agentId);
    if (doPaint !== false) {
      paintBoxesModule(agentId);
      fillBox1AgentInfo(agentId);
    }
    // Worker card click → show that worker's page in Box 3 stage
    try {
      if (
        /^worker[1-4]$/.test(agentId) &&
        typeof lastWorkerOutputs !== "undefined" &&
        lastWorkerOutputs &&
        lastWorkerOutputs.length &&
        typeof focusBox3WorkerResult === "function"
      ) {
        let idx = -1;
        for (let i = 0; i < lastWorkerOutputs.length; i++) {
          const w = String(
            (lastWorkerOutputs[i] && lastWorkerOutputs[i].worker) || ""
          ).toLowerCase();
          if (w === agentId || w.indexOf(agentId) >= 0) {
            idx = i;
            break;
          }
        }
        if (idx < 0) {
          const n = parseInt(agentId.replace("worker", "")) - 1;
          if (n >= 0 && n < lastWorkerOutputs.length) idx = n;
        }
        if (idx >= 0) focusBox3WorkerResult(idx);
      }
    } catch (_e) {
      /* ignore */
    }
  }

  /**
   * Agent-Klick: nur Modul-Rahmen 1px Agentenfarbe.
   * Einzelne Boxen nie agentenfarbig.
   */
  function paintBoxesModule(agentId) {
    lastClickedAgentId = agentId || lastClickedAgentId || null;
    const hex =
      agentId && COLOR_HEX[agentId] ? COLOR_HEX[agentId] : null;
    const mod = document.querySelector(".boxes");
    if (mod) {
      mod.style.setProperty(
        "--boxes-mod-color",
        hex || "var(--border)"
      );
    }
    const chatMod = document.getElementById("chat-mod");
    if (chatMod) {
      chatMod.style.setProperty(
        "--chat-mod-color",
        hex || "var(--border)"
      );
    }
    ["box1", "box2", "box3"].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.style.setProperty("--box-agent-color", "var(--border)");
    });
  }

  function escHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function paramVal(v, fallback) {
    if (v == null || v === "" || (typeof v === "number" && isNaN(v))) return fallback;
    return v;
  }

  /**
   * Box 1 = Agent-Erklärung: wer, wofür, wie eingestellt — alle Parameter lesbar.
   * Übersicht: kurze Rolle + kompakte Param-Zeilen (Wert + 1-Satz-Sinn).
   */
  function fillBox1AgentInfo(agentId) {
    const tip = TOOLTIPS[agentId];
    const agent = findAgent(agentId);
    if (typeof showInfoLayer === "function") showInfoLayer("live");
    if (els.placeholder) els.placeholder.hidden = true;
    if (els.tipRoot) els.tipRoot.hidden = false;

    const label = (agent && agent.label) || (tip && tip.title) || agentId;
    const layerIdx =
      AGENTS.findIndex(function (a) {
        return a.id === agentId;
      }) + 1;
    const role =
      (tip && tip.how_to) ||
      (DEFAULT_PROMPTS[agentId] || "").replace(/^\(code default\)\s*/i, "") ||
      "Agent in der Pipeline.";

    if (els.tipTitle) {
      els.tipTitle.textContent = label + " — das ist dieser Agent";
    }
    const roleEl = document.getElementById("tip-role");
    if (roleEl) {
      roleEl.textContent =
        "Layer " +
        layerIdx +
        " · " +
        role +
        (tip && tip.title && tip.title !== label ? " (" + tip.title + ")" : "");
    }

    const a = agent || {};
    const temp = paramVal(a.temperature, 0.5);
    const topP = paramVal(a.top_p, 1);
    const maxTok = paramVal(a.max_tokens, 800);
    const freq = paramVal(a.frequency_penalty, 0);
    const pres = paramVal(a.presence_penalty, 0);
    const model = a.model && a.model !== "—" ? a.model : "deepseek-chat (default)";
    const status =
      (a.parked ? "geparkt" : a.enabled ? "an" : "aus") +
      (a.online ? " · online" : " · offline") +
      (a.tts ? " · TTS an" : " · TTS aus") +
      (a.preset ? " · Flex-Preset: " + a.preset : "");

    const rows = [
      { k: "Status", v: status, tip: "An = nimmt an Pipeline teil. Geparkt = später. TTS = spricht Gedanken." },
      { k: "Model", v: String(model), tip: "Welches LLM dieser Agent nutzt." },
      {
        k: "Temperature",
        v: Number(temp).toFixed(2),
        tip: SLIDER_TIPS.temperature,
      },
      {
        k: "Top-P",
        v: Number(topP).toFixed(2),
        tip: SLIDER_TIPS.top_p,
      },
      {
        k: "Max Tokens",
        v: String(Math.round(Number(maxTok))),
        tip: SLIDER_TIPS.max_tokens,
      },
      {
        k: "Frequency",
        v: Number(freq).toFixed(2),
        tip: SLIDER_TIPS.frequency,
      },
      {
        k: "Presence",
        v: Number(pres).toFixed(2),
        tip: SLIDER_TIPS.presence,
      },
    ];
    if (a.tokens != null && Number(a.tokens) > 0) {
      rows.push({
        k: "Tokens (Session)",
        v: String(a.tokens) + (a.cost_usd != null ? " · $" + Number(a.cost_usd).toFixed(4) : ""),
        tip: "Verbrauch dieser Session für diesen Agenten.",
      });
    }

    const promptRaw =
      (a.system_prompt && String(a.system_prompt).trim()) ||
      DEFAULT_PROMPTS[agentId] ||
      "";
    const promptShort =
      promptRaw.length > 160 ? promptRaw.slice(0, 157) + "…" : promptRaw;

    let paramsHtml =
      '<div class="agent-explain-head">So ist er eingestellt</div><ul class="agent-param-list">';
    rows.forEach(function (r) {
      paramsHtml +=
        '<li class="agent-param-row" title="' +
        escHtml(r.tip) +
        '">' +
        '<span class="agent-param-k">' +
        escHtml(r.k) +
        "</span>" +
        '<span class="agent-param-v">' +
        escHtml(r.v) +
        "</span>" +
        '<span class="agent-param-tip">' +
        escHtml(r.tip) +
        "</span>" +
        "</li>";
    });
    paramsHtml += "</ul>";
    if (promptShort) {
      paramsHtml +=
        '<div class="agent-explain-head">Prompt / Rolle</div>' +
        '<p class="agent-prompt-snip" title="' +
        escHtml(promptRaw) +
        '">' +
        escHtml(promptShort) +
        "</p>";
    }
    paramsHtml +=
      '<p class="agent-explain-foot">Regler → Box 3 · Chat-Layer = Crux · Modulrahmen = Agentenfarbe</p>';

    if (els.tipHow) {
      // eslint-disable-next-line no-unsanitized/property
      els.tipHow.innerHTML = paramsHtml;
    }
    if (els.tipExample) {
      els.tipExample.textContent =
        (tip && tip.example) ||
        "Doppelklick Karte = an/aus · Klick = Info hier + Regler Box 3.";
    }

    /* Spiegel in Agent-Layer Body Box 1 */
    const body =
      typeof getAgentBoxBody === "function" ? getAgentBoxBody(1, agentId) : null;
    if (body) {
      // eslint-disable-next-line no-unsanitized/property
      body.innerHTML =
        '<div class="box1-agent-info">' +
        '<h2 class="tip-title">' +
        escHtml(label) +
        "</h2>" +
        '<p class="tip-role">' +
        escHtml(role) +
        "</p>" +
        paramsHtml +
        "</div>";
    }
  }

  function closeAgentPage() {
    const page = document.getElementById("agent-page");
    if (page) page.hidden = true;
  }

  const AGENT_PAGE_TABS = [
    "jetzt",
    "auftrag",
    "verlauf",
    "werkzeuge",
    "dateien",
    "memory",
    "ergebnis",
    "einstellungen",
  ];
  const AGENT_PAGE_RIGHTS = {
    brainstorm: "Darf Dialog in Box 2. Darf nicht Execute, Code oder Box 3.",
    memory: "Darf Recall. Darf nicht Boxen füllen.",
    flex: "Darf Box 1 und Wünsche. Darf nicht Execute, Tools, God-Mode.",
    coordinator: "Darf Plan und Distill. Darf nicht bauen.",
    worker1: "Darf Deliverable in Box 3. Darf nicht raten, Box 1/2 schreiben.",
    worker2: "Darf Deliverable in Box 3. Darf nicht raten, Box 1/2 schreiben.",
    worker3: "Darf Deliverable in Box 3. Darf nicht raten, Box 1/2 schreiben.",
    worker4: "Darf Deliverable in Box 3. Darf nicht raten, Box 1/2 schreiben.",
  };
  const AGENT_PAGE_ROLE = {
    brainstorm: "Ideenpartner — redet, baut nicht",
    memory: "Gedächtnis — merkt Fakten, füllt keine Boxen",
    flex: "Begleiter — prüft und fragt, startet keine Worker",
    coordinator: "Planer — destilliert und verteilt, baut nicht",
    worker1: "Arbeiter — führt den bestätigten Plan aus",
    worker2: "Arbeiter — führt den bestätigten Plan aus",
    worker3: "Arbeiter — Reservestelle, später",
    worker4: "Arbeiter — Reservestelle, später",
  };
  const AGENT_PAGE_LIVE = {
    laedt: { label: "lädt", sym: "↻" },
    wartet: { label: "wartet", sym: "○" },
    aktiv: { label: "aktiv", sym: "▶" },
    fragt: { label: "fragt", sym: "?" },
    blockiert: { label: "blockiert", sym: "⊘" },
    fehler: { label: "Fehler", sym: "×" },
    fertig: { label: "fertig", sym: "✓" },
    offline: { label: "offline", sym: "●" },
    leer: { label: "keine Daten", sym: "—" },
  };
  const AGENT_PAGE_HIST_FILTERS = [
    ["antwort", "Antworten"],
    ["werkzeug", "Werkzeuge"],
    ["datei", "Dateien"],
    ["memory", "Memory"],
    ["entscheidung", "Entscheidungen"],
    ["fehler", "Fehler"],
    ["kosten", "Kosten"],
  ];

  function _agentPageAdd(parent, tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text != null) el.textContent = text;
    if (parent) parent.appendChild(el);
    return el;
  }

  function _agentPageClear(el) {
    if (el) el.textContent = "";
  }

  function _agentPageMsgAgent(m) {
    if (typeof pipelineMessageAgent === "function") return pipelineMessageAgent(m);
    if (!m || typeof m !== "object") return "brainstorm";
    const reply = String(m.reply_agent_id || "").trim();
    if (reply) return reply;
    const target = String(m.target_agent_id || "").trim();
    if (target) return target;
    return "brainstorm";
  }

  function _agentPageMsgText(m) {
    if (typeof pipelineMessageText === "function") return pipelineMessageText(m);
    return String((m && (m.visible_text || m.user_text)) || "");
  }

  function _agentPageMsgUserAgent(m) {
    if (!m || typeof m !== "object") return false;
    const role = String(m.role || "").toLowerCase();
    if (role === "thought" || role === "reasoning" || role === "cot") return false;
    if (m.chain_of_thought && !m.visible_text && !m.user_text) return false;
    return role === "user" || role === "agent" || role === "assistant";
  }

  function _agentPageMessagesFor(pipe, agentId) {
    const msgs = (pipe && Array.isArray(pipe.messages) && pipe.messages) || [];
    return msgs.filter(function (m) {
      return _agentPageMsgUserAgent(m) && _agentPageMsgAgent(m) === agentId;
    });
  }

  function _agentPageFactText(f) {
    if (!f) return "";
    if (typeof f === "string") return f;
    return String(f.text || f.fact || f.value || "");
  }

  function _agentPageFileName(f) {
    if (!f) return "";
    if (typeof f === "string") return f;
    return String(f.name || f.path || "");
  }

  function _agentPageSecretName(nm) {
    const s = String(nm || "").toLowerCase();
    if (!s) return true;
    if (s === "key.txt" || s === ".env" || s === ".env.local") return true;
    return /api[_-]?key|secret|credential|\.pem$|\.key$/.test(s);
  }

  function _agentPageGlyph(agentId) {
    const id = String(agentId || "");
    if (id.indexOf("worker") === 0) return id.replace("worker", "") || "W";
    if (id === "brainstorm") return "B";
    if (id === "memory") return "M";
    if (id === "flex") return "F";
    if (id === "coordinator") return "C";
    return (id.charAt(0) || "?").toUpperCase();
  }

  function _agentPageMoney(n) {
    const x = Number(n || 0);
    if (!isFinite(x)) return "—";
    return x.toFixed(3).replace(".", ",") + " $";
  }

  function _agentPageRuntime(sec) {
    const s = Math.max(0, Math.floor(Number(sec || 0)));
    if (!s) return "—";
    const m = Math.floor(s / 60);
    const r = s % 60;
    return m + " min " + (r < 10 ? "0" : "") + r + " s";
  }

  function _agentPageClock(ts) {
    if (!ts) return "";
    const d = ts instanceof Date ? ts : new Date(ts);
    if (isNaN(d.getTime())) return String(ts).slice(0, 16);
    const hh = (d.getHours() < 10 ? "0" : "") + d.getHours();
    const mm = (d.getMinutes() < 10 ? "0" : "") + d.getMinutes();
    return hh + ":" + mm;
  }

  function _agentPageEmpty(parent, text) {
    return _agentPageAdd(parent, "p", "agent-page-empty", text || "Keine Daten");
  }

  function _agentPageLoading(parent, title) {
    _agentPageAdd(parent, "h2", "", title || "");
    _agentPageAdd(parent, "p", "agent-page-muted", "Ansicht wird geladen.");
    _agentPageAdd(parent, "div", "agent-page-skel", "");
    _agentPageAdd(parent, "div", "agent-page-skel w70", "");
    _agentPageAdd(parent, "div", "agent-page-skel w50", "");
  }

  function _agentPageKv(parent, rows) {
    const dl = _agentPageAdd(parent, "dl", "agent-page-kv", "");
    (rows || []).forEach(function (row) {
      if (!row) return;
      _agentPageAdd(dl, "dt", "", row[0]);
      _agentPageAdd(dl, "dd", "", row[1] == null || row[1] === "" ? "—" : String(row[1]));
    });
    return dl;
  }

  function _agentPageTag(parent, text, kind) {
    return _agentPageAdd(
      parent,
      "span",
      "agent-page-tag" + (kind ? " " + kind : ""),
      text
    );
  }

  function _agentPageLiveView(raw, agent, snap) {
    let token = agentLiveStatusToken(raw);
    if (!snap) token = "laedt";
    else if (token === "wartet" && agent && !agent.online) token = "offline";
    const spec = AGENT_PAGE_LIVE[token] || AGENT_PAGE_LIVE.wartet;
    return { token: token, label: spec.label, sym: spec.sym };
  }

  function _agentPagePaintLive(agentId, liveRaw, agent, snap) {
    const view = _agentPageLiveView(liveRaw, agent, snap);
    const page = document.getElementById("agent-page");
    if (page) page.dataset.state = view.token;
    const liveEl = document.getElementById("agent-page-live");
    if (liveEl) {
      liveEl.dataset.state = view.token;
      liveEl.dataset.status = view.token;
    }
    const textEl = document.getElementById("agent-page-live-text");
    if (textEl) textEl.textContent = view.label;
    else if (liveEl) liveEl.textContent = view.label;
    const symEl = document.getElementById("agent-page-live-sym");
    if (symEl) symEl.textContent = view.sym;
    const off = document.getElementById("agent-page-offline");
    if (off) {
      const name = (agent && agent.label) || agentId || "Agent";
      off.textContent =
        name +
        " ist offline. Anzeige der letzten bekannten Daten — keine neuen Aktionen möglich.";
      off.hidden = view.token !== "offline";
    }
    return view;
  }

  function _agentPagePaintRecipient(agentId, agent) {
    const note = document.getElementById("agent-page-recipient");
    if (!note) return;
    const id = String(agentId || "");
    const label = (agent && agent.label) || id || "Agent";
    if (id && sendTarget === id) {
      note.textContent = "Empfänger: " + label;
      note.classList.add("is-set");
    } else {
      note.textContent = "Ansicht geöffnet — Empfänger unverändert";
      note.classList.remove("is-set");
    }
  }

  function _agentPageRunSec(agentId, pipe) {
    const id = String(agentId || "");
    const send = String((pipe && pipe.send_target) || "");
    const stage = String((pipe && pipe.stage) || "idle");
    const agent = findAgent(id);
    const involved =
      send === id ||
      (agent && typeof agentIsActive === "function" && agentIsActive(agent));
    if (!involved && stage === "idle") return 0;
    if (typeof jobTimerStart === "number" && jobTimerStart) {
      return (Date.now() - jobTimerStart) / 1000;
    }
    if (typeof lastJobElapsedSec === "number" && lastJobElapsedSec > 0) {
      return lastJobElapsedSec;
    }
    return 0;
  }

  function _agentPagePreviewText(raw, cap) {
    const t = String(raw || "").replace(/\s+/g, " ").trim();
    if (!t) return "";
    const n = cap || 400;
    if (t.length <= n) return t;
    return t.slice(0, n) + " …";
  }

  function _paintChatTargets() {
    const root = document.getElementById("chat-targets");
    if (!root) return;
    if (typeof bindSendTargets === "function") bindSendTargets();
    root.querySelectorAll(".chat-target").forEach(function (el) {
      const on = el.dataset.target === sendTarget;
      el.classList.toggle("is-on", on);
      el.setAttribute("aria-checked", on ? "true" : "false");
    });
  }

  function showAgentPageTab(tabId, fromKeyboard) {
    const id = AGENT_PAGE_TABS.indexOf(tabId) >= 0 ? tabId : "jetzt";
    const page = document.getElementById("agent-page");
    if (page) page.dataset.tab = id;
    document.querySelectorAll("#agent-page-tabs .agent-page-tab").forEach(function (btn) {
      const on = btn.getAttribute("data-tab") === id;
      btn.classList.toggle("is-on", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
      btn.tabIndex = on ? 0 : -1;
    });
    AGENT_PAGE_TABS.forEach(function (t) {
      const panel = document.getElementById("agent-page-panel-" + t);
      if (!panel) return;
      const on = t === id;
      panel.classList.toggle("is-on", on);
      if (on) panel.removeAttribute("hidden");
      else panel.hidden = true;
    });
    if (fromKeyboard) {
      const tab = document.getElementById("agent-page-tab-" + id);
      if (tab && tab.focus) tab.focus();
    }
  }

  function _refreshAgentPageLive() {
    const page = document.getElementById("agent-page");
    if (!page || page.hidden || !page.dataset.agent) return;
    if (typeof agentLiveStatus !== "function") return;
    const agentId = page.dataset.agent;
    const agent = findAgent(agentId) || {};
    const snap = typeof lastSnapshot !== "undefined" ? lastSnapshot : null;
    const st = agentLiveStatus(agentId);
    _agentPagePaintLive(agentId, st, agent, snap);
    const pipe = (snap && snap.pipeline) || {};
    const runEl = document.getElementById("agent-page-runtime");
    if (runEl) runEl.textContent = _agentPageRuntime(_agentPageRunSec(agentId, pipe));
    const costEl = document.getElementById("agent-page-cost");
    if (costEl) costEl.textContent = _agentPageMoney(agent.cost_usd);
  }

  function openAgentPage(agentId) {
    const page = document.getElementById("agent-page");
    const body = document.getElementById("agent-page-body");
    if (!page || !body) return;
    const prevAgent = page.dataset.agent;
    const keepTab =
      !page.hidden && prevAgent === agentId && page.dataset.tab
        ? page.dataset.tab
        : "jetzt";
    const agent = findAgent(agentId) || {};
    const rights = AGENT_PAGE_RIGHTS[agentId] || "siehe Docs";
    const snap = typeof lastSnapshot !== "undefined" ? lastSnapshot : null;
    const pipe = (snap && snap.pipeline) || {};
    const expert = !!(page.dataset && page.dataset.expert === "1");
    const live =
      typeof agentLiveStatus === "function" ? agentLiveStatus(agentId) : "wartet";
    const roleText = AGENT_PAGE_ROLE[agentId] || rights;
    page.dataset.agent = agentId;
    const title = document.getElementById("agent-page-title");
    if (title) title.textContent = agent.label || agentId;
    const roleEl = document.getElementById("agent-page-role");
    if (roleEl) roleEl.textContent = roleText;
    const glyph = document.getElementById("agent-page-glyph");
    if (glyph) glyph.textContent = _agentPageGlyph(agentId);
    const mark = document.getElementById("agent-page-mark");
    if (mark) mark.title = agent.label || agentId;
    _agentPagePaintLive(agentId, live, agent, snap);
    _agentPagePaintRecipient(agentId, agent);
    const modelEl = document.getElementById("agent-page-model");
    if (modelEl) modelEl.textContent = agent.model || "—";
    const runEl = document.getElementById("agent-page-runtime");
    if (runEl) runEl.textContent = _agentPageRuntime(_agentPageRunSec(agentId, pipe));
    const costEl = document.getElementById("agent-page-cost");
    if (costEl) costEl.textContent = _agentPageMoney(agent.cost_usd);
    if (COLOR_HEX[agentId]) {
      page.style.setProperty("--agent-page-color", COLOR_HEX[agentId]);
    }

    const mineMsgs = _agentPageMessagesFor(pipe, agentId);
    fillAgentPageJetzt(agentId, agent, pipe, snap, live, mineMsgs);
    fillAgentPageAuftrag(agentId, pipe, rights);
    fillAgentPageVerlauf(agentId, agent, mineMsgs, expert);
    fillAgentPageWerkzeuge(snap, pipe, expert);
    fillAgentPageDateien(snap);
    fillAgentPageMemory(snap, pipe);
    fillAgentPageErgebnis(agentId, pipe, expert);
    fillAgentPageEinstellungen(agentId, agent, snap, expert, rights);

    showAgentPageTab(keepTab || "jetzt");
    page.hidden = false;
    if (typeof bindAgentPage === "function") bindAgentPage();
  }

  function fillAgentPageJetzt(agentId, agent, pipe, snap, live, mineMsgs) {
    const panel = document.getElementById("agent-page-panel-jetzt");
    if (!panel) return;
    _agentPageClear(panel);
    const view = _agentPageLiveView(live, agent, snap);
    if (view.token === "laedt") {
      _agentPageLoading(panel, "Jetzt");
      return;
    }
    const msgs = mineMsgs || [];
    const err = pipe.last_error || pipe.error || (snap && snap.last_error) || "";
    const ask =
      (pipe.pending_question && pipe.pending_question.text) ||
      "";
    const parked = !!(agent && agent.parked);
    const blocked =
      parked ||
      pipe.result_status === "FEHLER" ||
      (pipe.validation && pipe.validation.ok === false);
    const blockText = parked
      ? "Agent ist geparkt."
      : pipe.result_status === "FEHLER"
        ? "Ergebnisstatus FEHLER."
        : pipe.validation && pipe.validation.ok === false
          ? String(pipe.validation.reason || pipe.validation.error || "Prüfung fehlgeschlagen.")
          : "";
    const task =
      (pipe.user_text && String(pipe.user_text).trim()) ||
      (msgs.length ? _agentPageMsgText(msgs[msgs.length - 1]) : "");
    const empty =
      view.token === "leer" ||
      (!task && !msgs.length && !err && !ask && !blocked && view.token === "wartet");
    if (empty) {
      _agentPageAdd(panel, "h2", "", "Jetzt");
      _agentPageEmpty(
        panel,
        "Keine Daten. Es läuft kein Auftrag, es gibt keine Ereignisse."
      );
      return;
    }
    _agentPageAdd(panel, "h2", "", "Jetzt");
    const grid = _agentPageAdd(panel, "div", "agent-page-grid", "");
    const taskCard = _agentPageAdd(grid, "article", "agent-page-card", "");
    _agentPageAdd(taskCard, "h3", "", "Aktueller Auftrag");
    _agentPageAdd(taskCard, "p", "", task || "Kein laufender Auftrag.");
    const stepCard = _agentPageAdd(grid, "article", "agent-page-card", "");
    _agentPageAdd(stepCard, "h3", "", "Prüfbarer Schritt");
    const last = msgs.length ? msgs[msgs.length - 1] : null;
    const step = last
      ? ((last.role === "user" ? "Du: " : "") + _agentPageMsgText(last)).trim()
      : view.token === "wartet"
        ? "Kein Schritt."
        : view.label;
    _agentPageAdd(stepCard, "p", "", step || "—");
    const timeCard = _agentPageAdd(grid, "article", "agent-page-card", "");
    _agentPageAdd(timeCard, "h3", "", "Zeit");
    const runSec = _agentPageRunSec(agentId, pipe);
    _agentPageKv(timeCard, [
      ["Start", runSec ? "dieser Lauf" : "kein Lauf"],
      ["Dauer", _agentPageRuntime(runSec)],
    ]);
    const stCard = _agentPageAdd(grid, "article", "agent-page-card", "");
    _agentPageAdd(stCard, "h3", "", "Status");
    const onOff =
      (agent && agent.enabled ? "an" : "aus") +
      (agent && agent.online ? " · online" : " · offline") +
      (parked ? " · geparkt" : "");
    _agentPageAdd(stCard, "p", "", view.label + " — " + onOff);
    const blockCard = _agentPageAdd(
      grid,
      "article",
      "agent-page-card" + (blockText ? " edge-warn" : ""),
      ""
    );
    _agentPageAdd(blockCard, "h3", "", "Blocker");
    _agentPageAdd(blockCard, "p", "", blockText || "Kein Blocker.");

    if (ask && view.token === "fragt") {
      const ban = _agentPageAdd(panel, "div", "agent-page-banner warn", "");
      ban.id = "agent-page-jetzt-ask";
      _agentPageAdd(ban, "h3", "", "Frage an dich");
      _agentPageAdd(ban, "p", "", String(ask));
    }
    if (blockText && (view.token === "blockiert" || parked)) {
      const ban = _agentPageAdd(panel, "div", "agent-page-banner warn", "");
      _agentPageAdd(ban, "h3", "", "Blocker (Hervorhebung)");
      _agentPageAdd(ban, "p", "", blockText);
    }
    if (err) {
      const ban = _agentPageAdd(panel, "div", "agent-page-banner err", "");
      _agentPageAdd(ban, "h3", "", "Fehler");
      _agentPageAdd(ban, "p", "", String(err));
    }

    _agentPageAdd(panel, "h3", "agent-page-h", "Letzte 3 Ereignisse");
    const last3 = msgs.slice(-3).reverse();
    if (!last3.length) {
      _agentPageEmpty(panel, "Keine Daten");
    } else {
      const ol = _agentPageAdd(panel, "ol", "agent-page-list", "");
      last3.forEach(function (m) {
        const li = _agentPageAdd(ol, "li", "agent-page-event", "");
        _agentPageAdd(li, "span", "agent-page-meta", _agentPageClock(m.ts || m.time) || "—");
        const who = m.role === "user" ? "Du" : agent.label || agentId;
        _agentPageAdd(li, "span", "", who + ": " + _agentPageMsgText(m));
        _agentPageTag(li, m.role === "user" ? "Auftrag" : "Antwort");
      });
    }

    _agentPageAdd(panel, "h3", "agent-page-h", "Erlaubte Aktionen");
    const actions = _agentPageAdd(panel, "div", "agent-page-actions", "");
    if (view.token === "fertig") {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "Ergebnis öffnen";
      btn.addEventListener("click", function () {
        showAgentPageTab("ergebnis");
      });
      actions.appendChild(btn);
    } else if (view.token === "fragt" && ask) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "Zur Frage";
      btn.addEventListener("click", function () {
        const el = document.getElementById("agent-page-jetzt-ask");
        if (el && el.focus) el.focus();
      });
      actions.appendChild(btn);
    } else {
      _agentPageAdd(
        panel,
        "p",
        "agent-page-meta",
        "In diesem Zustand keine Aktion. Öffnen der Ansicht wählt den Empfänger nicht."
      );
    }
  }

  function fillAgentPageAuftrag(agentId, pipe, rights) {
    const panel = document.getElementById("agent-page-panel-auftrag");
    if (!panel) return;
    _agentPageClear(panel);
    const snap = typeof lastSnapshot !== "undefined" ? lastSnapshot : null;
    if (!snap) {
      _agentPageLoading(panel, "Auftrag");
      return;
    }
    const talk = String(pipe.user_text || "").trim();
    const notes = String(pipe.brainstorm_notes || "").trim();
    const reqs = Array.isArray(pipe.distilled_requirements)
      ? pipe.distilled_requirements
      : [];
    const executed =
      !!(pipe.result_status || (pipe.worker_outputs || []).length) ||
      ["work", "done", "coordinate", "distill"].indexOf(String(pipe.stage || "")) >= 0;
    if (!talk && !notes && !reqs.length && !executed) {
      _agentPageAdd(panel, "h2", "", "Auftrag");
      _agentPageEmpty(
        panel,
        "Keine Daten. Weder Gespräch noch bestätigtes Execute."
      );
      return;
    }
    _agentPageAdd(panel, "h2", "", "Auftrag");
    const split = _agentPageAdd(panel, "div", "agent-page-split", "");
    const talkCard = _agentPageAdd(split, "article", "agent-page-card", "");
    _agentPageTag(talkCard, "Gespräch — nicht ausgeführt");
    _agentPageAdd(talkCard, "h3", "", "Unterhaltung vor Execute");
    _agentPageAdd(
      talkCard,
      "p",
      "",
      talk || notes || "Kein Gesprächstext für diesen Agenten."
    );
    if (notes && talk && notes !== talk) {
      _agentPageAdd(talkCard, "p", "agent-page-meta", notes);
    }
    _agentPageAdd(
      talkCard,
      "p",
      "agent-page-meta",
      executed
        ? "Gespräch bleibt sichtbar. Execute ist bestätigt."
        : "Das ist Brainstorm. Noch kein Auftrag an diesen Agenten."
    );
    const exeCard = _agentPageAdd(
      split,
      "article",
      "agent-page-card" + (executed ? " edge-ok" : ""),
      ""
    );
    _agentPageTag(exeCard, executed ? "Bestätigtes Execute" : "Noch kein Execute");
    _agentPageAdd(exeCard, "h3", "", "Originalauftrag");
    _agentPageAdd(exeCard, "p", "", executed ? talk || notes || "—" : "Kein bestätigtes Execute.");
    const targetAgent = findAgent(pipe.send_target || agentId);
    _agentPageKv(exeCard, [
      ["Sender", "Du"],
      ["Empfänger", (targetAgent && targetAgent.label) || pipe.send_target || agentId],
      ["Stufe", pipe.stage || "idle"],
      ["Freigabe", executed ? (pipe.result_status || "Execute / Arbeit") : "nicht bestätigt"],
    ]);
    const grid = _agentPageAdd(panel, "div", "agent-page-grid", "");
    const goalCard = _agentPageAdd(grid, "article", "agent-page-card", "");
    _agentPageAdd(goalCard, "h3", "", "Ziele");
    if (reqs.length) {
      reqs.slice(0, 8).forEach(function (r) {
        _agentPageAdd(goalCard, "p", "", typeof r === "string" ? r : String(r.text || r));
      });
    } else {
      _agentPageAdd(goalCard, "p", "agent-page-muted", "Keine Daten");
    }
    const frame = _agentPageAdd(grid, "article", "agent-page-card", "");
    _agentPageAdd(frame, "h3", "", "Rahmen");
    const agent = findAgent(agentId) || {};
    _agentPageKv(frame, [
      ["Modell", agent.model || "—"],
      ["Kosten", _agentPageMoney(agent.cost_usd)],
      ["Rechte", rights],
      ["Ergebnis", pipe.result_status || "—"],
    ]);
  }

  function fillAgentPageVerlauf(agentId, agent, mineMsgs, expert) {
    const panel = document.getElementById("agent-page-panel-verlauf");
    if (!panel) return;
    _agentPageClear(panel);
    const snap = typeof lastSnapshot !== "undefined" ? lastSnapshot : null;
    if (!snap) {
      _agentPageLoading(panel, "Verlauf");
      return;
    }
    const pipe = (snap && snap.pipeline) || {};
    const items = [];
    const cap = expert ? 80 : 40;
    (mineMsgs || []).slice(-cap).forEach(function (m) {
      const who = m.role === "user" ? "Du" : agent.label || agentId;
      const text = _agentPageMsgText(m);
      items.push({
        kind: m.role === "user" ? "antwort" : agentId === "coordinator" ? "entscheidung" : "antwort",
        time: _agentPageClock(m.ts || m.time) || "—",
        title: who + " · " + (m.role === "user" ? "Auftrag" : "Antwort"),
        body: expert || text.length <= 800 ? text : text.slice(0, 797) + "…",
        meta: "Quelle: " + who,
      });
    });
    const log = [].concat(pipe.tool_log || [], pipe.tool_calls || []);
    log.slice(expert ? -20 : -8).forEach(function (e) {
      if (!e) return;
      const name = e.tool || e.name || "?";
      const ok = e.ok !== false;
      items.push({
        kind: ok ? "werkzeug" : "fehler",
        time: _agentPageClock(e.ts || e.time) || "—",
        title: name + " · Werkzeug · " + (ok ? "ok" : "Fehler"),
        body: String(e.reason || e.result || e.error || (ok ? "Aufruf ok." : "Aufruf fehlgeschlagen.")),
        meta: "Quelle: Werkzeug " + name + (e.mode ? " · " + e.mode : ""),
      });
    });
    if (pipe.memory_context) {
      items.push({
        kind: "memory",
        time: "—",
        title: "Memory · gelesen",
        body: "Memory-Kontext in diesem Lauf verwendet.",
        meta: "Quelle: Memory",
      });
    }
    if (agent && Number(agent.cost_usd) > 0) {
      items.push({
        kind: "kosten",
        time: "—",
        title: "Lauf · Kosten · " + _agentPageMoney(agent.cost_usd),
        body: (agent.tokens || 0) + " Token in dieser Sitzung.",
        meta: "Quelle: Abrechnung",
      });
    }
    const err = pipe.error || pipe.last_error || "";
    if (err) {
      items.push({
        kind: "fehler",
        time: "—",
        title: "Lauf · Fehler",
        body: String(err),
        meta: "Quelle: Pipeline",
      });
    }
    const ws = (snap && snap.workspace) || {};
    ["temp", "selected", "perm"].forEach(function (z) {
      (Array.isArray(ws[z]) ? ws[z] : []).forEach(function (f) {
        const nm = _agentPageFileName(f);
        if (!nm || _agentPageSecretName(nm)) return;
        items.push({
          kind: "datei",
          time: "—",
          title: nm + " · Datei",
          body: "Im Workspace vorhanden.",
          meta: "Quelle: Dateien",
        });
      });
    });
    _agentPageAdd(panel, "h2", "", "Verlauf");
    if (!items.length) {
      _agentPageEmpty(
        panel,
        "Keine Daten. Es wurden noch keine Antworten, Werkzeuge oder Dateien aufgezeichnet."
      );
      return;
    }
    _agentPageAdd(panel, "p", "agent-page-meta", "Nur sichtbare Arbeit. Keine internen Gedanken.");
    const filters = _agentPageAdd(panel, "div", "agent-page-filters", "");
    filters.setAttribute("role", "group");
    filters.setAttribute("aria-label", "Verlauf filtern");
    AGENT_PAGE_HIST_FILTERS.forEach(function (pair) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "is-on";
      b.setAttribute("data-filter", pair[0]);
      b.textContent = pair[1];
      filters.appendChild(b);
    });
    const emptyF = _agentPageAdd(panel, "p", "agent-page-meta", "Keine Einträge für diesen Filter.");
    emptyF.hidden = true;
    const list = _agentPageAdd(panel, "div", "agent-page-list", "");
    items.forEach(function (it) {
      const row = document.createElement("details");
      row.className = "agent-page-hist";
      row.setAttribute("data-kind", it.kind);
      const sum = document.createElement("summary");
      const t = document.createElement("span");
      t.className = "agent-page-meta";
      t.textContent = it.time;
      sum.appendChild(t);
      sum.appendChild(document.createTextNode(" " + it.title));
      row.appendChild(sum);
      const p = document.createElement("p");
      p.textContent = it.body || "";
      row.appendChild(p);
      const meta = document.createElement("p");
      meta.className = "agent-page-meta";
      meta.textContent = it.meta || "";
      row.appendChild(meta);
      list.appendChild(row);
    });
    filters.addEventListener("click", function (ev) {
      const btn = ev.target && ev.target.closest ? ev.target.closest("button") : null;
      if (!btn) return;
      btn.classList.toggle("is-on");
      const on = {};
      filters.querySelectorAll("button").forEach(function (b) {
        on[b.getAttribute("data-filter")] = b.classList.contains("is-on");
      });
      let any = false;
      list.querySelectorAll(".agent-page-hist").forEach(function (row) {
        const show = !!on[row.getAttribute("data-kind")];
        row.hidden = !show;
        if (show) any = true;
      });
      emptyF.hidden = any;
    });
  }

  function fillAgentPageWerkzeuge(snap, pipe, expert) {
    const panel = document.getElementById("agent-page-panel-werkzeuge");
    if (!panel) return;
    _agentPageClear(panel);
    if (!snap) {
      _agentPageLoading(panel, "Werkzeuge");
      return;
    }
    const tools = (snap && snap.tools) || [];
    const log = (pipe && (pipe.tool_log || pipe.tool_calls)) || [];
    const hasTools = Array.isArray(tools) && tools.length;
    const hasLog = Array.isArray(log) && log.length;
    _agentPageAdd(panel, "h2", "", "Werkzeuge");
    if (!hasTools && !hasLog) {
      _agentPageEmpty(panel, "Keine Daten. Keine Werkzeuge in dieser Sitzung.");
      return;
    }
    const byName = {};
    (log || []).forEach(function (e) {
      if (!e) return;
      const name = String(e.tool || e.name || "");
      if (!name) return;
      if (!byName[name]) byName[name] = [];
      byName[name].push(e);
    });
    const grid = _agentPageAdd(panel, "div", "agent-page-grid", "");
    const shown = {};
    function addToolCard(t, name, desc) {
      const n = name || "?";
      if (shown[n]) return;
      shown[n] = true;
      const calls = byName[n] || [];
      const last = calls.length ? calls[calls.length - 1] : null;
      const fail = calls.some(function (c) { return c && c.ok === false; });
      const ok = last && last.ok !== false;
      const edge = last ? (fail ? "edge-err" : ok ? "edge-ok" : "") : "";
      const card = _agentPageAdd(
        grid,
        "article",
        "agent-page-card agent-tool-card" + (edge ? " " + edge : ""),
        ""
      );
      _agentPageAdd(card, "h3", "", n);
      _agentPageAdd(card, "p", "", desc || "");
      const lastLine = last
        ? (last.ok !== false ? "ok" : "Fehler") +
          (last.mode ? " · " + last.mode : "") +
          (last.reason ? " · " + last.reason : "")
        : "nicht benutzt in diesem Lauf";
      _agentPageKv(card, [
        ["Status", last ? lastLine : "nicht benutzt in diesem Lauf"],
        ["Rechte", "nur Anzeige — kein Schalter hier"],
        ["Zuletzt", last ? (last.reason || last.mode || (last.ok !== false ? "ok" : "Fehler")) : "—"],
        ["Ergebnis", last ? (last.ok !== false ? "Aufruf ok" : "Aufruf fehlgeschlagen") : "kein Aufruf"],
      ]);
    }
    if (hasTools) {
      tools.slice(0, expert ? 40 : 12).forEach(function (t) {
        addToolCard(t, t.name, t.description);
      });
    }
    Object.keys(byName).forEach(function (n) {
      addToolCard(null, n, "");
    });
  }

  function fillAgentPageDateien(snap) {
    const panel = document.getElementById("agent-page-panel-dateien");
    if (!panel) return;
    _agentPageClear(panel);
    if (!snap) {
      _agentPageLoading(panel, "Dateien");
      return;
    }
    const ws = (snap && snap.workspace) || {};
    const zones = [
      ["perm", "Gelesen", "Workspace, dauerhaft"],
      ["selected", "Erzeugt", "Workspace, behalten"],
      ["temp", "Geändert", "Workspace, Entwurf"],
    ];
    _agentPageAdd(panel, "h2", "", "Dateien");
    _agentPageAdd(
      panel,
      "p",
      "agent-page-meta",
      "Schlüsseldateien werden nicht gezeigt. Keine Secrets, keine .env."
    );
    let n = 0;
    zones.forEach(function (z) {
      const list = Array.isArray(ws[z[0]]) ? ws[z[0]] : [];
      const files = list
        .map(function (f) {
          return { name: _agentPageFileName(f), raw: f };
        })
        .filter(function (row) {
          return row.name && !_agentPageSecretName(row.name);
        });
      _agentPageAdd(panel, "h3", "agent-page-h", z[1]);
      if (!files.length) {
        _agentPageEmpty(panel, "Keine Daten");
        return;
      }
      n += files.length;
      files.forEach(function (row) {
        const box = _agentPageAdd(panel, "div", "agent-page-file agent-file-row", "");
        const info = _agentPageAdd(box, "div", "", "");
        const title = document.createElement("p");
        const b = document.createElement("b");
        b.textContent = row.name;
        title.appendChild(b);
        title.appendChild(document.createTextNode(" · " + z[2]));
        info.appendChild(title);
        const meta = document.createElement("p");
        meta.className = "agent-page-meta";
        meta.textContent = z[1] + " · " + row.name;
        info.appendChild(meta);
      });
    });
    if (!n) {
      /* headings already have empty cards */
    }
  }

  function fillAgentPageMemory(snap, pipe) {
    const panel = document.getElementById("agent-page-panel-memory");
    if (!panel) return;
    _agentPageClear(panel);
    if (!snap) {
      _agentPageLoading(panel, "Memory");
      return;
    }
    const mem = (snap && snap.memory) || {};
    const hot = [];
    (mem.facts || []).forEach(function (f) {
      const t = _agentPageFactText(f);
      if (t && hot.indexOf(t) < 0) hot.push(t);
    });
    const warm = [];
    (mem.warm_facts || []).forEach(function (f) {
      const t = _agentPageFactText(f);
      if (t && warm.indexOf(t) < 0) warm.push(t);
    });
    const coldN = (snap.cold && snap.cold.count) || 0;
    _agentPageAdd(panel, "h2", "", "Memory");
    if (!hot.length && !warm.length && !coldN && !(pipe && pipe.memory_context)) {
      _agentPageEmpty(panel, "Keine Daten. Kein Memory gelesen, keine Vorschläge, keine Konflikte.");
      return;
    }
    _agentPageAdd(
      panel,
      "p",
      "agent-page-meta",
      "HOT / WARM / COLD sind am Rand und am Etikett unterscheidbar. API-Schlüssel werden nicht angezeigt."
    );
    if (pipe && pipe.memory_context) {
      _agentPageAdd(panel, "p", "agent-page-meta", "Memory verwendet in diesem Lauf.");
    }

    function memCards(title, list, kind, edge) {
      _agentPageAdd(panel, "h3", "agent-page-h", title);
      if (!list.length) {
        _agentPageEmpty(panel, "Keine Daten");
        return;
      }
      const grid = _agentPageAdd(panel, "div", "agent-page-grid", "");
      list.slice(0, 8).forEach(function (t) {
        const card = _agentPageAdd(
          grid,
          "article",
          "agent-page-card agent-mem-row " + edge,
          ""
        );
        const p = _agentPageAdd(card, "p", "", "");
        _agentPageTag(p, kind, kind.toLowerCase());
        p.appendChild(document.createTextNode(" " + t));
        _agentPageKv(card, [
          ["Lage", kind],
          ["Geltung", kind === "HOT" ? "dieser Lauf" : kind === "WARM" ? "dieses Projekt" : "Archiv"],
        ]);
      });
    }
    memCards("HOT", hot, "HOT", "edge-hot");
    memCards("WARM", warm, "WARM", "edge-warm");
    _agentPageAdd(panel, "h3", "agent-page-h", "COLD");
    if (coldN) {
      const card = _agentPageAdd(panel, "article", "agent-page-card edge-cold", "");
      const p = _agentPageAdd(card, "p", "", "");
      _agentPageTag(p, "COLD", "cold");
      p.appendChild(
        document.createTextNode(" " + coldN + " Archive im COLD-Speicher.")
      );
    } else {
      _agentPageEmpty(panel, "Keine Daten");
    }
  }

  function fillAgentPageErgebnis(agentId, pipe, expert) {
    const panel = document.getElementById("agent-page-panel-ergebnis");
    if (!panel) return;
    _agentPageClear(panel);
    const snap = typeof lastSnapshot !== "undefined" ? lastSnapshot : null;
    if (!snap) {
      _agentPageLoading(panel, "Ergebnis");
      return;
    }
    const outs = ((pipe && pipe.worker_outputs) || []).filter(function (o) {
      return _agentPageOutputMine(o, agentId);
    });
    const stage = (pipe && pipe.stage) || "idle";
    const status = (pipe && pipe.result_status) || "";
    const live =
      typeof agentLiveStatus === "function" ? agentLiveStatus(agentId) : "wartet";
    const view = _agentPageLiveView(live, findAgent(agentId), snap);
    _agentPageAdd(panel, "h2", "", "Ergebnis");
    if (!outs.length && !status && stage === "idle") {
      _agentPageEmpty(panel, "Keine Daten. Nichts anzusehen, nichts zu behalten.");
      return;
    }
    const banner = _agentPageAdd(panel, "div", "agent-page-banner", "");
    if (view.token === "fehler" || status === "FEHLER") banner.classList.add("err");
    else if (view.token === "fertig") banner.classList.add("ok");
    else if (view.token === "aktiv" || view.token === "fragt" || view.token === "blockiert") {
      /* running — no edge */
    }
    let bannerText = "Kein gespeichertes Ergebnis. Erfolg gibt es erst nach „Behalten“.";
    if (view.token === "fertig") {
      bannerText = "Entwurf fertig. Erfolg: nein — erst nach bestätigtem Speichern.";
    } else if (view.token === "fehler" || status === "FEHLER") {
      bannerText = "Lauf mit Fehler. Artefakt unvollständig. Erfolg: nein.";
    } else if (view.token === "wartet") {
      bannerText = "Kein Lauf, kein Ergebnis.";
    } else if (view.token === "offline") {
      bannerText = "Letzter bekannter Entwurf. Agent offline.";
    } else if (status) {
      bannerText = "Ergebnisstatus: " + status + ".";
    }
    _agentPageAdd(banner, "p", "", bannerText);

    const names = outs.map(function (o) {
      return (o && (o.name || o.worker || agentId)) + (o && o.task ? " · " + o.task : "");
    });
    const grid = _agentPageAdd(panel, "div", "agent-page-grid", "");
    const art = _agentPageAdd(grid, "article", "agent-page-card", "");
    _agentPageAdd(art, "h3", "", "Artefakte");
    _agentPageAdd(art, "p", "", names.length ? names.join(", ") : "Keine Daten");
    const test = _agentPageAdd(grid, "article", "agent-page-card", "");
    _agentPageAdd(test, "h3", "", "Tests / Belege");
    const val = pipe && pipe.validation;
    const testLine = val
      ? val.ok === false
        ? String(val.reason || val.error || "Prüfung fehlgeschlagen.")
        : "Prüfung ok."
      : "Kein automatischer Test in diesem Lauf.";
    _agentPageAdd(test, "p", "", testLine);
    const open = _agentPageAdd(grid, "article", "agent-page-card", "");
    _agentPageAdd(open, "h3", "", "Offene Punkte");
    const warnText = Array.isArray(pipe && pipe.quality_notes)
      ? (pipe.quality_notes || []).join(" ")
      : String((pipe && pipe.quality_notes) || "");
    const warnList = (pipe && pipe.warnings) || [];
    const openText =
      (warnList.length ? warnList.join(" · ") : "") || warnText || "Keine offenen Punkte.";
    _agentPageAdd(open, "p", "", openText);

    if (!outs.length) return;
    const actions = _agentPageAdd(panel, "div", "agent-page-actions agent-page-result-actions", "");
    const first = outs[0];
    const raw = String((first && first.result) || "");
    const preview = _agentPageAdd(panel, "pre", "agent-page-preview", "");
    preview.textContent = _agentPagePreviewText(raw, expert ? 1200 : 400);

    const viewBtn = document.createElement("button");
    viewBtn.type = "button";
    viewBtn.textContent = "Ansehen";
    viewBtn.addEventListener("click", function () {
      preview.classList.toggle("is-on");
    });
    actions.appendChild(viewBtn);

    let idx = -1;
    if (typeof lastWorkerOutputs !== "undefined" && lastWorkerOutputs) {
      for (let i = 0; i < lastWorkerOutputs.length; i++) {
        if (_agentPageOutputMine(lastWorkerOutputs[i], agentId)) {
          idx = i;
          break;
        }
      }
    }
    if (typeof keepWorkerToPersonalWs === "function" || document.getElementById("box3-btn-keep")) {
      const keepBtn = document.createElement("button");
      keepBtn.type = "button";
      keepBtn.textContent = "Behalten";
      keepBtn.addEventListener("click", function () {
        if (typeof keepWorkerToPersonalWs === "function") {
          keepWorkerToPersonalWs(first, idx >= 0 ? idx : 0);
          return;
        }
        const btn = document.getElementById("box3-btn-keep");
        if (btn) btn.click();
      });
      actions.appendChild(keepBtn);
    }
    if (document.getElementById("box3-btn-away")) {
      const awayBtn = document.createElement("button");
      awayBtn.type = "button";
      awayBtn.textContent = "Weg";
      awayBtn.addEventListener("click", function () {
        if (typeof focusBox3WorkerResult === "function" && idx >= 0) {
          focusBox3WorkerResult(idx);
        }
        const btn = document.getElementById("box3-btn-away");
        if (btn) btn.click();
      });
      actions.appendChild(awayBtn);
    }
  }

  function fillAgentPageEinstellungen(agentId, agent, snap, expert, rights) {
    const panel = document.getElementById("agent-page-panel-einstellungen");
    if (!panel) return;
    _agentPageClear(panel);
    if (!snap) {
      _agentPageLoading(panel, "Einstellungen");
      return;
    }
    _agentPageAdd(panel, "h2", "", "Einstellungen");
    _agentPageAdd(
      panel,
      "p",
      "agent-page-meta",
      "Drei Gruppen. Rechte sind harte Aussagen, kein Schalter. God-Mode hier nur Status. API-Schlüssel werden nicht angezeigt."
    );

    _agentPageAdd(panel, "h3", "agent-page-h", "Verhalten");
    [
      ["temperature", "Temperature", agent.temperature, SLIDER_DEFAULTS.temperature],
      ["top_p", "Top-P", agent.top_p, SLIDER_DEFAULTS.top_p],
      ["max_tokens", "Max Tokens", agent.max_tokens, SLIDER_DEFAULTS.max_tokens],
      ["frequency", "Frequency", agent.frequency_penalty, SLIDER_DEFAULTS.frequency],
      ["presence", "Presence", agent.presence_penalty, SLIDER_DEFAULTS.presence],
    ].forEach(function (row) {
      const block = _agentPageAdd(panel, "div", "agent-page-slider", "");
      block.dataset.slider = row[0];
      _agentPageAdd(
        block,
        "h3",
        "",
        row[1] + ": " + paramVal(row[2], row[3])
      );
      _agentPageAdd(block, "p", "agent-page-meta", SLIDER_TIPS[row[0]] || "");
    });
    const tuneBtn = document.createElement("button");
    tuneBtn.type = "button";
    tuneBtn.textContent = "Regler in Box 3";
    tuneBtn.addEventListener("click", function () {
      if (typeof openTuneModal === "function") openTuneModal(agentId);
    });
    panel.appendChild(tuneBtn);
    const modelCard = _agentPageAdd(panel, "article", "agent-page-card", "");
    _agentPageAdd(modelCard, "h3", "", "Modell");
    _agentPageAdd(modelCard, "p", "", agent.model || "—");
    _agentPageAdd(
      modelCard,
      "p",
      "agent-page-meta",
      "API-Schlüssel werden nicht angezeigt."
    );

    const expRow = _agentPageAdd(panel, "div", "agent-page-row", "");
    const expBtn = document.createElement("button");
    expBtn.type = "button";
    expBtn.textContent = expert ? "Standardansicht" : "Expertenansicht";
    expBtn.addEventListener("click", function () {
      const hidden = document.getElementById("agent-page-expert");
      if (hidden) hidden.click();
    });
    expRow.appendChild(expBtn);
    _agentPageAdd(
      expRow,
      "span",
      "agent-page-meta",
      "Kleine Zusatzdetails in Verlauf, Werkzeuge, Skills."
    );

    _agentPageAdd(panel, "h3", "agent-page-h", "Fähigkeiten");
    const skillHost = _agentPageAdd(panel, "div", "agent-page-skills", "");
    skillHost.id = "agent-page-skills";
    _agentPageAdd(skillHost, "p", "agent-page-muted", "Lade Skills…");
    function fillSkills(list) {
      const pageNow = document.getElementById("agent-page");
      if (!pageNow || pageNow.dataset.agent !== agentId) return;
      const host = document.getElementById("agent-page-skills") || skillHost;
      host.textContent = "";
      const mine = (list || []).filter(function (s) {
        const ag = s.agents || [];
        return !ag.length || ag.indexOf(agentId) >= 0;
      });
      if (!mine.length) {
        _agentPageEmpty(host, "Keine Daten. Keine zugewiesenen Skills.");
        return;
      }
      mine.forEach(function (s) {
        const card = _agentPageAdd(host, "article", "agent-page-card agent-page-skill", "");
        _agentPageAdd(
          card,
          "h3",
          "",
          (s.name || s.id || "?") +
            " v" +
            (s.version || "?") +
            (s.enabled === false ? " · aus" : "")
        );
        _agentPageAdd(
          card,
          "p",
          "",
          "Zweck: " + (s.description || "(Playbook, nur Prompt)")
        );
        _agentPageAdd(
          card,
          "p",
          "agent-page-meta",
          "Auslöser: " + ((s.triggers || []).join(", ") || "manuell / Rollen-Match")
        );
        if (expert) {
          _agentPageAdd(
            card,
            "p",
            "agent-page-meta",
            "Daten: Skill-Text unter " +
              (s.path || "skills/") +
              " · Quelle " +
              (s.source || "")
          );
          _agentPageAdd(
            card,
            "p",
            "agent-page-meta",
            "Wirkung: Prompt-Text an den Agenten. Grenze: kein Code, keine Extra-Rechte, keine Secrets."
          );
        }
      });
    }
    if (typeof api === "function") {
      api("GET", "/api/skills")
        .then(function (data) {
          fillSkills((data && data.skills) || []);
        })
        .catch(function () {
          fillSkills([]);
        });
    } else {
      fillSkills([]);
    }

    _agentPageAdd(panel, "h3", "agent-page-h", "Rechte");
    const rightsCard = _agentPageAdd(panel, "article", "agent-page-card", "");
    _agentPageAdd(rightsCard, "p", "", rights);
    const godOn = !!(snap && snap.god_mode && snap.god_mode.enabled);
    const god = _agentPageAdd(panel, "div", "agent-page-god", "");
    const godTitle = document.createElement("p");
    const godB = document.createElement("b");
    godB.textContent = "God-Mode: " + (godOn ? "an" : "aus");
    godTitle.appendChild(godB);
    godTitle.appendChild(document.createTextNode(" — nur Status, kein Schalter."));
    god.appendChild(godTitle);
    _agentPageAdd(
      god,
      "p",
      "agent-page-meta",
      "Einschalten geht nicht in dieser Ansicht. Nur das Desk-Badge darf God-Mode setzen. God-Mode nur über den roten Knopf."
    );
  }

  function bindAgentPage() {
    const back = document.getElementById("agent-page-back");
    if (back && !back._bound) {
      back._bound = true;
      back.addEventListener("click", closeAgentPage);
    }
    const expert = document.getElementById("agent-page-expert");
    if (expert && !expert._bound) {
      expert._bound = true;
      expert.addEventListener("click", function () {
        const page = document.getElementById("agent-page");
        if (!page) return;
        const on = page.dataset.expert === "1";
        page.dataset.expert = on ? "0" : "1";
        expert.textContent = on ? "Expertenansicht" : "Standardansicht";
        openAgentPage(page.dataset.agent || lastClickedAgentId || "brainstorm");
      });
    }
    const tabs = document.getElementById("agent-page-tabs");
    if (tabs && !tabs._bound) {
      tabs._bound = true;
      tabs.addEventListener("click", function (ev) {
        const btn =
          ev.target && ev.target.closest
            ? ev.target.closest(".agent-page-tab")
            : null;
        if (!btn) return;
        showAgentPageTab(btn.getAttribute("data-tab") || "jetzt");
      });
      tabs.addEventListener("keydown", function (ev) {
        const cur = tabs.querySelector('.agent-page-tab[aria-selected="true"]');
        const i = AGENT_PAGE_TABS.indexOf(
          cur ? cur.getAttribute("data-tab") : "jetzt"
        );
        if (ev.key === "ArrowRight" || ev.key === "ArrowDown") {
          ev.preventDefault();
          showAgentPageTab(AGENT_PAGE_TABS[(i + 1) % AGENT_PAGE_TABS.length], true);
        } else if (ev.key === "ArrowLeft" || ev.key === "ArrowUp") {
          ev.preventDefault();
          showAgentPageTab(
            AGENT_PAGE_TABS[(i + AGENT_PAGE_TABS.length - 1) % AGENT_PAGE_TABS.length],
            true
          );
        } else if (ev.key === "Home") {
          ev.preventDefault();
          showAgentPageTab(AGENT_PAGE_TABS[0], true);
        } else if (ev.key === "End") {
          ev.preventDefault();
          showAgentPageTab(AGENT_PAGE_TABS[AGENT_PAGE_TABS.length - 1], true);
        }
      });
    }
    const setTarget = document.getElementById("agent-page-set-target");
    if (setTarget && !setTarget._bound) {
      setTarget._bound = true;
      setTarget.addEventListener("click", function () {
        const page = document.getElementById("agent-page");
        const id = (page && page.dataset.agent) || lastClickedAgentId;
        if (!id) return;
        sendTarget = id;
        _paintChatTargets();
        _agentPagePaintRecipient(id, findAgent(id) || {});
      });
    }
  }

  function updateBoxBorders() {
    /* nur Modulrahmen; Box-Rahmen bleiben neutral */
    if (lastClickedAgentId && COLOR_HEX[lastClickedAgentId]) {
      paintBoxesModule(lastClickedAgentId);
      return;
    }
    const mod = document.querySelector(".boxes");
    if (mod) mod.style.setProperty("--boxes-mod-color", "var(--border)");
    ["box1", "box2", "box3"].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.style.setProperty("--box-agent-color", "var(--border)");
    });
  }

  function renderCards() {
    els.cards.innerHTML = "";
    AGENTS.forEach(function (agent) {
      const card = document.createElement("div");
      const isActive = agentIsActive(agent);
      card.className =
        "agent-card color-" + agent.color + (isActive ? " is-active" : "");
      card.dataset.agentId = agent.id;
      card.dataset.enabled = agent.enabled ? "true" : "false";
      card.dataset.toggleable = agent.toggleable ? "true" : "false";
      card.dataset.parked = agent.parked ? "true" : "false";
      card.dataset.tooltipId = agent.id;
      card.setAttribute("role", "button");
      card.setAttribute(
        "aria-label",
        agent.label +
          " — click: layer+info · click again or Shift+click: tune · double-click: toggle" +
          (agent.id === "flex" ? " · Shift+double-click: preset" : "")
      );
      const online = !!agent.online;
      const presetLine =
        agent.id === "flex" && agent.preset
          ? '<div class="card-preset">preset: ' + agent.preset + "</div>"
          : "";
      const tok = agent.tokens || 0;
      const cost =
        agent.cost_usd != null && !isNaN(agent.cost_usd)
          ? Number(agent.cost_usd)
          : 0;
      const costStr = cost > 0 ? "$" + cost.toFixed(4) : "$0";
      const live =
        typeof agentLiveStatus === "function" ? agentLiveStatus(agent.id) : "";
      if (live) card.dataset.live = live;
      // eslint-disable-next-line no-unsanitized/property
      card.innerHTML =
        '<div class="card-name">' +
        agent.label +
        "</div>" +
        '<div class="card-meta">LLM: ' +
        (agent.model || "—") +
        "</div>" +
        '<div class="card-tokens">tok: ' +
        tok +
        ' · <span class="card-cost">' +
        costStr +
        "</span></div>" +
        '<div class="card-online ' +
        (online ? "on" : "off") +
        '">' +
        (online ? "online" : "offline") +
        "</div>" +
        '<label class="card-tts" data-stop="1">' +
        '<input type="checkbox" ' +
        (agent.tts ? "checked " : "") +
        (agent.parked ? "disabled " : "") +
        "/> TTS</label>" +
        presetLine +
        '<div class="card-status">' +
        statusLabel(agent) +
        "</div>" +
        (live ? '<div class="card-live">' + live + "</div>" : "");

      const ttsInput = card.querySelector(".card-tts input");
      if (ttsInput) {
        ttsInput.addEventListener("click", function (ev) {
          ev.stopPropagation();
        });
        ttsInput.addEventListener("change", function (ev) {
          ev.stopPropagation();
          const on = !!ttsInput.checked;
          // Speak HERE (same user gesture) — short DE only, no EN, no long monologue
          if (on) {
            speakNow("TTS an: " + (agent.label || agent.id) + ".");
          } else {
            stopSpeech();
          }
          setAgentTts(agent.id, on);
        });
      }

      card.addEventListener("click", function (ev) {
        if (ev.target && ev.target.closest && ev.target.closest("[data-stop]")) {
          return;
        }
        if (clickTimer) clearTimeout(clickTimer);
        const shiftTune = !!ev.shiftKey;
        clickTimer = setTimeout(function () {
          clickTimer = null;
          activateAgentLayer(agent.id, true);
          document.body.dataset.agentUserPick = agent.id;
          if (typeof openAgentPage === "function") openAgentPage(agent.id);
          if (shiftTune && typeof openTuneModal === "function") {
            openTuneModal(agent.id);
          }
        }, 220);
      });

      card.addEventListener("dblclick", function (ev) {
        ev.preventDefault();
        if (clickTimer) {
          clearTimeout(clickTimer);
          clickTimer = null;
        }
        if (agent.id === "flex") {
          toast("Flex is fixed — always on, personal companion", "info");
          return;
        }
        toggleAgent(agent.id);
      });
      card.addEventListener("mouseenter", function () {
        showTooltip(agent.id);
      });

      els.cards.appendChild(card);
    });
    updateBoxBorders();
    if (typeof _refreshAgentPageLive === "function") _refreshAgentPageLive();
  }

  function findAgent(id) {
    for (let i = 0; i < AGENTS.length; i++) {
      if (AGENTS[i].id === id) return AGENTS[i];
    }
    return null;
  }

  const TOAST_MAX = 2;
  const toastQueue = [];

  function toast(message, kind) {
    toastQueue.push({ message: String(message || ""), kind: kind || "info" });
    flushToasts();
  }

  function flushToasts() {
    const host = document.getElementById("toast-host");
    if (!host) {
      while (toastQueue.length) {
        const item = toastQueue.shift();
        console.log("[toast]", item.kind, item.message);
      }
      return;
    }
    while (host.children.length < TOAST_MAX && toastQueue.length) {
      mountToast(host, toastQueue.shift());
    }
  }

  function mountToast(host, item) {
    const el = document.createElement("div");
    el.className = "toast toast-" + (item.kind || "info");
    el.textContent = item.message;
    host.appendChild(el);
    requestAnimationFrame(function () {
      el.classList.add("show");
    });
    function dismiss() {
      el.classList.remove("show");
      setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
        flushToasts();
      }, 220);
    }
    if (item.kind === "error") {
      el.classList.add("toast-sticky");
      const x = document.createElement("button");
      x.type = "button";
      x.className = "toast-dismiss";
      x.textContent = "×";
      x.addEventListener("click", dismiss);
      el.appendChild(x);
      return;
    }
    let remaining = 4000;
    let timer = null;
    let started = 0;
    function arm() {
      started = Date.now();
      timer = setTimeout(dismiss, remaining);
    }
    el.addEventListener("mouseenter", function () {
      if (!timer) return;
      remaining -= Date.now() - started;
      clearTimeout(timer);
      timer = null;
    });
    el.addEventListener("mouseleave", function () {
      if (timer || remaining <= 0) return;
      arm();
    });
    arm();
  }

