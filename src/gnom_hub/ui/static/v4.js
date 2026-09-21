(() => {
  "use strict";

  const $ = (q) => document.querySelector(q);
  const $$ = (q) => Array.from(document.querySelectorAll(q));
  const els = {
    ready: $("#ready-chip"),
    tollgate: $("#tollgate-chip"),
    god: $("#god-chip"),
    backup: $("#auto-backup-chip"),
    conversation: $("#conversation"),
    decisions: $("#decision-grid"),
    decisionCount: $("#decision-count"),
    workerTabs: $("#worker-tabs"),
    result: $("#result-stage"),
    input: $("#chat-input"),
    send: $("#send"),
    execute: $("#execute"),
    notice: $("#notice"),
    drop: $("#result-drop"),
    newer: $("#result-new"),
    keep: $("#result-keep"),
  };

  let snapshot = {};
  let systemState = {};
  let agents = [];
  let busy = false;
  let selectedWorker = "";
  let hiddenSuggestions = new Set();
  let noticeTimer = null;

  function toast(text, kind = "") {
    if (!els.notice) return;
    els.notice.textContent = text;
    els.notice.className = "notice show" + (kind ? " " + kind : "");
    clearTimeout(noticeTimer);
    noticeTimer = setTimeout(() => {
      els.notice.className = "notice";
    }, 2800);
  }

  async function api(path, options = {}) {
    const opts = { ...options };
    opts.headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    const res = await fetch(path, opts);
    if (!res.ok) {
      let detail = res.statusText || "Fehler";
      try {
        const body = await res.json();
        detail =
          (body.detail && (body.detail.message || body.detail.error || body.detail)) ||
          body.message ||
          body.error ||
          detail;
        if (typeof detail !== "string") detail = JSON.stringify(detail);
      } catch (_) {}
      throw new Error(detail);
    }
    return res.json();
  }

  function pipeline() {
    return snapshot.pipeline || {};
  }

  function normalizedMessages() {
    const p = pipeline();
    const rows = Array.isArray(p.messages) ? p.messages : [];
    if (rows.length) {
      return rows
        .map((m) => ({
          role: String(m.role || m.reply_agent_id || m.target_agent_id || ""),
          text: String(m.visible_text || m.text || "").trim(),
        }))
        .filter((m) => m.text && (m.role === "user" || m.role === "brainstorm"));
    }
    return (Array.isArray(p.brainstorm_turns) ? p.brainstorm_turns : [])
      .map((m) => ({
        role: String(m.role || ""),
        text: String(m.text || "").trim(),
      }))
      .filter((m) => m.text && (m.role === "user" || m.role === "brainstorm"));
  }

  function renderConversation() {
    const rows = normalizedMessages();
    els.conversation.textContent = "";
    if (!rows.length) {
      els.conversation.innerHTML =
        '<div class="empty-state"><strong>Red mit mir.</strong><span>Idee rein. Brainstorm denkt mit. Noch keine Arbeit.</span></div>';
      return;
    }
    rows.slice(-24).forEach((m) => {
      const div = document.createElement("div");
      div.className = "message " + (m.role === "user" ? "user" : "brainstorm");
      const role = document.createElement("span");
      role.className = "role";
      role.textContent = m.role === "user" ? "Du" : "Brainstorm";
      const body = document.createElement("div");
      body.textContent = m.text;
      div.append(role, body);
      els.conversation.appendChild(div);
    });
    els.conversation.scrollTop = els.conversation.scrollHeight;
  }

  function lastBrainstormText() {
    const rows = normalizedMessages();
    for (let i = rows.length - 1; i >= 0; i--) {
      if (rows[i].role === "brainstorm") return rows[i].text;
    }
    return "";
  }

  function cleanChoice(text) {
    return String(text || "")
      .replace(/\*\*/g, "")
      .replace(/^[-–—:;\s]+/, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function parseBrainstormChoices(text) {
    const lines = String(text || "").split(/\r?\n/);
    const out = [];
    for (const line of lines) {
      const m = line.match(/^\s*(?:[-*•]\s+|([A-Da-d])[.)]\s+)(.+)$/);
      if (!m) continue;
      const body = cleanChoice(m[2] || "");
      if (body.length < 8 || body.length > 260) continue;
      if (/^(was|welche|welcher|wie|oder)\b/i.test(body)) continue;
      if (!out.includes(body)) out.push(body);
      if (out.length >= 4) break;
    }
    return out;
  }

  function activeDecision() {
    const box = snapshot.flex_box1 || {};
    const questions = Array.isArray(box.questions) ? box.questions : [];
    const q = questions.find((x) => x && x.question_id && x.text);
    if (q && String(q.component || "") !== "start_work") {
      return {
        source: "flex",
        id: q.question_id,
        job: q.job_id || "",
        text: String(q.text || ""),
        options: Array.isArray(q.options) ? q.options.slice(0, 2) : [],
      };
    }
    const p = pipeline();
    if (p.pending_question && p.pending_question.text) {
      return {
        source: "clarify",
        text: String(p.pending_question.text),
        options: Array.isArray(p.pending_question.options)
          ? p.pending_question.options.slice(0, 2)
          : [],
      };
    }
    return null;
  }

  function decisionCard(title, body, makeLabel, onMake, onDrop) {
    const card = document.createElement("article");
    card.className = "decision-card";
    const h = document.createElement("h3");
    h.textContent = title;
    const p = document.createElement("p");
    p.textContent = body;
    const actions = document.createElement("div");
    actions.className = "decision-actions";
    const make = document.createElement("button");
    make.className = "make";
    make.type = "button";
    make.textContent = makeLabel || "Machen";
    make.addEventListener("click", onMake);
    const drop = document.createElement("button");
    drop.type = "button";
    drop.textContent = "Weg";
    drop.addEventListener("click", onDrop);
    actions.append(make, drop);
    card.append(h, p, actions);
    return card;
  }

  async function chooseSuggestion(choice) {
    if (busy) return;
    setBusy(true);
    try {
      const text =
        "Ich wähle diese Richtung verbindlich: " +
        choice +
        " Bitte diese Auswahl übernehmen und nicht erneut nach derselben Entscheidung fragen.";
      const snap = await api("/api/chat?sync=true", {
        method: "POST",
        body: JSON.stringify({ text, target: "brainstorm" }),
      });
      snapshot = snap;
      hiddenSuggestions.clear();
      renderAll();
      toast("Auswahl übernommen");
    } catch (err) {
      toast(err.message || "Auswahl fehlgeschlagen", "error");
    } finally {
      setBusy(false);
    }
  }

  async function answerDecision(decision, value) {
    if (busy) return;
    setBusy(true);
    try {
      let res;
      if (decision.source === "flex") {
        res = await api("/api/flex/answer?sync=false", {
          method: "POST",
          body: JSON.stringify({
            question_id: decision.id,
            job_id: decision.job,
            value,
          }),
        });
      } else {
        res = await api("/api/clarify?sync=false", {
          method: "POST",
          body: JSON.stringify({ option: value }),
        });
      }
      await consumeMaybeJob(res);
      await refresh();
      toast("Entscheidung übernommen");
    } catch (err) {
      toast(err.message || "Entscheidung fehlgeschlagen", "error");
    } finally {
      setBusy(false);
    }
  }

  function renderDecisions() {
    els.decisions.textContent = "";
    const decision = activeDecision();
    if (decision) {
      els.decisionCount.textContent = "1 Entscheidung";
      const opts = decision.options.length ? decision.options : ["Machen", "Weg"];
      const card = document.createElement("article");
      card.className = "decision-card";
      const h = document.createElement("h3");
      h.textContent = "Was möchtest du?";
      const p = document.createElement("p");
      p.textContent = decision.text;
      const actions = document.createElement("div");
      actions.className = "decision-actions";
      opts.slice(0, 2).forEach((opt, i) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = i === 0 ? "make" : "";
        btn.textContent = String(opt);
        btn.addEventListener("click", () => answerDecision(decision, String(opt)));
        actions.appendChild(btn);
      });
      card.append(h, p, actions);
      els.decisions.appendChild(card);
      return;
    }

    const choices = parseBrainstormChoices(lastBrainstormText()).filter(
      (c) => !hiddenSuggestions.has(c)
    );
    if (!choices.length) {
      els.decisionCount.textContent = "Nichts zu entscheiden.";
      els.decisions.innerHTML =
        '<div class="decision-empty">Hier erscheinen höchstens vier einfache Möglichkeiten.</div>';
      return;
    }
    els.decisionCount.textContent = choices.length + (choices.length === 1 ? " Möglichkeit" : " Möglichkeiten");
    choices.slice(0, 4).forEach((choice, index) => {
      const short = choice.length > 58 ? choice.slice(0, 55) + "…" : choice;
      const card = decisionCard(
        String.fromCharCode(65 + index) + " · " + short,
        choice,
        "Machen",
        () => chooseSuggestion(choice),
        () => {
          hiddenSuggestions.add(choice);
          renderDecisions();
        }
      );
      els.decisions.appendChild(card);
    });
  }

  function normalizeOutputs() {
    const p = pipeline();
    const raw = Array.isArray(p.worker_outputs) ? p.worker_outputs : [];
    if (raw.length) {
      return raw
        .map((o, i) => ({
          worker: String(o.worker || "worker" + (i + 1)),
          result: String(o.result || ""),
          task: String(o.task || ""),
          validation: o.validation || {},
        }))
        .filter((o) => o.result.trim());
    }
    const results = Array.isArray(p.worker_results) ? p.worker_results : [];
    return results
      .map((r, i) => ({
        worker: "worker" + (i + 1),
        result: String(r || ""),
        task: "",
        validation: {},
      }))
      .filter((o) => o.result.trim());
  }

  function looksHtml(text) {
    const s = String(text || "").trim().toLowerCase();
    return s.includes("<!doctype html") || (s.includes("<html") && s.includes("</html>"));
  }

  function selectedOutput() {
    const outs = normalizeOutputs();
    if (!outs.length) return null;
    return outs.find((o) => o.worker === selectedWorker) || outs[0];
  }

  function renderResults() {
    const outs = normalizeOutputs();
    els.workerTabs.textContent = "";
    if (!outs.length) {
      selectedWorker = "";
      els.result.innerHTML =
        '<div class="empty-state result-empty"><strong>Noch kein Ergebnis.</strong><span>Erst „Arbeit starten“ lässt Worker arbeiten.</span></div>';
      [els.drop, els.newer, els.keep].forEach((b) => (b.disabled = true));
      return;
    }
    if (!selectedWorker || !outs.some((o) => o.worker === selectedWorker)) {
      selectedWorker = outs[0].worker;
    }
    outs.forEach((out) => {
      const tab = document.createElement("button");
      tab.type = "button";
      tab.className = "worker-tab" + (out.worker === selectedWorker ? " active" : "");
      tab.textContent = out.worker.replace("worker", "W");
      const issues = Array.isArray(out.validation.issues) ? out.validation.issues : [];
      if (out.validation.ok === false || issues.length) tab.title = issues.join(", ");
      tab.addEventListener("click", () => {
        selectedWorker = out.worker;
        renderResults();
      });
      els.workerTabs.appendChild(tab);
    });
    const out = selectedOutput();
    els.result.textContent = "";
    if (out && looksHtml(out.result)) {
      const frame = document.createElement("iframe");
      frame.setAttribute("sandbox", "allow-scripts");
      frame.setAttribute("title", "Worker-Ergebnis " + out.worker);
      frame.srcdoc = out.result;
      els.result.appendChild(frame);
    } else {
      const pre = document.createElement("pre");
      pre.textContent = out ? out.result : "";
      els.result.appendChild(pre);
    }
    [els.drop, els.newer, els.keep].forEach((b) => (b.disabled = false));
  }

  function agentStatus(id) {
    const p = pipeline();
    const stage = String(p.stage || "").toLowerCase();
    const agent = agents.find((a) => String(a.id || "").toLowerCase() === id);
    if (agent && agent.enabled === false) return "aus";
    if (p.error && (stage === "error" || stage === id)) return "blockiert";
    if (stage === id || (id === "coordinator" && ["distill", "plan"].includes(stage))) return "arbeitet";
    const out = normalizeOutputs().find((o) => o.worker === id);
    if (out) return out.validation && out.validation.ok === false ? "blockiert" : "fertig";
    if (id === "brainstorm" && stage === "brainstorm") return "fertig";
    return "wartet";
  }

  function renderAgents() {
    $$(".agent-pill").forEach((el) => {
      const id = el.dataset.agent;
      const st = agentStatus(id);
      el.dataset.state = st;
      const small = el.querySelector("small");
      if (small) small.textContent = st;
    });
  }

  function renderHeader() {
    const p = pipeline();
    const stage = String(p.stage || "");
    const running = busy || ["memory", "distill", "plan", "work", "worker1", "worker2", "worker3", "worker4"].includes(stage);
    const hasError = !!p.error || stage === "error";
    els.ready.dataset.state = hasError ? "bad" : running ? "work" : "ok";
    els.ready.querySelector("b").textContent = hasError ? "blockiert" : running ? "arbeitet" : "READY";

    const tg = snapshot.tollgate || {};
    const tgBad = tg.error || tg.blocked || tg.ready === false;
    els.tollgate.dataset.state = tgBad ? "bad" : tg.ready === true || tg.enabled ? "ok" : "wait";

    const god = snapshot.god_mode || {};
    const godOn = !!god.enabled;
    els.god.classList.toggle("on", godOn);
    els.god.querySelector("b").textContent = godOn ? "God an" : "God aus";

    const backupOn = !!systemState.auto_backup_before_execute;
    els.backup.classList.toggle("on", backupOn);
    els.backup.setAttribute("aria-pressed", backupOn ? "true" : "false");
    els.backup.querySelector("b").textContent = backupOn ? "Backup an" : "Backup aus";
  }

  function renderAll() {
    renderHeader();
    renderAgents();
    renderConversation();
    renderDecisions();
    renderResults();
    const p = pipeline();
    const canTalk = !busy;
    els.send.disabled = !canTalk;
    els.execute.disabled =
      busy ||
      !(
        normalizedMessages().some((m) => m.role === "user") ||
        String(p.user_text || "").trim() ||
        String(p.brainstorm_notes || "").trim()
      );
  }

  function setBusy(on) {
    busy = !!on;
    els.send.disabled = busy;
    els.execute.disabled = busy;
    els.execute.classList.toggle("running", busy);
    els.execute.textContent = busy ? "arbeitet …" : "Arbeit starten";
    renderHeader();
  }

  async function pollJob(jobId) {
    const start = Date.now();
    while (Date.now() - start < 300000) {
      const job = await api("/api/jobs/" + encodeURIComponent(jobId));
      if (job.snapshot) {
        snapshot = job.snapshot;
        renderAll();
      }
      if (["done", "error", "cancelled"].includes(String(job.status || ""))) {
        if (job.status === "error") throw new Error(job.error || "Arbeitslauf fehlgeschlagen");
        return job.snapshot || null;
      }
      await new Promise((r) => setTimeout(r, 900));
    }
    throw new Error("Arbeitslauf dauert zu lange");
  }

  async function consumeMaybeJob(res) {
    if (res && res.job_id) {
      const snap = await pollJob(res.job_id);
      if (snap) snapshot = snap;
      return;
    }
    if (res && res.pipeline) snapshot = res;
  }

  async function refresh() {
    try {
      const [state, agentData, sys] = await Promise.all([
        api("/api/state"),
        api("/api/agents"),
        api("/api/system"),
      ]);
      snapshot = state || {};
      systemState = sys || {};
      agents = Array.isArray(agentData.agents) ? agentData.agents : [];
      renderAll();
    } catch (err) {
      toast(err.message || "Gnom nicht erreichbar", "error");
      els.ready.dataset.state = "bad";
      els.ready.querySelector("b").textContent = "offline";
    }
  }

  async function sendMessage() {
    const text = String(els.input.value || "").trim();
    if (!text || busy) return;
    els.input.value = "";
    setBusy(true);
    try {
      const res = await api("/api/chat?sync=true", {
        method: "POST",
        body: JSON.stringify({ text, target: "brainstorm" }),
      });
      snapshot = res;
      hiddenSuggestions.clear();
      renderAll();
    } catch (err) {
      els.input.value = text;
      toast(err.message || "Senden fehlgeschlagen", "error");
    } finally {
      setBusy(false);
    }
  }

  async function startWork() {
    if (busy) return;
    setBusy(true);
    if (systemState.auto_backup_before_execute) {
      els.execute.textContent = "sichert …";
    }
    try {
      const res = await api("/api/execute", { method: "POST", body: "{}" });
      await consumeMaybeJob(res);
      await refresh();
      const out = selectedOutput();
      if (out) toast("Ergebnis ist da");
      else if (activeDecision()) toast("Eine echte Entscheidung ist noch nötig");
      else toast("Lauf beendet – noch kein Ergebnis", "error");
    } catch (err) {
      toast(err.message || "Arbeit konnte nicht starten", "error");
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function rerunSelected() {
    const out = selectedOutput();
    if (!out || busy) return;
    setBusy(true);
    try {
      const res = await api("/api/workers/" + encodeURIComponent(out.worker) + "/rerun", {
        method: "POST",
        body: "{}",
      });
      await consumeMaybeJob(res);
      await refresh();
      toast(out.worker.replace("worker", "W") + " neu ausgeführt");
    } catch (err) {
      toast(err.message || "Neu fehlgeschlagen", "error");
    } finally {
      setBusy(false);
    }
  }

  async function keepSelected() {
    const out = selectedOutput();
    if (!out || busy) return;
    const ext = looksHtml(out.result) ? ".html" : ".txt";
    const name = out.worker + "_v4" + ext;
    setBusy(true);
    try {
      await api("/api/workspace/keep", {
        method: "POST",
        body: JSON.stringify({
          content: out.result,
          name,
          worker: out.worker,
          overwrite: false,
        }),
      });
      toast("Behalten: " + name);
    } catch (err) {
      toast(err.message || "Behalten fehlgeschlagen", "error");
    } finally {
      setBusy(false);
    }
  }

  async function toggleAutoBackup() {
    if (busy || !els.backup) return;
    const next = !systemState.auto_backup_before_execute;
    els.backup.disabled = true;
    try {
      systemState = await api("/api/system", {
        method: "POST",
        body: JSON.stringify({ auto_backup_before_execute: next }),
      });
      renderHeader();
      toast(next ? "Auto-Backup an · gilt auch bei God Mode" : "Auto-Backup aus");
    } catch (err) {
      toast(err.message || "Backup-Schalter fehlgeschlagen", "error");
    } finally {
      els.backup.disabled = false;
    }
  }

  els.send.addEventListener("click", sendMessage);
  els.execute.addEventListener("click", startWork);
  els.backup.addEventListener("click", toggleAutoBackup);
  els.newer.addEventListener("click", rerunSelected);
  els.keep.addEventListener("click", keepSelected);
  els.drop.addEventListener("click", () => {
    const out = selectedOutput();
    if (!out) return;
    const worker = out.worker;
    const outs = normalizeOutputs().filter((o) => o.worker !== worker);
    if (pipeline().worker_outputs) pipeline().worker_outputs = outs;
    selectedWorker = outs[0] ? outs[0].worker : "";
    renderResults();
    toast("Aus Ansicht genommen – nicht gelöscht");
  });
  els.input.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      sendMessage();
    }
  });
  els.input.addEventListener("input", () => {
    els.input.style.height = "auto";
    els.input.style.height = Math.min(92, Math.max(38, els.input.scrollHeight)) + "px";
  });
  els.god.addEventListener("click", () => {
    toast("God-Mode bleibt absichtlich getrennt. Schalter kommt nach dem Kernlauf.");
  });
  $("#mic").addEventListener("click", () => toast("Mikrofon kommt nach dem Kernlauf."));

  refresh();
  setInterval(() => {
    if (!busy) refresh();
  }, 5000);
})();
