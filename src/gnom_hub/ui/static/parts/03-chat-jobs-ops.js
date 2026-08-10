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

  async function _cycleFlexPreset() {
    toast("Flex is fixed — personal companion only", "info");
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
    /* Agent-IDs → volle Erklärung mit Parametern (Box 1 Überblick) */
    if (
      id &&
      typeof fillBox1AgentInfo === "function" &&
      AGENTS.some(function (a) {
        return a.id === id;
      })
    ) {
      fillBox1AgentInfo(id);
      return;
    }
    const tip = TOOLTIPS[id];
    if (!tip) return;
    showInfoLayer("live");
    if (els.placeholder) els.placeholder.hidden = true;
    if (els.tipRoot) els.tipRoot.hidden = false;
    if (els.tipTitle) els.tipTitle.textContent = tip.title;
    const roleEl = document.getElementById("tip-role");
    if (roleEl) roleEl.textContent = "";
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

  let busyJobId = null; // job holding pipeline (may differ from currentJobId after 409)

  function godModeLabel() {
    const b = els.godBadge || document.getElementById("god-badge");
    if (b && b.classList.contains("on")) return "God:ON";
    return "God:off";
  }

  function showBusyBanner(info) {
    const ban = document.getElementById("pipeline-busy-banner");
    const txt = document.getElementById("pipeline-busy-text");
    if (!ban) return;
    const id = (info && (info.busy_job_id || info.id)) || busyJobId || currentJobId || "?";
    const stage = (info && (info.busy_stage || info.stage)) || "?";
    const name = (info && (info.busy_name || info.name)) || "job";
    const cancelling = !!(info && info.cancel);
    busyJobId = id !== "?" ? id : busyJobId;
    const god = godModeLabel();
    if (txt) {
      txt.textContent = cancelling
        ? "Pipeline cancel… (" +
          name +
          " @ " +
          stage +
          ") · " +
          god +
          " · warte auf Stage-Ende"
        : "Pipeline busy: " +
          name +
          " @ " +
          stage +
          " · job " +
          id +
          " · " +
          god +
          (god === "God:off" ? " (Shell/GUI oft dry-run)" : "");
    }
    ban.hidden = false;
  }

  function hideBusyBanner() {
    const ban = document.getElementById("pipeline-busy-banner");
    if (ban) ban.hidden = true;
    busyJobId = null;
  }

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
    }, 250);
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
    // Keep chat input usable when only foreign busy (409) — allow Cancel banner
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
    if (!chatBusy && !busyJobId) hideBusyBanner();
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

  async function _rerunWorker(workerId) {
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
      let when = (p.mtime || p.exported_at || "").replace("T", " ").replace("+00:00", "Z");
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
    let next = window.prompt("Pack label (max 80 chars):", currentLabel || "");
    if (next === null) return;
    next = String(next).trim().slice(0, 80);
    if (!next) {
      toast("Label required", "error");
      return;
    }
    let notesNext = window.prompt(
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
      const labelHint = window.prompt("Pack label (optional, Enter to skip):", "");
      const notesHint = window.prompt("Pack notes (optional, Enter to skip):", "");
      const body = {
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

  function collectChatLogFrom(logEl) {
    const lines = [];
    if (!logEl) return lines;
    logEl.querySelectorAll(".chat-line").forEach(function (el) {
      lines.push({
        who: el.dataset.who || "system",
        text: el.dataset.text || "",
        ts: el.dataset.ts || "",
      });
    });
    return lines;
  }

  function collectChatLog() {
    return collectChatLogFrom(els.chatLog);
  }

  function chatLogElForAgent(agentId) {
    const aid = agentId || "brainstorm";
    if (aid === "brainstorm") {
      return (
        document.getElementById("chat-log") ||
        document.querySelector('.chat-agent-layer[data-agent="brainstorm"] .chat-log')
      );
    }
    return (
      document.getElementById("chat-log-" + aid) ||
      document.querySelector(
        '.chat-agent-layer[data-agent="' + aid + '"] .chat-log'
      )
    );
  }

  /** B4: persist every agent chat layer (not only the active one). */
  function persistChatLog() {
    try {
      const all = {};
      AGENTS.forEach(function (a) {
        const log = chatLogElForAgent(a.id);
        if (!log) return;
        all[a.id] = collectChatLogFrom(log).slice(-80);
      });
      /* also active pointer if missing from AGENTS edge case */
      if (els.chatLog) {
        const aid =
          els.chatLog.dataset.agent || lastClickedAgentId || "brainstorm";
        if (!all[aid]) all[aid] = collectChatLogFrom(els.chatLog).slice(-80);
      }
      sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(all));
    } catch (_e) {
      /* quota / private mode */
    }
  }

  function fillChatLogEl(logEl, lines) {
    if (!logEl || !lines || !lines.length) return;
    const prev = els.chatLog;
    els.chatLog = logEl;
    logEl.innerHTML = "";
    lines.forEach(function (entry) {
      if (typeof entry === "string") {
        const line = document.createElement("p");
        line.className = "chat-line";
        line.dataset.who = "system";
        line.dataset.text = entry;
        line.textContent = entry;
        logEl.appendChild(line);
        return;
      }
      renderChatLine(entry.who || "system", entry.text || "", entry.ts || "");
    });
    logEl.scrollTop = logEl.scrollHeight;
    els.chatLog = prev;
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
    try {
      let raw = sessionStorage.getItem(CHAT_STORAGE_KEY);
      let data = null;
      if (raw) {
        data = JSON.parse(raw);
      } else {
        /* migrate legacy single-array log → brainstorm */
        raw = sessionStorage.getItem(CHAT_STORAGE_LEGACY);
        if (raw) {
          const legacy = JSON.parse(raw);
          if (Array.isArray(legacy) && legacy.length) {
            data = { brainstorm: legacy };
            try {
              sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(data));
              sessionStorage.removeItem(CHAT_STORAGE_LEGACY);
            } catch (_e2) {
              /* ignore */
            }
          }
        }
      }
      if (!data) return;

      if (Array.isArray(data)) {
        /* still legacy shape */
        const log = chatLogElForAgent("brainstorm");
        if (log) fillChatLogEl(log, data);
      } else if (typeof data === "object") {
        Object.keys(data).forEach(function (aid) {
          if (!Array.isArray(data[aid])) return;
          const log = chatLogElForAgent(aid);
          if (log) fillChatLogEl(log, data[aid]);
        });
      }
      if (typeof syncActiveChatLog === "function") {
        syncActiveChatLog(lastClickedAgentId || "brainstorm");
      }
    } catch (_e) {
      /* ignore */
    }
  }

  function renderChatLine(who, text, ts) {
    if (!els.chatLog) {
      if (typeof syncActiveChatLog === "function") {
        syncActiveChatLog(lastClickedAgentId || "brainstorm");
      }
    }
    if (!els.chatLog) return null;
    const w = String(who || "system").replace(/\W+/g, "");
    const line = document.createElement("div");
    const isYou = w === "you";
    const isSys = w === "system";
    line.className =
      "chat-line chat-who-" +
      w +
      " mb-1.5 flex w-full gap-2 " +
      (isYou ? "justify-end" : "justify-start");
    line.dataset.who = who;
    line.dataset.text = text;
    line.dataset.ts = ts || "";

    const bubble = document.createElement("div");
    bubble.className =
      "chat-body max-w-[92%] rounded-lg px-2.5 py-1.5 text-[12px] leading-snug shadow-sm " +
      (isYou
        ? "bg-gnom-accent/15 border border-gnom-accent/30 text-gnom-text rounded-br-sm"
        : isSys
          ? "bg-gnom-elev/80 border border-gnom-border text-gnom-muted rounded-bl-sm"
          : "bg-gnom-card border border-gnom-border text-gnom-text rounded-bl-sm");

    if (ts) {
      const tsel = document.createElement("span");
      tsel.className = "chat-ts mr-1.5 text-2xs tabular-nums text-gnom-muted opacity-75";
      tsel.textContent = ts;
      bubble.appendChild(tsel);
    }
    const label = document.createElement("span");
    label.className =
      "chat-who-label mr-1 text-2xs font-semibold uppercase tracking-wide " +
      (isYou ? "text-gnom-accent" : isSys ? "text-gnom-muted" : "text-gnom-flex");
    label.textContent = who;
    bubble.appendChild(label);
    const body = document.createElement("span");
    body.className = "chat-text whitespace-pre-wrap break-words";
    body.textContent = text;
    bubble.appendChild(document.createTextNode(" "));
    bubble.appendChild(body);
    line.appendChild(bubble);
    els.chatLog.appendChild(line);
    return line;
  }

  function clearChatLog() {
    AGENTS.forEach(function (a) {
      const log = chatLogElForAgent(a.id);
      if (log) log.innerHTML = "";
    });
    if (els.chatLog) els.chatLog.innerHTML = "";
    try {
      sessionStorage.removeItem(CHAT_STORAGE_KEY);
      sessionStorage.removeItem(CHAT_STORAGE_LEGACY);
    } catch (_e) {
      /* ignore */
    }
    toast("Chat log cleared (all agents)", "ok");
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
    busyJobId = jobId;
    showBusyBanner({ busy_job_id: jobId, busy_name: "job", busy_stage: "queued" });
    const deadline = Date.now() + (maxMs || 180000);
    let lastStage = "";
    let lastToolLogLen = 0;
    // Adaptive poll: snappy at start, calm later (speed + stability)
    let pollDelayMs = 180;
    try {
      while (Date.now() < deadline) {
        let job;
        try {
          job = await api("GET", "/api/jobs/" + encodeURIComponent(jobId));
        } catch (_pollErr) {
          // transient — retry until deadline
          await new Promise(function (resolve) {
            setTimeout(resolve, 600);
          });
          continue;
        }
        const stage =
          job.stage ||
          (job.snapshot && job.snapshot.pipeline && job.snapshot.pipeline.stage) ||
          "";
        showBusyBanner({
          busy_job_id: jobId,
          busy_name: job.name || "job",
          busy_stage: stage || job.status,
          cancel: job.cancel,
        });
        // Live tool log → chat (so desk sees real tool use, not only final box)
        const tlog = Array.isArray(job.tool_log) ? job.tool_log : [];
        if (tlog.length > lastToolLogLen) {
          for (let ti = lastToolLogLen; ti < tlog.length; ti++) {
            const e = tlog[ti] || {};
            const mode = e.mode ? " · " + e.mode : "";
            const ok = e.ok === false ? "FAIL" : "ok";
            appendChat(
              "system",
              "Tool: " + (e.tool || "?") + " " + ok + mode
            );
          }
          lastToolLogLen = tlog.length;
        }
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
          hideBusyBanner();
          await resyncState();
          return job;
        }
        // Faster while queued/early; back off when stable mid-work
        if (document.hidden) {
          pollDelayMs = 900;
        } else if (
          lastStage === "work" ||
          lastStage === "worker1" ||
          lastStage === "worker2" ||
          lastStage === "worker3" ||
          lastStage === "worker4"
        ) {
          pollDelayMs = Math.min(650, pollDelayMs + 40);
        } else {
          pollDelayMs = Math.min(500, Math.max(180, pollDelayMs + 25));
        }
        await new Promise(function (resolve) {
          setTimeout(resolve, pollDelayMs);
        });
      }
      // Timeout: cancel orphan + resync so UI is not left mid-pipeline
      try {
        await api("POST", "/api/jobs/" + encodeURIComponent(jobId) + "/cancel");
        appendChat("system", "Job timed out — cancel requested.");
      } catch (_c) {
        /* ignore */
      }
      hideBusyBanner();
      await resyncState();
      throw new Error("Pipeline timeout");
    } finally {
      if (currentJobId === jobId) currentJobId = null;
    }
  }

  async function waitPipelineFree(maxMs) {
    const deadline = Date.now() + (maxMs || 45000);
    while (Date.now() < deadline) {
      try {
        const b = await api("GET", "/api/jobs/busy");
        if (!b || !b.busy) {
          hideBusyBanner();
          busyJobId = null;
          currentJobId = null;
          if (typeof setChatBusy === "function") setChatBusy(false);
          await resyncState();
          return true;
        }
        showBusyBanner({
          busy_job_id: b.busy_job_id,
          busy_name: b.busy_name || "job",
          busy_stage: b.busy_stage || "cancelling",
          cancel: true,
        });
      } catch (_e) {
        /* ignore */
      }
      await new Promise(function (resolve) {
        setTimeout(resolve, 500);
      });
    }
    return false;
  }

  async function cancelCurrentJob() {
    const jid = currentJobId || busyJobId;
    if (!jid) {
      // one-shot: cancel whatever server says is busy
      try {
        const r = await api("POST", "/api/jobs/cancel-busy");
        if (r && r.busy) {
          toast("Cancel requested — warte bis Pipeline frei…", "info");
          appendChat("system", "Cancel busy job " + ((r.cancelled && r.cancelled.id) || ""));
          showBusyBanner({
            busy_job_id: (r.cancelled && r.cancelled.id) || "?",
            busy_stage: "cancelling",
            busy_name: "job",
            cancel: true,
          });
          const free = await waitPipelineFree(45000);
          toast(
            free ? "Pipeline frei" : "Cancel läuft noch (LLM kann warten)",
            free ? "ok" : "info"
          );
          if (free) appendChat("system", "Pipeline free — ready.");
        } else {
          toast("No running job", "info");
          hideBusyBanner();
        }
        await resyncState();
      } catch (err) {
        toast("Cancel failed: " + err.message, "error");
      }
      return;
    }
    try {
      await api("POST", "/api/jobs/" + encodeURIComponent(jid) + "/cancel");
      toast("Cancel requested — warte bis Pipeline frei…", "info");
      appendChat("system", "Cancel requested for job " + jid);
      showBusyBanner({
        busy_job_id: jid,
        busy_stage: "cancelling",
        busy_name: "job",
        cancel: true,
      });
      const free = await waitPipelineFree(45000);
      toast(
        free ? "Pipeline frei" : "Cancel läuft noch (LLM kann warten)",
        free ? "ok" : "info"
      );
      if (free) appendChat("system", "Pipeline free — ready.");
      await resyncState();
    } catch (err) {
      toast("Cancel failed: " + err.message, "error");
    }
  }

  function handleBusyError(err, userText) {
    const d = err && err.detail;
    const obj = d && typeof d === "object" ? d : null;
    const msg =
      (obj && (obj.message || obj.hint)) ||
      (err && err.message) ||
      "Pipeline busy";
    if (obj && obj.busy_job_id) {
      busyJobId = obj.busy_job_id;
      showBusyBanner(obj);
    } else {
      showBusyBanner({ busy_job_id: busyJobId || "?", busy_stage: "busy", busy_name: "pipeline" });
    }
    appendChat("system", msg + (userText ? " (deine Nachricht wurde nicht gestartet)" : ""));
    toast(msg, "error");
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


  /** Colored flag chips: standing wishes attached to next Send/Execute */
  const CHAT_FLAG_DEFS = [
    { id: "dark", color: "#7c5cff", label: "Dunkel", wish: "User: always enable dark theme" },
    { id: "de", color: "#5b9cff", label: "Deutsch", wish: "User: prefers German language answers" },
    { id: "interact", color: "#3dd68c", label: "Klicks", wish: "User: wants real interactions (onclick / JS)" },
    { id: "short", color: "#f0b429", label: "Knapp", wish: "User: prefers short answers and lean UI" },
    { id: "strict", color: "#f07178", label: "Strikt", wish: "User: standing wishes are absolute — implement fully" },
  ];
  let activeChatFlags = {};

  function renderChatFlags() {
    const root = document.getElementById("chat-flags");
    if (!root) return;
    let label = root.querySelector(".chat-flags-label");
    root.innerHTML = "";
    if (!label) {
      label = document.createElement("span");
      label.className =
        "chat-flags-label text-2xs uppercase tracking-wide text-gnom-muted";
      label.title = "Klick = an nächste Nachricht anhängen";
      label.textContent = "Flags";
    }
    root.appendChild(label);
    CHAT_FLAG_DEFS.forEach(function (f) {
      const b = document.createElement("button");
      b.type = "button";
      b.className =
        "chat-flag h-4 w-4 shrink-0 rounded-sm border border-black/40 shadow-sm transition " +
        "hover:scale-110 hover:opacity-100 " +
        (activeChatFlags[f.id]
          ? "is-on opacity-100 ring-2 ring-gnom-text ring-offset-1 ring-offset-gnom-bg"
          : "opacity-55");
      b.style.setProperty("--flag-color", f.color);
      b.style.background = f.color;
      b.title = f.label + " — " + f.wish;
      b.setAttribute("aria-label", f.label);
      b.dataset.id = f.id;
      b.addEventListener("click", function () {
        if (activeChatFlags[f.id]) delete activeChatFlags[f.id];
        else activeChatFlags[f.id] = f;
        renderChatFlags();
      });
      root.appendChild(b);
    });
  }

  function composeChatWithFlags(text) {
    const t = (text || "").trim();
    const flags = Object.keys(activeChatFlags)
      .map(function (k) {
        return activeChatFlags[k];
      })
      .filter(Boolean);
    if (!flags.length) return t;
    const block = flags
      .map(function (f) {
        return f.wish;
      })
      .join("\n");
    // Keep flags selected so Execute also sees them; user toggles off manually
    return (t + "\n\n" + block).trim();
  }

  function _clearChatFlags() {
    activeChatFlags = {};
    renderChatFlags();
  }

  // init chips once DOM ready (script is deferred/end)
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderChatFlags);
  } else {
    renderChatFlags();
  }


  async function persistActiveFlagsAsWishes() {
    const flags = Object.keys(activeChatFlags).map(function (k) {
      return activeChatFlags[k];
    });
    if (!flags.length) return;
    for (let i = 0; i < flags.length; i++) {
      const f = flags[i];
      if (!f || !f.wish) continue;
      try {
        await api("POST", "/api/flex/feedback", {
          button_id: "custom_note",
          label: f.label || f.id,
          note: f.wish.replace(/^User:\s*/i, ""),
        });
      } catch (_e) {
        /* ignore single flag fail */
      }
    }
  }

  async function sendChat() {

    const raw = (els.chatInput.value || "").trim();
    if (!raw || chatBusy) return;
    const text = composeChatWithFlags(raw);
    appendChat("you", text);
    pushChatHist(raw);
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
      // Pipeline already busy — do not poll forever
      if (start.busy || start.status === "busy") {
        handleBusyError(
          { message: start.message || start.error, detail: start },
          text
        );
        return;
      }
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
          hideBusyBanner();
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
      if (err && (err.status === 409 || (err.detail && err.detail.busy))) {
        handleBusyError(err, text);
      } else {
        appendChat("system", "Chat failed: " + err.message);
        toast("Chat failed: " + err.message, "error");
      }
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
    try {
      await persistActiveFlagsAsWishes();
    } catch (_e) {
      /* non-fatal */
    }

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

