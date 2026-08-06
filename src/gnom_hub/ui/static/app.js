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
  let uiLang = "en";

  const FLEX_PRESETS = ["personal", "security", "neutral", "researcher"];

  const COLOR_HEX = {
    brainstorm: "#ff0000",
    memory: "#0066ff",
    flex: "#ffff00",
    coordinator: "#00cc44",
    worker1: "#00d4ff",
    worker2: "#7c3aed",
    worker3: "#ff2d95",
    worker4: "#ff6600",
  };

  const SLIDER_TIPS = {
    temperature:
      "Temperature: higher = more creative/random; lower = more focused and deterministic.",
    top_p:
      "Top-P (nucleus): samples from the smallest set of tokens whose probability mass ≥ p. Lower = safer.",
    max_tokens:
      "Max Tokens: hard cap on completion length. Higher allows longer HTML/docs; costs more.",
    frequency:
      "Frequency Penalty: reduces repeating the same tokens already used in the answer.",
    presence:
      "Presence Penalty: encourages talking about new topics; reduces staying on the same idea.",
  };

  // Display hints only (role prompts live in Python). Empty = code default.
  // Never treat these as the real system prompt unless the user edits Extra tuning.
  const DEFAULT_PROMPTS = {
    brainstorm:
      "(code default) Dialogue partner — build on history, concrete angles, optional “Soll ich umsetzen?”, no full code dump.",
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
    btnSave: document.getElementById("btn-save"),
    btnHelp: document.getElementById("btn-help"),
    btnSystem: document.getElementById("btn-system"),
    btnReset: document.getElementById("btn-reset"),
    stageBadge: document.getElementById("stage-badge"),
    llmBadge: document.getElementById("llm-badge"),
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
  };

  let activeStage = "idle";
  let tuneAgentId = null;
  /** Agent id last clicked — box module 1px border color */
  let lastClickedAgentId = null;
  let clickTimer = null;
  let recognition = null;
  let listening = false;
  let lastSpokenKey = "";
  let pendingSpeech = ""; // spoken on next click if browser blocked autoplay
  let ttsUnlocked = false; // true after speak started from a real click
  let lastAgentThoughts = {}; // reasoning streams for TTS (not Box text)
  let lastNudgeKey = ""; // avoid re-spamming Flex corrections in chat
  let currentJobId = null;
  let lastWorkerOutputs = [];
  let jobTimerStart = null;
  let jobTimerInterval = null;
  let lastJobElapsedSec = 0;
  let lastReportedPipelineError = null;
  let lastCanExecute = false;
  const CHAT_STORAGE_KEY = "gnom-hub-chat-log-v1";
  const HISTORY_KEY = "gnom-hub-result-history-v1";
  const CHAT_HIST_KEY = "gnom-hub-chat-input-hist-v1";
  const CHAT_HIST_MAX = 50;
  const HISTORY_MAX = 12;
  let resultHistory = [];
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
      log.className = "chat-log";
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
        /* compat aliases for primary content hosts */
        if (n === 2 && agent.id === "brainstorm") body.id = "box2-content";
        if (n === 3 && agent.id === "worker1") body.id = "box3-content";
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
    if (boxNum === 3 && aid === "worker1") {
      const b = document.getElementById("box3-content");
      if (b) return b;
    }
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

  /** Box 1 = Info-Platz: Agent-Tooltip füllt den Raum. */
  function fillBox1AgentInfo(agentId) {
    const tip = TOOLTIPS[agentId];
    const agent = findAgent(agentId);
    if (typeof showInfoLayer === "function") showInfoLayer("live");
    if (els.placeholder) els.placeholder.hidden = true;
    if (els.tipRoot) els.tipRoot.hidden = false;
    if (tip) {
      if (els.tipTitle) els.tipTitle.textContent = tip.title || (agent && agent.label) || agentId;
      if (els.tipHow) els.tipHow.textContent = tip.how_to || "";
      if (els.tipExample) els.tipExample.textContent = tip.example || "";
    } else if (agent) {
      if (els.tipTitle) els.tipTitle.textContent = agent.label || agentId;
      if (els.tipHow)
        els.tipHow.textContent =
          "Layer " +
          (AGENTS.findIndex(function (a) {
            return a.id === agentId;
          }) +
            1) +
          " · Klick = Info in Box 1 · Regler in Box 3 · Modulrahmen = Agentenfarbe.";
      if (els.tipExample)
        els.tipExample.textContent =
          "Model: " + (agent.model || "—") + (agent.enabled ? " · on" : " · off");
    }
    /* auch in Agent-Layer Body von Box 1 (Platz nutzen) */
    const body =
      typeof getAgentBoxBody === "function" ? getAgentBoxBody(1, agentId) : null;
    if (body) {
      const title = (tip && tip.title) || (agent && agent.label) || agentId;
      const how = (tip && tip.how_to) || "";
      const ex = (tip && tip.example) || "";
      body.innerHTML =
        '<div class="box1-agent-info">' +
        '<h2 class="tip-title">' +
        title +
        "</h2>" +
        (how ? '<p class="tip-how">' + how + "</p>" : "") +
        (ex ? '<p class="tip-example">' + ex + "</p>" : "") +
        "</div>";
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
          " — click to tune, double-click to toggle" +
          (agent.id === "flex" ? ", Shift+double-click cycles preset" : "")
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
        "</div>";

      const ttsInput = card.querySelector(".card-tts input");
      if (ttsInput) {
        ttsInput.addEventListener("click", function (ev) {
          ev.stopPropagation();
        });
        ttsInput.addEventListener("change", function (ev) {
          ev.stopPropagation();
          const on = !!ttsInput.checked;
          // Speak HERE (same user gesture) — not after await/API
          if (on) {
            speakNow(
              "Gedanken an für " + (agent.label || agent.id) + ". Ich spreche den Denkprozess, nicht den Text."
            );
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
        clickTimer = setTimeout(function () {
          clickTimer = null;
          activateAgentLayer(agent.id, true);
          openTuneModal(agent.id);
        }, 220);
      });

      card.addEventListener("dblclick", function (ev) {
        ev.preventDefault();
        if (clickTimer) {
          clearTimeout(clickTimer);
          clickTimer = null;
        }
        if (agent.id === "flex" && ev.shiftKey) {
          cycleFlexPreset();
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
  }

  function findAgent(id) {
    for (let i = 0; i < AGENTS.length; i++) {
      if (AGENTS[i].id === id) return AGENTS[i];
    }
    return null;
  }

  function toast(message, kind) {
    const host = document.getElementById("toast-host");
    if (!host) {
      console.log("[toast]", kind || "info", message);
      return;
    }
    const el = document.createElement("div");
    el.className = "toast toast-" + (kind || "info");
    el.textContent = message;
    host.appendChild(el);
    requestAnimationFrame(function () {
      el.classList.add("show");
    });
    setTimeout(function () {
      el.classList.remove("show");
      setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
      }, 220);
    }, 4200);
  }

/* part: 01-api-snapshot-tts.js  lines 324-704 of app.js — edit parts, run scripts/build_ui_js.py */
  async function api(method, path, body) {
    const opts = { method: method, headers: { "Content-Type": "application/json" } };
    if (body !== undefined) opts.body = JSON.stringify(body);
    let res;
    try {
      res = await fetch(API + path, opts);
    } catch (netErr) {
      toast("Network error: " + netErr.message, "error");
      throw netErr;
    }
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const j = await res.json();
        detail = j.detail || JSON.stringify(j);
      } catch (e) { /* ignore */ }
      toast(String(detail), "error");
      throw new Error(detail);
    }
    try {
      return await res.json();
    } catch (parseErr) {
      toast("Bad JSON from server (job/state) — " + (parseErr.message || parseErr), "error");
      throw parseErr;
    }
  }

  function applyAgentsFromServer(list) {
    if (!list || !list.length) return;
    list.forEach(function (s) {
      const a = findAgent(s.id);
      if (!a) return;
      a.enabled = !!s.enabled;
      a.toggleable = s.toggleable !== false;
      if (s.model) a.model = s.model;
      else if (s.role) a.model = "default";
      if (s.preset) a.preset = s.preset;
      a.tokens = s.tokens || 0;
      a.cost_usd = s.cost_usd != null ? Number(s.cost_usd) : 0;
      a.calls = s.calls != null ? Number(s.calls) : 0;
      a.online = !!s.online;
      a.tts = !!s.tts;
      a.system_prompt = s.system_prompt || "";
      a.temperature = s.temperature != null ? s.temperature : null;
      a.top_p = s.top_p != null ? s.top_p : null;
      a.max_tokens = s.max_tokens != null ? s.max_tokens : null;
      a.frequency_penalty =
        s.frequency_penalty != null ? s.frequency_penalty : null;
      a.presence_penalty =
        s.presence_penalty != null ? s.presence_penalty : null;
      a.parked = false;
    });
    renderCards();
  }

  function applySnapshot(snap) {
    if (!snap) return;
    applyUiPackExtras(snap);
    if (snap.agents) applyAgentsFromServer(snap.agents);
    const p = snap.pipeline || {};
    activeStage = p.stage || "idle";
    if (els.stageBadge) els.stageBadge.textContent = activeStage;
    renderCards();
    updateBoxBorders();
    if (els.flexSelect && snap.agents) {
      const flex = snap.agents.find(function (a) {
        return a.id === "flex";
      });
      if (flex && flex.preset) els.flexSelect.value = flex.preset;
    }

    if (snap.version) {
      const vb = document.getElementById("ver-badge");
      if (vb) vb.textContent = "v" + String(snap.version).replace(/^v/, "");
      document.title = "Gnom-Hub v" + String(snap.version).replace(/^v/, "");
    }

    if (els.llmBadge && snap.llm) {
      const ds = !!snap.llm.deepseek;
      const ol = !!snap.llm.ollama;
      const ok = ds || ol;
      const tok =
        (snap.llm.prompt_tokens || 0) + (snap.llm.completion_tokens || 0);
      let label = "LLM: stub";
      if (ds && ol) label = "LLM: DeepSeek+Ollama";
      else if (ds) label = "LLM: DeepSeek";
      else if (ol) label = "LLM: Ollama";
      els.llmBadge.textContent = ok ? label + " · " + tok + " tok" : label;
      els.llmBadge.classList.toggle("has-key", ok);
      els.llmBadge.title =
        "prompt=" +
        (snap.llm.prompt_tokens || 0) +
        " completion=" +
        (snap.llm.completion_tokens || 0);
    }
    updateCostBadge(snap.llm);
    if (els.memBadge && snap.memory_summary) {
      const short = String(snap.memory_summary).replace(/^HOT:\s*/i, "");
      const nodes =
        snap.canvas && snap.canvas.nodes != null
          ? " · canvas " + snap.canvas.nodes
          : "";
      els.memBadge.textContent = "Mem: " + short + nodes;
      els.memBadge.title = snap.memory_summary;
    }
    if (els.vecBadge && snap.vectors) {
      els.vecBadge.textContent = "Vec: " + (snap.vectors.count || 0);
      const coldN = snap.cold && snap.cold.count != null ? snap.cold.count : "—";
      els.vecBadge.title = "Click: vector store · docs=" + (snap.vectors.count || 0) + " · cold=" + coldN;
    }
    if (els.godBadge) {
      const on = !!(snap.god_mode && snap.god_mode.enabled);
      els.godBadge.textContent = on ? "God: ON" : "God: off";
      els.godBadge.classList.toggle("on", on);
    }
    if (els.coldBadge && snap.cold) {
      els.coldBadge.textContent = "Cold: " + (snap.cold.count || 0);
    }

    // Only toast fresh pipeline warnings/errors (avoid re-firing on every poll/bootstrap)
    if (snap.last_error && p.stage === "error") {
      toast(snap.last_error, "error");
    }
    if (p.warnings && p.warnings.length && (p.stage === "done" || p.stage === "error")) {
      // show at most 2 so UI is not flooded
      p.warnings.slice(0, 2).forEach(function (w) {
        toast(String(w), "info");
      });
    }

    // Flex told agents what was missing — surface once so you don't have to nag
    if (p.stage === "done" && p.agent_nudges && p.agent_nudges.length) {
      const nk = JSON.stringify(p.agent_nudges).slice(0, 200);
      if (nk !== lastNudgeKey) {
        lastNudgeKey = nk;
        p.agent_nudges.slice(0, 4).forEach(function (n) {
          const aid = (n && n.agent) || "?";
          const msg = (n && n.message) || "";
          if (!msg) return;
          appendChat("system", "Flex → " + aid + ": " + msg);
        });
        toast("Flex hat Agenten korrigiert (ohne dass du es wiederholen musst)", "ok");
      }
    }

    // Mermaid canvas preview under Box 3 when nodes exist
    if (snap.canvas && snap.canvas.mermaid && snap.canvas.nodes > 0) {
      const box3 = document.getElementById("box3-content");
      if (box3) {
        let prev = box3.querySelector(".canvas-preview");
        if (!prev) {
          prev = document.createElement("pre");
          prev.className = "canvas-preview";
          box3.appendChild(prev);
        }
        prev.textContent = snap.canvas.mermaid;
      }
    }

    if (snap.telegram && els.llmBadge) {
      // append telegram hint into mem badge title
      if (els.memBadge && snap.telegram.configured) {
        const run = snap.telegram.running ? "on" : "off";
        els.memBadge.title =
          (els.memBadge.title || "") + " | Telegram configured (" + run + ")";
      }
    }

    /* content → agent layers (box2: brainstorm/flex/coordinator; box3: workers) */
    if (p.brainstorm_turns && p.brainstorm_turns.length) {
      const lines = ["=== Brainstorm dialogue ==="];
      p.brainstorm_turns.forEach(function (t) {
        const role = t.role === "user" ? "You" : "Brainstorm";
        lines.push("");
        lines.push(role + ":");
        lines.push(String(t.text || ""));
      });
      setBox2(lines.join("\n"));
    } else if (p.brainstorm_notes) {
      setBox2("=== Brainstorm ===\n" + p.brainstorm_notes);
    } else if (p.stage === "idle") {
      setBox2(
        "Brainstorm dialogue appears here.\n\n" +
          "1) Send messages to brainstorm freely\n" +
          "2) Press Execute when ready for workers"
      );
    }
    if (p.flex_notes && typeof setBox2Agent === "function") {
      setBox2Agent("flex", "=== Flex review ===\n" + p.flex_notes, "Flex");
    }
    if (
      p.distilled_requirements &&
      p.distilled_requirements.length &&
      typeof setBox2Agent === "function"
    ) {
      const req = ["=== Requirements ==="].concat(
        p.distilled_requirements.map(function (r) {
          return "• " + r;
        })
      );
      setBox2Agent("coordinator", req.join("\n"), "Coordinator");
    }

    lastCanExecute = !!p.can_execute;
    if (els.btnExecute) {
      els.btnExecute.disabled = !lastCanExecute || chatBusy;
    }

    renderBox3Workers(p);

    if (p.pending_question && p.pending_question.text) {
      showClarify(p.pending_question.text);
    } else if (p.stage !== "clarify") {
      hideClarify();
    }

    // Only log pipeline errors once, and only while stage is error
    if (p.error && p.stage === "error") {
      if (p.error !== lastReportedPipelineError) {
        lastReportedPipelineError = p.error;
        appendChat("system", "Error: " + p.error);
      }
    } else if (p.stage === "done" || p.stage === "brainstorm" || !p.error) {
      lastReportedPipelineError = null;
    }

    // Keep latest thoughts for TTS (reasoning only)
    if (snap.agent_thoughts && typeof snap.agent_thoughts === "object") {
      lastAgentThoughts = snap.agent_thoughts;
    }

    // TTS: speak Gedanken after brainstorm / done — not the written HTML/notes
    if (p.stage === "done" || p.stage === "brainstorm") {
      maybeSpeakPipeline(p, snap);
    }
  }

  function stripForSpeech(text) {
    let s = String(text || "");
    s = s.replace(/```[\s\S]*?```/g, " ");
    s = s.replace(/<!DOCTYPE[\s\S]*$/i, " ");
    s = s.replace(/<[^>]+>/g, " ");
    s = s.replace(/&[a-z]+;/gi, " ");
    s = s.replace(/\s+/g, " ").trim();
    return s.slice(0, 400);
  }

  function stopSpeech() {
    try {
      if (window.speechSynthesis) window.speechSynthesis.cancel();
    } catch (_e) {
      /* ignore */
    }
    pendingSpeech = "";
  }

  /** Prefer German TTS (ui_lang or German text). */
  function pickTtsLang(text) {
    const clean = String(text || "");
    if (uiLang === "de" || /[äöüÄÖÜß]/.test(clean)) return "de-DE";
    // Default spoken thoughts in DE when UI is German-first desk
    if (uiLang !== "en") return "de-DE";
    return "en-US";
  }

  /** Must run inside a click/change handler — not after await. */
  function speakNow(text) {
    if (!window.speechSynthesis) {
      toast("TTS not available in this browser", "info");
      return false;
    }
    const clean = stripForSpeech(text);
    if (!clean) return false;
    try {
      // Do not cancel+speak in a broken way: cancel only if busy
      if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
        window.speechSynthesis.cancel();
      }
      const u = new SpeechSynthesisUtterance(clean);
      u.lang = pickTtsLang(clean);
      u.rate = 1.05;
      const voices = window.speechSynthesis.getVoices() || [];
      if (voices.length) {
        const want = u.lang.slice(0, 2).toLowerCase();
        const match =
          voices.find(function (v) {
            return (v.lang || "").toLowerCase().indexOf(want) === 0;
          }) ||
          voices.find(function (v) {
            return (v.lang || "").toLowerCase().indexOf("de") === 0;
          }) ||
          voices[0];
        if (match) u.voice = match;
      }
      u.onstart = function () {
        ttsUnlocked = true;
      };
      u.onerror = function (ev) {
        const err = (ev && ev.error) || "error";
        if (err !== "interrupted" && err !== "canceled") {
          pendingSpeech = clean;
          toast("TTS blocked — click page once, then enable TTS again", "info");
        }
      };
      window.speechSynthesis.speak(u);
      // Some Chrome builds need resume after speak
      try {
        window.speechSynthesis.resume();
      } catch (_r) {
        /* ignore */
      }
      return true;
    } catch (_e) {
      pendingSpeech = clean;
      toast("TTS failed — click page and try again", "info");
      return false;
    }
  }

  function speakOrQueue(text) {
    const clean = stripForSpeech(text);
    if (!clean) return;
    if (ttsUnlocked) {
      speakNow(clean);
    } else {
      pendingSpeech = clean;
      toast("TTS: click anywhere to hear", "info");
    }
  }

  if (typeof window !== "undefined" && window.speechSynthesis) {
    try {
      window.speechSynthesis.getVoices();
      window.speechSynthesis.onvoiceschanged = function () {
        window.speechSynthesis.getVoices();
      };
    } catch (_e) {
      /* ignore */
    }
    document.addEventListener(
      "click",
      function () {
        if (pendingSpeech) {
          const t = pendingSpeech;
          pendingSpeech = "";
          speakNow(t);
        }
      },
      true
    );
  }

  /**
   * TTS speaks agent *thoughts* (reasoning), not the written Box text / HTML.
   * Thoughts come from snapshot.agent_thoughts when the agent has TTS on
   * (backend enables DeepSeek thinking for that call).
   */
  function maybeSpeakPipeline(p, snap) {
    const thoughts =
      (snap && snap.agent_thoughts) ||
      (p && p.agent_thoughts) ||
      lastAgentThoughts ||
      {};
    const thoughtKey = Object.keys(thoughts)
      .map(function (k) {
        return k + ":" + String(thoughts[k] || "").slice(0, 40);
      })
      .join("|");
    const key =
      (p.stage || "") +
      "|" +
      thoughtKey +
      "|" +
      ((p.worker_outputs && p.worker_outputs.length) || 0);
    if (key === lastSpokenKey) return;
    const chunks = [];
    function pushThought(agentId, label) {
      const a = findAgent(agentId);
      if (!a || !a.tts) return;
      const t = thoughts[agentId];
      if (t && String(t).trim()) {
        chunks.push((label || a.label || agentId) + ". " + stripForSpeech(t));
      }
    }
    pushThought("brainstorm", "Brainstorm");
    pushThought("memory", "Memory");
    pushThought("flex", "Flex");
    pushThought("coordinator", "Coordinator");
    ["worker1", "worker2", "worker3", "worker4"].forEach(function (wid) {
      pushThought(wid, null);
    });
    if (chunks.length) {
      lastSpokenKey = key;
      speakOrQueue(chunks.join(" "));
    }
  }

  async function setAgentTts(id, on) {
    const a = findAgent(id);
    if (!a || a.parked) return;
    a.tts = on;
    try {
      const data = await api("POST", "/api/agents/" + encodeURIComponent(id) + "/tune", {
        tts: on,
      });
      if (data) {
        a.tts = !!data.tts;
        a.online = !!data.online;
      }
      // Do NOT speak after await — gesture is gone (Chrome blocks it)
      renderCards();
      toast(on ? "TTS on: " + (a.label || id) : "TTS off: " + (a.label || id), on ? "ok" : "info");
    } catch (err) {
      appendChat("system", "TTS save failed: " + err.message);
      toast("TTS save failed", "error");
    }
  }

/* part: 02-modals-tools-ws.js  lines 705-1949 of app.js — edit parts, run scripts/build_ui_js.py */
  function openTuneModal(id) {
    const a = findAgent(id);
    const layer = document.getElementById("tune-layer");
    if (!a || !layer) return;
    tuneAgentId = id;
    const title = document.getElementById("tune-title");
    if (title) title.textContent = a.label + " — tuning";
    const promptEl = document.getElementById("tune-prompt");
    if (promptEl)
      promptEl.value = a.system_prompt || DEFAULT_PROMPTS[id] || "";
    const modelEl = document.getElementById("tune-model");
    if (modelEl) modelEl.value = a.model || "deepseek-chat";
    const keyEl = document.getElementById("tune-key");
    if (keyEl) keyEl.value = "";
    const setRange = function (idEl, valEl, v, def, digits) {
      const el = document.getElementById(idEl);
      if (!el) return;
      const num = v != null ? Number(v) : def;
      el.value = String(num);
      const valNode = document.getElementById(valEl);
      if (valNode)
        valNode.textContent =
          digits === 0 ? String(Math.round(num)) : Number(num).toFixed(digits);
    };
    setRange("tune-temp", "tune-temp-val", a.temperature, 0.5, 2);
    setRange("tune-topp", "tune-topp-val", a.top_p, 1, 2);
    setRange("tune-maxtok", "tune-maxtok-val", a.max_tokens, 800, 0);
    setRange("tune-freq", "tune-freq-val", a.frequency_penalty, 0, 2);
    setRange("tune-pres", "tune-pres-val", a.presence_penalty, 0, 2);
    const tts = document.getElementById("tune-tts");
    if (tts) tts.checked = !!a.tts;
    layer.hidden = false;
    document.body.classList.add("tune-open");
    showSliderTip("temperature");
  }

  function closeTuneModal() {
    const layer = document.getElementById("tune-layer");
    if (layer) layer.hidden = true;
    document.body.classList.remove("tune-open");
    tuneAgentId = null;
  }

  function showSliderTip(key) {
    const tip = SLIDER_TIPS[key];
    if (!tip) return;
    // Box 1 layer "Regler" — dynamic info for active control
    if (typeof showInfoLayer === "function") showInfoLayer("tune");
    const title = document.getElementById("tune-tip-title");
    const how = document.getElementById("tune-tip-how");
    const ex = document.getElementById("tune-tip-example");
    const val = document.getElementById("tune-tip-value");
    if (title) title.textContent = "Regler: " + key;
    if (how) how.textContent = tip;
    if (ex)
      ex.textContent =
        "Schieber — Info live in Box 1. Regler-UI in Box 3.";
    // current value if range exists
    const map = {
      temperature: "tune-temp",
      top_p: "tune-topp",
      max_tokens: "tune-maxtok",
      frequency: "tune-freq",
      presence: "tune-pres",
    };
    const el = document.getElementById(map[key] || "");
    if (val && el) val.textContent = "Aktuell: " + el.value;
  }

  function bindTuneSliders() {
    const pairs = [
      ["tune-temp", "tune-temp-val", 2, "temperature"],
      ["tune-topp", "tune-topp-val", 2, "top_p"],
      ["tune-maxtok", "tune-maxtok-val", 0, "max_tokens"],
      ["tune-freq", "tune-freq-val", 2, "frequency"],
      ["tune-pres", "tune-pres-val", 2, "presence"],
    ];
    pairs.forEach(function (p) {
      const el = document.getElementById(p[0]);
      if (!el) return;
      el.addEventListener("input", function () {
        const n = Number(el.value);
        const valNode = document.getElementById(p[1]);
        if (valNode)
          valNode.textContent =
            p[2] === 0 ? String(Math.round(n)) : n.toFixed(p[2]);
        showSliderTip(p[3]);
      });
      el.addEventListener("pointerdown", function () {
        showSliderTip(p[3]);
      });
    });
  }

  async function saveTuneModal() {
    if (!tuneAgentId) return;
    const ttsOn = !!document.getElementById("tune-tts").checked;
    const body = {
      // Don't persist UI placeholder hints as real system_prompt
      system_prompt: (function () {
        var v = (document.getElementById("tune-prompt").value || "").trim();
        var hint = (DEFAULT_PROMPTS[tuneAgentId] || "").trim();
        if (!v || v === hint || v.indexOf("(code default)") === 0) return "";
        // stale LOL default from older UI — drop it
        if (v.indexOf("Output 5") >= 0 && v.indexOf("bullet") >= 0) return "";
        return v;
      })(),
      model: document.getElementById("tune-model").value,
      temperature: Number(document.getElementById("tune-temp").value),
      top_p: Number(document.getElementById("tune-topp").value),
      max_tokens: Number(document.getElementById("tune-maxtok").value),
      frequency_penalty: Number(document.getElementById("tune-freq").value),
      presence_penalty: Number(document.getElementById("tune-pres").value),
      tts: ttsOn,
    };
    const key = document.getElementById("tune-key").value.trim();
    if (key) body.api_key = key;
    // Speak in the same click as Save (before await)
    if (ttsOn) {
      const a = findAgent(tuneAgentId);
      speakNow(
        "Gedanken an für " +
          ((a && a.label) || tuneAgentId) +
          ". Ich spreche den Denkprozess, nicht den Text."
      );
    } else {
      stopSpeech();
    }
    try {
      const data = await api(
        "POST",
        "/api/agents/" + encodeURIComponent(tuneAgentId) + "/tune",
        body
      );
      applyAgentsFromServer([data]);
      closeTuneModal();
      toast("Agent tuning saved", "ok");
      try {
        await api("POST", "/api/save");
      } catch (_e) {
        /* optional */
      }
    } catch (err) {
      toast("Tune failed: " + err.message, "error");
    }
  }

  async function openSystemModal() {
    if (!els.systemModal) return;
    try {
      const s = await api("GET", "/api/system");
      const parts = [];
      parts.push(s.deepseek ? "DeepSeek: on" : "DeepSeek: off");
      parts.push(s.ollama ? "Ollama: on" : "Ollama: off");
      if (s.version) parts.push("v" + s.version);
      document.getElementById("system-llm").textContent = parts.join(" · ");
      document.getElementById("sys-free-only").checked = !!s.free_only;
      document.getElementById("sys-budget").value =
        s.max_budget_usd != null ? s.max_budget_usd : "";
      document.getElementById("sys-model").value = s.default_model || "deepseek-chat";
      // Ollama model datalist
      try {
        const om = await api("GET", "/api/ollama/models");
        const dl = document.getElementById("ollama-models-list");
        const line = document.getElementById("sys-ollama-models");
        if (dl) {
          dl.innerHTML = "";
          (om.models || []).forEach(function (name) {
            const opt = document.createElement("option");
            opt.value = "ollama/" + name;
            dl.appendChild(opt);
          });
        }
        if (line) {
          line.textContent = om.ok
            ? "Ollama models: " + ((om.models || []).join(", ") || "(none pulled)")
            : "Ollama models: offline";
        }
      } catch (_e) {
        /* ignore */
      }
      document.getElementById("system-spend").textContent =
        "Spent: $" +
        (Number(s.spent_usd) || 0).toFixed(4) +
        " · tokens " +
        ((s.prompt_tokens || 0) + (s.completion_tokens || 0));
      const langEl = document.getElementById("sys-lang");
      if (langEl) langEl.value = s.ui_lang || uiLang || "en";
      const ck = document.getElementById("system-ckpt");
      if (ck) {
        ck.textContent = s.checkpoint_exists
          ? "Checkpoint: available (Load to resume)"
          : "Checkpoint: none yet";
      }
      // Worker presets
      try {
        const pl = await api("GET", "/api/worker-presets");
        const sel = document.getElementById("sys-preset-select");
        if (sel) {
          const cur = sel.value;
          sel.innerHTML = '<option value="">— select preset —</option>';
          (pl.presets || []).forEach(function (p) {
            const opt = document.createElement("option");
            opt.value = p.name || "";
            opt.textContent =
              (p.name || "?") + " (" + (p.source_agent || "") + ")";
            sel.appendChild(opt);
          });
          if (cur) sel.value = cur;
        }
      } catch (_e2) {
        /* ignore */
      }
      // Team presets + plan_mode
      try {
        const tp = await api("GET", "/api/team-presets");
        const tsel = document.getElementById("sys-team-select");
        if (tsel) {
          const cur = tsel.value;
          tsel.innerHTML = '<option value="">— select team —</option>';
          (tp.presets || []).forEach(function (p) {
            const opt = document.createElement("option");
            opt.value = p.name || "";
            opt.textContent =
              (p.name || "?") +
              (p.plan_mode ? " · " + p.plan_mode : "");
            tsel.appendChild(opt);
          });
          if (cur) tsel.value = cur;
        }
        const pm = document.getElementById("sys-plan-mode");
        if (pm && tp.plan_mode) pm.value = tp.plan_mode;
      } catch (_te) {
        /* ignore */
      }
      const ap = document.getElementById("sys-auto-pack");
      if (ap) ap.checked = !!s.auto_pack_after_execute;
      const pm = document.getElementById("sys-pack-max");
      if (pm && s.pack_max != null) pm.value = String(s.pack_max);
      try {
        await renderHotList();
      } catch (_h) {
        /* ignore */
      }
      try {
        await renderWarmList();
      } catch (_w) {
        /* ignore */
      }
      // Session packs list
      try {
        await renderPackList(s.packs);
      } catch (_pe) {
        /* ignore */
      }
      // Backups list
      try {
        const bl = await api("GET", "/api/backups");
        const ul = document.getElementById("sys-backup-list");
        if (ul) {
          ul.innerHTML = "";
          const items = bl.backups || s.backups || [];
          if (!items.length) {
            const li = document.createElement("li");
            li.className = "muted";
            li.textContent = "(no backups yet)";
            ul.appendChild(li);
          } else {
            items.slice(0, 8).forEach(function (b) {
              const li = document.createElement("li");
              li.style.display = "flex";
              li.style.gap = "6px";
              li.style.alignItems = "center";
              const nameSpan = document.createElement("span");
              nameSpan.className = "ws-name";
              nameSpan.style.flex = "1";
              nameSpan.style.minWidth = "0";
              nameSpan.style.overflow = "hidden";
              nameSpan.style.textOverflow = "ellipsis";
              nameSpan.style.whiteSpace = "nowrap";
              nameSpan.textContent =
                (b.name || "") +
                " · " +
                (b.bytes != null ? Math.round(b.bytes / 1024) + " KB" : "");
              nameSpan.title = "Click to download";
              nameSpan.addEventListener("click", function () {
                window.location.href =
                  "/api/backups/" + encodeURIComponent(b.name) + "/download";
              });
              const rst = document.createElement("button");
              rst.type = "button";
              rst.className = "btn-ws-sm";
              rst.textContent = "Rest";
              rst.title = "Restore HOT/WARM/agents from this backup";
              rst.addEventListener("click", function (ev) {
                ev.stopPropagation();
                restoreBackupByName(b.name);
              });
              const del = document.createElement("button");
              del.type = "button";
              del.className = "ws-action";
              del.textContent = "×";
              del.title = "Delete backup";
              del.addEventListener("click", function (ev) {
                ev.stopPropagation();
                deleteBackupByName(b.name);
              });
              li.appendChild(nameSpan);
              li.appendChild(rst);
              li.appendChild(del);
              ul.appendChild(li);
            });
          }
        }
      } catch (_e3) {
        /* ignore */
      }
    } catch (err) {
      toast("System load failed: " + err.message, "error");
    }
    els.systemModal.hidden = false;
  }

  async function applySelectedPreset() {
    const sel = document.getElementById("sys-preset-select");
    const agent = document.getElementById("sys-preset-agent");
    const name = sel && sel.value;
    if (!name) {
      toast("Select a preset", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/worker-presets/apply", {
        name: name,
        agent_id: (agent && agent.value) || "worker1",
      });
      applyAgentsFromServer([data]);
      toast("Preset applied to " + ((agent && agent.value) || "worker1"), "ok");
    } catch (err) {
      toast("Apply failed: " + err.message, "error");
    }
  }

  async function deleteSelectedPreset() {
    const sel = document.getElementById("sys-preset-select");
    const name = sel && sel.value;
    if (!name) {
      toast("Select a preset", "info");
      return;
    }
    if (!confirm('Delete preset "' + name + '"?')) return;
    try {
      await api("POST", "/api/worker-presets/delete", {
        name: name,
        agent_id: "worker1",
      });
      toast("Preset deleted", "ok");
      openSystemModal();
    } catch (err) {
      toast("Delete failed: " + err.message, "error");
    }
  }

  async function applySelectedTeam() {
    const sel = document.getElementById("sys-team-select");
    const name = sel && sel.value;
    if (!name) {
      toast("Select a team preset", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/team-presets/apply", { name: name });
      if (data.agents) applyAgentsFromServer(data.agents);
      else if (data.snapshot) applySnapshot(data.snapshot);
      const pm = document.getElementById("sys-plan-mode");
      if (pm && data.plan_mode) pm.value = data.plan_mode;
      appendChat(
        "system",
        "Team preset → " + name + " · plan_mode=" + (data.plan_mode || "?")
      );
      toast("Team applied: " + name, "ok");
      renderCards();
    } catch (err) {
      toast("Team apply failed: " + err.message, "error");
    }
  }

  async function saveCurrentTeam() {
    const name = prompt("Team preset name:", "my-team");
    if (!name || !String(name).trim()) return;
    try {
      const data = await api("POST", "/api/team-presets", {
        name: String(name).trim(),
      });
      toast(
        "Team saved: " + ((data.preset && data.preset.name) || name),
        "ok"
      );
      openSystemModal();
    } catch (err) {
      toast("Team save failed: " + err.message, "error");
    }
  }

  async function deleteSelectedTeam() {
    const sel = document.getElementById("sys-team-select");
    const name = sel && sel.value;
    if (!name) {
      toast("Select a team preset", "info");
      return;
    }
    if (!confirm('Delete team preset "' + name + '"?')) return;
    try {
      await api("POST", "/api/team-presets/delete", { name: name });
      toast("Team deleted", "ok");
      openSystemModal();
    } catch (err) {
      toast("Team delete failed: " + err.message, "error");
    }
  }

  async function setPlanModeFromUi() {
    const pm = document.getElementById("sys-plan-mode");
    const mode = pm && pm.value;
    if (!mode) return;
    try {
      const data = await api("POST", "/api/plan-mode", { plan_mode: mode });
      toast("plan_mode → " + (data.plan_mode || mode), "ok");
    } catch (err) {
      toast("plan_mode failed: " + err.message, "error");
    }
  }

  function closeSystemModal() {
    if (els.systemModal) els.systemModal.hidden = true;
  }

  async function saveSystemModal() {
    const budgetRaw = document.getElementById("sys-budget").value.trim();
    const langEl = document.getElementById("sys-lang");
    const apEl = document.getElementById("sys-auto-pack");
    const body = {
      free_only: !!document.getElementById("sys-free-only").checked,
      default_model: document.getElementById("sys-model").value.trim() || "deepseek-chat",
      max_budget_usd: budgetRaw === "" ? null : Number(budgetRaw),
      ui_lang: langEl ? langEl.value : "en",
      auto_pack_after_execute: apEl ? !!apEl.checked : false,
      pack_max: (function () {
        const el = document.getElementById("sys-pack-max");
        if (!el || el.value === "") return undefined;
        const n = parseInt(el.value, 10);
        return Number.isFinite(n) ? n : undefined;
      })(),
    };
    try {
      await api("POST", "/api/system", body);
      if (body.ui_lang) await loadTooltips(body.ui_lang);
      closeSystemModal();
      toast("System settings applied", "ok");
      const snap = await api("GET", "/api/state");
      applySnapshot(snap);
    } catch (err) {
      toast("System save failed: " + err.message, "error");
    }
  }

  function closeVectorModal() {
    if (els.vectorModal) els.vectorModal.hidden = true;
  }

  function closeUsageModal() {
    if (els.usageModal) els.usageModal.hidden = true;
  }

  function closeToolsModal() {
    if (els.toolsModal) els.toolsModal.hidden = true;
  }

  async function openToolsModal() {
    if (!els.toolsModal) return;
    els.toolsModal.hidden = false;
    await refreshToolsModal();
    await refreshComputerUseLine();
  }

  async function refreshComputerUseLine() {
    const line = document.getElementById("cu-god-line");
    if (!line) return;
    try {
      const data = await api("GET", "/api/computer-use");
      const god = !!(data.god_mode && data.god_mode.enabled);
      const allow =
        (data.computer &&
          data.computer.action &&
          data.computer.action.shell_allow) ||
        [];
      line.textContent =
        "God-Mode: " +
        (god ? "ON (real control)" : "off (dry-run only)") +
        " · shell: " +
        allow.slice(0, 6).join(" ") +
        (allow.length > 6 ? "…" : "");
    } catch (_e) {
      line.textContent = "Computer use: status unavailable";
    }
  }

  function showCuResult(obj) {
    const pre = document.getElementById("tools-result");
    if (!pre) return;
    pre.textContent =
      typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
  }

  async function cuInspect() {
    try {
      const data = await api("POST", "/api/computer-use/inspect");
      showCuResult(data);
      toast(
        data.capture && data.capture.ok
          ? "Screenshot saved"
          : "Inspect done (maybe stub capture)",
        "ok"
      );
    } catch (err) {
      toast("Inspect failed: " + err.message, "error");
    }
  }

  async function cuClick() {
    const x = Number((document.getElementById("cu-x") || {}).value || 0);
    const y = Number((document.getElementById("cu-y") || {}).value || 0);
    try {
      const data = await api("POST", "/api/computer-use/click", { x: x, y: y });
      showCuResult(data);
      toast(
        data.dry_run
          ? "Dry-run click — enable God badge first"
          : "Clicked " + x + "," + y,
        data.dry_run ? "info" : "ok"
      );
    } catch (err) {
      toast("Click failed: " + err.message, "error");
    }
  }

  async function cuType() {
    const text = String((document.getElementById("cu-type") || {}).value || "");
    if (!text.trim()) {
      toast("Enter text to type", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/computer-use/type", { text: text });
      showCuResult(data);
      toast(
        data.dry_run ? "Dry-run type — enable God badge first" : "Typed",
        data.dry_run ? "info" : "ok"
      );
    } catch (err) {
      toast("Type failed: " + err.message, "error");
    }
  }

  async function cuShell() {
    const cmd = String((document.getElementById("cu-shell") || {}).value || "");
    if (!cmd.trim()) {
      toast("Enter shell command", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/computer-use/shell", { cmd: cmd });
      showCuResult(data);
      toast(
        data.dry_run ? "Dry-run shell — enable God badge first" : data.detail,
        data.ok || data.dry_run ? "ok" : "error"
      );
    } catch (err) {
      toast("Shell failed: " + err.message, "error");
    }
  }

  async function refreshToolsModal() {
    const ul = document.getElementById("tools-list");
    const sel = document.getElementById("tools-select");
    const countEl = document.getElementById("tools-count");
    try {
      const data = await api("GET", "/api/plugins");
      const tools = data.tools || [];
      if (countEl) {
        countEl.textContent =
          "Tools: " +
          tools.length +
          " · plugins: " +
          (data.plugins ? data.plugins.length : 0);
      }
      if (ul) {
        ul.innerHTML = "";
        if (!tools.length) {
          const li = document.createElement("li");
          li.className = "muted";
          li.textContent = "(no tools)";
          ul.appendChild(li);
        } else {
          tools.forEach(function (t) {
            const li = document.createElement("li");
            li.textContent =
              (t.name || "?") +
              " [" +
              (t.plugin || "core") +
              "] — " +
              String(t.description || "").slice(0, 100);
            li.title = JSON.stringify(t.input_schema || {}, null, 0);
            li.style.cursor = "pointer";
            li.addEventListener("click", function () {
              if (sel) sel.value = t.name;
            });
            ul.appendChild(li);
          });
        }
      }
      if (sel) {
        const prev = sel.value;
        sel.innerHTML = "";
        tools.forEach(function (t) {
          const opt = document.createElement("option");
          opt.value = t.name;
          opt.textContent = t.name;
          sel.appendChild(opt);
        });
        if (prev) sel.value = prev;
      }
    } catch (err) {
      toast("Tools load failed: " + err.message, "error");
    }
  }

  function parseToolArgs(name, raw) {
    const text = String(raw || "").trim();
    if (!text) return {};
    if (text.charAt(0) === "{") {
      return JSON.parse(text);
    }
    if (name === "web_fetch") return { url: text };
    if (name === "memory_search") return { query: text };
    if (name === "pipeline_do") return { text: text };
    if (name === "hub_status") return {};
    return { text: text };
  }

  async function runSelectedTool() {
    const sel = document.getElementById("tools-select");
    const argsEl = document.getElementById("tools-args");
    const out = document.getElementById("tools-result");
    const name = sel ? sel.value : "";
    if (!name) {
      toast("Select a tool", "info");
      return;
    }
    let argumentsObj = {};
    try {
      argumentsObj = parseToolArgs(name, argsEl ? argsEl.value : "");
    } catch (err) {
      toast("Invalid args JSON: " + err.message, "error");
      return;
    }
    try {
      const data = await api("POST", "/api/tools/call", {
        name: name,
        arguments: argumentsObj,
      });
      const result = data.result;
      const text =
        typeof result === "string"
          ? result
          : JSON.stringify(result, null, 2);
      if (out) out.textContent = text;
      toast("Tool " + name + " ok", "ok");
    } catch (err) {
      if (out) out.textContent = "Error: " + err.message;
      toast("Tool failed: " + err.message, "error");
    }
  }

  async function runQuickFetch() {
    const urlEl = document.getElementById("tools-fetch-url");
    const out = document.getElementById("tools-result");
    let url = urlEl ? String(urlEl.value || "").trim() : "";
    if (!url) {
      toast("Enter a URL", "info");
      return;
    }
    if (url.indexOf("http://") !== 0 && url.indexOf("https://") !== 0) {
      url = "https://" + url;
    }
    try {
      const data = await api("POST", "/api/tools/call", {
        name: "web_fetch",
        arguments: { url: url, max_chars: 6000 },
      });
      if (out) {
        out.textContent =
          typeof data.result === "string"
            ? data.result
            : JSON.stringify(data.result, null, 2);
      }
      toast("Fetch ok", "ok");
    } catch (err) {
      if (out) out.textContent = "Fetch error: " + err.message;
      toast("Fetch failed: " + err.message, "error");
    }
  }


  async function openUsageModal() {
    if (!els.usageModal) return;
    els.usageModal.hidden = false;
    await refreshUsageModal();
  }

  async function refreshUsageModal() {
    const body = document.getElementById("usage-body");
    const ul = document.getElementById("usage-jobs");
    try {
      const [usage, jobsData] = await Promise.all([
        api("GET", "/api/usage"),
        api("GET", "/api/jobs?limit=12"),
      ]);
      const spent = Number(usage.spent_usd || 0);
      const pt = Number(usage.prompt_tokens || 0);
      const ct = Number(usage.completion_tokens || 0);
      const budget =
        usage.max_budget_usd != null && usage.max_budget_usd !== ""
          ? Number(usage.max_budget_usd)
          : null;
      const lines = [
        "spent: $" + spent.toFixed(4),
        "tokens: " + pt + " prompt + " + ct + " completion",
        "budget: " + (budget != null && !isNaN(budget) ? "$" + budget.toFixed(2) : "none"),
        "free_only: " + !!usage.free_only,
        "",
        "by agent:",
      ];
      const by = usage.by_agent || {};
      const keys = Object.keys(by);
      if (!keys.length) {
        lines.push("(no LLM calls yet)");
      } else {
        keys.forEach(function (aid) {
          const b = by[aid] || {};
          lines.push(
            "  " +
              aid +
              ": $" +
              Number(b.cost_usd || 0).toFixed(4) +
              " · calls=" +
              (b.calls || 0) +
              " · tok=" +
              (Number(b.prompt_tokens || 0) + Number(b.completion_tokens || 0))
          );
        });
      }
      if (body) body.textContent = lines.join(String.fromCharCode(10));

      if (ul) {
        ul.innerHTML = "";
        const jobs = jobsData.jobs || [];
        if (!jobs.length) {
          const li = document.createElement("li");
          li.className = "muted";
          li.textContent = "(no jobs yet)";
          ul.appendChild(li);
        } else {
          jobs.forEach(function (j) {
            const li = document.createElement("li");
            li.style.display = "flex";
            li.style.gap = "6px";
            li.style.alignItems = "center";
            const lab = document.createElement("span");
            lab.style.flex = "1";
            lab.style.minWidth = "0";
            lab.style.overflow = "hidden";
            lab.style.textOverflow = "ellipsis";
            lab.style.whiteSpace = "nowrap";
            lab.textContent =
              (j.id || "") +
              " · " +
              (j.name || "") +
              " · " +
              (j.status || "") +
              "/" +
              (j.stage || "");
            lab.title = (j.error || j.started_at || "");
            li.appendChild(lab);
            if (j.status === "running") {
              const btn = document.createElement("button");
              btn.type = "button";
              btn.className = "btn-ws-sm";
              btn.textContent = "Cancel";
              btn.addEventListener("click", function () {
                cancelJobById(j.id);
              });
              li.appendChild(btn);
            }
            ul.appendChild(li);
          });
        }
      }
    } catch (err) {
      if (body) body.textContent = "Usage load failed: " + err.message;
    }
  }

  async function cancelJobById(id) {
    if (!id) return;
    try {
      await api("POST", "/api/jobs/" + encodeURIComponent(id) + "/cancel");
      toast("Cancel requested", "ok");
      await refreshUsageModal();
    } catch (err) {
      toast("Cancel failed: " + err.message, "error");
    }
  }

  async function resetUsageCounters() {
    if (!confirm("Reset session usage counters to zero?")) return;
    try {
      await api("POST", "/api/usage/reset");
      toast("Usage reset", "ok");
      await refreshUsageModal();
      // refresh cost badge via state
      try {
        const st = await api("GET", "/api/state");
        applySnapshot(st);
      } catch (_e) {
        /* ignore */
      }
    } catch (err) {
      toast("Usage reset failed: " + err.message, "error");
    }
  }


  async function openVectorModal() {
    if (!els.vectorModal) return;
    els.vectorModal.hidden = false;
    await refreshVectorList();
  }

  async function refreshVectorList() {
    const ul = document.getElementById("vector-list");
    const countEl = document.getElementById("vector-count");
    try {
      const data = await api("GET", "/api/vector?limit=40");
      if (countEl) countEl.textContent = "Docs: " + (data.count || 0);
      if (!ul) return;
      ul.innerHTML = "";
      const docs = data.docs || [];
      if (!docs.length) {
        const li = document.createElement("li");
        li.className = "muted";
        li.textContent = "(empty — add text or run Execute to index requirements)";
        ul.appendChild(li);
        return;
      }
      docs.forEach(function (d) {
        const li = document.createElement("li");
        li.style.display = "flex";
        li.style.gap = "6px";
        li.style.alignItems = "center";
        const lab = document.createElement("span");
        lab.style.flex = "1";
        lab.style.minWidth = "0";
        lab.style.overflow = "hidden";
        lab.style.textOverflow = "ellipsis";
        lab.style.whiteSpace = "nowrap";
        lab.textContent = (d.id || "?") + ": " + (d.text || "");
        lab.title = d.text || "";
        const del = document.createElement("button");
        del.type = "button";
        del.className = "btn-ws-sm";
        del.textContent = "Del";
        del.addEventListener("click", function () {
          deleteVectorDoc(d.id);
        });
        li.appendChild(lab);
        li.appendChild(del);
        ul.appendChild(li);
      });
    } catch (err) {
      toast("Vector list failed: " + err.message, "error");
    }
  }

  async function searchVectors() {
    const qEl = document.getElementById("vector-query");
    const hitsEl = document.getElementById("vector-hits");
    const q = qEl ? String(qEl.value || "").trim() : "";
    if (!q) {
      toast("Enter a search query", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/vector/search", {
        query: q,
        limit: 8,
      });
      const hits = data.hits || [];
      if (!hitsEl) return;
      if (!hits.length) {
        hitsEl.textContent = "No hits for: " + q;
        return;
      }
      hitsEl.textContent = hits
        .map(function (h) {
          return (
            (h.score != null ? h.score : "?") +
            " · " +
            (h.id || "") +
            " — " +
            String(h.text || "").slice(0, 160)
          );
        })
        .join("\n");
    } catch (err) {
      toast("Vector search failed: " + err.message, "error");
    }
  }

  async function addVectorDoc() {
    const input = document.getElementById("vector-add-input");
    const text = input ? String(input.value || "").trim() : "";
    if (!text) {
      toast("Enter text to add", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/vector/add", {
        text: text,
        meta: { source: "ui" },
      });
      if (input) input.value = "";
      if (data.docs) {
        // re-render from response
        const countEl = document.getElementById("vector-count");
        if (countEl) countEl.textContent = "Docs: " + (data.count || 0);
      }
      await refreshVectorList();
      toast("Vector doc " + (data.id || "added"), "ok");
    } catch (err) {
      toast("Vector add failed: " + err.message, "error");
    }
  }

  async function deleteVectorDoc(id) {
    if (!id || !confirm('Delete vector doc "' + id + '"?')) return;
    try {
      await api("DELETE", "/api/vector/" + encodeURIComponent(id));
      await refreshVectorList();
      toast("Deleted " + id, "ok");
    } catch (err) {
      toast("Vector delete failed: " + err.message, "error");
    }
  }

  async function clearVectorStore() {
    if (!confirm("Clear ALL vector docs?")) return;
    try {
      await api("POST", "/api/vector/clear");
      await refreshVectorList();
      const hitsEl = document.getElementById("vector-hits");
      if (hitsEl) hitsEl.textContent = "Search hits appear here.";
      toast("Vector store cleared", "ok");
    } catch (err) {
      toast("Vector clear failed: " + err.message, "error");
    }
  }

  async function saveCheckpoint() {
    try {
      const data = await api("POST", "/api/checkpoint/save");
      toast("Checkpoint saved", "ok");
      const ck = document.getElementById("system-ckpt");
      if (ck) ck.textContent = "Checkpoint: " + (data.path || "saved");
    } catch (err) {
      toast("Checkpoint save failed: " + err.message, "error");
    }
  }

  async function loadCheckpoint() {
    try {
      const snap = await api("POST", "/api/checkpoint/load");
      applySnapshot(snap);
      toast("Checkpoint loaded", "ok");
      closeSystemModal();
    } catch (err) {
      toast("Checkpoint load failed: " + err.message, "error");
    }
  }

  async function runCleanState() {
    if (
      !confirm(
        "Clean state: clear HOT session, temp workspace, pipeline & checkpoint. WARM facts stay. Continue?"
      )
    ) {
      return;
    }
    try {
      const snap = await api("POST", "/api/clean");
      applySnapshot(snap);
      toast(
        "Clean done (temp removed: " +
          ((snap.clean && snap.clean.temp_removed) || 0) +
          ")",
        "ok"
      );
    } catch (err) {
      toast("Clean failed: " + err.message, "error");
    }
  }

  async function runBackup() {
    try {
      const data = await api("POST", "/api/backup");
      toast("Backup: " + (data.path || "ok"), "ok");
      appendChat("system", "Backup saved: " + (data.path || ""));
    } catch (err) {
      toast("Backup failed: " + err.message, "error");
    }
  }

  async function saveWorkerPresetFromTune() {
    if (!tuneAgentId || tuneAgentId.indexOf("worker") !== 0) {
      toast("Open a Worker card to save a worker preset", "info");
      return;
    }
    const name = prompt("Preset name:", tuneAgentId + "-preset");
    if (!name) return;
    try {
      // apply current form first
      await saveTuneModal();
      const data = await api("POST", "/api/worker-presets", {
        name: name,
        agent_id: tuneAgentId,
      });
      toast(
        "Preset saved: " + ((data.preset && data.preset.name) || name),
        "ok"
      );
    } catch (err) {
      toast("Preset save failed: " + err.message, "error");
    }
  }

  async function openWorkspaceModal() {
    if (!els.workspaceModal) return;
    els.workspaceModal.hidden = false;
    await refreshWorkspace();
  }

  function closeWorkspaceModal() {
    if (els.workspaceModal) els.workspaceModal.hidden = true;
  }

  async function refreshWorkspace() {
    try {
      const snap = await api("GET", "/api/workspace");
      renderWorkspaceLists(snap);
    } catch (err) {
      toast("Workspace load failed: " + err.message, "error");
    }
  }

  async function downloadWorkspaceZip(zone) {
    try {
      const data = await api(
        "POST",
        "/api/workspace/export?zone=" + encodeURIComponent(zone || "all")
      );
      if (!data.name) {
        toast("Export failed", "error");
        return;
      }
      window.location.href =
        "/api/workspace/exports/" + encodeURIComponent(data.name);
      toast(
        "Workspace zip ready (" +
          (data.bytes != null ? Math.round(data.bytes / 1024) + " KB" : data.name) +
          ")",
        "ok"
      );
    } catch (err) {
      toast("Workspace export failed: " + err.message, "error");
    }
  }

  function renderWorkspaceLists(snap) {
    const tempUl = document.getElementById("ws-temp-list");
    const permUl = document.getElementById("ws-perm-list");
    if (!tempUl || !permUl) return;
    tempUl.innerHTML = "";
    permUl.innerHTML = "";
    (snap.temp || []).forEach(function (f) {
      tempUl.appendChild(wsListItem(f, "temp"));
    });
    (snap.perm || []).forEach(function (f) {
      permUl.appendChild(wsListItem(f, "perm"));
    });
    if (!(snap.temp || []).length) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = "(empty — Execute fills temp)";
      tempUl.appendChild(li);
    }
    if (!(snap.perm || []).length) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = "(empty — promote from temp)";
      permUl.appendChild(li);
    }
  }

  function wsListItem(f, zone) {
    const li = document.createElement("li");
    const name = document.createElement("span");
    name.className = "ws-name";
    name.textContent = f.name;
    name.title = f.name;
    const bytes = document.createElement("span");
    bytes.className = "ws-bytes";
    bytes.textContent = f.bytes != null ? f.bytes + " B" : "";
    li.appendChild(name);
    li.appendChild(bytes);
    if (zone === "temp") {
      const promo = document.createElement("button");
      promo.type = "button";
      promo.className = "ws-action";
      promo.textContent = "↑ perm";
      promo.title = "Promote to permanent";
      promo.addEventListener("click", function (ev) {
        ev.stopPropagation();
        promoteWs(f.name);
      });
      li.appendChild(promo);
    }
    const del = document.createElement("button");
    del.type = "button";
    del.className = "ws-action";
    del.textContent = "×";
    del.title = "Delete";
    del.addEventListener("click", function (ev) {
      ev.stopPropagation();
      deleteWs(zone, f.name);
    });
    li.appendChild(del);
    li.addEventListener("click", function () {
      previewWs(zone, f.name);
      li.parentNode.querySelectorAll("li").forEach(function (x) {
        x.classList.remove("active");
      });
      li.classList.add("active");
    });
    return li;
  }

  async function previewWs(zone, name) {
    const title = document.getElementById("ws-preview-title");
    const pre = document.getElementById("ws-preview");
    if (title) title.textContent = zone + " / " + name;
    try {
      const data = await api(
        "GET",
        "/api/workspace/file?zone=" +
          encodeURIComponent(zone) +
          "&name=" +
          encodeURIComponent(name)
      );
      if (pre) pre.textContent = data.content || "(empty)";
    } catch (err) {
      if (pre) pre.textContent = "Preview failed: " + err.message;
    }
  }

  async function promoteWs(name) {
    try {
      const data = await api(
        "POST",
        "/api/workspace/promote/" + encodeURIComponent(name)
      );
      renderWorkspaceLists(data.workspace || (await api("GET", "/api/workspace")));
      toast("Promoted " + name, "ok");
    } catch (err) {
      toast("Promote failed: " + err.message, "error");
    }
  }

  async function deleteWs(zone, name) {
    try {
      const data = await api(
        "POST",
        "/api/workspace/delete?zone=" +
          encodeURIComponent(zone) +
          "&name=" +
          encodeURIComponent(name)
      );
      renderWorkspaceLists(data.workspace || (await api("GET", "/api/workspace")));
      toast("Deleted " + name, "ok");
    } catch (err) {
      toast("Delete failed: " + err.message, "error");
    }
  }

  async function clearTempWs() {
    if (!confirm("Clear all temp workspace files?")) return;
    try {
      const data = await api("POST", "/api/workspace/clear-temp");
      renderWorkspaceLists(data.workspace || { temp: [], perm: [] });
      toast("Temp cleared (" + (data.removed || 0) + ")", "ok");
    } catch (err) {
      toast("Clear failed: " + err.message, "error");
    }
  }

  async function onFlexSelectChange() {
    if (!els.flexSelect) return;
    const next = els.flexSelect.value;
    try {
      const data = await api("POST", "/api/agents/flex/preset", { preset: next });
      const flex = findAgent("flex");
      if (flex) flex.preset = data.preset || next;
      renderCards();
      appendChat("system", "Flex preset → " + (data.preset || next));
    } catch (err) {
      toast("Flex preset failed: " + err.message, "error");
    }
  }

