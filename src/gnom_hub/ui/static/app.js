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
    { id: "worker3", label: "Worker 3", color: "worker3", enabled: false, toggleable: true, parked: false, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
    { id: "worker4", label: "Worker 4", color: "worker4", enabled: false, toggleable: true, parked: false, model: "—", preset: null, tokens: 0, online: false, tts: false, system_prompt: "", temperature: null, top_p: null, max_tokens: null, frequency_penalty: null, presence_penalty: null },
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
    btnTrace: document.getElementById("btn-trace"),
    flexSelect: document.getElementById("flex-preset-select"),
    traceModal: document.getElementById("trace-modal"),
  };

  let activeStage = "idle";
  let tuneAgentId = null;
  let clickTimer = null;
  let recognition = null;
  let listening = false;
  let lastSpokenKey = "";
  let currentJobId = null;
  const CHAT_STORAGE_KEY = "gnom-hub-chat-log-v1";

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
      (activeStage === "work" && agent.id.indexOf("worker") === 0) ||
      (activeStage === "worker1" && agent.id === "worker1") ||
      (activeStage === "worker2" && agent.id === "worker2") ||
      (activeStage === "worker3" && agent.id === "worker3") ||
      (activeStage === "worker4" && agent.id === "worker4") ||
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
      const spent =
        typeof snap.llm.spent_usd === "number"
          ? " · $" + snap.llm.spent_usd.toFixed(4)
          : "";
      let label = "LLM: stub";
      if (ds && ol) label = "LLM: DeepSeek+Ollama";
      else if (ds) label = "LLM: DeepSeek";
      else if (ol) label = "LLM: Ollama";
      els.llmBadge.textContent = ok ? label + " · " + tok + " tok" + spent : label;
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

    // Quality strip under box 3
    const box3 = document.getElementById("box3-content");
    if (box3) {
      let qel = box3.querySelector(".quality-strip");
      if (p.quality_notes) {
        if (!qel) {
          qel = document.createElement("div");
          qel.className = "quality-strip";
          box3.appendChild(qel);
        }
        qel.textContent = p.quality_notes;
        qel.hidden = false;
      } else if (qel) {
        qel.hidden = true;
      }
    }

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
    if (!a || !els.tuneModal) return;
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
              const nameSpan = document.createElement("span");
              nameSpan.className = "ws-name";
              nameSpan.textContent =
                (b.name || "") +
                " · " +
                (b.bytes != null ? Math.round(b.bytes / 1024) + " KB" : "");
              nameSpan.title = "Click to download";
              nameSpan.addEventListener("click", function () {
                window.location.href =
                  "/api/backups/" + encodeURIComponent(b.name) + "/download";
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

  function closeSystemModal() {
    if (els.systemModal) els.systemModal.hidden = true;
  }

  async function saveSystemModal() {
    const budgetRaw = document.getElementById("sys-budget").value.trim();
    const langEl = document.getElementById("sys-lang");
    const body = {
      free_only: !!document.getElementById("sys-free-only").checked,
      default_model: document.getElementById("sys-model").value.trim() || "deepseek-chat",
      max_budget_usd: budgetRaw === "" ? null : Number(budgetRaw),
      ui_lang: langEl ? langEl.value : "en",
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

  async function openTraceModal() {
    if (!els.traceModal) return;
    const body = document.getElementById("trace-body");
    try {
      const data = await api("GET", "/api/trace?limit=60");
      const lines = (data.trace || []).map(function (e) {
        const d = e.data;
        let extra = "";
        if (d && typeof d === "object") {
          if (d.stage) extra = " stage=" + d.stage;
          else if (d.worker) extra = " " + d.worker;
          else if (d.notes) extra = " " + String(d.notes).slice(0, 80);
          else if (d.error) extra = " " + d.error;
        }
        return (e.ts || "") + "  " + (e.event || "") + extra;
      });
      if (body) {
        body.textContent = lines.length
          ? lines.join("\n")
          : "No events yet. Run Brainstorm / Execute.";
      }
    } catch (err) {
      if (body) body.textContent = "Trace failed: " + err.message;
    }
    els.traceModal.hidden = false;
  }

  function closeTraceModal() {
    if (els.traceModal) els.traceModal.hidden = true;
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

  async function exportLast() {
    try {
      const data = await api("GET", "/api/export/last");
      const blob = new Blob([data.content || ""], {
        type: "text/markdown;charset=utf-8",
      });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = data.filename || "gnom-hub-export.md";
      document.body.appendChild(a);
      a.click();
      setTimeout(function () {
        URL.revokeObjectURL(a.href);
        a.remove();
      }, 500);
      toast("Exported " + (data.chars || 0) + " chars", "ok");
    } catch (err) {
      toast("Export failed: " + err.message, "error");
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
    const btnSendExec = document.getElementById("btn-send-exec");
    if (btnSendExec) btnSendExec.disabled = chatBusy;
    const btnCancel = document.getElementById("btn-cancel");
    if (btnCancel) {
      btnCancel.hidden = !chatBusy;
      btnCancel.disabled = !chatBusy;
    }
    if (els.btnMic) els.btnMic.disabled = chatBusy;
    if (els.chatInput) els.chatInput.disabled = chatBusy;
    if (els.stageBadge && chatBusy) els.stageBadge.textContent = "running…";
  }

  function persistChatLog() {
    if (!els.chatLog) return;
    try {
      const lines = [];
      els.chatLog.querySelectorAll(".chat-line").forEach(function (el) {
        lines.push(el.textContent || "");
      });
      sessionStorage.setItem(
        CHAT_STORAGE_KEY,
        JSON.stringify(lines.slice(-80))
      );
    } catch (_e) {
      /* quota / private mode */
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
      lines.forEach(function (t) {
        const line = document.createElement("p");
        line.className = "chat-line";
        line.textContent = t;
        els.chatLog.appendChild(line);
      });
      els.chatLog.scrollTop = els.chatLog.scrollHeight;
    } catch (_e) {
      /* ignore */
    }
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

  async function pollJob(jobId, maxMs) {
    currentJobId = jobId;
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
      if (st === "done" || st === "error" || st === "clarify" || st === "cancelled") {
        currentJobId = null;
        return job;
      }
      await new Promise(function (r) {
        setTimeout(r, 450);
      });
    }
    currentJobId = null;
    throw new Error("Pipeline timeout");
  }

  async function cancelCurrentJob() {
    if (!currentJobId) {
      toast("No running job", "info");
      return;
    }
    try {
      await api("POST", "/api/jobs/" + encodeURIComponent(currentJobId) + "/cancel");
      toast("Cancel requested", "info");
      appendChat("system", "Cancel requested for job " + currentJobId);
    } catch (err) {
      toast("Cancel failed: " + err.message, "error");
    }
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
      if (start.job_id && snap && snap.pipeline && snap.pipeline.stage === "cancelled") {
        appendChat("system", "Job cancelled.");
        toast("Cancelled", "info");
      } else if (stage === "brainstorm") {
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
        try {
          await api("POST", "/api/save");
          appendChat("system", "Auto-saved HOT + agents.");
        } catch (_e) {
          /* non-fatal */
        }
      } else if (stage === "clarify") {
        appendChat("system", "Clarify needed in Box 1 before workers finish.");
        toast("Clarify needed", "info");
      } else if (stage === "cancelled") {
        appendChat("system", "Execute cancelled.");
        toast("Cancelled", "info");
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
    const line = document.createElement("p");
    line.className = "chat-line";
    line.textContent = who + ": " + text;
    els.chatLog.appendChild(line);
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
        "Keyboard: Enter send · Ctrl/⌘+Enter execute · Esc cancel";
      toast("Help offline: " + err.message, "error");
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
    }
    const btnCopy = document.createElement("button");
    btnCopy.type = "button";
    btnCopy.className = "worker-mode-btn copy-btn";
    btnCopy.textContent = "Copy";
    btnCopy.title = "Copy result to clipboard";
    btnCopy.addEventListener("click", function (ev) {
      ev.stopPropagation();
      const text = raw || "";
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(
          function () {
            toast("Copied " + text.length + " chars", "ok");
          },
          function () {
            toast("Copy failed", "error");
          }
        );
      } else {
        toast("Clipboard not available", "error");
      }
    });
    mode.appendChild(btnCopy);
    head.appendChild(mode);
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

  function init() {
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
    els.chatInput.addEventListener("keydown", function (ev) {
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
      if (ev.key === "Escape" && chatBusy) {
        ev.preventDefault();
        cancelCurrentJob();
      }
    });
    const btnClearChat = document.getElementById("btn-clear-chat");
    if (btnClearChat) btnClearChat.addEventListener("click", clearChatLog);
    els.btnSave.addEventListener("click", onSave);
    if (els.btnHelp) els.btnHelp.addEventListener("click", onHelp);
    if (els.btnSystem) els.btnSystem.addEventListener("click", openSystemModal);
    if (els.btnWorkspace) els.btnWorkspace.addEventListener("click", openWorkspaceModal);
    if (els.btnTrace) els.btnTrace.addEventListener("click", openTraceModal);
    const btnExport = document.getElementById("btn-export");
    if (btnExport) btnExport.addEventListener("click", exportLast);
    if (els.flexSelect) els.flexSelect.addEventListener("change", onFlexSelectChange);
    const trClose = document.getElementById("trace-close");
    if (trClose) trClose.addEventListener("click", closeTraceModal);
    if (els.traceModal) {
      els.traceModal.addEventListener("click", function (ev) {
        if (ev.target === els.traceModal) closeTraceModal();
      });
    }
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
