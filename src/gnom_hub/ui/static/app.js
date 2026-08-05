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
      how_to:
        "Dynamic panels for Worker 1 and Worker 2. HTML pages get a live Preview + Source. Toggle Preview/Source per worker.",
      example: "Landing-page HTML renders in a sandboxed preview; code stays readable under Source.",
    },
    chat: {
      title: "Chat",
      how_to: "Type a message and press Send. Starts the brainstorm pipeline.",
      example: "Type: 'Help me plan a weekend trip' → Send.",
    },
    save: {
      title: "Save",
      how_to: "One global Save. Persists HOT session + mermaid canvas + agent toggles.",
      example: "Click Save after a good brainstorm so work is not lost.",
    },
    help: {
      title: "Help",
      how_to: "Shows a short how-to in Box 1 (Arounder).",
      example: "Click Help when you forget the pipeline order.",
    },
    reset: {
      title: "Reset",
      how_to: "Clears HOT session, canvas, and pipeline state. Agent on/off stays.",
      example: "Reset before a new project so old facts do not leak in.",
    },
    clarify: {
      title: "Clarify",
      how_to: "Answer distillation questions with Yes, No, Whatever, or Later.",
      example: "Question: 'Use dark theme?' → Yes / No / Whatever / Later.",
    },
    system: {
      title: "System",
      how_to: "Keys, free-only mode, budget, default model. Global LLM settings.",
      example: "Turn free-only off, set max budget USD, check DeepSeek key.",
    },
    workspace: {
      title: "Workspace",
      how_to:
        "Temp holds agent outputs after Execute. Preview files, Promote to permanent, or Clear temp.",
      example: "Execute a landing page → worker1_done.html appears in Temp → Promote.",
    },
  };

  const FLEX_PRESETS = ["security", "neutral", "researcher"];

  const COLOR_HEX = {
    brainstorm: "#e03131",
    memory: "#1c7ed6",
    flex: "#f59f00",
    coordinator: "#2f9e44",
    worker1: "#fd7e14",
    worker2: "#9c36b5",
    worker3: "#0ca678",
    worker4: "#868e96",
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

  const DEFAULT_PROMPTS = {
    brainstorm: "You are the Brainstorm agent. Output 5–8 concrete bullet ideas for the USER TASK.",
    memory: "You are the Memory agent. Select or curate durable facts relevant to the task.",
    flex: "You are Flex. List 3–5 concrete risks/questions/trade-offs (by preset).",
    coordinator: "You are the Coordinator. Distill requirements and assign worker tasks.",
    worker1: "You are Worker 1. Deliver a concrete useful result for your assigned task.",
    worker2: "You are Worker 2. Deliver a concrete useful result for your assigned task.",
    worker3: "Reserved worker slot.",
    worker4: "Reserved worker slot.",
  };

  /** 8 slots – Worker3/4 UI-reserved (shown on; pipeline uses Worker 1+2) */
  const AGENTS = [
    { id: "brainstorm", label: "Brainstorm", color: "brainstorm", enabled: true, toggleable: true, parked: false, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
    { id: "memory", label: "Memory", color: "memory", enabled: true, toggleable: false, parked: false, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
    { id: "flex", label: "Flex", color: "flex", enabled: true, toggleable: true, parked: false, model: "—", preset: "security", tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
    { id: "coordinator", label: "Coordinator", color: "coordinator", enabled: true, toggleable: true, parked: false, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
    { id: "worker1", label: "Worker 1", color: "worker1", enabled: true, toggleable: true, parked: false, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
    { id: "worker2", label: "Worker 2", color: "worker2", enabled: true, toggleable: true, parked: false, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
    { id: "worker3", label: "Worker 3", color: "worker3", enabled: true, toggleable: false, parked: true, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
    { id: "worker4", label: "Worker 4", color: "worker4", enabled: true, toggleable: false, parked: true, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
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
    memBadge: document.getElementById("mem-badge"),
    vecBadge: document.getElementById("vec-badge"),
    godBadge: document.getElementById("god-badge"),
    coldBadge: document.getElementById("cold-badge"),
    btnArchive: document.getElementById("btn-archive"),
    coldBrowser: document.getElementById("cold-browser"),
    coldList: document.getElementById("cold-list"),
    coldDetail: document.getElementById("cold-detail"),
    btnColdClose: document.getElementById("btn-cold-close"),
    tuneModal: document.getElementById("tune-modal"),
    systemModal: document.getElementById("system-modal"),
    workspaceModal: document.getElementById("workspace-modal"),
    btnWorkspace: document.getElementById("btn-workspace"),
    flexSelect: document.getElementById("flex-preset-select"),
  };

  let activeStage = "idle";
  let tuneAgentId = null;
  let clickTimer = null;
  let recognition = null;
  let listening = false;
  let lastSpokenKey = "";

  function statusLabel(agent) {
    if (agent.parked) return agent.enabled ? "on · later" : "off / parked";
    return agent.enabled ? "on" : "off";
  }

  function agentIsActive(agent) {
    return (
      activeStage === agent.id ||
      (activeStage === "memory" && agent.id === "memory") ||
      (activeStage === "brainstorm" && agent.id === "brainstorm") ||
      (activeStage === "distill" && agent.id === "coordinator") ||
      (activeStage === "clarify" && agent.id === "coordinator") ||
      (activeStage === "flex" && agent.id === "flex") ||
      (activeStage === "coordinate" && agent.id === "coordinator") ||
      (activeStage === "work" &&
        (agent.id === "worker1" || agent.id === "worker2")) ||
      (activeStage === "worker1" && agent.id === "worker1") ||
      (activeStage === "worker2" && agent.id === "worker2") ||
      (activeStage === "done" && agent.id === "memory")
    );
  }

  function updateBoxBorders() {
    const map = {
      idle: { box1: null, box2: null, box3: null },
      memory: { box1: "memory", box2: null, box3: null },
      brainstorm: { box1: null, box2: "brainstorm", box3: null },
      distill: { box1: "coordinator", box2: "coordinator", box3: null },
      clarify: { box1: "coordinator", box2: null, box3: null },
      flex: { box1: null, box2: "flex", box3: null },
      coordinate: { box1: "coordinator", box2: null, box3: "coordinator" },
      work: { box1: null, box2: null, box3: "worker1" },
      done: { box1: "memory", box2: "brainstorm", box3: "worker2" },
      error: { box1: null, box2: null, box3: null },
    };
    const m = map[activeStage] || map.idle;
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
          setAgentTts(agent.id, !!ttsInput.checked);
        });
      }

      card.addEventListener("click", function (ev) {
        if (ev.target && ev.target.closest && ev.target.closest("[data-stop]")) {
          return;
        }
        if (agent.parked) return;
        if (clickTimer) clearTimeout(clickTimer);
        clickTimer = setTimeout(function () {
          clickTimer = null;
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
      if (!a.parked) a.parked = false;
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
    updateBoxBorders();
    if (els.flexSelect && snap.agents) {
      const flex = snap.agents.find(function (a) {
        return a.id === "flex";
      });
      if (flex && flex.preset) els.flexSelect.value = flex.preset;
    }

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
    if (els.vecBadge && snap.vectors) {
      els.vecBadge.textContent = "Vec: " + (snap.vectors.count || 0);
      const coldN = snap.cold && snap.cold.count != null ? snap.cold.count : "—";
      els.vecBadge.title = "Vector docs + COLD archives=" + coldN;
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

    const strip = document.getElementById("memory-strip");
    const stripBody = document.getElementById("memory-strip-body");
    if (strip && stripBody) {
      const mem = snap.memory || {};
      const facts = mem.facts || [];
      const warm = mem.warm_facts || [];
      const ctx = mem.context || p.memory_context || "";
      if (facts.length || warm.length || ctx) {
        strip.hidden = false;
        const lines = [];
        if (warm.length) {
          lines.push("WARM (durable):");
          warm.slice(-4).forEach(function (f) {
            lines.push("• " + f);
          });
        }
        if (facts.length) {
          lines.push("HOT (session):");
          facts.slice(-4).forEach(function (f) {
            lines.push("• " + f);
          });
        }
        if (!facts.length && !warm.length && ctx) {
          lines.push(ctx);
        }
        stripBody.textContent = lines.join("\n");
      } else {
        strip.hidden = true;
        stripBody.textContent = "";
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

    const box2 = [];
    if (p.brainstorm_turns && p.brainstorm_turns.length) {
      box2.push("=== Brainstorm dialogue ===");
      p.brainstorm_turns.forEach(function (t) {
        const role = t.role === "user" ? "You" : "Brainstorm";
        box2.push("");
        box2.push(role + ":");
        box2.push(String(t.text || ""));
      });
    } else if (p.brainstorm_notes) {
      box2.push("=== Brainstorm ===");
      box2.push(p.brainstorm_notes);
    }
    if (p.flex_notes) {
      box2.push("");
      box2.push("=== Flex review ===");
      box2.push(p.flex_notes);
    }
    if (p.distilled_requirements && p.distilled_requirements.length) {
      box2.push("");
      box2.push("=== Requirements ===");
      p.distilled_requirements.forEach(function (r) {
        box2.push("• " + r);
      });
    }
    if (box2.length) {
      setBox2(box2.join("\n"));
    } else if (p.stage === "idle") {
      setBox2(
        "Brainstorm dialogue appears here.\n\n" +
          "1) Send messages to brainstorm freely\n" +
          "2) Press Execute when ready for workers"
      );
    }

    if (els.btnExecute) {
      els.btnExecute.disabled = !p.can_execute || chatBusy;
    }

    renderBox3Workers(p);

    if (p.pending_question && p.pending_question.text) {
      showClarify(p.pending_question.text);
    } else if (p.stage !== "clarify") {
      hideClarify();
    }

    if (p.error) appendChat("system", "Error: " + p.error);

    if (p.stage === "done") {
      maybeSpeakPipeline(p);
    }
  }

  function speakText(text) {
    if (!text || !window.speechSynthesis) return;
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(String(text).slice(0, 600));
      u.lang = /[äöüÄÖÜß]/.test(text) ? "de-DE" : "en-US";
      window.speechSynthesis.speak(u);
    } catch (_e) {
      /* ignore */
    }
  }

  function maybeSpeakPipeline(p) {
    const key =
      (p.brainstorm_notes || "").slice(0, 40) +
      "|" +
      ((p.worker_results && p.worker_results[0]) || "").slice(0, 40);
    if (key === lastSpokenKey) return;
    const chunks = [];
    const b = findAgent("brainstorm");
    if (b && b.tts && p.brainstorm_notes) {
      chunks.push("Brainstorm: " + p.brainstorm_notes);
    }
    const f = findAgent("flex");
    if (f && f.tts && p.flex_notes) {
      chunks.push("Flex: " + p.flex_notes);
    }
    (p.worker_outputs || []).forEach(function (o, i) {
      const a = findAgent(o.worker || "worker" + (i + 1));
      if (a && a.tts && o.result) {
        chunks.push((a.label || o.worker) + ": " + o.result);
      }
    });
    if (!chunks.length && p.worker_results) {
      p.worker_results.forEach(function (r, i) {
        const a = findAgent("worker" + (i + 1));
        if (a && a.tts && r) chunks.push(a.label + ": " + r);
      });
    }
    if (chunks.length) {
      lastSpokenKey = key;
      speakText(chunks.join(". "));
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
      renderCards();
    } catch (err) {
      appendChat("system", "TTS save failed: " + err.message);
    }
  }

  function openTuneModal(id) {
    const a = findAgent(id);
    if (!a || a.parked || !els.tuneModal) return;
    tuneAgentId = id;
    document.getElementById("tune-title").textContent = a.label + " — tuning";
    document.getElementById("tune-prompt").value =
      a.system_prompt || DEFAULT_PROMPTS[id] || "";
    document.getElementById("tune-model").value = a.model || "deepseek-chat";
    document.getElementById("tune-key").value = "";
    const setRange = function (idEl, valEl, v, def, digits) {
      const el = document.getElementById(idEl);
      const num = v != null ? Number(v) : def;
      el.value = String(num);
      document.getElementById(valEl).textContent =
        digits === 0 ? String(Math.round(num)) : Number(num).toFixed(digits);
    };
    setRange("tune-temp", "tune-temp-val", a.temperature, 0.5, 2);
    setRange("tune-topp", "tune-topp-val", a.top_p, 1, 2);
    setRange("tune-maxtok", "tune-maxtok-val", a.max_tokens, 800, 0);
    setRange("tune-freq", "tune-freq-val", a.frequency_penalty, 0, 2);
    setRange("tune-pres", "tune-pres-val", a.presence_penalty, 0, 2);
    document.getElementById("tune-tts").checked = !!a.tts;
    els.tuneModal.hidden = false;
    showSliderTip("temperature");
  }

  function closeTuneModal() {
    if (els.tuneModal) els.tuneModal.hidden = true;
    tuneAgentId = null;
  }

  function showSliderTip(key) {
    const tip = SLIDER_TIPS[key];
    if (!tip) return;
    if (els.placeholder) els.placeholder.hidden = true;
    if (els.tipRoot) els.tipRoot.hidden = false;
    if (els.tipTitle) els.tipTitle.textContent = "Slider: " + key;
    if (els.tipHow) els.tipHow.textContent = tip;
    if (els.tipExample) els.tipExample.textContent = "Change the slider — live explanation stays in Box 1.";
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
        document.getElementById(p[1]).textContent =
          p[2] === 0 ? String(Math.round(n)) : n.toFixed(p[2]);
        showSliderTip(p[3]);
      });
    });
  }

  async function saveTuneModal() {
    if (!tuneAgentId) return;
    const body = {
      system_prompt: document.getElementById("tune-prompt").value,
      model: document.getElementById("tune-model").value,
      temperature: Number(document.getElementById("tune-temp").value),
      top_p: Number(document.getElementById("tune-topp").value),
      max_tokens: Number(document.getElementById("tune-maxtok").value),
      frequency_penalty: Number(document.getElementById("tune-freq").value),
      presence_penalty: Number(document.getElementById("tune-pres").value),
      tts: !!document.getElementById("tune-tts").checked,
    };
    const key = document.getElementById("tune-key").value.trim();
    if (key) body.api_key = key;
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
      document.getElementById("system-llm").textContent = s.deepseek
        ? "DeepSeek: connected"
        : "DeepSeek: no key (stub mode)";
      document.getElementById("sys-free-only").checked = !!s.free_only;
      document.getElementById("sys-budget").value =
        s.max_budget_usd != null ? s.max_budget_usd : "";
      document.getElementById("sys-model").value = s.default_model || "deepseek-chat";
      document.getElementById("system-spend").textContent =
        "Spent: $" +
        (Number(s.spent_usd) || 0).toFixed(4) +
        " · tokens " +
        ((s.prompt_tokens || 0) + (s.completion_tokens || 0));
    } catch (err) {
      toast("System load failed: " + err.message, "error");
    }
    els.systemModal.hidden = false;
  }

  function closeSystemModal() {
    if (els.systemModal) els.systemModal.hidden = true;
  }

  async function saveSystemModal() {
    const budgetRaw = document.getElementById("sys-budget").value.trim();
    const body = {
      free_only: !!document.getElementById("sys-free-only").checked,
      default_model: document.getElementById("sys-model").value.trim() || "deepseek-chat",
      max_budget_usd: budgetRaw === "" ? null : Number(budgetRaw),
    };
    try {
      await api("POST", "/api/system", body);
      closeSystemModal();
      toast("System settings applied", "ok");
      const snap = await api("GET", "/api/state");
      applySnapshot(snap);
    } catch (err) {
      toast("System save failed: " + err.message, "error");
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

  let chatBusy = false;

  function setChatBusy(busy) {
    chatBusy = !!busy;
    if (els.btnSend) {
      els.btnSend.disabled = chatBusy;
      els.btnSend.textContent = chatBusy ? "…" : "Send";
    }
    if (els.btnExecute) {
      // re-evaluated in applySnapshot; only hard-disable while busy
      if (chatBusy) els.btnExecute.disabled = true;
    }
    if (els.btnMic) els.btnMic.disabled = chatBusy;
    if (els.chatInput) els.chatInput.disabled = chatBusy;
    if (els.stageBadge && chatBusy) els.stageBadge.textContent = "running…";
  }

  async function pollJob(jobId, maxMs) {
    const deadline = Date.now() + (maxMs || 120000);
    let lastStage = "";
    while (Date.now() < deadline) {
      const job = await api("GET", "/api/jobs/" + encodeURIComponent(jobId));
      const stage = job.stage || (job.snapshot && job.snapshot.pipeline && job.snapshot.pipeline.stage) || "";
      if (stage && stage !== lastStage) {
        lastStage = stage;
        if (els.stageBadge) els.stageBadge.textContent = stage;
        appendChat("system", "Stage: " + stage);
      }
      if (job.snapshot) applySnapshot(job.snapshot);
      const st = job.status;
      if (st === "done" || st === "error" || st === "clarify") {
        return job;
      }
      await new Promise(function (r) {
        setTimeout(r, 450);
      });
    }
    throw new Error("Pipeline timeout");
  }

  async function sendChat() {
    const text = (els.chatInput.value || "").trim();
    if (!text || chatBusy) return;
    appendChat("you", text);
    els.chatInput.value = "";
    const cb = w.GnomHub.onSend;
    if (typeof cb === "function") cb(text);

    setChatBusy(true);
    const live =
      els.llmBadge && els.llmBadge.classList.contains("has-key");
    appendChat(
      "system",
      live
        ? "Brainstorm turn (Live LLM)…"
        : "Brainstorm turn (stub)…"
    );
    toast(live ? "Brainstorming…" : "Brainstorming…", "info");

    try {
      const start = await api("POST", "/api/chat", { text: text });
      let snap = start;
      if (start.job_id) {
        const job = await pollJob(start.job_id, live ? 180000 : 30000);
        snap = job.snapshot || (await api("GET", "/api/state"));
        if (job.status === "error") {
          appendChat("system", "Brainstorm error: " + (job.error || "?"));
          toast(job.error || "Brainstorm error", "error");
          return;
        }
      }
      applySnapshot(snap);
      const stage =
        (snap.pipeline && snap.pipeline.stage) || start.stage || "";
      if (stage === "brainstorm") {
        appendChat(
          "system",
          "Brainstorm ready — keep chatting, or press Execute for workers."
        );
        toast("Brainstorm ready · Execute when ready", "ok");
      } else if (stage === "done") {
        appendChat("system", "Pipeline done.");
        toast("Pipeline done", "ok");
      } else if (stage === "clarify") {
        appendChat("system", "Need a clarify answer in Box 1.");
        toast("Clarify needed in Box 1", "info");
      }
    } catch (err) {
      appendChat("system", "Chat failed: " + err.message);
      toast("Chat failed: " + err.message, "error");
    } finally {
      setChatBusy(false);
    }
  }

  async function runExecute() {
    if (chatBusy) return;
    if (els.btnExecute && els.btnExecute.disabled) {
      toast("Brainstorm first, then Execute", "info");
      return;
    }
    setChatBusy(true);
    const live =
      els.llmBadge && els.llmBadge.classList.contains("has-key");
    appendChat(
      "system",
      live
        ? "Execute started (distill → flex → workers)…"
        : "Execute started (stub)…"
    );
    toast("Executing…", "info");
    try {
      const start = await api("POST", "/api/execute");
      let snap = start;
      if (start.job_id) {
        const job = await pollJob(start.job_id, live ? 180000 : 30000);
        snap = job.snapshot || (await api("GET", "/api/state"));
        if (job.status === "error") {
          appendChat("system", "Execute error: " + (job.error || "?"));
          toast(job.error || "Execute error", "error");
          return;
        }
      }
      applySnapshot(snap);
      const stage = (snap.pipeline && snap.pipeline.stage) || "";
      if (stage === "done") {
        appendChat("system", "Execute done — see Box 3.");
        toast("Execute done", "ok");
      } else if (stage === "clarify") {
        appendChat("system", "Clarify needed in Box 1 before workers finish.");
        toast("Clarify needed", "info");
      }
    } catch (err) {
      appendChat("system", "Execute failed: " + err.message);
      toast("Execute failed: " + err.message, "error");
    } finally {
      setChatBusy(false);
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

  async function onHelp() {
    try {
      const h = await api("GET", "/api/help");
      showTooltip("help");
      if (els.placeholder) els.placeholder.hidden = true;
      els.tipRoot.hidden = false;
      els.tipTitle.textContent = h.title || "Help";
      els.tipHow.textContent = h.how_to || "";
      els.tipExample.textContent =
        (h.pipeline ? h.pipeline + "\n\n" : "") + (h.example || "");
    } catch (err) {
      showTooltip("help");
      toast("Help offline: " + err.message, "error");
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
      const strip = document.getElementById("memory-strip");
      if (strip) strip.hidden = true;
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

  async function onClarify(answer) {
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
      }
      applySnapshot(snap);
      if (snap.pipeline && snap.pipeline.stage === "done") {
        appendChat("system", "Pipeline done.");
        toast("Pipeline done", "ok");
      }
    } catch (err) {
      appendChat("system", "Clarify failed: " + err.message);
      toast("Clarify failed: " + err.message, "error");
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

  function setBox2(htmlOrText) {
    const body = document.getElementById("box2-content");
    if (!body) return;
    body.innerHTML = "";
    const pre = document.createElement("pre");
    pre.className = "result-block";
    pre.textContent = htmlOrText || "";
    body.appendChild(pre);
  }

  /** Extract fenced ```html … ``` or raw HTML document from worker text. */
  function extractHtml(raw) {
    const s = String(raw || "");
    const fence = s.match(/```(?:html|HTML)?\s*([\s\S]*?)```/);
    if (fence && fence[1] && /<\w+/i.test(fence[1])) {
      return fence[1].trim();
    }
    const doctype = s.match(/(<!DOCTYPE\s+html[\s\S]*)$/i);
    if (doctype) return doctype[1].trim();
    const htmlTag = s.match(/(<html[\s\S]*<\/html>)/i);
    if (htmlTag) return htmlTag[1].trim();
    // fragment with enough tags
    if (/<\w+[\s>][\s\S]*<\/\w+>/i.test(s) && (s.match(/<\w+/g) || []).length >= 2) {
      const trimmed = s.trim();
      if (trimmed.startsWith("<")) return trimmed;
    }
    return null;
  }

  /**
   * Box 3: dynamic Worker 1 / Worker 2 panels.
   * HTML → sandboxed Preview + Source; plain text → readable pre.
   */
  function renderBox3Workers(pipeline) {
    const body = document.getElementById("box3-content");
    if (!body) return;
    const canvas = body.querySelector(".canvas-preview");
    body.innerHTML = "";
    body.classList.add("box3-dynamic");

    const outputs = normalizeWorkerOutputs(pipeline);
    if (!outputs.length) {
      const empty = document.createElement("p");
      empty.className = "muted empty-hint";
      if (pipeline && pipeline.stage === "done") {
        empty.textContent =
          "(no worker output — enable Coordinator + Worker 1/2, then Send)";
      } else if (pipeline && pipeline.stage === "work") {
        empty.textContent = "Workers running…";
      } else {
        empty.textContent =
          "Worker 1 & 2 results appear here (text, plans, full HTML preview).";
      }
      body.appendChild(empty);
      if (canvas) body.appendChild(canvas);
      return;
    }

    outputs.forEach(function (out, idx) {
      body.appendChild(buildWorkerPanel(out, idx));
    });
    if (canvas) body.appendChild(canvas);
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

  function buildWorkerPanel(out, idx) {
    const panel = document.createElement("div");
    panel.className = "worker-panel worker-panel-" + (out.worker || idx);
    panel.dataset.worker = out.worker || "";

    const head = document.createElement("div");
    head.className = "worker-panel-head";
    const title = document.createElement("span");
    title.className = "worker-panel-title";
    title.textContent = out.name || "Worker " + (idx + 1);
    head.appendChild(title);

    const raw = out.result || "";
    const html = extractHtml(raw);
    const isHtml = !!html;

    const mode = document.createElement("div");
    mode.className = "worker-panel-modes";
    if (isHtml) {
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
      mode.appendChild(btnPrev);
      mode.appendChild(btnSrc);
      head.appendChild(mode);
    }
    panel.appendChild(head);

    if (out.task) {
      const taskEl = document.createElement("div");
      taskEl.className = "worker-panel-task";
      taskEl.textContent = "Task: " + String(out.task).split("\n")[0].slice(0, 160);
      panel.appendChild(taskEl);
    }

    const content = document.createElement("div");
    content.className = "worker-panel-body";

    const sourcePre = document.createElement("pre");
    sourcePre.className = "result-block worker-source";
    sourcePre.textContent = raw;

    if (isHtml) {
      const frame = document.createElement("iframe");
      frame.className = "worker-preview-frame";
      frame.setAttribute(
        "sandbox",
        "allow-same-origin allow-forms allow-popups allow-modals"
      );
      frame.setAttribute("title", (out.name || "Worker") + " preview");
      // Prefer full document; wrap fragments
      let doc = html;
      if (!/<!DOCTYPE/i.test(doc) && !/<html/i.test(doc)) {
        doc =
          "<!DOCTYPE html><html><head><meta charset=\"utf-8\">" +
          "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">" +
          "<style>body{font-family:system-ui,sans-serif;margin:12px;}</style>" +
          "</head><body>" +
          doc +
          "</body></html>";
      }
      frame.srcdoc = doc;
      content.appendChild(frame);
      sourcePre.hidden = true;
      content.appendChild(sourcePre);

      mode.querySelectorAll(".worker-mode-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
          mode.querySelectorAll(".worker-mode-btn").forEach(function (b) {
            b.classList.remove("is-active");
          });
          btn.classList.add("is-active");
          const m = btn.dataset.mode;
          if (m === "preview") {
            frame.hidden = false;
            sourcePre.hidden = true;
          } else {
            frame.hidden = true;
            sourcePre.hidden = false;
          }
        });
      });
    } else {
      content.appendChild(sourcePre);
    }
    panel.appendChild(content);
    return panel;
  }

  function setBox3(htmlOrText) {
    // Legacy plain-text path (tests / external hooks)
    renderBox3Workers({
      stage: "done",
      worker_results: htmlOrText ? [String(htmlOrText)] : [],
    });
  }

  async function bootstrap() {
    try {
      // Ensure all pipeline agents are ON (Worker 1+2 included)
      try {
        const allOn = await api("POST", "/api/agents/enable-all");
        if (allOn.agents) applyAgentsFromServer(allOn.agents);
      } catch (_e) {
        /* older server without endpoint */
      }
      const snap = await api("GET", "/api/state");
      applySnapshot(snap);
      // Force UI cards on for active slots
      AGENTS.forEach(function (a) {
        if (a.id === "worker3" || a.id === "worker4") {
          a.enabled = true;
        } else {
          a.enabled = true;
        }
      });
      const defaultModel = (snap.llm && snap.llm.default_model) || "deepseek-chat";
      AGENTS.forEach(function (a) {
        if (!a.model || a.model === "—") a.model = defaultModel;
      });
      renderCards();
    } catch (err) {
      console.warn("[GnomHub] offline / no API yet:", err.message);
    }
  }

  function init() {
    renderCards();
    bindTooltipHovers();
    bindTuneSliders();

    els.btnSend.addEventListener("click", sendChat);
    if (els.btnExecute) els.btnExecute.addEventListener("click", runExecute);
    if (els.btnMic) els.btnMic.addEventListener("click", toggleMic);
    els.chatInput.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") {
        ev.preventDefault();
        sendChat();
      }
    });
    els.btnSave.addEventListener("click", onSave);
    if (els.btnHelp) els.btnHelp.addEventListener("click", onHelp);
    if (els.btnSystem) els.btnSystem.addEventListener("click", openSystemModal);
    if (els.btnWorkspace) els.btnWorkspace.addEventListener("click", openWorkspaceModal);
    if (els.flexSelect) els.flexSelect.addEventListener("change", onFlexSelectChange);
    if (els.btnReset) els.btnReset.addEventListener("click", onReset);
    const wsClose = document.getElementById("workspace-close");
    const wsClear = document.getElementById("ws-clear-temp");
    if (wsClose) wsClose.addEventListener("click", closeWorkspaceModal);
    if (wsClear) wsClear.addEventListener("click", clearTempWs);
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
    if (els.btnColdClose) {
      els.btnColdClose.addEventListener("click", function () {
        hideColdBrowser();
        showTooltip("box1");
      });
    }

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
