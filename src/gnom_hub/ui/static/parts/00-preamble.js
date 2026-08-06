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
    chatLog: document.getElementById("chat-log"),
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

  /** Box-Modul: 1px Rahmen in Agentenfarbe (Klick). */
  function paintBoxesModule(agentId) {
    lastClickedAgentId = agentId || null;
    const hex =
      agentId && COLOR_HEX[agentId] ? COLOR_HEX[agentId] : null;
    const mod = document.querySelector(".boxes");
    if (mod) {
      mod.style.setProperty(
        "--boxes-mod-color",
        hex || "var(--border)"
      );
    }
    ["box1", "box2", "box3"].forEach(function (id) {
      const el = document.getElementById(id);
      if (!el) return;
      el.style.setProperty(
        "--box-agent-color",
        hex || "var(--border)"
      );
    });
  }

  function updateBoxBorders() {
    /* Klick-Agent hat Vorrang: ganzes Modul in Agentenfarbe 1px */
    if (lastClickedAgentId && COLOR_HEX[lastClickedAgentId]) {
      paintBoxesModule(lastClickedAgentId);
      return;
    }
    const map = {
      idle: { box1: null, box2: null, box3: null },
      memory: { box1: "memory", box2: null, box3: null },
      brainstorm: { box1: null, box2: "brainstorm", box3: null },
      distill: { box1: "coordinator", box2: "coordinator", box3: null },
      clarify: { box1: "coordinator", box2: null, box3: null },
      flex: { box1: null, box2: "flex", box3: null },
      coordinate: { box1: "coordinator", box2: null, box3: "coordinator" },
      work: { box1: null, box2: null, box3: "worker1" },
      worker1: { box1: null, box2: null, box3: "worker1" },
      worker2: { box1: null, box2: null, box3: "worker2" },
      worker3: { box1: null, box2: null, box3: "worker3" },
      worker4: { box1: null, box2: null, box3: "worker4" },
      done: { box1: null, box2: null, box3: null },
      error: { box1: null, box2: null, box3: null },
    };
    const m = map[activeStage] || map.idle;
    const mod = document.querySelector(".boxes");
    if (mod) {
      mod.style.setProperty("--boxes-mod-color", "var(--border)");
    }
    [
      ["box1", m.box1],
      ["box2", m.box2],
      ["box3", m.box3],
    ].forEach(function (pair) {
      const el = document.getElementById(pair[0]);
      if (!el) return;
      const aid = pair[1];
      el.style.setProperty(
        "--box-agent-color",
        aid && COLOR_HEX[aid] ? COLOR_HEX[aid] : "var(--border)"
      );
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
          paintBoxesModule(agent.id);
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

