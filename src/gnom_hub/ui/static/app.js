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
    btnHelp: document.getElementById("btn-help"),
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
    if (p.brainstorm_notes) {
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
      setBox2("Brainstorm thoughts appear here.\n\n(Type a message below and press Send.)");
    }

    if (p.worker_results && p.worker_results.length) {
      const lines = ["=== Worker results ==="];
      p.worker_results.forEach(function (r, i) {
        lines.push("");
        lines.push("--- Worker " + (i + 1) + " ---");
        lines.push(r);
      });
      setBox3(lines.join("\n"));
    } else if (p.stage === "done") {
      setBox3("(no worker output — coordinator or workers off)");
    } else if (p.stage === "idle") {
      setBox3("Worker results appear here after Send.");
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

  let chatBusy = false;

  function setChatBusy(busy) {
    chatBusy = !!busy;
    if (els.btnSend) {
      els.btnSend.disabled = chatBusy;
      els.btnSend.textContent = chatBusy ? "…" : "Send";
    }
    if (els.chatInput) els.chatInput.disabled = chatBusy;
    if (els.stageBadge && chatBusy) els.stageBadge.textContent = "running…";
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
        ? "Pipeline running (Live LLM, 10–40s)…"
        : "Pipeline running (stub mode, fast)…"
    );
    toast(live ? "Pipeline running (live)…" : "Pipeline running…", "info");

    try {
      const snap = await api("POST", "/api/chat", { text: text });
      applySnapshot(snap);
      if (snap.pipeline && snap.pipeline.stage === "done") {
        appendChat("system", "Pipeline done.");
        toast("Pipeline done", "ok");
      } else if (snap.pipeline && snap.pipeline.stage === "clarify") {
        appendChat("system", "Need a clarify answer in Box 1.");
        toast("Clarify needed in Box 1", "info");
      } else if (snap.pipeline && snap.pipeline.stage === "error") {
        appendChat("system", "Pipeline error: " + (snap.pipeline.error || "?"));
        toast(snap.pipeline.error || "Pipeline error", "error");
      }
    } catch (err) {
      appendChat("system", "Chat failed: " + err.message);
      toast("Chat failed: " + err.message, "error");
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
    if (!body) return;
    body.innerHTML = "";
    const pre = document.createElement("pre");
    pre.className = "result-block";
    pre.textContent = htmlOrText || "";
    body.appendChild(pre);
  }
  function setBox3(htmlOrText) {
    const body = document.getElementById("box3-content");
    if (!body) return;
    // keep optional canvas-preview if present
    const canvas = body.querySelector(".canvas-preview");
    body.innerHTML = "";
    const pre = document.createElement("pre");
    pre.className = "result-block";
    pre.textContent = htmlOrText || "";
    body.appendChild(pre);
    if (canvas) body.appendChild(canvas);
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
    if (els.btnHelp) els.btnHelp.addEventListener("click", onHelp);
    if (els.btnReset) els.btnReset.addEventListener("click", onReset);
    if (els.btnArchive) els.btnArchive.addEventListener("click", onArchive);
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
