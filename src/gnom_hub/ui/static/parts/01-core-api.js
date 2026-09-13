/* part: 01-core-api.js — edit parts, run scripts/build_ui_js.py */
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
      let detailObj = null;
      try {
        const j = await res.json();
        detailObj = j.detail !== undefined ? j.detail : j;
        if (detailObj && typeof detailObj === "object") {
          detail =
            detailObj.message ||
            detailObj.error ||
            detailObj.hint ||
            detailObj.detail ||
            JSON.stringify(detailObj);
          if (detailObj.code) detail = "[" + detailObj.code + "] " + detail;
          if (detailObj.retryable) detail += " (retryable)";
        } else {
          detail = detailObj != null ? detailObj : JSON.stringify(j);
        }
      } catch (e) {
        /* ignore */
      }
      // Structured busy (409) — no toast spam; callers handle banner
      const err = new Error(String(detail));
      err.status = res.status;
      err.detail = detailObj;
      if (res.status !== 409) {
        toast(String(detail), "error");
      }
      throw err;
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

  async function answerFlexQuestion(q, value) {
    if (!q || !q.question_id) return;
    try {
      const start = await api("POST", "/api/flex/answer", {
        question_id: q.question_id,
        job_id: q.job_id || "",
        value: value,
      });
      const wantsStart = !!(
        start.flex_answer && start.flex_answer.wants_start_work
      );
      if (wantsStart) {
        toast("Arbeit starten", "ok");
        if (typeof appendChat === "function") {
          appendChat("system", "Execute started (distill → flex → workers)…");
        }
      }
      let snap = start;
      // execute_async envelope is {job_id, stage:queued} without flex_box1.
      // Applying it as a snapshot wipes Box 1 — poll like #btn-execute.
      if (start.job_id && typeof pollJob === "function") {
        if (typeof setChatBusy === "function") setChatBusy(true);
        try {
          const job = await pollJob(start.job_id, 300000);
          snap = job.snapshot || (await api("GET", "/api/state"));
          if (job.status === "error") {
            if (typeof appendChat === "function") {
              appendChat("system", "Execute error: " + (job.error || "?"));
            }
            toast(job.error || "Execute error", "error");
            applySnapshot(snap);
            return;
          }
          if (job.status === "cancelled") {
            if (typeof appendChat === "function") {
              appendChat("system", "Execute cancelled.");
            }
            toast("Cancelled", "info");
            applySnapshot(snap);
            return;
          }
        } finally {
          if (typeof setChatBusy === "function") setChatBusy(false);
          currentJobId = null;
        }
      }
      applySnapshot(snap);
    } catch (err) {
      toast(
        (err && err.message) || "Antwort nicht übernommen",
        "error"
      );
    }
  }

  function renderFlexBox1(box) {
    const host = document.getElementById("flex-ask");
    const list = document.getElementById("flex-ask-list");
    if (!host || !list) return;
    let qs = (box && Array.isArray(box.questions) ? box.questions : []).filter(
      function (q) {
        return q && q.question_id && q.text;
      }
    );
    const placeholder = document.querySelector("#box1-layer-live .box1-placeholder");
    if (!qs.length) {
      host.hidden = true;
      list.textContent = "";
      if (placeholder) placeholder.hidden = false;
      return;
    }
    host.hidden = false;
    if (placeholder) placeholder.hidden = true;
    qs = qs.slice(0, 1);
    if (typeof markOwner === "function") markOwner(host, "flex");
    else host.dataset.agent = "flex";
    const title = document.getElementById("flex-ask-title");
    if (title) title.textContent = (box && box.title) || "Rückfragen und Entscheidungen";
    list.textContent = "";
    qs.forEach(function (q) {
      const card = document.createElement("div");
      card.className = "flex-ask-card";
      if (typeof markOwner === "function") {
        markOwner(card, q.agent_id || "flex");
      }
      const p = document.createElement("p");
      p.className = "flex-ask-text";
      p.textContent = String(q.text || "");
      card.appendChild(p);
      const meta = document.createElement("p");
      meta.className = "flex-ask-meta muted";
      meta.textContent = String(q.agent_id || "") + " · " + String(q.task_id || "");
      card.appendChild(meta);
      const comp = String(q.component || "text").toLowerCase();
      const opts = Array.isArray(q.options) ? q.options.slice() : [];
      function optionIsLater(opt) {
        const low = String(opt || "").trim().toLowerCase();
        return (
          low === "later" ||
          low === "später" ||
          low === "spaeter" ||
          low.indexOf("später") === 0 ||
          low.indexOf("later") === 0
        );
      }
      function addLaterIfMissing(list) {
        if (!list.some(optionIsLater)) list.push("Später");
        return list;
      }
      if (comp === "free_text" || comp === "text") {
        const row = document.createElement("div");
        row.className = "flex-ask-free";
        const inp = document.createElement("input");
        inp.type = "text";
        inp.maxLength = 200;
        inp.placeholder = "Antwort…";
        const send = document.createElement("button");
        send.type = "button";
        send.textContent = "Senden";
        function sendText() {
          const val = String(inp.value || "").trim();
          if (!val) return;
          answerFlexQuestion(q, val);
        }
        send.addEventListener("click", sendText);
        inp.addEventListener("keydown", function (ev) {
          if (ev.key === "Enter") {
            ev.preventDefault();
            sendText();
          }
        });
        row.appendChild(inp);
        row.appendChild(send);
        card.appendChild(row);
      } else if (comp === "multi_select") {
        const picked = [];
        const btns = document.createElement("div");
        btns.className = "flex-ask-btns";
        opts.forEach(function (opt) {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "flex-ask-btn";
          btn.textContent = String(opt);
          btn.addEventListener("click", function () {
            const label = String(opt);
            const i = picked.indexOf(label);
            if (i >= 0) {
              picked.splice(i, 1);
              btn.classList.remove("is-on");
            } else {
              picked.push(label);
              btn.classList.add("is-on");
            }
          });
          btns.appendChild(btn);
        });
        const hint = document.createElement("p");
        hint.className = "flex-ask-hint muted";
        hint.textContent = "Mehrfachauswahl — antippen, dann Senden";
        card.appendChild(hint);
        const send = document.createElement("button");
        send.type = "button";
        send.className = "flex-ask-btn flex-ask-send";
        send.textContent = "Senden";
        send.addEventListener("click", function () {
          if (!picked.length) return;
          answerFlexQuestion(q, picked.slice());
        });
        btns.appendChild(send);
        card.appendChild(btns);
      } else {
        if (comp === "later" || !opts.length) addLaterIfMissing(opts);
        const btns = document.createElement("div");
        btns.className = "flex-ask-btns";
        opts.forEach(function (opt) {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "flex-ask-btn";
          btn.textContent = String(opt);
          btn.addEventListener("click", function () {
            answerFlexQuestion(q, opt);
          });
          btns.appendChild(btn);
        });
        card.appendChild(btns);
      }
      list.appendChild(card);
    });
  }

  function pipelineMessageAgent(m) {
    if (!m || typeof m !== "object") return "brainstorm";
    const reply = String(m.reply_agent_id || "").trim();
    if (reply) return reply;
    const target = String(m.target_agent_id || "").trim();
    if (target) return target;
    const conv = String(m.conversation_id || "");
    if (conv.indexOf("conv-") === 0 && conv.length > 5) return conv.slice(5);
    return "brainstorm";
  }

  function pipelineMessageText(m) {
    let text = String((m && (m.visible_text || m.user_text)) || "");
    const src = String((m && m.source) || "");
    if (
      (src === "template" || src === "fallback") &&
      text.indexOf("[Vorlage] ") !== 0
    ) {
      text = "[Vorlage] " + text;
    }
    return text;
  }

  function pipelineMessageWho(m) {
    if (!m) return "system";
    if (m.role === "user") return "you";
    if (m.role === "agent") return pipelineMessageAgent(m);
    return String(m.role || "system");
  }

  /** Server messages are the conversation truth — chat log + Box2, not a second copy. */
  function renderPipelineMessages(messages, activeTarget) {
    if (!Array.isArray(messages) || !messages.length) return;
    const byAgent = {};
    messages.forEach(function (m) {
      if (!m || typeof m !== "object") return;
      const aid = pipelineMessageAgent(m);
      if (!byAgent[aid]) byAgent[aid] = [];
      let ts = "";
      const rawTs = String(m.created_at || m.accepted_at || "");
      if (rawTs.length >= 19) ts = rawTs.slice(11, 19);
      byAgent[aid].push({
        who: pipelineMessageWho(m),
        text: pipelineMessageText(m),
        ts: ts,
      });
    });
    const prevLog = els.chatLog;
    Object.keys(byAgent).forEach(function (aid) {
      const log =
        typeof chatLogElForAgent === "function" ? chatLogElForAgent(aid) : null;
      if (log && typeof fillChatLogEl === "function") {
        fillChatLogEl(log, byAgent[aid]);
        return;
      }
      if (!log) return;
      els.chatLog = log;
      log.innerHTML = "";
      byAgent[aid].forEach(function (entry) {
        if (typeof renderChatLine === "function") {
          renderChatLine(entry.who, entry.text, entry.ts);
        }
      });
    });
    els.chatLog = prevLog;
    if (typeof persistChatLog === "function") persistChatLog();

    const active = activeTarget || sendTarget || "brainstorm";
    const conv = messages.filter(function (m) {
      return m && pipelineMessageAgent(m) === active;
    });
    if (!conv.length) return;
    const lines = [];
    conv.forEach(function (m) {
      const aid = pipelineMessageAgent(m);
      const role =
        m.role === "user"
          ? "Du"
          : typeof box2AgentTabLabel === "function"
            ? box2AgentTabLabel(aid)
            : aid;
      lines.push("");
      lines.push(role + ":");
      lines.push(pipelineMessageText(m));
    });
    const body = lines.join("\n").replace(/^\n/, "");
    if (typeof setBox2 === "function") setBox2(body);
    if (active !== "brainstorm" && typeof setBox2Agent === "function") {
      setBox2Agent(active, body, active);
    }
  }

  function applySnapshot(snap) {
    if (!snap) {
      lastSnapshot = null;
      return;
    }
    // Job start envelopes ({job_id, stage:queued}) are not state snapshots.
    if (snap.job_id && !snap.pipeline && !snap.flex_box1) {
      return;
    }
    lastSnapshot = snap;
    applyUiPackExtras(snap);
    if (snap.agents) applyAgentsFromServer(snap.agents);
    const p = snap.pipeline || {};
    activeStage = p.stage || "idle";
    if (els.stageBadge) {
      const stageDe = {
        idle: "leer",
        brainstorm: "Brain",
        distill: "Distill",
        execute: "Arbeit",
        running: "läuft",
        done: "fertig",
        error: "Fehler",
        cancelled: "abgebrochen",
      };
      els.stageBadge.textContent = stageDe[activeStage] || activeStage;
    }
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
      const auth = snap.llm.auth || {};
      const sys = String(auth.system || "");
      const wrk = String(auth.worker_effective || auth.worker || "");
      const blocked = !!auth.session_auth_blocked;
      const placeholder = !!auth.placeholder_detected || sys === "placeholder" || wrk === "placeholder";
      const ok = (ds || ol) && !blocked;
      const tok =
        (snap.llm.prompt_tokens || 0) + (snap.llm.completion_tokens || 0);
      const viaTg = !!snap.llm.via_tollgate;
      const tg = snap.tollgate || {};
      const tgOk = tg.ok !== false;
      let label = "LLM: stub";
      if (blocked) label = "LLM: auth blocked";
      else if (placeholder && !ok) label = "LLM: key placeholder";
      else if (!ok && sys === "missing") label = "LLM: no key";
      else if (viaTg && (ds || ol)) {
        const route = (snap.llm.last_route && snap.llm.last_route.provider) || "";
        label = route ? "LLM: Tollgate/" + route : "LLM: Tollgate";
      } else if (ds && ol) label = "LLM: DeepSeek+Ollama";
      else if (ds) label = "LLM: DeepSeek";
      else if (ol) label = "LLM: Ollama";
      els.llmBadge.textContent = ok ? label + " · " + tok + " tok" : label;
      els.llmBadge.classList.toggle("has-key", ok);
      els.llmBadge.classList.toggle("auth-warn", placeholder && !ok);
      els.llmBadge.classList.toggle("auth-bad", blocked || (!ok && !placeholder && sys === "missing"));
      const tot = (tg.usage_totals || {});
      els.llmBadge.title =
        "via_tollgate=" +
        (viaTg ? "yes" : "no") +
        (tg.url ? " url=" + tg.url : " in-process") +
        " home=" +
        (tg.home || "?") +
        " tg.ok=" +
        (tgOk ? "yes" : "no") +
        (tot.calls != null ? " day_calls=" + tot.calls : "") +
        (tot.usd != null ? " day_usd=" + Number(tot.usd).toFixed(4) : "") +
        " deepseek=" +
        (ds ? "yes" : "no") +
        " ollama=" +
        (ol ? "yes" : "no") +
        " auth.system=" +
        (sys || "?") +
        " auth.worker=" +
        (wrk || "?") +
        " blocked=" +
        (blocked ? "yes" : "no") +
        (snap.llm.last_route && snap.llm.last_route.provider
          ? " last=" +
            snap.llm.last_route.provider +
            (snap.llm.last_route.model ? "/" + snap.llm.last_route.model : "")
          : "") +
        " prompt=" +
        (snap.llm.prompt_tokens || 0) +
        " completion=" +
        (snap.llm.completion_tokens || 0) +
        " — keys: User/Key.txt · desk: tollgate doctor";
    }
    updateCostBadge(snap.llm, snap.tollgate);
    if (els.memBadge && snap.memory_summary) {
      const short = String(snap.memory_summary).replace(/^HOT:\s*/i, "");
      const nodes =
        snap.canvas && snap.canvas.nodes != null
          ? " · canvas " + snap.canvas.nodes
          : "";
      els.memBadge.textContent = "Mem: " + short + nodes;
      els.memBadge.title = snap.memory_summary;
    }
    if (els.skillsBadge && snap.skills) {
      const sc = snap.skills.count != null ? snap.skills.count : 0;
      const en = snap.skills.enabled != null ? snap.skills.enabled : sc;
      els.skillsBadge.textContent = "Skills: " + en + "/" + sc;
      els.skillsBadge.title = "Playbook skills enabled/total — click to manage";
    }
    if (els.vecBadge && snap.vectors) {
      const emb = snap.vectors.embedder || "bow";
      els.vecBadge.textContent =
        "Vec: " +
        (snap.vectors.count || 0) +
        (emb && emb !== "bow" ? "·" + emb : "");
      const coldN = snap.cold && snap.cold.count != null ? snap.cold.count : "—";
      els.vecBadge.title =
        "Click: vector store · docs=" +
        (snap.vectors.count || 0) +
        " · embedder=" +
        emb +
        " · cold=" +
        coldN;
    }
    if (els.godBadge) {
      const on = !!(snap.god_mode && snap.god_mode.enabled);
      els.godBadge.textContent = on ? "God: an" : "God: aus";
      els.godBadge.classList.toggle("on", on);
      els.godBadge.title = on
        ? "God an — echte Desktop-Aktionen. Antippen schaltet aus."
        : "God aus — nur Trockenlauf. Antippen schaltet an (Nachfrage).";
    }
    if (els.coldBadge && snap.cold) {
      els.coldBadge.textContent = "Cold: " + (snap.cold.count || 0);
    }
    if (els.toolsBadge || document.getElementById("tools-run-history")) {
      // Prefer tool_calls; fall back to tool_log (live job strip) for count/why
      let calls = (p && p.tool_calls) || [];
      if ((!calls || !calls.length) && p && Array.isArray(p.tool_log) && p.tool_log.length) {
        calls = p.tool_log.map(function (e) {
          return {
            name: (e && (e.tool || e.name)) || "?",
            tool: (e && (e.tool || e.name)) || "?",
            ok: !e || e.ok !== false,
            reason: (e && e.reason) || "",
            mode: (e && e.mode) || "",
          };
        });
      }
      const n = calls.length;
      const names = calls
        .map(function (c) {
          return (c && (c.name || c.tool)) || "?";
        })
        .slice(0, 8);
      const uniq = [];
      names.forEach(function (nm) {
        if (uniq.indexOf(nm) < 0) uniq.push(nm);
      });
      const whys = [];
      calls.forEach(function (c) {
        const r = c && c.reason ? String(c.reason).trim() : "";
        if (r && whys.indexOf(r) < 0) whys.push(r);
      });
      let nFail = 0;
      calls.forEach(function (c) {
        if (c && c.ok === false) nFail += 1;
      });
      if (els.toolsBadge) {
        els.toolsBadge.textContent = n
          ? nFail
            ? "Werkzeuge: " + n + "·" + nFail + "!"
            : "Werkzeuge: " + n
          : "Werkzeuge: 0";
        els.toolsBadge.classList.toggle("has-calls", n > 0);
        els.toolsBadge.classList.toggle("has-fail", nFail > 0);
        els.toolsBadge.title =
          n > 0
            ? "This run: " +
              uniq.join(", ") +
              (n > uniq.length ? " (+)" : "") +
              " · " +
              n +
              " call(s)" +
              (nFail ? " · " + nFail + " failed" : "") +
              (whys.length ? " · why: " + whys.slice(0, 4).join("; ") : "") +
              " — click for history"
            : "No tool calls this run — click for Tools modal";
      }
      lastToolCalls = calls.slice();
      if (typeof renderToolsRunHistory === "function") {
        renderToolsRunHistory(calls);
      }
      if (n > 0 && (p.stage === "done" || p.stage === "work")) {
        const tk = uniq.join(",") + "|" + n + "|" + whys.slice(0, 2).join(";");
        if (tk !== lastToolsKey) {
          lastToolsKey = tk;
          toast(
            "Tools: " +
              uniq.join(", ") +
              " (" +
              n +
              ")" +
              (whys.length ? " — " + whys[0].slice(0, 60) : ""),
            nFail ? "error" : "ok"
          );
        }
      }
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

    // Tool strip in Box 3 (persists after job done)
    if (typeof renderToolStrip === "function") {
      renderToolStrip(p.tool_log || [], p.quality_notes || "");
    }
    // One toast when plan mode resolved (debug + user-facing clarity)
    if (p.stage === "done" && p.resolved_plan_mode) {
      const pk =
        String(p.resolved_plan_mode) +
        "|" +
        String(p.plan_html_score != null ? p.plan_html_score : "") +
        "|" +
        String((p.user_text || "").slice(0, 40));
      if (pk !== lastPlanKey) {
        lastPlanKey = pk;
        let msg = "Plan: " + p.resolved_plan_mode;
        if (p.plan_html_score != null && p.plan_html_score !== "") {
          msg += " · score=" + p.plan_html_score;
        }
        toast(msg, "info");
      }
    }
    // One toast if tools ran dry-run while God is off
    if (p.stage === "done" && p.tool_log && p.tool_log.length) {
      const dry = p.tool_log.filter(function (e) {
        return e && e.mode === "dry-run";
      }).length;
      const godOn = !!(snap.god_mode && snap.god_mode.enabled);
      const key = "dry:" + dry + ":" + (p.quality_notes || "").slice(0, 40);
      if (dry > 0 && !godOn && key !== lastDryRunKey) {
        lastDryRunKey = key;
        toast(
          dry + " Tool(s) dry-run — God-Mode an für echte Shell/GUI",
          "info"
        );
      }
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

    // Right Platzhalter: Flex feedback panel (dynamic buttons)
    if (typeof applyFlexReview === "function") {
      applyFlexReview(snap.flex_review || null, p);
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
      const lines = ["=== Brainstorm-Dialog ==="];
      p.brainstorm_turns.forEach(function (t) {
        const role =
          t.role === "user"
            ? "Du"
            : typeof box2AgentTabLabel === "function"
              ? box2AgentTabLabel(t.role)
              : "Brainstorm";
        lines.push("");
        lines.push(role + ":");
        lines.push(String(t.text || ""));
      });
      setBox2(lines.join("\n"));
    } else if (p.brainstorm_notes) {
      setBox2("=== Brainstorm ===\n" + p.brainstorm_notes);
    } else if (p.stage === "idle") {
      setBox2(
        "Noch keine Antwort. Senden = reden. Die Antwort erscheint hier."
      );
    }
    if (p.flex_notes && typeof setBox2Agent === "function") {
      setBox2Agent("flex", "=== Flex-Rückmeldung ===\n" + p.flex_notes, "Flex");
    }
    if (
      p.distilled_requirements &&
      p.distilled_requirements.length &&
      typeof setBox2Agent === "function"
    ) {
      const req = ["=== Anforderungen ==="].concat(
        p.distilled_requirements.map(function (r) {
          return "• " + r;
        })
      );
      setBox2Agent("coordinator", req.join("\n"), "Koordinator");
    }
    if (typeof renderBox2ReplyTabs === "function") {
      renderBox2ReplyTabs(p.brainstorm_turns);
    }

    /* Canonical conversation wins over brainstorm_turns / notes (same content as chat). */
    if (Array.isArray(p.messages) && p.messages.length) {
      renderPipelineMessages(
        p.messages,
        p.send_target || sendTarget || "brainstorm"
      );
    }

    lastCanExecute = !!p.can_execute;
    if (els.btnExecute) {
      els.btnExecute.disabled = !lastCanExecute || chatBusy;
    }

    renderBox3Workers(p);

    const flexBox = snap.flex_box1 || { questions: p.flex_questions || [] };
    if (typeof renderFlexBox1 === "function") {
      renderFlexBox1(flexBox);
    }
    const flexQs = Array.isArray(flexBox.questions) ? flexBox.questions : [];
    const flexShowsCoordinator = flexQs.some(function (q) {
      return (
        q &&
        q.text &&
        (q.agent_id === "coordinator" || q.task_id === "clarify")
      );
    });

    if (
      p.pending_question &&
      p.pending_question.text &&
      !flexShowsCoordinator
    ) {
      const qOpts =
        Array.isArray(p.pending_question.options) &&
        p.pending_question.options.length
          ? p.pending_question.options
          : null;
      showClarify(p.pending_question.text, qOpts);
    } else if (flexShowsCoordinator) {
      hideClarify();
    } else if (p.stage !== "clarify") {
      hideClarify();
      // Brainstorm / Flex options → Box1 pick cards
      if (
        typeof parseChoiceList === "function" &&
        typeof renderChoiceCards === "function" &&
        (p.stage === "brainstorm" ||
          p.stage === "idle" ||
          p.stage === "done" ||
          !p.stage)
      ) {
        let owner = "brainstorm";
        let picks = parseChoiceList(p.brainstorm_notes || "");
        if (!picks.length && Array.isArray(p.brainstorm_turns)) {
          for (let ti = p.brainstorm_turns.length - 1; ti >= 0; ti--) {
            const turn = p.brainstorm_turns[ti];
            if (turn && (turn.role === "assistant" || turn.role === "brainstorm")) {
              picks = parseChoiceList(turn.text || "");
              if (picks.length) break;
            }
          }
        }
        if (!picks.length && p.flex_notes) {
          picks = parseChoiceList(p.flex_notes);
          owner = "flex";
        }
        if (picks.length) {
          renderChoiceCards(
            picks,
            "suggest",
            owner === "flex" ? "Flex — antippen" : "Brainstorm — antippen",
            owner
          );
          if (typeof bindChoiceCardChrome === "function") bindChoiceCardChrome();
        } else if (typeof hideChoiceCards === "function") {
          const grid = document.getElementById("box1-choice-grid");
          if (grid && grid.querySelector(".mode-suggest")) hideChoiceCards();
        }
      }
    }

    if (typeof renderDeferredClarify === "function") {
      renderDeferredClarify(p.deferred_clarifies || []);
    }

    // Later / deferred clarify hygiene — surface reminder, no zombie box
    if (Array.isArray(p.deferred_clarifies) && p.deferred_clarifies.length) {
      const n = p.deferred_clarifies.length;
      const last = p.deferred_clarifies[n - 1] || {};
      const key =
        "def:" + n + ":" + String(last.id || "") + ":" + String(last.option || "");
      if (lastDeferredClarifyKey !== key) {
        lastDeferredClarifyKey = key;
        appendChat(
          "system",
          "Clarify deferred (" +
            n +
            "): " +
            String(last.text || "").slice(0, 120) +
            " — park only, no workers. Re-Send when ready."
        );
      }
    }

    // Only log pipeline errors once, and only while stage is error
    if (p.error && p.stage === "error") {
      if (p.error !== lastReportedPipelineError) {
        lastReportedPipelineError = p.error;
        const pe = String(p.error || "");
        const isProtect = /agent protection|budget|max_tokens|tollgate protect|fail-closed|protect —|🛑/i.test(
          pe
        );
        appendChat("system", (isProtect ? "🛑 Protect: " : "Error: ") + pe);
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
      maybeSpeakFlexSupport(p, snap);
    }
  }

