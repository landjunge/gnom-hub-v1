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
    if (s === "fragt nach") return "fragt";
    if (s === "benutzt Werkzeug") return "werkzeug";
    if (s === "hat Ergebnis") return "ergebnis";
    if (s === "Fehler") return "fehler";
    if (s === "denkt" || s === "blockiert" || s === "wartet") return s;
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

  function showAgentPageTab(tabId) {
    const id = AGENT_PAGE_TABS.indexOf(tabId) >= 0 ? tabId : "jetzt";
    const page = document.getElementById("agent-page");
    if (page) page.dataset.tab = id;
    document.querySelectorAll("#agent-page-tabs .agent-page-tab").forEach(function (btn) {
      const on = btn.getAttribute("data-tab") === id;
      btn.classList.toggle("is-on", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    AGENT_PAGE_TABS.forEach(function (t) {
      const panel = document.getElementById("agent-page-panel-" + t);
      if (!panel) return;
      const on = t === id;
      panel.classList.toggle("is-on", on);
      if (on) panel.removeAttribute("hidden");
      else panel.hidden = true;
    });
  }

  function _refreshAgentPageLive() {
    const page = document.getElementById("agent-page");
    if (!page || page.hidden || !page.dataset.agent) return;
    const liveEl = document.getElementById("agent-page-live");
    if (!liveEl || typeof agentLiveStatus !== "function") return;
    const st = agentLiveStatus(page.dataset.agent);
    liveEl.textContent = st;
    liveEl.dataset.status = agentLiveStatusToken(st);
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
    const tip = TOOLTIPS[agentId] || {};
    const rights = AGENT_PAGE_RIGHTS[agentId] || "siehe Docs";
    const snap = typeof lastSnapshot !== "undefined" ? lastSnapshot : null;
    const pipe = (snap && snap.pipeline) || {};
    const expert = !!(page.dataset && page.dataset.expert === "1");
    const live =
      typeof agentLiveStatus === "function" ? agentLiveStatus(agentId) : "wartet";
    const roleText = (tip && tip.how_to) || rights;
    page.dataset.agent = agentId;
    const title = document.getElementById("agent-page-title");
    if (title) title.textContent = agent.label || agentId;
    const roleEl = document.getElementById("agent-page-role");
    if (roleEl) roleEl.textContent = roleText;
    const liveEl = document.getElementById("agent-page-live");
    if (liveEl) {
      liveEl.textContent = live;
      liveEl.dataset.status = agentLiveStatusToken(live);
    }
    const modelEl = document.getElementById("agent-page-model");
    if (modelEl) {
      modelEl.textContent =
        (agent.model || "—") + "  (API-Schlüssel werden nicht angezeigt)";
    }
    const costEl = document.getElementById("agent-page-cost");
    if (costEl) {
      costEl.textContent =
        (agent.tokens || 0) +
        " tok · $" +
        Number(agent.cost_usd || 0).toFixed(4);
    }
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
    const status =
      (agent.enabled ? "an" : "aus") +
      (agent.online ? " · online" : " · offline") +
      (agent.parked ? " · geparkt" : "");
    _agentPageAdd(panel, "p", "agent-page-line", "Status: " + live + " · " + status);
    const isTarget = String(pipe.send_target || "") === agentId;
    if (isTarget && pipe.user_text) {
      _agentPageAdd(
        panel,
        "p",
        "agent-page-line",
        "Aktuell: " + String(pipe.user_text).slice(0, 240)
      );
    } else if (mineMsgs.length) {
      const last = mineMsgs[mineMsgs.length - 1];
      const who = last.role === "user" ? "Du" : agent.label || agentId;
      _agentPageAdd(
        panel,
        "p",
        "agent-page-line",
        "Letzte Nachricht (" + who + "): " + _agentPageMsgText(last).slice(0, 240)
      );
    } else {
      _agentPageAdd(panel, "p", "agent-page-line", "Aktuell: (keine)");
    }
    const last3 = mineMsgs.slice(-3);
    if (last3.length) {
      _agentPageAdd(panel, "h3", "agent-page-h", "Letzte Nachrichten");
      last3.forEach(function (m) {
        const who = m.role === "user" ? "Du" : agent.label || agentId;
        _agentPageAdd(
          panel,
          "p",
          "agent-page-line",
          who + ": " + _agentPageMsgText(m).slice(0, 240)
        );
      });
    }
    const err = pipe.last_error || pipe.error || (snap && snap.last_error) || "";
    if (err) {
      _agentPageAdd(panel, "p", "agent-page-line", "Fehler: " + String(err));
    }
    if (agent.parked) {
      _agentPageAdd(panel, "p", "agent-page-line", "Blocker: Agent ist geparkt.");
    } else if (pipe.result_status === "FEHLER") {
      _agentPageAdd(panel, "p", "agent-page-line", "Blocker: Ergebnisstatus FEHLER.");
    } else if (pipe.pending_question && pipe.pending_question.text) {
      _agentPageAdd(
        panel,
        "p",
        "agent-page-line",
        "Blocker: " + String(pipe.pending_question.text).slice(0, 240)
      );
    }
  }

  function fillAgentPageAuftrag(agentId, pipe, rights) {
    const panel = document.getElementById("agent-page-panel-auftrag");
    if (!panel) return;
    _agentPageClear(panel);
    _agentPageAdd(
      panel,
      "p",
      "agent-page-line",
      "Auftrag: " + (pipe.user_text ? String(pipe.user_text) : "(keiner)")
    );
    _agentPageAdd(
      panel,
      "p",
      "agent-page-line",
      "Empfänger: " + (pipe.send_target || sendTarget || agentId)
    );
    _agentPageAdd(
      panel,
      "p",
      "agent-page-line",
      "Stage: " + (pipe.stage || "idle")
    );
    _agentPageAdd(
      panel,
      "p",
      "agent-page-line",
      "Ergebnisstatus: " + (pipe.result_status || "—")
    );
    _agentPageAdd(panel, "p", "agent-page-line", "Rechte: " + rights);
  }

  function fillAgentPageVerlauf(agentId, agent, mineMsgs, expert) {
    const panel = document.getElementById("agent-page-panel-verlauf");
    if (!panel) return;
    _agentPageClear(panel);
    if (!mineMsgs.length) {
      _agentPageAdd(panel, "p", "agent-page-line", "Kein Verlauf für diesen Agenten.");
      return;
    }
    const cap = expert ? mineMsgs.length : Math.min(mineMsgs.length, 40);
    mineMsgs.slice(-cap).forEach(function (m) {
      const who = m.role === "user" ? "Du" : agent.label || agentId;
      const text = _agentPageMsgText(m);
      _agentPageAdd(
        panel,
        "p",
        "agent-page-line",
        who + ": " + (expert || text.length <= 800 ? text : text.slice(0, 797) + "…")
      );
    });
  }

  function fillAgentPageWerkzeuge(snap, pipe, expert) {
    const panel = document.getElementById("agent-page-panel-werkzeuge");
    if (!panel) return;
    _agentPageClear(panel);
    const tools = (snap && snap.tools) || [];
    const log = (pipe && (pipe.tool_log || pipe.tool_calls)) || [];
    const hasTools = Array.isArray(tools) && tools.length;
    const hasLog = Array.isArray(log) && log.length;
    if (!hasTools && !hasLog) {
      _agentPageAdd(
        panel,
        "p",
        "agent-page-line",
        "Keine Werkzeuge in dieser Sitzung."
      );
      return;
    }
    if (hasTools) {
      tools.slice(0, expert ? 40 : 12).forEach(function (t) {
        const card = _agentPageAdd(panel, "div", "agent-tool-card", "");
        _agentPageAdd(card, "p", "agent-page-line", t.name || "?");
        _agentPageAdd(card, "p", "agent-page-line", t.description || "");
      });
    }
    if (hasLog) {
      _agentPageAdd(panel, "h3", "agent-page-h", "Letzte Aufrufe");
      log.slice(expert ? -20 : -8).forEach(function (e) {
        const name = (e && (e.tool || e.name)) || "?";
        const ok = !e || e.ok !== false ? "ok" : "FAIL";
        const mode = e && e.mode ? " · " + e.mode : "";
        _agentPageAdd(panel, "p", "agent-page-line", name + " · " + ok + mode);
      });
    }
  }

  function fillAgentPageDateien(snap) {
    const panel = document.getElementById("agent-page-panel-dateien");
    if (!panel) return;
    _agentPageClear(panel);
    const ws = (snap && snap.workspace) || {};
    const zones = [
      ["selected", "Selected"],
      ["temp", "Temp"],
      ["perm", "Perm"],
    ];
    let n = 0;
    zones.forEach(function (z) {
      const list = Array.isArray(ws[z[0]]) ? ws[z[0]] : [];
      const names = list
        .map(_agentPageFileName)
        .filter(function (nm) {
          return !!nm;
        });
      if (!names.length) return;
      n += names.length;
      _agentPageAdd(panel, "h3", "agent-page-h", z[1]);
      names.forEach(function (nm) {
        const row = _agentPageAdd(panel, "div", "agent-file-row", "");
        _agentPageAdd(row, "p", "agent-page-line", nm);
      });
    });
    if (!n) {
      _agentPageAdd(
        panel,
        "p",
        "agent-page-line",
        "Keine Dateien in selected, temp oder perm."
      );
    }
  }

  function fillAgentPageMemory(snap, pipe) {
    const panel = document.getElementById("agent-page-panel-memory");
    if (!panel) return;
    _agentPageClear(panel);
    const mem = (snap && snap.memory) || {};
    const hotN = mem.hot_count != null ? mem.hot_count : (mem.facts || []).length;
    const warmN =
      mem.warm_count != null ? mem.warm_count : (mem.warm_facts || []).length;
    _agentPageAdd(
      panel,
      "p",
      "agent-page-line",
      "HOT: " + hotN + " · WARM: " + warmN
    );
    if (pipe && pipe.memory_context) {
      _agentPageAdd(panel, "p", "agent-page-line", "Memory verwendet");
    }
    const facts = [];
    (mem.facts || []).forEach(function (f) {
      const t = _agentPageFactText(f);
      if (t && facts.indexOf(t) < 0) facts.push(t);
    });
    (mem.warm_facts || []).forEach(function (f) {
      const t = _agentPageFactText(f);
      if (t && facts.indexOf(t) < 0) facts.push(t);
    });
    if (!facts.length) {
      _agentPageAdd(panel, "p", "agent-page-line", "Keine Fakten in dieser Sitzung.");
      return;
    }
    facts.slice(0, 6).forEach(function (t) {
      const row = _agentPageAdd(panel, "div", "agent-mem-row", "");
      _agentPageAdd(row, "p", "agent-page-line", t);
    });
  }

  function fillAgentPageErgebnis(agentId, pipe, expert) {
    const panel = document.getElementById("agent-page-panel-ergebnis");
    if (!panel) return;
    _agentPageClear(panel);
    const calls = (pipe && (pipe.tool_calls || pipe.tool_log)) || [];
    const nTools = Array.isArray(calls) ? calls.length : 0;
    _agentPageAdd(
      panel,
      "p",
      "agent-page-line",
      "Stage: " + ((pipe && pipe.stage) || "idle")
    );
    _agentPageAdd(
      panel,
      "p",
      "agent-page-line",
      "Ergebnisstatus: " + ((pipe && pipe.result_status) || "—")
    );
    _agentPageAdd(panel, "p", "agent-page-line", "Tools: " + nTools);
    const outs = ((pipe && pipe.worker_outputs) || []).filter(function (o) {
      return _agentPageOutputMine(o, agentId);
    });
    if (!outs.length) {
      _agentPageAdd(
        panel,
        "p",
        "agent-page-line",
        "Kein Deliverable für diesen Agenten."
      );
      return;
    }
    outs.forEach(function (out) {
      const raw = String((out && out.result) || "");
      const shown =
        expert || raw.length <= 600 ? raw : raw.slice(0, 597) + "…";
      _agentPageAdd(
        panel,
        "p",
        "agent-page-line",
        (out.name || out.worker || agentId) + (out.task ? " · " + out.task : "")
      );
      if (shown) _agentPageAdd(panel, "p", "agent-page-line", shown);
      const actions = _agentPageAdd(panel, "div", "agent-page-result-actions", "");
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
        keepBtn.className = "btn-ws-sm";
        keepBtn.textContent = "Behalten";
        keepBtn.addEventListener("click", function () {
          if (typeof keepWorkerToPersonalWs === "function") {
            keepWorkerToPersonalWs(out, idx >= 0 ? idx : 0);
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
        awayBtn.className = "btn-ws-sm";
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
    });
  }

  function fillAgentPageEinstellungen(agentId, agent, snap, expert, rights) {
    const panel = document.getElementById("agent-page-panel-einstellungen");
    if (!panel) return;
    _agentPageClear(panel);
    _agentPageAdd(panel, "h3", "agent-page-h", "Verhalten");
    [
      ["temperature", "Temperature", agent.temperature, SLIDER_DEFAULTS.temperature],
      ["top_p", "Top-P", agent.top_p, SLIDER_DEFAULTS.top_p],
      ["max_tokens", "Max Tokens", agent.max_tokens, SLIDER_DEFAULTS.max_tokens],
      ["frequency", "Frequency", agent.frequency_penalty, SLIDER_DEFAULTS.frequency],
      ["presence", "Presence", agent.presence_penalty, SLIDER_DEFAULTS.presence],
    ].forEach(function (row) {
      const p = _agentPageAdd(
        panel,
        "p",
        "agent-page-line",
        row[1] + ": " + paramVal(row[2], row[3]) + " — " + (SLIDER_TIPS[row[0]] || "")
      );
      p.dataset.slider = row[0];
    });
    const tuneBtn = document.createElement("button");
    tuneBtn.type = "button";
    tuneBtn.className = "btn-ws-sm";
    tuneBtn.textContent = "Regler in Box 3";
    tuneBtn.addEventListener("click", function () {
      if (typeof openTuneModal === "function") openTuneModal(agentId);
    });
    panel.appendChild(tuneBtn);
    _agentPageAdd(
      panel,
      "p",
      "agent-page-line",
      "Modell: " + (agent.model || "—") + "  (API-Schlüssel werden nicht angezeigt)"
    );

    _agentPageAdd(panel, "h3", "agent-page-h", "Fähigkeiten");
    const skillHost = _agentPageAdd(panel, "div", "agent-page-skills", "");
    skillHost.id = "agent-page-skills";
    _agentPageAdd(skillHost, "p", "agent-page-line", "Lade Skills…");
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
        _agentPageAdd(host, "p", "agent-page-line", "Keine zugewiesenen Skills.");
        return;
      }
      mine.forEach(function (s) {
        const card = _agentPageAdd(host, "div", "agent-page-skill", "");
        _agentPageAdd(
          card,
          "p",
          "agent-page-line",
          (s.name || s.id || "?") +
            " v" +
            (s.version || "?") +
            (s.enabled === false ? " · aus" : "")
        );
        _agentPageAdd(
          card,
          "p",
          "agent-page-line",
          "Zweck: " + (s.description || "(Playbook, nur Prompt)")
        );
        _agentPageAdd(
          card,
          "p",
          "agent-page-line",
          "Auslöser: " + ((s.triggers || []).join(", ") || "manuell / Rollen-Match")
        );
        if (expert) {
          _agentPageAdd(
            card,
            "p",
            "agent-page-line",
            "Daten: Skill-Text unter " +
              (s.path || "skills/") +
              " · Quelle " +
              (s.source || "")
          );
          _agentPageAdd(
            card,
            "p",
            "agent-page-line",
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
    _agentPageAdd(panel, "p", "agent-page-line", rights);
    const godOn = !!(snap && snap.god_mode && snap.god_mode.enabled);
    _agentPageAdd(
      panel,
      "p",
      "agent-page-line",
      "God: " +
        (godOn ? "an" : "aus") +
        " · God-Mode nur über den roten Knopf"
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

