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

  const TOOLTIPS = {
    brainstorm: {
      title: "Brainstorm",
      how_to:
        "Free idea agent. Double-click the card to enable or disable. Ideas land in Box 2.",
      example:
        "You chat about a logo → Brainstorm lists colors, styles, and slogans in Box 2.",
    },
    memory: {
      title: "Memory",
      how_to:
        "Always on. Keeps session facts and the Mermaid canvas. Cannot be toggled off.",
      example:
        "After a task, Memory stores key decisions so later chats stay consistent.",
    },
    flex: {
      title: "Flex",
      how_to:
        "Role-switch agent (Security, Neutral, Researcher, …). Double-click to toggle.",
      example:
        "Set Flex to Security → it reviews plans for risks before workers run.",
    },
    coordinator: {
      title: "Coordinator",
      how_to: "Plans work and drives 1–2 workers. Double-click to toggle.",
      example:
        "After distillation, Coordinator splits tasks and fills Box 3 via workers.",
    },
    worker1: {
      title: "Worker 1",
      how_to:
        "First execution slot. Double-click to toggle. Results show in Box 3.",
      example:
        "Coordinator assigns 'draft outline' → Worker 1 writes it into Box 3.",
    },
    worker2: {
      title: "Worker 2",
      how_to:
        "Second execution slot. Double-click to toggle. Results show in Box 3.",
      example: "Parallel research task runs on Worker 2 while Worker 1 drafts.",
    },
    worker3: {
      title: "Worker 3 (parked)",
      how_to: "Slot reserved for later. v1 uses at most two workers.",
      example: "Shows as off/parked until more workers are enabled later.",
    },
    worker4: {
      title: "Worker 4 (parked)",
      how_to: "Slot reserved for later. v1 uses at most two workers.",
      example: "Shows as off/parked until more workers are enabled later.",
    },
    box1: {
      title: "Arounder (Box 1)",
      how_to:
        "Hover cards and controls for help. Clarify Yes/No/Whatever/Later when asked.",
      example: "Hover Memory → this panel explains what Memory does.",
    },
    box2: {
      title: "Brainstorm (Box 2)",
      how_to: "Shows free thoughts from the Brainstorm agent.",
      example: "Ideas stream here while you chat.",
    },
    box3: {
      title: "Worker results (Box 3)",
      how_to: "Live output from active workers driven by the Coordinator.",
      example: "Drafts and task results appear here.",
    },
    chat: {
      title: "Chat",
      how_to: "Type a message and press Send. Starts the brainstorm pipeline.",
      example: "Type: 'Help me plan a weekend trip' → Send.",
    },
    save: {
      title: "Save",
      how_to: "One global Save. Persists HOT session + mermaid canvas.",
      example: "Click Save after a good brainstorm so work is not lost.",
    },
    clarify: {
      title: "Clarify",
      how_to: "Answer distillation questions with Yes, No, Whatever, or Later.",
      example: "Question: 'Use dark theme?' → Yes / No / Whatever / Later.",
    },
  };

  const FLEX_PRESETS = ["security", "neutral", "researcher"];

  /** 8 slots – Worker3/4 parked for v1 (local only until API has them) */
  const AGENTS = [
    { id: "brainstorm", label: "Brainstorm", color: "brainstorm", enabled: true, toggleable: true, parked: false, model: "—", preset: null, tokens: 0 },
    { id: "memory", label: "Memory", color: "memory", enabled: true, toggleable: false, parked: false, model: "—", preset: null, tokens: 0 },
    { id: "flex", label: "Flex", color: "flex", enabled: true, toggleable: true, parked: false, model: "—", preset: "security", tokens: 0 },
    { id: "coordinator", label: "Coordinator", color: "coordinator", enabled: true, toggleable: true, parked: false, model: "—", preset: null, tokens: 0 },
    { id: "worker1", label: "Worker 1", color: "worker1", enabled: true, toggleable: true, parked: false, model: "—", preset: null, tokens: 0 },
    { id: "worker2", label: "Worker 2", color: "worker2", enabled: true, toggleable: true, parked: false, model: "—", preset: null, tokens: 0 },
    { id: "worker3", label: "Worker 3", color: "worker3", enabled: false, toggleable: true, parked: true, model: "—", preset: null, tokens: 0 },
    { id: "worker4", label: "Worker 4", color: "worker4", enabled: false, toggleable: true, parked: true, model: "—", preset: null, tokens: 0 },
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
    btnSave: document.getElementById("btn-save"),
    stageBadge: document.getElementById("stage-badge"),
    llmBadge: document.getElementById("llm-badge"),
    memBadge: document.getElementById("mem-badge"),
  };

  let activeStage = "idle";

  function statusLabel(agent) {
    if (agent.parked && !agent.enabled) return "off / parked";
    return agent.enabled ? "on" : "off";
  }

  function renderCards() {
    els.cards.innerHTML = "";
    AGENTS.forEach(function (agent) {
      const card = document.createElement("div");
      const isActive =
        activeStage === agent.id ||
        (activeStage === "work" && (agent.id === "worker1" || agent.id === "worker2")) ||
        (activeStage === "coordinate" && agent.id === "coordinator") ||
        (activeStage === "distill" && agent.id === "coordinator");
      card.className =
        "agent-card color-" + agent.color + (isActive ? " is-active" : "");
      card.dataset.agentId = agent.id;
      card.dataset.enabled = agent.enabled ? "true" : "false";
      card.dataset.toggleable = agent.toggleable ? "true" : "false";
      card.dataset.parked = agent.parked ? "true" : "false";
      card.dataset.tooltipId = agent.id;
      card.setAttribute("role", "button");
      const tipExtra =
        agent.id === "flex"
          ? " Double-click toggle. Shift+double-click cycles preset."
          : agent.toggleable
            ? " (double-click to toggle)"
            : " (always on)";
      card.setAttribute("aria-label", agent.label + tipExtra);
      const presetLine =
        agent.id === "flex" && agent.preset
          ? '<div class="card-preset">preset: ' + agent.preset + "</div>"
          : "";
      const tok = agent.tokens || 0;
      card.innerHTML =
        '<div class="card-name">' +
        agent.label +
        "</div>" +
        '<div class="card-meta">LLM: ' +
        (agent.model || "—") +
        "</div>" +
        '<div class="card-tokens">tok: ' +
        tok +
        "</div>" +
        presetLine +
        '<div class="card-status">' +
        statusLabel(agent) +
        "</div>";

      card.addEventListener("dblclick", function (ev) {
        ev.preventDefault();
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
    return res.json();
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
      a.parked = false;
    });
    renderCards();
  }

  function applySnapshot(snap) {
    if (!snap) return;
    if (snap.agents) applyAgentsFromServer(snap.agents);
    const p = snap.pipeline || {};
    activeStage = p.stage || "idle";
    if (els.stageBadge) els.stageBadge.textContent = activeStage;
    renderCards();

    if (els.llmBadge && snap.llm) {
      const ok = !!snap.llm.deepseek;
      const tok =
        (snap.llm.prompt_tokens || 0) + (snap.llm.completion_tokens || 0);
      const spent =
        typeof snap.llm.spent_usd === "number"
          ? " · $" + snap.llm.spent_usd.toFixed(4)
          : "";
      els.llmBadge.textContent = ok
        ? "LLM: DeepSeek · " + tok + " tok" + spent
        : "LLM: stub (no key)";
      els.llmBadge.classList.toggle("has-key", ok);
      els.llmBadge.title =
        "prompt=" +
        (snap.llm.prompt_tokens || 0) +
        " completion=" +
        (snap.llm.completion_tokens || 0);
    }
    if (els.memBadge && snap.memory_summary) {
      const short = String(snap.memory_summary).replace(/^HOT:\s*/i, "");
      const nodes =
        snap.canvas && snap.canvas.nodes != null
          ? " · canvas " + snap.canvas.nodes
          : "";
      els.memBadge.textContent = "Mem: " + short + nodes;
      els.memBadge.title = snap.memory_summary;
    }

    if (snap.last_error) {
      toast(snap.last_error, "error");
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

    const box2 = [];
    if (p.brainstorm_notes) box2.push(p.brainstorm_notes);
    if (p.flex_notes) {
      box2.push("");
      box2.push("Flex review:");
      box2.push(p.flex_notes);
    }
    if (p.distilled_requirements && p.distilled_requirements.length) {
      box2.push("");
      box2.push("Requirements:");
      p.distilled_requirements.forEach(function (r) {
        box2.push("• " + r);
      });
    }
    if (box2.length) setBox2(box2.join("\n"));

    if (p.worker_results && p.worker_results.length) {
      setBox3(p.worker_results.join("\n"));
    } else if (p.stage === "done") {
      setBox3("(no worker output — coordinator or workers off)");
    }

    if (p.pending_question && p.pending_question.text) {
      showClarify(p.pending_question.text);
    } else if (p.stage !== "clarify") {
      hideClarify();
    }

    if (p.error) appendChat("system", "Error: " + p.error);
  }

  async function cycleFlexPreset() {
    const flex = findAgent("flex");
    if (!flex) return;
    const cur = flex.preset || "security";
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

  function showTooltip(id) {
    const tip = TOOLTIPS[id];
    if (!tip) return;
    if (els.placeholder) els.placeholder.hidden = true;
    els.tipRoot.hidden = false;
    els.tipTitle.textContent = tip.title;
    els.tipHow.textContent = tip.how_to;
    els.tipExample.textContent = tip.example;
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
    els.clarify.hidden = false;
    els.clarifyQ.textContent = question || "Please choose:";
    els.clarify.dataset.tooltipId = "clarify";
  }

  function hideClarify() {
    els.clarify.hidden = true;
    els.clarifyQ.textContent = "";
  }

  async function sendChat() {
    const text = (els.chatInput.value || "").trim();
    if (!text) return;
    appendChat("you", text);
    els.chatInput.value = "";
    const cb = w.GnomHub.onSend;
    if (typeof cb === "function") cb(text);

    try {
      const snap = await api("POST", "/api/chat", { text: text });
      applySnapshot(snap);
      if (snap.pipeline && snap.pipeline.stage === "done") {
        appendChat("system", "Pipeline done.");
        toast("Pipeline done", "ok");
      } else if (snap.pipeline && snap.pipeline.stage === "clarify") {
        appendChat("system", "Need a clarify answer in Box 1.");
        toast("Clarify needed in Box 1", "info");
      }
    } catch (err) {
      appendChat("system", "Chat failed: " + err.message);
    }
  }

  function appendChat(who, text) {
    const line = document.createElement("p");
    line.className = "chat-line";
    line.textContent = who + ": " + text;
    els.chatLog.appendChild(line);
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
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

  async function onClarify(answer) {
    const cb = w.GnomHub.onClarify;
    if (typeof cb === "function") cb(answer);
    try {
      const snap = await api("POST", "/api/clarify", { option: answer });
      applySnapshot(snap);
      appendChat("you", "[clarify] " + answer);
      if (snap.pipeline && snap.pipeline.stage === "done") {
        appendChat("system", "Pipeline done.");
      }
    } catch (err) {
      appendChat("system", "Clarify failed: " + err.message);
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

  function setBox2(htmlOrText) {
    const body = document.getElementById("box2-content");
    if (body) body.textContent = htmlOrText;
  }
  function setBox3(htmlOrText) {
    const body = document.getElementById("box3-content");
    if (body) body.textContent = htmlOrText;
  }

  async function bootstrap() {
    try {
      const snap = await api("GET", "/api/state");
      applySnapshot(snap);
      const defaultModel = (snap.llm && snap.llm.default_model) || "deepseek-chat";
      AGENTS.forEach(function (a) {
        if (!a.parked && (!a.model || a.model === "—")) a.model = defaultModel;
      });
      renderCards();
    } catch (err) {
      console.warn("[GnomHub] offline / no API yet:", err.message);
    }
  }

  function init() {
    renderCards();
    bindTooltipHovers();

    els.btnSend.addEventListener("click", sendChat);
    els.chatInput.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") {
        ev.preventDefault();
        sendChat();
      }
    });
    els.btnSave.addEventListener("click", onSave);

    document.querySelectorAll(".btn-clarify").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const answer = btn.getAttribute("data-answer");
        hideClarify();
        onClarify(answer);
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
