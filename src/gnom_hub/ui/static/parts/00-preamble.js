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
  /** Sequential TTS queue — one utterance fully finishes before the next (no cut-off). */
  let ttsQueue = [];
  let ttsPumping = false;
  let lastAgentThoughts = {}; // reasoning streams for TTS (not Box text)
  let lastNudgeKey = ""; // avoid re-spamming Flex corrections in chat
  let currentJobId = null;
  let lastWorkerOutputs = [];
  let jobTimerStart = null;
  let jobTimerInterval = null;
  let lastJobElapsedSec = 0;
  let lastReportedPipelineError = null;
  let lastCanExecute = false;
  /** Per-agent chat logs: { brainstorm: [...], worker1: [...], ... } */
  const CHAT_STORAGE_KEY = "gnom-hub-chat-logs-by-agent-v1";
  const CHAT_STORAGE_LEGACY = "gnom-hub-chat-log-v1";
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
        const shiftTune = !!ev.shiftKey;
        /* second click on same agent the user already picked → tune */
        const alreadyUserPick =
          document.body.dataset.agentUserPick === agent.id &&
          lastClickedAgentId === agent.id;
        clickTimer = setTimeout(function () {
          clickTimer = null;
          /* B1: click = layer + Box1 info only; tune only explicit */
          activateAgentLayer(agent.id, true);
          document.body.dataset.agentUserPick = agent.id;
          if (shiftTune || alreadyUserPick) {
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

