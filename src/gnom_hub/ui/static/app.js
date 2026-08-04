/**
 * Gnom-Hub v1 – desktop UI skeleton (static).
 * Hooks: window.GnomHub.onSend / onSave / onToggle / onClarify
 */
(function () {
  "use strict";

  /** @type {Window & { GnomHub?: Record<string, unknown> }} */
  const w = window;
  w.GnomHub = w.GnomHub || {};

  // Mirror of tooltips.py (en). Served static until /api/tooltips exists.
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
      how_to:
        "Slot reserved for later. v1 uses at most two workers. Double-click still toggles local state.",
      example:
        "Shows as off/parked until more workers are enabled in a later release.",
    },
    worker4: {
      title: "Worker 4 (parked)",
      how_to:
        "Slot reserved for later. v1 uses at most two workers. Double-click still toggles local state.",
      example:
        "Shows as off/parked until more workers are enabled in a later release.",
    },
    box1: {
      title: "Arounder (Box 1)",
      how_to:
        "Hover cards and controls to see title, how-to, and example here. Clarify Yes/No/Whatever/Later when asked.",
      example: "Hover Memory → this panel explains what Memory does.",
    },
    box2: {
      title: "Brainstorm (Box 2)",
      how_to:
        "Shows free thoughts and distilled summary from the Brainstorm agent.",
      example:
        "Ideas stream here while you chat; distillation may ask questions in Box 1.",
    },
    box3: {
      title: "Worker results (Box 3)",
      how_to: "Live output from active workers driven by the Coordinator.",
      example: "Drafts, research notes, and task results appear here.",
    },
    chat: {
      title: "Chat",
      how_to: "Type a message and press Send. Starts the brainstorm pipeline.",
      example: "Type: 'Help me plan a weekend trip' → Send.",
    },
    save: {
      title: "Save",
      how_to:
        "One global Save. Persists session / memory state (wired later via API).",
      example: "Click Save after a good brainstorm so work is not lost.",
    },
    clarify: {
      title: "Clarify",
      how_to:
        "Answer distillation questions with Yes, No, Whatever, or Later.",
      example: "Question: 'Use dark theme?' → Yes / No / Whatever / Later.",
    },
  };

  /** 8 slots – Worker3/4 parked for v1 */
  const AGENTS = [
    { id: "brainstorm", label: "Brainstorm", color: "brainstorm", enabled: true, toggleable: true, parked: false },
    { id: "memory", label: "Memory", color: "memory", enabled: true, toggleable: false, parked: false },
    { id: "flex", label: "Flex", color: "flex", enabled: true, toggleable: true, parked: false },
    { id: "coordinator", label: "Coordinator", color: "coordinator", enabled: true, toggleable: true, parked: false },
    { id: "worker1", label: "Worker 1", color: "worker1", enabled: true, toggleable: true, parked: false },
    { id: "worker2", label: "Worker 2", color: "worker2", enabled: true, toggleable: true, parked: false },
    { id: "worker3", label: "Worker 3", color: "worker3", enabled: false, toggleable: true, parked: true },
    { id: "worker4", label: "Worker 4", color: "worker4", enabled: false, toggleable: true, parked: true },
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
  };

  function statusLabel(agent) {
    if (agent.parked && !agent.enabled) return "off / parked";
    return agent.enabled ? "on" : "off";
  }

  function renderCards() {
    els.cards.innerHTML = "";
    AGENTS.forEach(function (agent) {
      const card = document.createElement("div");
      card.className = "agent-card color-" + agent.color;
      card.dataset.agentId = agent.id;
      card.dataset.enabled = agent.enabled ? "true" : "false";
      card.dataset.toggleable = agent.toggleable ? "true" : "false";
      card.dataset.parked = agent.parked ? "true" : "false";
      card.dataset.tooltipId = agent.id;
      card.setAttribute("role", "button");
      card.setAttribute(
        "aria-label",
        agent.label + (agent.toggleable ? " (double-click to toggle)" : " (always on)")
      );
      card.innerHTML =
        '<div class="card-name">' +
        agent.label +
        "</div>" +
        '<div class="card-meta">LLM: —</div>' +
        '<div class="card-status">' +
        statusLabel(agent) +
        "</div>";

      card.addEventListener("dblclick", function (ev) {
        ev.preventDefault();
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

  function toggleAgent(id) {
    const agent = findAgent(id);
    if (!agent || !agent.toggleable) return;
    agent.enabled = !agent.enabled;
    if (agent.enabled) agent.parked = false;

    const card = els.cards.querySelector('[data-agent-id="' + id + '"]');
    if (card) {
      card.dataset.enabled = agent.enabled ? "true" : "false";
      card.dataset.parked = agent.parked ? "true" : "false";
      const st = card.querySelector(".card-status");
      if (st) st.textContent = statusLabel(agent);
    }

    const payload = { id: agent.id, enabled: agent.enabled };
    const cb = w.GnomHub.onToggle;
    if (typeof cb === "function") {
      cb(payload);
    } else {
      console.log("[GnomHub] toggle", payload);
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

  /** Show Yes/No/Whatever/Later until answered. */
  function showClarify(question) {
    els.clarify.hidden = false;
    els.clarifyQ.textContent = question || "Please choose:";
    els.clarify.dataset.tooltipId = "clarify";
  }

  function hideClarify() {
    els.clarify.hidden = true;
    els.clarifyQ.textContent = "";
  }

  function sendChat() {
    const text = (els.chatInput.value || "").trim();
    if (!text) return;
    appendChat("you", text);
    els.chatInput.value = "";
    const cb = w.GnomHub.onSend;
    if (typeof cb === "function") {
      cb(text);
    } else {
      console.log("[GnomHub] send", text);
    }
  }

  function appendChat(who, text) {
    const line = document.createElement("p");
    line.className = "chat-line";
    line.textContent = who + ": " + text;
    els.chatLog.appendChild(line);
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
  }

  function onSave() {
    const cb = w.GnomHub.onSave;
    if (typeof cb === "function") {
      cb();
    } else {
      console.log("[GnomHub] save");
    }
  }

  // Public API for later pipeline / tests
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
  w.GnomHub.setBox2 = function (htmlOrText) {
    const body = document.getElementById("box2-content");
    if (body) body.textContent = htmlOrText;
  };
  w.GnomHub.setBox3 = function (htmlOrText) {
    const body = document.getElementById("box3-content");
    if (body) body.textContent = htmlOrText;
  };

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
        const cb = w.GnomHub.onClarify;
        if (typeof cb === "function") {
          cb(answer);
        } else {
          console.log("[GnomHub] clarify", answer);
        }
        hideClarify();
      });
    });

    // Default Box 1 hint
    showTooltip("box1");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