/* part: 03-chat-jobs-ops.js  lines 1950-3681 of app.js — edit parts, run scripts/build_ui_js.py */
  function toggleMic() {
    const SR =
      window.SpeechRecognition || window.webkitSpeechRecognition || null;
    if (!SR) {
      toast("Speech recognition not supported in this browser", "error");
      return;
    }
    if (listening && recognition) {
      try {
        recognition.stop();
      } catch (_e) {
        /* */
      }
      listening = false;
      if (els.btnMic) els.btnMic.classList.remove("listening");
      return;
    }
    recognition = new SR();
    recognition.lang = "de-DE";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onstart = function () {
      listening = true;
      if (els.btnMic) els.btnMic.classList.add("listening");
    };
    recognition.onend = function () {
      listening = false;
      if (els.btnMic) els.btnMic.classList.remove("listening");
    };
    recognition.onerror = function (ev) {
      listening = false;
      if (els.btnMic) els.btnMic.classList.remove("listening");
      toast("Mic error: " + (ev.error || "unknown"), "error");
    };
    recognition.onresult = function (ev) {
      let text = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        text += ev.results[i][0].transcript;
      }
      if (els.chatInput && text) {
        els.chatInput.value = (els.chatInput.value + " " + text).trim();
      }
    };
    try {
      recognition.start();
    } catch (err) {
      toast("Mic start failed: " + err.message, "error");
    }
  }

  async function cycleFlexPreset() {
    const flex = findAgent("flex");
    if (!flex) return;
    const cur = flex.preset || "personal";
    const idx = FLEX_PRESETS.indexOf(cur);
    const next = FLEX_PRESETS[(idx + 1) % FLEX_PRESETS.length];
    try {
      const data = await api("POST", "/api/agents/flex/preset", { preset: next });
      flex.preset = data.preset || next;
      renderCards();
      appendChat("system", "Flex preset → " + flex.preset);
    } catch (err) {
      appendChat("system", "Flex preset failed: " + err.message);
    }
  }

  async function toggleAgent(id) {
    const agent = findAgent(id);
    if (!agent || !agent.toggleable || agent.parked) return;

    const payload = { id: agent.id, enabled: !agent.enabled };
    const cb = w.GnomHub.onToggle;
    if (typeof cb === "function") cb(payload);

    try {
      const data = await api("POST", "/api/agents/" + encodeURIComponent(id) + "/toggle");
      if (data.agents) applyAgentsFromServer(data.agents);
      else {
        agent.enabled = !!data.enabled;
        renderCards();
      }
    } catch (err) {
      appendChat("system", "Toggle failed: " + err.message);
    }
  }

  async function loadTooltips(lang) {
    try {
      const data = await api("GET", "/api/tooltips?lang=" + encodeURIComponent(lang || "en"));
      // hub returns flat map id → {title, how_to, example}
      TOOLTIPS = data.tooltips || data || {};
      uiLang = lang || "en";
    } catch (_e) {
      /* keep previous */
    }
  }

  /** Box 1 info layers (Live | Regler | Gnom) — switched by JS, no box buttons */
  function showInfoLayer(name) {
    const allowed = { live: 1, tune: 1, gnom: 1 };
    const n = allowed[name] ? name : "live";
    document.querySelectorAll("#box1-content .info-layer").forEach(function (el) {
      const on = el.getAttribute("data-info-layer") === n;
      el.hidden = !on;
      el.classList.toggle("is-active", on);
    });
  }

  function showTooltip(id) {
    const tip = TOOLTIPS[id];
    if (!tip) return;
    showInfoLayer("live");
    if (els.placeholder) els.placeholder.hidden = true;
    if (els.tipRoot) els.tipRoot.hidden = false;
    if (els.tipTitle) els.tipTitle.textContent = tip.title;
    if (els.tipHow) els.tipHow.textContent = tip.how_to;
    if (els.tipExample) els.tipExample.textContent = tip.example;
  }

  function bindTooltipHovers() {
    document.querySelectorAll("[data-tooltip-id]").forEach(function (node) {
      node.addEventListener("mouseenter", function () {
        const id = node.getAttribute("data-tooltip-id");
        if (id) showTooltip(id);
      });
    });
  }

  function showClarify(question) {
    if (els.clarify) els.clarify.hidden = false;
    if (els.clarifyQ) els.clarifyQ.textContent = question || "Please choose:";
    if (els.clarify) els.clarify.dataset.tooltipId = "clarify";
  }

  function hideClarify() {
    if (els.clarify) els.clarify.hidden = true;
    if (els.clarifyQ) els.clarifyQ.textContent = "";
  }

  let chatBusy = false;

  function formatDuration(sec) {
    if (sec < 60) return sec.toFixed(1) + "s";
    const m = Math.floor(sec / 60);
    const s = (sec % 60).toFixed(1);
    return m + "m " + s + "s";
  }

  function startJobTimer() {
    jobTimerStart = Date.now();
    lastJobElapsedSec = 0;
    const el = document.getElementById("job-timer");
    if (el) {
      el.hidden = false;
      el.classList.remove("is-done");
      el.classList.add("is-running");
      el.textContent = "0.0s";
    }
    if (jobTimerInterval) clearInterval(jobTimerInterval);
    jobTimerInterval = setInterval(function () {
      if (!jobTimerStart) return;
      const sec = (Date.now() - jobTimerStart) / 1000;
      const t = document.getElementById("job-timer");
      if (t) t.textContent = formatDuration(sec);
    }, 100);
  }

  function stopJobTimer() {
    if (jobTimerInterval) {
      clearInterval(jobTimerInterval);
      jobTimerInterval = null;
    }
    let sec = 0;
    if (jobTimerStart) {
      sec = (Date.now() - jobTimerStart) / 1000;
      lastJobElapsedSec = sec;
    }
    jobTimerStart = null;
    const el = document.getElementById("job-timer");
    if (el) {
      el.hidden = false;
      el.classList.remove("is-running");
      el.classList.add("is-done");
      el.textContent = formatDuration(sec);
    }
    return sec;
  }

  function setChatBusy(busy) {
    const next = !!busy;
    if (next && !chatBusy) startJobTimer();
    if (!next && chatBusy) stopJobTimer();
    chatBusy = next;
    if (els.btnSend) {
      els.btnSend.disabled = chatBusy;
      els.btnSend.textContent = chatBusy ? "…" : "Send";
    }
    if (els.btnExecute) {
      // Must re-apply can_execute when busy ends — applySnapshot often ran while busy=true
      els.btnExecute.disabled = !lastCanExecute || chatBusy;
    }
    const btnSendExec = document.getElementById("btn-send-exec");
    if (btnSendExec) btnSendExec.disabled = chatBusy;
    const btnCancel = document.getElementById("btn-cancel");
    if (btnCancel) {
      btnCancel.hidden = !chatBusy;
      btnCancel.disabled = !chatBusy;
    }
    if (els.btnMic) els.btnMic.disabled = chatBusy;
    if (els.chatInput) els.chatInput.disabled = chatBusy;
    if (els.stageBadge) {
      if (chatBusy) {
        els.stageBadge.textContent = "running…";
      } else if (activeStage) {
        // Restore real stage — otherwise badge stays on "running…" and UI feels frozen
        els.stageBadge.textContent = activeStage;
      }
    }
  }

  function updateCostBadge(llm) {
    const el = els.costBadge || document.getElementById("cost-badge");
    if (!el) return;
    const spent = llm && typeof llm.spent_usd === "number" ? llm.spent_usd : 0;
    const tok =
      llm
        ? (llm.prompt_tokens || 0) + (llm.completion_tokens || 0)
        : 0;
    const budget =
      llm && llm.max_budget_usd != null && llm.max_budget_usd !== ""
        ? Number(llm.max_budget_usd)
        : null;
    let text = "$" + spent.toFixed(4);
    if (budget != null && !isNaN(budget) && budget > 0) {
      text += " / $" + budget.toFixed(2);
      const ratio = spent / budget;
      el.classList.toggle("cost-warn", ratio >= 0.7 && ratio < 0.95);
      el.classList.toggle("cost-hot", ratio >= 0.95);
    } else {
      el.classList.remove("cost-warn", "cost-hot");
    }
    el.textContent = text;
    el.title =
      "Session spend $" +
      spent.toFixed(6) +
      (budget != null && !isNaN(budget) ? " · budget $" + budget : " · no budget cap") +
      " · " +
      tok +
      " tokens" +
      (llm && llm.free_only ? " · free_only" : "");
  }

  function loadResultHistory() {
    try {
      const raw = sessionStorage.getItem(HISTORY_KEY);
      if (!raw) {
        resultHistory = [];
        return;
      }
      const arr = JSON.parse(raw);
      resultHistory = Array.isArray(arr) ? arr : [];
    } catch (_e) {
      resultHistory = [];
    }
  }

  function saveResultHistory() {
    try {
      sessionStorage.setItem(
        HISTORY_KEY,
        JSON.stringify(resultHistory.slice(0, HISTORY_MAX))
      );
    } catch (_e) {
      /* quota */
    }
  }

  function pushResultHistory(pipeline, meta) {
    const outputs = normalizeWorkerOutputs(pipeline);
    if (!outputs.length) return;
    const entry = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
      ts: new Date().toISOString(),
      label:
        (meta && meta.label) ||
        (pipeline && pipeline.user_text
          ? String(pipeline.user_text).slice(0, 48)
          : "Execute") +
          " · " +
          outputs.length +
          "w",
      user_text: (pipeline && pipeline.user_text) || "",
      brainstorm_notes: (pipeline && pipeline.brainstorm_notes) || "",
      brainstorm_turns: (pipeline && pipeline.brainstorm_turns) || [],
      can_reexec: !!(
        (pipeline && pipeline.brainstorm_notes) ||
        (pipeline && pipeline.user_text)
      ),
      outputs: outputs.map(function (o) {
        return {
          worker: o.worker,
          name: o.name,
          task: o.task,
          result: o.result,
          index: o.index,
        };
      }),
    };
    resultHistory.unshift(entry);
    if (resultHistory.length > HISTORY_MAX) {
      resultHistory = resultHistory.slice(0, HISTORY_MAX);
    }
    saveResultHistory();
    renderHistorySelect();
  }

  function renderHistorySelect() {
    const sel = document.getElementById("result-history");
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = "";
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent =
      resultHistory.length
        ? "History (" + resultHistory.length + ")…"
        : "History…";
    sel.appendChild(opt0);
    resultHistory.forEach(function (e) {
      const o = document.createElement("option");
      o.value = e.id;
      const t = e.ts
        ? e.ts.slice(11, 19)
        : "";
      o.textContent = (t ? t + " · " : "") + (e.label || e.id);
      sel.appendChild(o);
    });
    if (cur) sel.value = cur;
  }

  function restoreHistoryEntry(id) {
    const entry = resultHistory.find(function (e) {
      return e.id === id;
    });
    if (!entry) {
      toast("History entry not found", "info");
      return;
    }
    lastWorkerOutputs = entry.outputs || [];
    renderBox3Workers({
      stage: "done",
      worker_outputs: lastWorkerOutputs,
    });
    const re = document.getElementById("btn-reexec");
    if (re) {
      re.disabled = !entry.can_reexec && !(entry.user_text || entry.brainstorm_notes);
      re.dataset.historyId = entry.id;
    }
    focusBox3();
    toast("Restored: " + (entry.label || id), "ok");
  }

  function exportResultHistory() {
    if (!resultHistory.length) {
      toast("No history to export", "info");
      return;
    }
    const lines = ["# Gnom-Hub result history", ""];
    resultHistory.forEach(function (e, i) {
      lines.push("## " + (i + 1) + ". " + (e.label || e.id));
      lines.push("time: " + (e.ts || ""));
      if (e.user_text) lines.push("user: " + e.user_text);
      lines.push("");
      (e.outputs || []).forEach(function (o) {
        lines.push("### " + (o.name || o.worker || "worker"));
        if (o.task) lines.push("Task: " + o.task);
        lines.push(o.result || "");
        lines.push("");
      });
      lines.push("---");
      lines.push("");
    });
    const text = lines.join("\n");
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "gnom-hub-history.md";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 500);
    toast("History exported (" + resultHistory.length + " runs)", "ok");
  }

  async function rerunWorker(workerId) {
    if (chatBusy) {
      toast("Busy — wait for current job", "info");
      return;
    }
    const wid = String(workerId || "").toLowerCase();
    if (!wid) return;
    setChatBusy(true);
    appendChat("system", "Re-run " + wid + "…");
    toast("Re-running " + wid + "…", "info");
    try {
      const live =
        els.llmBadge && els.llmBadge.classList.contains("has-key");
      const start = await api(
        "POST",
        "/api/workers/" + encodeURIComponent(wid) + "/rerun"
      );
      let snap = start;
      if (start.job_id) {
        const job = await pollJob(start.job_id, live ? 180000 : 30000);
        snap = job.snapshot || (await api("GET", "/api/state"));
        if (job.status === "error") {
          appendChat("system", "Re-run error: " + (job.error || "?"));
          toast(job.error || "Re-run failed", "error");
          applySnapshot(snap);
          return;
        }
        if (job.status === "cancelled") {
          appendChat("system", "Re-run cancelled.");
          applySnapshot(snap);
          return;
        }
      }
      applySnapshot(snap);
      const stage = (snap.pipeline && snap.pipeline.stage) || "";
      if (stage === "done") {
        appendChat("system", "Re-run done: " + wid);
        toast(wid + " re-run done", "ok");
        focusBox3();
        try {
          pushResultHistory(snap.pipeline || {}, {
            label: "↻ " + wid,
          });
        } catch (_h) {
          /* ignore */
        }
      } else if (stage === "error") {
        appendChat(
          "system",
          "Re-run failed: " + ((snap.pipeline && snap.pipeline.error) || "?")
        );
      }
    } catch (err) {
      appendChat("system", "Re-run failed: " + err.message);
      toast("Re-run failed: " + err.message, "error");
    } finally {
      setChatBusy(false);
      currentJobId = null;
    }
  }

  async function reexecFromHistory() {
    if (chatBusy) {
      toast("Busy — wait for current job", "info");
      return;
    }
    const re = document.getElementById("btn-reexec");
    const id = re && re.dataset.historyId;
    const sel = document.getElementById("result-history");
    const pick = id || (sel && sel.value);
    const entry = resultHistory.find(function (e) {
      return e.id === pick;
    });
    if (!entry) {
      toast("Pick a History entry first", "info");
      return;
    }
    if (!(entry.user_text || entry.brainstorm_notes)) {
      toast("This history entry has no brainstorm to re-run (pre-2.0 entry)", "info");
      return;
    }
    appendChat("system", "Re-Exec from history: " + (entry.label || entry.id));
    setChatBusy(true);
    try {
      const start = await api("POST", "/api/reexecute", {
        user_text: entry.user_text || "",
        brainstorm_notes: entry.brainstorm_notes || "",
        brainstorm_turns: entry.brainstorm_turns || [],
      });
      let snap = start;
      if (start.job_id) {
        const job = await pollJob(start.job_id, 180000);
        snap = job.snapshot || (await api("GET", "/api/state"));
        if (job.status === "error") {
          appendChat("system", "Re-Exec error: " + (job.error || "?"));
          toast(job.error || "Re-Exec error", "error");
          return;
        }
      }
      applySnapshot(snap);
      if (snap.pipeline && snap.pipeline.stage === "done") {
        appendChat("system", "Re-Exec done — see Box 3.");
        toast("Re-Exec done", "ok");
        focusBox3();
        try {
          pushResultHistory(snap.pipeline || {}, {
            label: "Re-Exec · " + String(entry.label || "").slice(0, 30),
          });
        } catch (_h) {}
      } else if (snap.pipeline && snap.pipeline.stage === "clarify") {
        appendChat("system", "Clarify needed in Box 1.");
        toast("Clarify needed", "info");
      }
    } catch (err) {
      appendChat("system", "Re-Exec failed: " + err.message);
      toast("Re-Exec failed: " + err.message, "error");
    } finally {
      setChatBusy(false);
    }
  }


  async function renderHotList(facts) {
    const ul = document.getElementById("sys-hot-list");
    if (!ul) return;
    let list = facts;
    if (!list) {
      try {
        const data = await api("GET", "/api/memory");
        list = data.facts || [];
      } catch (_e) {
        list = [];
      }
    }
    ul.innerHTML = "";
    if (!list || !list.length) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = "(no HOT facts yet)";
      ul.appendChild(li);
      return;
    }
    list.slice(-12).forEach(function (text) {
      const li = document.createElement("li");
      li.style.display = "flex";
      li.style.gap = "6px";
      li.style.alignItems = "center";
      const lab = document.createElement("span");
      lab.style.flex = "1";
      lab.style.minWidth = "0";
      lab.style.overflow = "hidden";
      lab.style.textOverflow = "ellipsis";
      lab.style.whiteSpace = "nowrap";
      lab.textContent = text;
      lab.title = text;
      const promo = document.createElement("button");
      promo.type = "button";
      promo.className = "btn-ws-sm";
      promo.textContent = "→W";
      promo.title = "Promote to WARM";
      promo.addEventListener("click", function () {
        promoteHotFact(text);
      });
      const del = document.createElement("button");
      del.type = "button";
      del.className = "btn-ws-sm";
      del.textContent = "Del";
      del.addEventListener("click", function () {
        deleteHotFact(text);
      });
      li.appendChild(lab);
      li.appendChild(promo);
      li.appendChild(del);
      ul.appendChild(li);
    });
  }

  async function addHotFact() {
    const input = document.getElementById("sys-hot-input");
    const text = input ? String(input.value || "").trim() : "";
    if (!text) {
      toast("Enter a HOT fact", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/memory/hot", { text: text });
      if (input) input.value = "";
      await renderHotList(data.facts);
      toast(data.ok ? "HOT fact added" : "Already present", "ok");
    } catch (err) {
      toast("HOT add failed: " + err.message, "error");
    }
  }

  async function deleteHotFact(text) {
    if (!confirm("Delete HOT fact: " + String(text || "").slice(0, 60) + "?")) return;
    try {
      const data = await api(
        "DELETE",
        "/api/memory/hot?text=" + encodeURIComponent(text || "")
      );
      await renderHotList(data.facts);
      toast("HOT fact removed", "ok");
    } catch (err) {
      toast("HOT delete failed: " + err.message, "error");
    }
  }

  async function promoteHotFact(text) {
    try {
      const data = await api("POST", "/api/memory/hot/promote", {
        text: text,
      });
      await renderHotList(data.facts);
      await renderWarmList(data.warm_facts);
      toast(
        data.warm_added ? "Promoted to WARM" : "Already in WARM",
        "ok"
      );
    } catch (err) {
      toast("Promote failed: " + err.message, "error");
    }
  }

  async function clearHotFacts() {
    if (!confirm("Clear all HOT session facts?")) return;
    try {
      await api("POST", "/api/memory/hot/clear");
      await renderHotList([]);
      toast("HOT facts cleared", "ok");
    } catch (err) {
      toast("HOT clear failed: " + err.message, "error");
    }
  }

  async function renderWarmList(facts) {
    const ul = document.getElementById("sys-warm-list");
    if (!ul) return;
    let list = facts;
    if (!list) {
      try {
        const data = await api("GET", "/api/memory");
        list = data.warm_facts || (data.warm && data.warm.facts) || [];
      } catch (_e) {
        list = [];
      }
    }
    // Prefer full list from memory endpoint
    if (!facts) {
      try {
        const data = await api("GET", "/api/memory");
        // memory_dict may nest differently — try several
        if (Array.isArray(data.warm_facts)) list = data.warm_facts;
        else if (data.memory && Array.isArray(data.memory.warm_facts))
          list = data.memory.warm_facts;
      } catch (_e2) {
        /* keep */
      }
    }
    ul.innerHTML = "";
    if (!list || !list.length) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = "(no WARM facts yet)";
      ul.appendChild(li);
      return;
    }
    // show last 12 with absolute index if possible
    const all = list.slice(-12);
    all.forEach(function (text, offset) {
      const idx = offset + 1;
      const li = document.createElement("li");
      li.style.display = "flex";
      li.style.gap = "6px";
      li.style.alignItems = "center";
      const lab = document.createElement("span");
      lab.style.flex = "1";
      lab.style.minWidth = "0";
      lab.style.overflow = "hidden";
      lab.style.textOverflow = "ellipsis";
      lab.style.whiteSpace = "nowrap";
      lab.textContent = idx + ". " + text;
      lab.title = text;
      const del = document.createElement("button");
      del.type = "button";
      del.className = "btn-ws-sm";
      del.textContent = "Del";
      del.addEventListener("click", function () {
        deleteWarmFact(idx, text);
      });
      li.appendChild(lab);
      li.appendChild(del);
      ul.appendChild(li);
    });
  }

  async function addWarmFact() {
    const input = document.getElementById("sys-warm-input");
    const text = input ? String(input.value || "").trim() : "";
    if (!text) {
      toast("Enter a WARM fact", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/memory/warm", { text: text });
      if (input) input.value = "";
      await renderWarmList(data.warm_facts);
      toast(data.ok ? "WARM fact added" : "Already present", "ok");
    } catch (err) {
      toast("WARM add failed: " + err.message, "error");
    }
  }

  async function deleteWarmFact(index, text) {
    if (!confirm("Delete WARM fact: " + String(text || "").slice(0, 60) + "?")) return;
    try {
      const data = await api(
        "DELETE",
        "/api/memory/warm?text=" + encodeURIComponent(text || "")
      );
      await renderWarmList(data.warm_facts);
      toast("WARM fact removed", "ok");
    } catch (err) {
      toast("WARM delete failed: " + err.message, "error");
    }
  }

  async function clearWarmFacts() {
    if (!confirm("Clear ALL WARM facts?")) return;
    try {
      await api("POST", "/api/memory/warm/clear");
      await renderWarmList([]);
      toast("WARM cleared", "ok");
    } catch (err) {
      toast("WARM clear failed: " + err.message, "error");
    }
  }


  let packListCache = [];

  async function renderPackList(items) {
    const ul = document.getElementById("sys-pack-list");
    if (!ul) return;
    let list = items;
    if (!list) {
      try {
        const data = await api("GET", "/api/session/packs");
        list = data.packs || [];
      } catch (_e) {
        list = [];
      }
    }
    packListCache = list || [];
    const filterEl = document.getElementById("sys-pack-filter");
    const q = filterEl ? String(filterEl.value || "").trim().toLowerCase() : "";
    if (q) {
      list = packListCache.filter(function (p) {
        const hay = (
          (p.label || "") +
          " " +
          (p.name || "") +
          " " +
          (p.notes || "") +
          " " +
          (p.mtime || "") +
          " " +
          (p.exported_at || "")
        ).toLowerCase();
        return hay.indexOf(q) !== -1;
      });
    } else {
      list = packListCache;
    }
    ul.innerHTML = "";
    if (!list.length) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = q
        ? "(no packs match filter)"
        : "(no packs yet — Pack ↓ after Execute)";
      ul.appendChild(li);
      return;
    }
    list.slice(0, 12).forEach(function (p) {
      const li = document.createElement("li");
      li.style.display = "flex";
      li.style.gap = "6px";
      li.style.alignItems = "center";
      const lab = document.createElement("span");
      lab.style.flex = "1";
      lab.style.minWidth = "0";
      lab.style.overflow = "hidden";
      lab.style.textOverflow = "ellipsis";
      lab.style.whiteSpace = "nowrap";
      var when = (p.mtime || p.exported_at || "").replace("T", " ").replace("+00:00", "Z");
      if (when.length > 16) when = when.slice(0, 16);
      lab.textContent =
        (p.label || p.name || "?") + (when ? " · " + when : "");
      lab.title =
        (p.name || "") +
        (p.label ? " — " + p.label : "") +
        (p.notes ? "\n" + p.notes : "");
      const loadBtn = document.createElement("button");
      loadBtn.type = "button";
      loadBtn.className = "btn-ws-sm";
      loadBtn.textContent = "Load";
      loadBtn.title = "Import this pack";
      loadBtn.addEventListener("click", function () {
        loadNamedPack(p.name);
      });
      const renBtn = document.createElement("button");
      renBtn.type = "button";
      renBtn.className = "btn-ws-sm";
      renBtn.textContent = "Ren";
      renBtn.title = "Rename label";
      renBtn.addEventListener("click", function () {
        renameNamedPack(p.name, p.label || "", p.notes || "");
      });
      const dlBtn = document.createElement("button");
      dlBtn.type = "button";
      dlBtn.className = "btn-ws-sm";
      dlBtn.textContent = "↓";
      dlBtn.title = "Download pack JSON (USB)";
      dlBtn.addEventListener("click", function () {
        downloadNamedPack(p.name);
      });
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn-ws-sm";
      delBtn.textContent = "Del";
      delBtn.title = "Delete pack file";
      delBtn.addEventListener("click", function () {
        deleteNamedPack(p.name);
      });
      li.appendChild(lab);
      li.appendChild(loadBtn);
      li.appendChild(renBtn);
      li.appendChild(dlBtn);
      li.appendChild(delBtn);
      ul.appendChild(li);
    });
  }

  async function loadNamedPack(name) {
    if (!name) return;
    if (!confirm('Import pack "' + name + '"? Current HOT/pipeline will be replaced.')) {
      return;
    }
    try {
      const snap = await api(
        "POST",
        "/api/session/packs/" + encodeURIComponent(name) + "/import"
      );
      applySnapshot(snap);
      appendChat("system", "Loaded pack: " + name);
      toast("Pack loaded", "ok");
    } catch (err) {
      toast("Pack load failed: " + err.message, "error");
    }
  }

  async function renameNamedPack(name, currentLabel, currentNotes) {
    if (!name) return;
    var next = window.prompt("Pack label (max 80 chars):", currentLabel || "");
    if (next === null) return;
    next = String(next).trim().slice(0, 80);
    if (!next) {
      toast("Label required", "error");
      return;
    }
    var notesNext = window.prompt(
      "Pack notes (optional, max 200):",
      currentNotes || ""
    );
    if (notesNext === null) notesNext = currentNotes || "";
    notesNext = String(notesNext).trim().slice(0, 200);
    try {
      const data = await api(
        "PATCH",
        "/api/session/packs/" + encodeURIComponent(name),
        { label: next, notes: notesNext }
      );
      await renderPackList(data.packs);
      toast("Pack updated", "ok");
    } catch (err) {
      toast("Pack rename failed: " + err.message, "error");
    }
  }

  async function downloadNamedPack(name) {
    if (!name) return;
    try {
      const data = await api(
        "GET",
        "/api/session/packs/" + encodeURIComponent(name)
      );
      const pack = data.pack || data;
      const blob = new Blob([JSON.stringify(pack, null, 2)], {
        type: "application/json",
      });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      URL.revokeObjectURL(a.href);
      toast("Pack downloaded", "ok");
    } catch (err) {
      toast("Pack download failed: " + err.message, "error");
    }
  }

  async function deleteNamedPack(name) {
    if (!name || !confirm('Delete pack "' + name + '"?')) return;
    try {
      const data = await api(
        "DELETE",
        "/api/session/packs/" + encodeURIComponent(name)
      );
      await renderPackList(data.packs);
      toast("Pack deleted", "ok");
    } catch (err) {
      toast("Pack delete failed: " + err.message, "error");
    }
  }

  async function exportSessionPack() {
    try {
      var labelHint = window.prompt("Pack label (optional, Enter to skip):", "");
      var notesHint = window.prompt("Pack notes (optional, Enter to skip):", "");
      var body = {
        persist: true,
        include_workspace: true,
        ui_chat_log: collectChatLog().slice(-80),
        ui_result_history: resultHistory.slice(0, HISTORY_MAX),
        ui_prefs: {
          ui_lang: uiLang || "en",
        },
      };
      if (labelHint !== null && String(labelHint).trim()) {
        body.label = String(labelHint).trim().slice(0, 80);
      }
      if (notesHint !== null && String(notesHint).trim()) {
        body.notes = String(notesHint).trim().slice(0, 200);
      }
      const data = await api("POST", "/api/session/pack/export", body);
      const pack = data.pack || data;
      const blob = new Blob([JSON.stringify(pack, null, 2)], {
        type: "application/json",
      });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = data.filename || "gnom-hub-session.json";
      a.click();
      URL.revokeObjectURL(a.href);
      await renderPackList(data.packs);
      toast(
        data.path ? "Pack saved + downloaded" : "Session pack downloaded",
        "ok"
      );
    } catch (err) {
      toast("Pack export failed: " + err.message, "error");
    }
  }

  function importSessionPack() {
    const input = document.getElementById("sys-pack-file");
    if (input) input.click();
  }

  async function onSessionPackFile(ev) {
    const file = ev.target && ev.target.files && ev.target.files[0];
    if (!file) return;
    try {
      const text = await file.text();
      const pack = JSON.parse(text);
      const snap = await api("POST", "/api/session/pack", {
        pack: pack.pack || pack,
        include_warm: true,
        include_agents: true,
        store: true,
      });
      applySnapshot(snap);
      await renderPackList();
      appendChat("system", "Session pack imported: " + (pack.label || file.name));
      toast("Session pack imported + stored", "ok");
    } catch (err) {
      toast("Pack import failed: " + err.message, "error");
    } finally {
      if (ev.target) ev.target.value = "";
    }
  }

  function formatChatTime(d) {
    const dt = d || new Date();
    try {
      return dt.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch (_e) {
      return (
        String(dt.getHours()).padStart(2, "0") +
        ":" +
        String(dt.getMinutes()).padStart(2, "0") +
        ":" +
        String(dt.getSeconds()).padStart(2, "0")
      );
    }
  }

  function persistChatLog() {
    if (!els.chatLog) return;
    try {
      sessionStorage.setItem(
        CHAT_STORAGE_KEY,
        JSON.stringify(collectChatLog().slice(-80))
      );
    } catch (_e) {
      /* quota / private mode */
    }
  }

  function collectChatLog() {
    const lines = [];
    if (!els.chatLog) return lines;
    els.chatLog.querySelectorAll(".chat-line").forEach(function (el) {
      lines.push({
        who: el.dataset.who || "system",
        text: el.dataset.text || el.textContent || "",
        ts: el.dataset.ts || "",
      });
    });
    return lines;
  }

  function applyUiPackExtras(snap) {
    if (!snap) return;
    if (Array.isArray(snap.ui_chat_log)) {
      if (els.chatLog) {
        els.chatLog.innerHTML = "";
        snap.ui_chat_log.forEach(function (entry) {
          if (typeof entry === "string") {
            renderChatLine("system", entry, "");
          } else {
            renderChatLine(
              entry.who || "system",
              entry.text || "",
              entry.ts || ""
            );
          }
        });
        els.chatLog.scrollTop = els.chatLog.scrollHeight;
      }
      persistChatLog();
    }
    if (Array.isArray(snap.ui_result_history)) {
      resultHistory = snap.ui_result_history.slice(0, HISTORY_MAX);
      saveResultHistory();
      renderHistorySelect();
    }
    if (snap.ui_prefs && typeof snap.ui_prefs === "object") {
      if (snap.ui_prefs.ui_lang === "en" || snap.ui_prefs.ui_lang === "de") {
        uiLang = snap.ui_prefs.ui_lang;
        loadTooltips(uiLang);
        const langEl = document.getElementById("sys-lang");
        if (langEl) langEl.value = uiLang;
      }
    }
  }

  function restoreChatLog() {
    if (!els.chatLog) return;
    try {
      const raw = sessionStorage.getItem(CHAT_STORAGE_KEY);
      if (!raw) return;
      const lines = JSON.parse(raw);
      if (!Array.isArray(lines) || !lines.length) return;
      els.chatLog.innerHTML = "";
      lines.forEach(function (entry) {
        if (typeof entry === "string") {
          // legacy plain lines
          const line = document.createElement("p");
          line.className = "chat-line";
          line.textContent = entry;
          els.chatLog.appendChild(line);
          return;
        }
        renderChatLine(entry.who || "system", entry.text || "", entry.ts || "");
      });
      els.chatLog.scrollTop = els.chatLog.scrollHeight;
    } catch (_e) {
      /* ignore */
    }
  }

  function renderChatLine(who, text, ts) {
    const line = document.createElement("p");
    line.className = "chat-line chat-who-" + String(who).replace(/\W+/g, "");
    line.dataset.who = who;
    line.dataset.text = text;
    line.dataset.ts = ts || "";
    if (ts) {
      const tsel = document.createElement("span");
      tsel.className = "chat-ts";
      tsel.textContent = ts;
      line.appendChild(tsel);
      line.appendChild(document.createTextNode(" "));
    }
    const body = document.createElement("span");
    body.className = "chat-body";
    body.textContent = who + ": " + text;
    line.appendChild(body);
    els.chatLog.appendChild(line);
    return line;
  }

  function clearChatLog() {
    if (els.chatLog) els.chatLog.innerHTML = "";
    try {
      sessionStorage.removeItem(CHAT_STORAGE_KEY);
    } catch (_e) {
      /* ignore */
    }
    toast("Chat log cleared", "ok");
  }

  async function resyncState() {
    try {
      const snap = await api("GET", "/api/state");
      applySnapshot(snap);
      return snap;
    } catch (_e) {
      return null;
    }
  }

  async function pollJob(jobId, maxMs) {
    currentJobId = jobId;
    const deadline = Date.now() + (maxMs || 180000);
    let lastStage = "";
    try {
      while (Date.now() < deadline) {
        let job;
        try {
          job = await api("GET", "/api/jobs/" + encodeURIComponent(jobId));
        } catch (_pollErr) {
          // transient — retry until deadline
          await new Promise(function (r) {
            setTimeout(r, 600);
          });
          continue;
        }
        const stage =
          job.stage ||
          (job.snapshot && job.snapshot.pipeline && job.snapshot.pipeline.stage) ||
          "";
        if (stage && stage !== lastStage) {
          lastStage = stage;
          if (els.stageBadge) els.stageBadge.textContent = stage;
          // Prefer job.stage (worker1…) over pipeline enum for card pulse
          if (
            stage === "worker1" ||
            stage === "worker2" ||
            stage === "worker3" ||
            stage === "worker4" ||
            stage === "brainstorm" ||
            stage === "distill" ||
            stage === "flex" ||
            stage === "coordinate" ||
            stage === "memory" ||
            stage === "work"
          ) {
            activeStage = stage;
            renderCards();
            updateBoxBorders();
          }
          if (
            stage !== "worker1" &&
            stage !== "worker2" &&
            stage !== "worker3" &&
            stage !== "worker4"
          ) {
            appendChat("system", "Stage: " + stage);
          } else {
            appendChat("system", "Worker: " + stage);
          }
        }
        if (job.snapshot) {
          applySnapshot(job.snapshot);
          // Keep live worker id pulse if job is mid-worker (snapshot stage is still "work")
          if (
            stage === "worker1" ||
            stage === "worker2" ||
            stage === "worker3" ||
            stage === "worker4"
          ) {
            activeStage = stage;
            renderCards();
            updateBoxBorders();
          }
        }
        const st = job.status;
        if (st === "done" || st === "error" || st === "clarify" || st === "cancelled") {
          // Always resync so can_execute / stage match server after soft-cancel
          await resyncState();
          return job;
        }
        await new Promise(function (r) {
          setTimeout(r, 450);
        });
      }
      // Timeout: cancel orphan + resync so UI is not left mid-pipeline
      try {
        await api("POST", "/api/jobs/" + encodeURIComponent(jobId) + "/cancel");
        appendChat("system", "Job timed out — cancel requested.");
      } catch (_c) {
        /* ignore */
      }
      await resyncState();
      throw new Error("Pipeline timeout");
    } finally {
      if (currentJobId === jobId) currentJobId = null;
    }
  }

  async function cancelCurrentJob() {
    if (!currentJobId) {
      toast("No running job", "info");
      return;
    }
    const jid = currentJobId;
    try {
      await api("POST", "/api/jobs/" + encodeURIComponent(jid) + "/cancel");
      toast("Cancel requested", "info");
      appendChat("system", "Cancel requested for job " + jid);
      await resyncState();
    } catch (err) {
      toast("Cancel failed: " + err.message, "error");
    }
  }

  function loadChatHist() {
    try {
      const raw = localStorage.getItem(CHAT_HIST_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      chatHist = Array.isArray(arr)
        ? arr.filter(function (s) {
            return typeof s === "string" && s.trim();
          }).slice(-CHAT_HIST_MAX)
        : [];
    } catch (_e) {
      chatHist = [];
    }
    chatHistIdx = -1;
    chatDraft = "";
  }

  function saveChatHist() {
    try {
      localStorage.setItem(
        CHAT_HIST_KEY,
        JSON.stringify(chatHist.slice(-CHAT_HIST_MAX))
      );
    } catch (_e) {
      /* ignore quota */
    }
  }

  /** Push a sent line (like shell history). Dedupes consecutive duplicates. */
  function pushChatHist(text) {
    const t = String(text || "").trim();
    if (!t) return;
    if (chatHist.length && chatHist[chatHist.length - 1] === t) {
      chatHistIdx = -1;
      chatDraft = "";
      return;
    }
    chatHist.push(t);
    if (chatHist.length > CHAT_HIST_MAX) {
      chatHist = chatHist.slice(-CHAT_HIST_MAX);
    }
    saveChatHist();
    chatHistIdx = -1;
    chatDraft = "";
  }

  /**
   * ArrowUp = older, ArrowDown = newer (back to empty draft).
   * Same mental model as bash/zsh.
   */
  function chatHistNav(dir) {
    if (!els.chatInput || !chatHist.length) return;
    if (chatHistIdx === -1) {
      if (dir < 0) {
        chatDraft = els.chatInput.value;
        chatHistIdx = chatHist.length - 1;
      } else {
        return;
      }
    } else {
      chatHistIdx += dir;
      if (chatHistIdx < 0) chatHistIdx = 0;
      if (chatHistIdx >= chatHist.length) {
        chatHistIdx = -1;
        els.chatInput.value = chatDraft;
        return;
      }
    }
    const line = chatHist[chatHistIdx] || "";
    els.chatInput.value = line;
    try {
      els.chatInput.setSelectionRange(line.length, line.length);
    } catch (_e) {
      /* ignore */
    }
  }

  async function sendChat() {
    const text = (els.chatInput.value || "").trim();
    if (!text || chatBusy) return;
    appendChat("you", text);
    pushChatHist(text);
    els.chatInput.value = "";
    chatHistIdx = -1;
    chatDraft = "";
    const cb = w.GnomHub.onSend;
    if (typeof cb === "function") cb(text);

    setChatBusy(true);
    // Prefer long poll always for async jobs (badge may lag bootstrap)
    const pollMs = 180000;
    appendChat("system", "Brainstorm turn…");
    toast("Brainstorming…", "info");

    try {
      const start = await api("POST", "/api/chat", { text: text });
      let snap = start;
      if (start.job_id) {
        const job = await pollJob(start.job_id, pollMs);
        snap = job.snapshot || (await api("GET", "/api/state"));
        if (job.status === "error") {
          appendChat("system", "Brainstorm error: " + (job.error || "?"));
          toast(job.error || "Brainstorm error", "error");
          applySnapshot(snap);
          return;
        }
        if (job.status === "cancelled") {
          appendChat("system", "Job cancelled.");
          toast("Cancelled", "info");
          applySnapshot(snap);
          return;
        }
      }
      applySnapshot(snap);
      const stage =
        (snap.pipeline && snap.pipeline.stage) || start.stage || "";
      if (stage === "brainstorm") {
        appendChat(
          "system",
          "Brainstorm — bei klarer Bau-Anweisung startet die Pipeline von selbst; "
            + "sonst fragt Brainstorm (z.B. „Soll ich umsetzen?“). Antwort: ja / ok / plan erstellen."
        );
        toast("Brainstorm · ja/ok = umsetzen, oder harter Bau-Befehl = sofort", "ok");
      } else if (stage === "done") {
        appendChat(
          "system",
          "Umsetzung aus Kontext (Befehl oder dein Ja nach Nachfrage) — siehe Box 3."
        );
        toast("Umgesetzt · Box 3", "ok");
        focusBox3();
      } else if (stage === "clarify") {
        appendChat("system", "Need a clarify answer in Box 1.");
        toast("Clarify needed in Box 1", "info");
      } else if (stage === "cancelled") {
        appendChat("system", "Job cancelled.");
        toast("Cancelled", "info");
      }
    } catch (err) {
      appendChat("system", "Chat failed: " + err.message);
      toast("Chat failed: " + err.message, "error");
    } finally {
      setChatBusy(false);
      currentJobId = null;
    }
  }

  async function runExecute() {
    if (chatBusy) return;
    if (els.btnExecute && els.btnExecute.disabled) {
      toast("Brainstorm first, then Execute", "info");
      return;
    }
    setChatBusy(true);
    appendChat("system", "Execute started (distill → flex → workers)…");
    toast("Executing…", "info");
    try {
      const start = await api("POST", "/api/execute");
      let snap = start;
      if (start.job_id) {
        const job = await pollJob(start.job_id, 300000);
        snap = job.snapshot || (await api("GET", "/api/state"));
        if (job.status === "error") {
          appendChat("system", "Execute error: " + (job.error || "?"));
          toast(job.error || "Execute error", "error");
          applySnapshot(snap);
          return;
        }
        if (job.status === "cancelled") {
          appendChat("system", "Execute cancelled.");
          toast("Cancelled", "info");
          applySnapshot(snap);
          return;
        }
      }
      applySnapshot(snap);
      const stage = (snap.pipeline && snap.pipeline.stage) || "";
      if (stage === "done") {
        const dur =
          lastJobElapsedSec ||
          (jobTimerStart ? (Date.now() - jobTimerStart) / 1000 : 0);
        appendChat(
          "system",
          "Execute done in " + formatDuration(dur) + " — see Box 3."
        );
        toast("Execute done · " + formatDuration(dur), "ok");
        focusBox3();
        try {
          pushResultHistory(snap.pipeline || {}, {
            label:
              ((snap.pipeline && snap.pipeline.user_text) || "Execute").slice(
                0,
                40
              ) +
              " · " +
              formatDuration(dur),
          });
        } catch (_h) {
          /* non-fatal */
        }
        try {
          await api("POST", "/api/save");
          appendChat("system", "Auto-saved HOT + agents.");
        } catch (_e) {
          /* non-fatal */
        }
      } else if (stage === "clarify") {
        appendChat("system", "Clarify needed in Box 1 before workers finish.");
        toast("Clarify needed", "info");
      }
    } catch (err) {
      appendChat("system", "Execute failed: " + err.message);
      toast("Execute failed: " + err.message, "error");
    } finally {
      setChatBusy(false);
      currentJobId = null;
    }
  }

  async function sendAndExecute() {
    const text = (els.chatInput.value || "").trim();
    if (chatBusy) return;
    if (text) {
      await sendChat();
    }
    // After brainstorm, run execute if possible
    if (!chatBusy) {
      await runExecute();
    }
  }

  function appendChat(who, text) {
    /* Crux: write into active agent chat layer */
    if (typeof syncActiveChatLog === "function") {
      syncActiveChatLog(lastClickedAgentId || "brainstorm");
    }
    if (!els.chatLog) return;
    renderChatLine(who, text, formatChatTime());
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
    persistChatLog();
  }

  async function onSave() {
    const cb = w.GnomHub.onSave;
    if (typeof cb === "function") cb();
    try {
      const data = await api("POST", "/api/save");
      appendChat("system", "Saved. " + (data.summary || ""));
      toast("Saved HOT memory + agent state", "ok");
    } catch (err) {
      appendChat("system", "Save failed: " + err.message);
    }
  }

  async function onHelp() {
    try {
      const h = await api("GET", "/api/help");
      showTooltip("help");
      if (els.placeholder) els.placeholder.hidden = true;
      els.tipRoot.hidden = false;
      els.tipTitle.textContent = h.title || "Help";
      els.tipHow.textContent = h.how_to || "";
      const keys = h.keys ? "\n\n" + h.keys : "";
      els.tipExample.textContent =
        (h.pipeline ? h.pipeline + "\n\n" : "") +
        (h.example || "") +
        keys;
    } catch (err) {
      if (els.placeholder) els.placeholder.hidden = true;
      els.tipRoot.hidden = false;
      els.tipTitle.textContent = "Help";
      els.tipHow.textContent =
        "Send = brainstorm. Execute = workers. Send+Exec = both. Card click = tune.";
      els.tipExample.textContent =
        "Keyboard: Enter send · Ctrl/⌘+Enter execute · Ctrl/⌘+S save · Esc cancel/close FS";
      toast("Help offline: " + err.message, "error");
    }
  }

  async function restoreBackupByName(name) {
    if (!name) return;
    if (
      !confirm(
        'Restore backup "' +
          name +
          '"? Current HOT is archived to COLD if non-empty. HOT/WARM/agents will be replaced.'
      )
    ) {
      return;
    }
    try {
      const snap = await api(
        "POST",
        "/api/backups/" + encodeURIComponent(name) + "/restore"
      );
      applySnapshot(snap);
      appendChat(
        "system",
        "Restored backup: " + (snap.restored_backup || name)
      );
      toast(
        "Backup restored" +
          (snap.checkpoint_loaded ? " (+ checkpoint)" : ""),
        "ok"
      );
      openSystemModal();
    } catch (err) {
      toast("Restore backup failed: " + err.message, "error");
    }
  }

  async function deleteBackupByName(name) {
    if (!name || !confirm('Delete backup "' + name + '"?')) return;
    try {
      await api("DELETE", "/api/backups/" + encodeURIComponent(name));
      toast("Backup deleted", "ok");
      openSystemModal();
    } catch (err) {
      toast("Delete backup failed: " + err.message, "error");
    }
  }

  async function onReset() {
    if (
      !window.confirm(
        "Reset HOT session? Current HOT is archived to COLD first. WARM facts stay."
      )
    ) {
      return;
    }
    try {
      const snap = await api("POST", "/api/reset");
      applySnapshot(snap);
      setBox2("Brainstorm thoughts appear here.\n\n(Empty — send a chat message to start.)");
      setBox3("Worker results appear here.\n\n(Empty — workers fill this after the pipeline.)");
      hideClarify();
      appendChat("system", "Session reset (HOT archived to COLD if non-empty).");
      toast("Session reset", "ok");
    } catch (err) {
      appendChat("system", "Reset failed: " + err.message);
    }
  }

  async function onArchive() {
    try {
      const data = await api("POST", "/api/cold/archive", { label: "manual" });
      toast("Archived to COLD: " + (data.archive && data.archive.id), "ok");
      const snap = await api("GET", "/api/state");
      applySnapshot(snap);
    } catch (err) {
      toast("Archive failed: " + err.message, "error");
    }
  }

  async function toggleGodMode() {
    const on = els.godBadge && els.godBadge.classList.contains("on");
    const next = !on;
    if (next) {
      if (
        !window.confirm(
          "Enable God-Mode? Elevated actions (clicks/allowlisted shell) become available."
        )
      ) {
        return;
      }
    }
    try {
      const data = await api("POST", "/api/god-mode", {
        enabled: next,
        reason: "ui-toggle",
      });
      if (els.godBadge) {
        els.godBadge.textContent = data.enabled ? "God: ON" : "God: off";
        els.godBadge.classList.toggle("on", !!data.enabled);
      }
      toast(data.enabled ? "God-Mode ON" : "God-Mode OFF", data.enabled ? "info" : "ok");
    } catch (err) {
      toast("God-Mode failed: " + err.message, "error");
    }
  }

  function showColdBrowser() {
    if (els.placeholder) els.placeholder.hidden = true;
    if (els.tipRoot) els.tipRoot.hidden = true;
    if (els.coldBrowser) els.coldBrowser.hidden = false;
  }

  function hideColdBrowser() {
    if (els.coldBrowser) els.coldBrowser.hidden = true;
    if (els.coldDetail) els.coldDetail.textContent = "";
  }

  async function openColdBrowser() {
    showColdBrowser();
    try {
      const data = await api("GET", "/api/cold");
      const list = data.archives || [];
      if (!els.coldList) return;
      els.coldList.innerHTML = "";
      if (!list.length) {
        els.coldList.innerHTML = "<li>(no archives yet — use Archive or Reset)</li>";
        return;
      }
      list.forEach(function (a) {
        const li = document.createElement("li");
        li.textContent =
          (a.id || "?") +
          " · " +
          (a.label || "") +
          " · msg=" +
          (a.messages != null ? a.messages : "?");
        li.dataset.id = a.id;
        li.addEventListener("click", function () {
          Array.prototype.forEach.call(els.coldList.querySelectorAll("li"), function (n) {
            n.classList.remove("active");
          });
          li.classList.add("active");
          loadColdDetail(a.id);
        });
        els.coldList.appendChild(li);
      });
    } catch (err) {
      toast("COLD list failed: " + err.message, "error");
    }
  }

  async function loadColdDetail(id) {
    selectedColdId = id || null;
    try {
      const data = await api("GET", "/api/cold/" + encodeURIComponent(id));
      const meta = data.meta || {};
      const sess = data.session || {};
      const facts = sess.facts || [];
      const msgs = sess.messages || [];
      const lines = [
        "id: " + (meta.id || id),
        "label: " + (meta.label || ""),
        "created: " + (meta.created_at || ""),
        "messages: " + msgs.length + " · facts: " + facts.length,
        "",
        "Facts:",
      ];
      facts.slice(0, 8).forEach(function (f) {
        lines.push("• " + f);
      });
      if (data.canvas) {
        lines.push("", "Canvas (head):", String(data.canvas).slice(0, 300));
      }
      if (els.coldDetail) els.coldDetail.textContent = lines.join("\n");
    } catch (err) {
      toast("COLD load failed: " + err.message, "error");
    }
  }

  async function restoreSelectedCold() {
    if (!selectedColdId) {
      toast("Select a COLD archive first", "info");
      return;
    }
    if (
      !confirm(
        'Restore COLD "' +
          selectedColdId +
          '" into HOT? Current HOT is archived first if non-empty.'
      )
    ) {
      return;
    }
    try {
      const snap = await api(
        "POST",
        "/api/cold/" + encodeURIComponent(selectedColdId) + "/restore"
      );
      applySnapshot(snap);
      appendChat(
        "system",
        "Restored COLD: " +
          ((snap.restored && snap.restored.id) || selectedColdId)
      );
      toast("COLD restored to HOT", "ok");
      await openColdBrowser();
    } catch (err) {
      toast("COLD restore failed: " + err.message, "error");
    }
  }

  async function deleteSelectedCold() {
    if (!selectedColdId) {
      toast("Select a COLD archive first", "info");
      return;
    }
    if (!confirm('Delete COLD archive "' + selectedColdId + '"?')) return;
    try {
      await api(
        "DELETE",
        "/api/cold/" + encodeURIComponent(selectedColdId)
      );
      selectedColdId = null;
      if (els.coldDetail) els.coldDetail.textContent = "";
      toast("COLD deleted", "ok");
      await openColdBrowser();
    } catch (err) {
      toast("COLD delete failed: " + err.message, "error");
    }
  }

  async function onClarify(answer) {
    if (chatBusy) {
      toast("Busy — wait for current job", "info");
      return;
    }
    const cb = w.GnomHub.onClarify;
    if (typeof cb === "function") cb(answer);
    appendChat("you", "[clarify] " + answer);
    setChatBusy(true);
    try {
      const start = await api("POST", "/api/clarify", { option: answer });
      let snap = start;
      if (start.job_id) {
        const job = await pollJob(start.job_id, 180000);
        snap = job.snapshot || (await api("GET", "/api/state"));
        if (job.status === "error") {
          appendChat("system", "Clarify error: " + (job.error || "?"));
          toast(job.error || "Clarify failed", "error");
          // Re-show clarify UI if still needed
          applySnapshot(snap);
          return;
        }
      }
      applySnapshot(snap);
      // Hide only after successful response (applySnapshot may keep it if still clarify)
      if (!(snap.pipeline && snap.pipeline.stage === "clarify")) {
        hideClarify();
      }
      if (snap.pipeline && snap.pipeline.stage === "done") {
        appendChat("system", "Pipeline done.");
        toast("Pipeline done", "ok");
      }
    } catch (err) {
      appendChat("system", "Clarify failed: " + err.message);
      toast("Clarify failed: " + err.message, "error");
      // Restore buttons/state so user can retry
      await resyncState();
    } finally {
      setChatBusy(false);
    }
  }

  w.GnomHub.showClarify = showClarify;
  w.GnomHub.hideClarify = hideClarify;
  w.GnomHub.showTooltip = showTooltip;
  w.GnomHub.getAgents = function () {
    return AGENTS.map(function (a) {
      return {
        id: a.id,
        enabled: a.enabled,
        toggleable: a.toggleable,
        parked: a.parked,
      };
    });
  };
  w.GnomHub.setBox2 = setBox2;
  w.GnomHub.setBox3 = setBox3;
  w.GnomHub.applySnapshot = applySnapshot;

/* part: 04-boxes.js  lines 3682-4267 of app.js — edit parts, run scripts/build_ui_js.py */

  /**
   * Dynamic presentation inside a box/panel:
   * HTML → live preview (+ Source), code fence → code view, JSON → pretty, else text.
   * Fills the host; host must be a flex column with min-height:0.
   */
  function renderDynamicContent(host, raw, opts) {
    opts = opts || {};
    const text = String(raw || "");
    host.innerHTML = "";
    host.classList.add("dyn-host");

    const html = extractHtml(text);
    if (html) {
      host.dataset.kind = "html";
      const bar = document.createElement("div");
      bar.className = "dyn-bar";
      const kind = document.createElement("span");
      kind.className = "dyn-kind";
      kind.textContent = "HTML";
      bar.appendChild(kind);
      const modes = document.createElement("div");
      modes.className = "worker-panel-modes";
      const btnPrev = document.createElement("button");
      btnPrev.type = "button";
      btnPrev.className = "worker-mode-btn is-active";
      btnPrev.textContent = "Preview";
      btnPrev.dataset.mode = "preview";
      const btnSrc = document.createElement("button");
      btnSrc.type = "button";
      btnSrc.className = "worker-mode-btn";
      btnSrc.textContent = "Source";
      btnSrc.dataset.mode = "source";
      modes.appendChild(btnPrev);
      modes.appendChild(btnSrc);
      bar.appendChild(modes);
      host.appendChild(bar);

      const stage = document.createElement("div");
      stage.className = "dyn-stage";
      const frame = document.createElement("iframe");
      frame.className = "worker-preview-frame dyn-frame";
      frame.setAttribute(
        "sandbox",
        "allow-same-origin allow-forms allow-popups allow-modals"
      );
      frame.setAttribute("title", opts.title || "preview");
      frame.setAttribute("scrolling", "no"); /* pure box — no scroll */
      frame.srcdoc = wrapHtmlDocument(html);
      const pre = document.createElement("pre");
      pre.className = "result-block worker-source dyn-source";
      pre.textContent = text;
      pre.hidden = true;
      stage.appendChild(frame);
      stage.appendChild(pre);
      host.appendChild(stage);

      modes.querySelectorAll(".worker-mode-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
          modes.querySelectorAll(".worker-mode-btn").forEach(function (b) {
            b.classList.remove("is-active");
          });
          btn.classList.add("is-active");
          if (btn.dataset.mode === "preview") {
            frame.hidden = false;
            pre.hidden = true;
          } else {
            frame.hidden = true;
            pre.hidden = false;
          }
        });
      });
      return "html";
    }

    // fenced code ```lang ... ```
    const fence = text.match(/```([a-zA-Z0-9_+-]*)\s*\n([\s\S]*?)```/);
    if (fence && fence[2] && fence[2].trim().length > 0) {
      host.dataset.kind = "code";
      const bar = document.createElement("div");
      bar.className = "dyn-bar";
      const kind = document.createElement("span");
      kind.className = "dyn-kind";
      kind.textContent = (fence[1] || "code").toUpperCase();
      bar.appendChild(kind);
      host.appendChild(bar);
      const stage = document.createElement("div");
      stage.className = "dyn-stage";
      const pre = document.createElement("pre");
      pre.className = "result-block dyn-source dyn-code";
      pre.textContent = fence[2].replace(/\n$/, "");
      stage.appendChild(pre);
      // if more text outside fence, append note
      const rest = text.replace(fence[0], "").trim();
      if (rest) {
        const note = document.createElement("pre");
        note.className = "result-block dyn-note";
        note.textContent = rest;
        stage.appendChild(note);
      }
      host.appendChild(stage);
      return "code";
    }

    // JSON object/array
    const t = text.trim();
    if (
      (t.startsWith("{") && t.endsWith("}")) ||
      (t.startsWith("[") && t.endsWith("]"))
    ) {
      try {
        const pretty = JSON.stringify(JSON.parse(t), null, 2);
        host.dataset.kind = "json";
        const bar = document.createElement("div");
        bar.className = "dyn-bar";
        const kind = document.createElement("span");
        kind.className = "dyn-kind";
        kind.textContent = "JSON";
        bar.appendChild(kind);
        host.appendChild(bar);
        const stage = document.createElement("div");
        stage.className = "dyn-stage";
        const pre = document.createElement("pre");
        pre.className = "result-block dyn-source dyn-code";
        pre.textContent = pretty;
        stage.appendChild(pre);
        host.appendChild(stage);
        return "json";
      } catch (_e) {
        /* fall through */
      }
    }

    host.dataset.kind = "text";
    const stage = document.createElement("div");
    stage.className = "dyn-stage";
    const pre = document.createElement("pre");
    pre.className = "result-block dyn-source";
    pre.textContent = text;
    stage.appendChild(pre);
    host.appendChild(stage);
    return "text";
  }

  function setBox2(htmlOrText) {
    const body =
      (typeof getAgentBoxBody === "function" && getAgentBoxBody(2, "brainstorm")) ||
      document.getElementById("box2-content");
    if (!body) return;
    renderDynamicContent(body, htmlOrText || "", { title: "Brainstorm" });
  }

  /** Write text into a specific agent layer in box 2 (e.g. flex notes). */
  function setBox2Agent(agentId, htmlOrText, title) {
    const body =
      (typeof getAgentBoxBody === "function" && getAgentBoxBody(2, agentId)) ||
      document.getElementById("box2-" + agentId);
    if (!body) return;
    renderDynamicContent(body, htmlOrText || "", { title: title || agentId });
  }

  /**
   * Extract real HTML documents for Preview iframes.
   * Strict on purpose: QA/a11y notes often mention tags (e.g. </html>) and must
   * stay as plain text — not empty/broken preview frames.
   */
  function extractHtml(raw) {
    const s = String(raw || "");
    // Explicit ```html fence with a real document or substantial markup
    const fenceHtml = s.match(/```html\s*([\s\S]*?)```/i);
    if (fenceHtml && fenceHtml[1]) {
      const body = fenceHtml[1].trim();
      if (/<!DOCTYPE\s+html|<html[\s>]/i.test(body)) return body;
      if (body.startsWith("<") && (body.match(/<\w+/g) || []).length >= 4) return body;
    }
    // Full document with doctype + closing html (preferred)
    const fullDoc = s.match(/(<!DOCTYPE\s+html[\s\S]*?<\/html>)/i);
    if (fullDoc) return fullDoc[1].trim();
    // Open doctype document (truncated mid-file still previewable)
    const doctypeOpen = s.match(/(<!DOCTYPE\s+html[\s\S]{120,})$/i);
    if (doctypeOpen && /<(html|head|body)[\s>]/i.test(doctypeOpen[1])) {
      return doctypeOpen[1].trim();
    }
    const htmlTag = s.match(/(<html[\s\S]*?<\/html>)/i);
    if (htmlTag) return htmlTag[1].trim();
    // Markup-first fragment only: must start with tag, enough structure, high density
    const trimmed = s.trim();
    if (
      trimmed.startsWith("<") &&
      /<\/(div|section|body|main|header|footer|article|html)>/i.test(trimmed)
    ) {
      const tags = (trimmed.match(/<\w+/g) || []).length;
      const prose = trimmed.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
      // Prefer markup over prose (avoids checklists that quote a few tags)
      if (tags >= 6 && prose.length < trimmed.length * 0.55) return trimmed;
    }
    return null;
  }

  /**
   * Box 3: dynamic — one panel per worker result (all outputs, not only first).
   * HTML → Preview + Source; plain text → pre. Panels share height equally.
   */
  function updateBox3Toolbar() {
    // Box 3 toolbar intentionally minimal (no history/diff chrome)
  }

  function renderBox3Workers(pipeline) {
    const outputs = normalizeWorkerOutputs(pipeline);
    lastWorkerOutputs = outputs;
    updateBox3Toolbar();

    /* clear each worker agent layer in box 3 */
    ["worker1", "worker2", "worker3", "worker4"].forEach(function (wid) {
      const body =
        (typeof getAgentBoxBody === "function" && getAgentBoxBody(3, wid)) ||
        document.getElementById("box3-" + wid) ||
        (wid === "worker1" ? document.getElementById("box3-content") : null);
      if (!body) return;
      body.innerHTML = "";
      body.classList.add("box3-dynamic");
      const empty = document.createElement("p");
      empty.className = "muted empty-hint";
      if (pipeline && pipeline.stage === "work") {
        empty.textContent = "Workers running…";
      } else {
        empty.textContent = wid + " result";
      }
      body.appendChild(empty);
    });

    if (!outputs.length) {
      return;
    }

    /* each worker output → that agent’s layer in box 3 */
    outputs.forEach(function (out, idx) {
      const wid =
        (out && (out.worker || out.id || out.name) || "").toString().toLowerCase();
      let agentId = null;
      if (/worker\s*1|w1/.test(wid) || wid === "worker1") agentId = "worker1";
      else if (/worker\s*2|w2/.test(wid) || wid === "worker2") agentId = "worker2";
      else if (/worker\s*3|w3/.test(wid) || wid === "worker3") agentId = "worker3";
      else if (/worker\s*4|w4/.test(wid) || wid === "worker4") agentId = "worker4";
      else agentId = "worker" + Math.min(idx + 1, 4);

      const body =
        (typeof getAgentBoxBody === "function" && getAgentBoxBody(3, agentId)) ||
        document.getElementById(agentId === "worker1" ? "box3-content" : "box3-" + agentId);
      if (!body) return;
      body.innerHTML = "";
      body.classList.add("box3-dynamic");
      renderDynamicContent(body, (out && out.result) || "", {
        title: ((out && out.name) || agentId) + " preview",
      });
    });

    box3FocusIdx = 0;
    bindBoxLayerControls();
  }

  /** Save one worker HTML into personal WS (WS-gnom-hub-v1/selected/). */
  async function keepWorkerToPersonalWs(out, idx) {
    const raw = (out && out.result) || "";
    const html = extractHtml(raw);
    if (!html) {
      toast("No HTML to keep — only HTML goes to personal WS", "info");
      return;
    }
    const name =
      ((out && (out.worker || out.name)) || "worker" + (idx + 1))
        .toString()
        .replace(/[^\w.-]+/g, "_") + ".html";
    try {
      const data = await api("POST", "/api/workspace/keep", {
        content: html,
        name: name,
        worker: (out && out.worker) || null,
      });
      toast(
        "Saved → " + (data.path || "personal WS/selected/") + " (Clear won't delete this)",
        "ok"
      );
      // optional clipboard convenience
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(html).catch(function () {});
      }
    } catch (err) {
      toast("Keep failed: " + (err.message || err), "error");
    }
  }

  function copyAllWorkerResults() {
    if (!lastWorkerOutputs.length) {
      toast("No worker results to copy", "info");
      return;
    }
    // Keep each HTML result into personal WS (only chosen outputs that are HTML)
    var kept = 0;
    lastWorkerOutputs.forEach(function (o, i) {
      if (extractHtml(o.result || "")) {
        kept += 1;
        keepWorkerToPersonalWs(o, i);
      }
    });
    if (!kept) {
      toast("No HTML among worker results to keep", "info");
      return;
    }
    const parts = lastWorkerOutputs.map(function (o, i) {
      const label = o.name || "Worker " + (i + 1);
      return "=== " + label + " ===\n" + (o.result || "");
    });
    const text = parts.join("\n\n");
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () {
          toast("Kept HTML to personal WS + clipboard (" + text.length + " chars)", "ok");
        },
        function () {
          toast("Copy failed", "error");
        }
      );
    } else {
      toast("Clipboard not available", "error");
    }
  }

  /**
   * Simple line LCS unified-style diff (capped for large texts).
   * Returns array of {type: same|add|del|meta, text}.
   */
  function computeLineDiff(textA, textB) {
    const MAX = 400;
    let a = String(textA || "").split("\n");
    let b = String(textB || "").split("\n");
    let truncated = false;
    if (a.length > MAX) {
      a = a.slice(0, MAX);
      truncated = true;
    }
    if (b.length > MAX) {
      b = b.slice(0, MAX);
      truncated = true;
    }
    const n = a.length;
    const m = b.length;
    // DP LCS lengths
    const dp = [];
    for (let i = 0; i <= n; i++) {
      dp[i] = new Array(m + 1).fill(0);
    }
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        if (a[i] === b[j]) dp[i][j] = dp[i + 1][j + 1] + 1;
        else dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
    const lines = [];
    let i = 0;
    let j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) {
        lines.push({ type: "same", text: "  " + a[i] });
        i++;
        j++;
      } else if (dp[i + 1][j] >= dp[i][j + 1]) {
        lines.push({ type: "del", text: "- " + a[i] });
        i++;
      } else {
        lines.push({ type: "add", text: "+ " + b[j] });
        j++;
      }
    }
    while (i < n) {
      lines.push({ type: "del", text: "- " + a[i] });
      i++;
    }
    while (j < m) {
      lines.push({ type: "add", text: "+ " + b[j] });
      j++;
    }
    if (truncated) {
      lines.push({
        type: "meta",
        text: "… truncated to first " + MAX + " lines per side",
      });
    }
    return lines;
  }

  function closeDiffOverlay() {
    const el = document.getElementById("diff-overlay");
    if (el) el.remove();
  }

  function openWorkerDiff() {
    if (lastWorkerOutputs.length < 2) {
      toast("Need at least two worker results to diff", "info");
      return;
    }
    closeDiffOverlay();
    closeWorkerFullscreen();
    const a = lastWorkerOutputs[0];
    const b = lastWorkerOutputs[1];
    const nameA = a.name || "Worker 1";
    const nameB = b.name || "Worker 2";
    const rows = computeLineDiff(a.result || "", b.result || "");

    const overlay = document.createElement("div");
    overlay.id = "diff-overlay";
    overlay.className = "diff-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-label", "Worker diff");

    const bar = document.createElement("div");
    bar.className = "diff-bar";
    const title = document.createElement("span");
    title.className = "diff-title";
    title.textContent = "Diff: " + nameA + " → " + nameB;
    const actions = document.createElement("div");
    actions.className = "worker-fs-actions";
    const btnCopy = document.createElement("button");
    btnCopy.type = "button";
    btnCopy.className = "worker-mode-btn";
    btnCopy.textContent = "Copy diff";
    btnCopy.addEventListener("click", function () {
      const text = rows.map(function (r) {
        return r.text;
      }).join("\n");
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(
          function () {
            toast("Diff copied", "ok");
          },
          function () {
            toast("Copy failed", "error");
          }
        );
      }
    });
    const btnClose = document.createElement("button");
    btnClose.type = "button";
    btnClose.className = "worker-mode-btn";
    btnClose.textContent = "Close · Esc";
    btnClose.addEventListener("click", closeDiffOverlay);
    actions.appendChild(btnCopy);
    actions.appendChild(btnClose);
    bar.appendChild(title);
    bar.appendChild(actions);

    const body = document.createElement("div");
    body.className = "diff-body";
    const meta = document.createElement("span");
    meta.className = "diff-line diff-meta";
    meta.textContent =
      "− " + nameA + "   + " + nameB + "   (" + rows.length + " lines)";
    body.appendChild(meta);
    rows.forEach(function (r) {
      const span = document.createElement("span");
      span.className = "diff-line diff-" + r.type;
      span.textContent = r.text;
      body.appendChild(span);
    });

    overlay.appendChild(bar);
    overlay.appendChild(body);
    overlay.addEventListener("click", function (ev) {
      if (ev.target === overlay) closeDiffOverlay();
    });
    document.body.appendChild(overlay);
  }

  function normalizeWorkerOutputs(pipeline) {
    const p = pipeline || {};
    if (p.worker_outputs && p.worker_outputs.length) {
      return p.worker_outputs.map(function (o, i) {
        return {
          worker: o.worker || "worker" + (i + 1),
          name: o.name || "Worker " + (i + 1),
          task: o.task || "",
          result: o.result != null ? String(o.result) : "",
          index: o.index != null ? o.index : i + 1,
        };
      });
    }
    if (p.worker_results && p.worker_results.length) {
      return p.worker_results.map(function (r, i) {
        return {
          worker: "worker" + (i + 1),
          name: "Worker " + (i + 1),
          task: "",
          result: String(r),
          index: i + 1,
        };
      });
    }
    return [];
  }

  let box3FocusIdx = 0;
  let box3FrontSlot = "a"; // which dual-layer slot is front
  let box3BlendBusy = false;

  function updateBox3WorkerLabel(idx, n) {
    /* label UI removed — pure box frame */
    void idx;
    void n;
  }

  function paintWorkerIntoSlot(slotEl, out, idx) {
    if (!slotEl) return;
    slotEl.innerHTML = "";
    slotEl.dataset.workerIdx = String(idx);
    const wrap = document.createElement("div");
    wrap.className = "worker-panel-body dual-slot-body";
    renderDynamicContent(wrap, (out && out.result) || "", {
      title: ((out && out.name) || "Worker") + " preview",
    });
    // copy control lives on box layer-controls; keep content clean
    slotEl.appendChild(wrap);
  }

  function focusBox3Worker(idx) {
    const dual = document.getElementById("box3-dual");
    if (!dual || !lastWorkerOutputs.length) return;
    if (box3BlendBusy) return;
    const n = lastWorkerOutputs.length;
    const nextIdx = ((idx % n) + n) % n;
    if (nextIdx === box3FocusIdx && dual.querySelector(".layer-slot.is-front .dual-slot-body")) {
      updateBox3WorkerLabel(box3FocusIdx, n);
      return;
    }

    const front = dual.querySelector(".layer-slot.is-front");
    const back = dual.querySelector(".layer-slot:not(.is-front)");
    if (!front || !back) return;

    // paint next worker into back layer, then crossfade
    paintWorkerIntoSlot(back, lastWorkerOutputs[nextIdx], nextIdx);
    box3BlendBusy = true;
    // force reflow so transition runs
    void back.offsetWidth;
    front.classList.remove("is-front");
    front.classList.add("is-back");
    back.classList.remove("is-back");
    back.classList.add("is-front");
    box3FocusIdx = nextIdx;
    box3FrontSlot = back.dataset.slot || box3FrontSlot;
    updateBox3WorkerLabel(box3FocusIdx, n);

    window.setTimeout(function () {
      box3BlendBusy = false;
      // clear old front to free memory (large HTML)
      const old = dual.querySelector(".layer-slot:not(.is-front)");
      if (old) old.innerHTML = "";
    }, 380);
  }

  function bindBoxLayerControls() {
    /* box chrome buttons removed — pure frame */
  }

  function wrapHtmlDocument(html) {
    let doc = html || "";
    if (!/<!DOCTYPE/i.test(doc) && !/<html/i.test(doc)) {
      doc =
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">" +
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">" +
        "<style>body{font-family:system-ui,sans-serif;margin:12px;}</style>" +
        "</head><body>" +
        doc +
        "</body></html>";
    }
    return doc;
  }

  function workerFileBase(out) {
    return (out.name || out.worker || "worker")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "worker";
  }

  function downloadWorkerResult(out, raw, html) {
    const isHtml = !!html;
    const blob = new Blob([isHtml ? wrapHtmlDocument(html) : raw || ""], {
      type: isHtml ? "text/html;charset=utf-8" : "text/plain;charset=utf-8",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = workerFileBase(out) + (isHtml ? ".html" : ".txt");
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 500);
    toast("Downloaded " + a.download, "ok");
  }

  function openWorkerInTab(html) {
    const doc = wrapHtmlDocument(html);
    const blob = new Blob([doc], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const win = window.open(url, "_blank");
    if (!win) {
      toast("Popup blocked — allow popups for new tab", "error");
      URL.revokeObjectURL(url);
      return;
    }
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 60000);
    toast("Opened in new tab", "ok");
  }

  async function saveWorkerToWorkspace(out, raw, html, zone) {
    const isHtml = !!html;
    const z = zone === "perm" ? "perm" : "temp";
    const name =
      workerFileBase(out) +
      "_" +
      Date.now().toString(36) +
      (isHtml ? ".html" : ".txt");
    const content = isHtml ? wrapHtmlDocument(html) : raw || "";
    try {
      const data = await api("POST", "/api/workspace/write", {
        zone: z,
        name: name,
        content: content,
      });
      const label = z === "perm" ? "perm" : "temp";
      toast("Saved → " + label + ": " + name, "ok");
      appendChat(
        "system",
        "Workspace[" + label + "] ← " + name + (data.path ? " (" + data.path + ")" : "")
      );
    } catch (err) {
      toast("Workspace save failed: " + err.message, "error");
    }
  }

  function closeWorkerFullscreen() {
    const el = document.getElementById("worker-fs-overlay");
    if (el) el.remove();
    document.body.classList.remove("worker-fs-open");
  }

  function openWorkerFullscreen(out, raw, html) {
    closeWorkerFullscreen();
    const overlay = document.createElement("div");
    overlay.id = "worker-fs-overlay";
    overlay.className = "worker-fs-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-label", "Fullscreen preview");

    const bar = document.createElement("div");
    bar.className = "worker-fs-bar";
    const title = document.createElement("span");
    title.className = "worker-fs-title";
    title.textContent = (out.name || "Worker") + " · fullscreen";
    const actions = document.createElement("div");
    actions.className = "worker-fs-actions";

    const btnDl = document.createElement("button");
    btnDl.type = "button";
    btnDl.className = "worker-mode-btn";
    btnDl.textContent = "Download";
    btnDl.addEventListener("click", function () {
      downloadWorkerResult(out, raw, html);
    });

    const btnClose = document.createElement("button");
    btnClose.type = "button";
    btnClose.className = "worker-mode-btn";
    btnClose.textContent = "Close · Esc";
    btnClose.addEventListener("click", closeWorkerFullscreen);

    actions.appendChild(btnDl);
    actions.appendChild(btnClose);
    bar.appendChild(title);
    bar.appendChild(actions);

    const body = document.createElement("div");
    body.className = "worker-fs-body";
    if (html) {
      const frame = document.createElement("iframe");
      frame.className = "worker-fs-frame";
      frame.setAttribute(
        "sandbox",
        "allow-same-origin allow-forms allow-popups allow-modals"
      );
      frame.setAttribute("title", (out.name || "Worker") + " fullscreen");
      frame.srcdoc = wrapHtmlDocument(html);
      body.appendChild(frame);
    } else {
      const pre = document.createElement("pre");
      pre.className = "worker-fs-source";
      pre.textContent = raw || "";
      body.appendChild(pre);
    }

    overlay.appendChild(bar);
    overlay.appendChild(body);
    overlay.addEventListener("click", function (ev) {
      if (ev.target === overlay) closeWorkerFullscreen();
    });
    document.body.appendChild(overlay);
    document.body.classList.add("worker-fs-open");
  }

  /** Scroll Box 3 into view and flash highlight after Execute. */
  function focusBox3() {
    const box = document.getElementById("box3");
    if (!box) return;
    try {
      box.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (_e) {
      box.scrollIntoView();
    }
    box.classList.add("box3-flash");
    setTimeout(function () {
      box.classList.remove("box3-flash");
    }, 1200);
  }

  function setBox3(htmlOrText) {
    // Legacy plain-text path (tests / external hooks)
    renderBox3Workers({
      stage: "done",
      worker_results: htmlOrText ? [String(htmlOrText)] : [],
    });
  }

  async function bootstrap() {
    restoreChatLog();
    try {
      // Ensure all pipeline agents are ON (Worker 1+2 included)
      try {
        const allOn = await api("POST", "/api/agents/enable-all");
        if (allOn.agents) applyAgentsFromServer(allOn.agents);
      } catch (_e) {
        /* older server without endpoint */
      }
      const snap = await api("GET", "/api/state");
      await loadTooltips((snap && snap.ui_lang) || "en");
      applySnapshot(snap);
      const defaultModel = (snap.llm && snap.llm.default_model) || "deepseek-chat";
      AGENTS.forEach(function (a) {
        if (!a.model || a.model === "—") a.model = defaultModel;
      });
      // phase3 UI chrome (god/cold/vec badges)
      if (snap.features && snap.features.phase3 === false) {
        document.body.classList.add("phase3-off");
      } else {
        document.body.classList.remove("phase3-off");
      }
      renderCards();
    } catch (err) {
      console.warn("[GnomHub] offline / no API yet:", err.message);
    }
  }

/* part: 05-init.js  lines 4268-4656 of app.js — edit parts, run scripts/build_ui_js.py */
  function init() {
    if (typeof buildAgentLayers === "function") buildAgentLayers();
    if (typeof buildChatLayers === "function") buildChatLayers();
    renderCards();
    bindTooltipHovers();
    bindTuneSliders();

    els.btnSend.addEventListener("click", sendChat);
    if (els.btnExecute) els.btnExecute.addEventListener("click", runExecute);
    const btnSendExec = document.getElementById("btn-send-exec");
    if (btnSendExec) btnSendExec.addEventListener("click", sendAndExecute);
    const btnCancel = document.getElementById("btn-cancel");
    if (btnCancel) btnCancel.addEventListener("click", cancelCurrentJob);
    if (els.btnMic) els.btnMic.addEventListener("click", toggleMic);
    const presetApply = document.getElementById("sys-preset-apply");
    const presetDel = document.getElementById("sys-preset-delete");
    if (presetApply) presetApply.addEventListener("click", applySelectedPreset);
    if (presetDel) presetDel.addEventListener("click", deleteSelectedPreset);
    const teamApply = document.getElementById("sys-team-apply");
    const teamSave = document.getElementById("sys-team-save");
    const teamDel = document.getElementById("sys-team-delete");
    const planMode = document.getElementById("sys-plan-mode");
    if (teamApply) teamApply.addEventListener("click", applySelectedTeam);
    if (teamSave) teamSave.addEventListener("click", saveCurrentTeam);
    if (teamDel) teamDel.addEventListener("click", deleteSelectedTeam);
    if (planMode) planMode.addEventListener("change", setPlanModeFromUi);
    loadChatHist();
    els.chatInput.addEventListener("keydown", function (ev) {
      // Terminal-style history: ↑ older · ↓ newer
      if (ev.key === "ArrowUp") {
        ev.preventDefault();
        chatHistNav(-1);
        return;
      }
      if (ev.key === "ArrowDown") {
        ev.preventDefault();
        chatHistNav(1);
        return;
      }
      // Typing resets history cursor to "live draft"
      if (ev.key.length === 1 || ev.key === "Backspace" || ev.key === "Delete") {
        if (chatHistIdx !== -1) {
          chatHistIdx = -1;
          chatDraft = "";
        }
      }
      // Ctrl/Cmd+Enter = Execute; plain Enter = Send
      if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
        ev.preventDefault();
        runExecute();
        return;
      }
      if (ev.key === "Enter") {
        ev.preventDefault();
        sendChat();
      }
    });
    document.addEventListener("keydown", function (ev) {
      // Esc: close overlays first, else cancel running job
      if (ev.key === "Escape") {
        if (els.toolsModal && !els.toolsModal.hidden) {
          ev.preventDefault();
          closeToolsModal();
          return;
        }
        if (els.usageModal && !els.usageModal.hidden) {
          ev.preventDefault();
          closeUsageModal();
          return;
        }
        if (els.vectorModal && !els.vectorModal.hidden) {
          ev.preventDefault();
          closeVectorModal();
          return;
        }
        if (document.getElementById("diff-overlay")) {
          ev.preventDefault();
          closeDiffOverlay();
          return;
        }
        if (document.getElementById("worker-fs-overlay")) {
          ev.preventDefault();
          closeWorkerFullscreen();
          return;
        }
        if (chatBusy) {
          ev.preventDefault();
          cancelCurrentJob();
        }
        return;
      }
      // Ctrl/Cmd+S = save HOT + agents (skip when typing in modal fields is fine — still save)
      if ((ev.ctrlKey || ev.metaKey) && (ev.key === "s" || ev.key === "S")) {
        ev.preventDefault();
        onSave();
      }
    });
    const btnCopyAll = document.getElementById("btn-copy-all");
    if (btnCopyAll) btnCopyAll.addEventListener("click", copyAllWorkerResults);
    const btnDiff = document.getElementById("btn-diff");
    if (btnDiff) btnDiff.addEventListener("click", openWorkerDiff);
    const hist = document.getElementById("result-history");
    if (hist) {
      hist.addEventListener("change", function () {
        if (hist.value) restoreHistoryEntry(hist.value);
      });
    }
    loadResultHistory();    renderHistorySelect();

    const btnReexec = document.getElementById("btn-reexec");
    if (btnReexec) btnReexec.addEventListener("click", reexecFromHistory);
    const btnHistExport = document.getElementById("btn-hist-export");
    if (btnHistExport) btnHistExport.addEventListener("click", exportResultHistory);
    const histSel = document.getElementById("result-history");
    if (histSel) {
      histSel.addEventListener("change", function () {
        const re = document.getElementById("btn-reexec");
        if (!re) return;
        const entry = resultHistory.find(function (e) {
          return e.id === histSel.value;
        });
        re.disabled = !(entry && (entry.can_reexec || entry.user_text || entry.brainstorm_notes));
        re.dataset.historyId = entry ? entry.id : "";
      });
    }
    const packExp = document.getElementById("sys-pack-export");
    if (packExp) packExp.addEventListener("click", exportSessionPack);
    const packImp = document.getElementById("sys-pack-import");
    if (packImp) packImp.addEventListener("click", importSessionPack);
    const packFilter = document.getElementById("sys-pack-filter");
    if (packFilter) {
      packFilter.addEventListener("input", function () {
        renderPackList(packListCache);
      });
    }
    const hotAdd = document.getElementById("sys-hot-add");
    if (hotAdd) hotAdd.addEventListener("click", addHotFact);
    const hotClear = document.getElementById("sys-hot-clear");
    if (hotClear) hotClear.addEventListener("click", clearHotFacts);
    const hotInput = document.getElementById("sys-hot-input");
    if (hotInput) {
      hotInput.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          addHotFact();
        }
      });
    }
    const warmAdd = document.getElementById("sys-warm-add");
    if (warmAdd) warmAdd.addEventListener("click", addWarmFact);
    const warmClear = document.getElementById("sys-warm-clear");
    if (warmClear) warmClear.addEventListener("click", clearWarmFacts);
    const warmInput = document.getElementById("sys-warm-input");
    if (warmInput) {
      warmInput.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          addWarmFact();
        }
      });
    }
    const packFile = document.getElementById("sys-pack-file");
    if (packFile) packFile.addEventListener("change", onSessionPackFile);

    updateBox3Toolbar();
    if (typeof bindBoxLayerControls === "function") bindBoxLayerControls();
    const btnClearChat = document.getElementById("btn-clear-chat");
    if (btnClearChat) btnClearChat.addEventListener("click", clearChatLog);
    els.btnSave.addEventListener("click", onSave);
    if (els.btnHelp) els.btnHelp.addEventListener("click", onHelp);
    if (els.btnSystem) els.btnSystem.addEventListener("click", openSystemModal);
    if (els.btnWorkspace) els.btnWorkspace.addEventListener("click", openWorkspaceModal);
    if (els.btnTools) els.btnTools.addEventListener("click", openToolsModal);
    const cuInspectBtn = document.getElementById("cu-inspect");
    const cuClickBtn = document.getElementById("cu-click");
    const cuTypeBtn = document.getElementById("cu-type-btn");
    const cuShellBtn = document.getElementById("cu-shell-btn");
    if (cuInspectBtn) cuInspectBtn.addEventListener("click", cuInspect);
    if (cuClickBtn) cuClickBtn.addEventListener("click", cuClick);
    if (cuTypeBtn) cuTypeBtn.addEventListener("click", cuType);
    if (cuShellBtn) cuShellBtn.addEventListener("click", cuShell);
    const toolsClose = document.getElementById("tools-close");
    if (toolsClose) toolsClose.addEventListener("click", closeToolsModal);
    if (els.toolsModal) {
      els.toolsModal.addEventListener("click", function (ev) {
        if (ev.target === els.toolsModal) closeToolsModal();
      });
    }
    const toolsRun = document.getElementById("tools-run");
    if (toolsRun) toolsRun.addEventListener("click", runSelectedTool);
    const toolsRefresh = document.getElementById("tools-refresh");
    if (toolsRefresh) toolsRefresh.addEventListener("click", refreshToolsModal);
    const toolsFetchBtn = document.getElementById("tools-fetch-btn");
    if (toolsFetchBtn) toolsFetchBtn.addEventListener("click", runQuickFetch);
    const toolsArgs = document.getElementById("tools-args");
    if (toolsArgs) {
      toolsArgs.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          runSelectedTool();
        }
      });
    }
    const toolsFetchUrl = document.getElementById("tools-fetch-url");
    if (toolsFetchUrl) {
      toolsFetchUrl.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          runQuickFetch();
        }
      });
    }
    if (els.flexSelect) els.flexSelect.addEventListener("change", onFlexSelectChange);
    const ckSave = document.getElementById("sys-ckpt-save");
    const ckLoad = document.getElementById("sys-ckpt-load");
    if (ckSave) ckSave.addEventListener("click", saveCheckpoint);
    if (ckLoad) ckLoad.addEventListener("click", loadCheckpoint);
    const sysBackup = document.getElementById("sys-backup");
    const sysClean = document.getElementById("sys-clean");
    if (sysBackup) sysBackup.addEventListener("click", runBackup);
    if (sysClean) sysClean.addEventListener("click", runCleanState);
    const tunePreset = document.getElementById("tune-preset-save");
    if (tunePreset) tunePreset.addEventListener("click", saveWorkerPresetFromTune);
    if (els.btnReset) els.btnReset.addEventListener("click", onReset);
    const wsClose = document.getElementById("workspace-close");
    const wsClear = document.getElementById("ws-clear-temp");
    if (wsClose) wsClose.addEventListener("click", closeWorkspaceModal);
    if (wsClear) wsClear.addEventListener("click", clearTempWs);
    const wsDlTemp = document.getElementById("ws-dl-temp");
    if (wsDlTemp) {
      wsDlTemp.addEventListener("click", function () {
        downloadWorkspaceZip("temp");
      });
    }
    const wsDlPerm = document.getElementById("ws-dl-perm");
    if (wsDlPerm) {
      wsDlPerm.addEventListener("click", function () {
        downloadWorkspaceZip("perm");
      });
    }
    const wsDlAll = document.getElementById("ws-dl-all");
    if (wsDlAll) {
      wsDlAll.addEventListener("click", function () {
        downloadWorkspaceZip("all");
      });
    }
    if (els.workspaceModal) {
      els.workspaceModal.addEventListener("click", function (ev) {
        if (ev.target === els.workspaceModal) closeWorkspaceModal();
      });
    }
    if (els.btnArchive) els.btnArchive.addEventListener("click", onArchive);
    const tuneClose = document.getElementById("tune-close");
    const tuneSave = document.getElementById("tune-save");
    if (tuneClose) tuneClose.addEventListener("click", closeTuneModal);
    if (tuneSave) tuneSave.addEventListener("click", saveTuneModal);
    if (els.tuneModal) {
      els.tuneModal.addEventListener("click", function (ev) {
        if (ev.target === els.tuneModal) closeTuneModal();
      });
    }
    const sysClose = document.getElementById("system-close");
    const sysSave = document.getElementById("system-save");
    if (sysClose) sysClose.addEventListener("click", closeSystemModal);
    if (sysSave) sysSave.addEventListener("click", saveSystemModal);
    if (els.systemModal) {
      els.systemModal.addEventListener("click", function (ev) {
        if (ev.target === els.systemModal) closeSystemModal();
      });
    }
    if (els.godBadge) {
      els.godBadge.addEventListener("click", toggleGodMode);
      els.godBadge.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          toggleGodMode();
        }
      });
    }
    if (els.coldBadge) {
      els.coldBadge.addEventListener("click", openColdBrowser);
      els.coldBadge.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          openColdBrowser();
        }
      });
    }
    if (els.vecBadge) {
      els.vecBadge.addEventListener("click", openVectorModal);
      els.vecBadge.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          openVectorModal();
        }
      });
    }
    if (els.costBadge) {
      els.costBadge.addEventListener("click", openUsageModal);
      els.costBadge.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          openUsageModal();
        }
      });
    }
    const usageClose = document.getElementById("usage-close");
    if (usageClose) usageClose.addEventListener("click", closeUsageModal);
    if (els.usageModal) {
      els.usageModal.addEventListener("click", function (ev) {
        if (ev.target === els.usageModal) closeUsageModal();
      });
    }
    const usageRefresh = document.getElementById("usage-refresh");
    if (usageRefresh) usageRefresh.addEventListener("click", refreshUsageModal);
    const usageReset = document.getElementById("usage-reset");
    if (usageReset) usageReset.addEventListener("click", resetUsageCounters);
    const vectorClose = document.getElementById("vector-close");
    if (vectorClose) vectorClose.addEventListener("click", closeVectorModal);
    if (els.vectorModal) {
      els.vectorModal.addEventListener("click", function (ev) {
        if (ev.target === els.vectorModal) closeVectorModal();
      });
    }
    const vectorSearchBtn = document.getElementById("vector-search-btn");
    if (vectorSearchBtn) vectorSearchBtn.addEventListener("click", searchVectors);
    const vectorRefresh = document.getElementById("vector-refresh");
    if (vectorRefresh) vectorRefresh.addEventListener("click", refreshVectorList);
    const vectorClear = document.getElementById("vector-clear");
    if (vectorClear) vectorClear.addEventListener("click", clearVectorStore);
    const vectorAddBtn = document.getElementById("vector-add-btn");
    if (vectorAddBtn) vectorAddBtn.addEventListener("click", addVectorDoc);
    const vectorQuery = document.getElementById("vector-query");
    if (vectorQuery) {
      vectorQuery.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          searchVectors();
        }
      });
    }
    const vectorAddInput = document.getElementById("vector-add-input");
    if (vectorAddInput) {
      vectorAddInput.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          addVectorDoc();
        }
      });
    }
    if (els.btnColdClose) {
      els.btnColdClose.addEventListener("click", function () {
        hideColdBrowser();
        showTooltip("box1");
      });
    }
    const btnColdRestore = document.getElementById("btn-cold-restore");
    if (btnColdRestore) {
      btnColdRestore.addEventListener("click", restoreSelectedCold);
    }
    const btnColdDelete = document.getElementById("btn-cold-delete");
    if (btnColdDelete) {
      btnColdDelete.addEventListener("click", deleteSelectedCold);
    }

    document.querySelectorAll(".btn-clarify").forEach(function (btn) {
      btn.addEventListener("click", function () {
        onClarify(btn.getAttribute("data-answer"));
      });
    });

    showTooltip("box1");
    bootstrap();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
