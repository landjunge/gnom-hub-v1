/* part: 01-api-snapshot-tts.js  lines 324-704 of app.js — edit parts, run scripts/build_ui_js.py */
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

  function applySnapshot(snap) {
    lastSnapshot = snap || null;
    if (!snap) return;
    applyUiPackExtras(snap);
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
      const auth = snap.llm.auth || {};
      const sys = String(auth.system || "");
      const wrk = String(auth.worker_effective || auth.worker || "");
      const blocked = !!auth.session_auth_blocked;
      const placeholder = !!auth.placeholder_detected || sys === "placeholder" || wrk === "placeholder";
      const ok = (ds || ol) && !blocked;
      const tok =
        (snap.llm.prompt_tokens || 0) + (snap.llm.completion_tokens || 0);
      let label = "LLM: stub";
      if (blocked) label = "LLM: auth blocked";
      else if (placeholder && !ok) label = "LLM: key placeholder";
      else if (!ok && sys === "missing") label = "LLM: no key";
      else if (ds && ol) label = "LLM: DeepSeek+Ollama";
      else if (ds) label = "LLM: DeepSeek";
      else if (ol) label = "LLM: Ollama";
      els.llmBadge.textContent = ok ? label + " · " + tok + " tok" : label;
      els.llmBadge.classList.toggle("has-key", ok);
      els.llmBadge.classList.toggle("auth-warn", placeholder && !ok);
      els.llmBadge.classList.toggle("auth-bad", blocked || (!ok && !placeholder && sys === "missing"));
      els.llmBadge.title =
        "deepseek=" +
        (ds ? "yes" : "no") +
        " ollama=" +
        (ol ? "yes" : "no") +
        " auth.system=" +
        (sys || "?") +
        " auth.worker=" +
        (wrk || "?") +
        " blocked=" +
        (blocked ? "yes" : "no") +
        " prompt=" +
        (snap.llm.prompt_tokens || 0) +
        " completion=" +
        (snap.llm.completion_tokens || 0) +
        " — set User/Key.txt DEEPSEEK_API_KEY (not sk-your-…)";
    }
    updateCostBadge(snap.llm);
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
      els.godBadge.textContent = on ? "God: ON · live" : "God: off · dry-run";
      els.godBadge.classList.toggle("on", on);
      els.godBadge.title = on
        ? "God-Mode ON — Shell/GUI/click echt. Klick zum Ausschalten."
        : "God-Mode off — Shell/GUI dry-run/blocked. Klick zum Einschalten.";
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
            ? "Tools: " + n + "·" + nFail + "!"
            : "Tools: " + n
          : "Tools: 0";
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
      const lines = ["=== Brainstorm dialogue ==="];
      p.brainstorm_turns.forEach(function (t) {
        const role = t.role === "user" ? "You" : "Brainstorm";
        lines.push("");
        lines.push(role + ":");
        lines.push(String(t.text || ""));
      });
      setBox2(lines.join("\n"));
    } else if (p.brainstorm_notes) {
      setBox2("=== Brainstorm ===\n" + p.brainstorm_notes);
    } else if (p.stage === "idle") {
      setBox2(
        "Brainstorm dialogue appears here.\n\n" +
          "1) Send messages to brainstorm freely\n" +
          "2) Press Execute when ready for workers"
      );
    }
    if (p.flex_notes && typeof setBox2Agent === "function") {
      setBox2Agent("flex", "=== Flex review ===\n" + p.flex_notes, "Flex");
    }
    if (
      p.distilled_requirements &&
      p.distilled_requirements.length &&
      typeof setBox2Agent === "function"
    ) {
      const req = ["=== Requirements ==="].concat(
        p.distilled_requirements.map(function (r) {
          return "• " + r;
        })
      );
      setBox2Agent("coordinator", req.join("\n"), "Coordinator");
    }

    lastCanExecute = !!p.can_execute;
    if (els.btnExecute) {
      els.btnExecute.disabled = !lastCanExecute || chatBusy;
    }

    renderBox3Workers(p);

    if (p.pending_question && p.pending_question.text) {
      showClarify(p.pending_question.text);
    } else if (p.stage !== "clarify") {
      hideClarify();
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
        appendChat("system", "Error: " + p.error);
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

  /** Recent spoken fingerprints — never queue the same text twice. */
  const ttsSpokenFp = {};
  let ttsToastAt = 0;
  let ttsPrepareInflight = {};

  function stripForSpeech(text) {
    let s = String(text || "");
    s = s.replace(/```[\s\S]*?```/g, " ");
    s = s.replace(/<!DOCTYPE[\s\S]*$/i, " ");
    s = s.replace(/<[^>]+>/g, " ");
    s = s.replace(/&[a-z]+;/gi, " ");
    s = s.replace(/\s+/g, " ").trim();
    // Keep spoken Gedanken short (product: not a lecture)
    return s.slice(0, 520);
  }

  function speechFp(text) {
    return String(text || "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 220);
  }

  function looksMostlyGermanClient(text) {
    const t = String(text || "").trim();
    if (!t) return true;
    if (/[äöüÄÖÜß]/.test(t)) return true;
    if (/\b(der|die|das|und|ich|nicht|eine|für|mit|soll|wird|auch|noch|nur|wenn|dann|bitte|hier|box)\b/i.test(t)) {
      return true;
    }
    const en = (t.match(/\b(the|and|with|for|this|that|should|would|could|build|page|user|about|from|have|will)\b/gi) || []).length;
    return en < 3;
  }

  function looksMostlyEnglishClient(text) {
    const t = String(text || "").trim();
    if (!t) return false;
    if (/[äöüÄÖÜß]/.test(t)) return false;
    if (/\b(der|die|das|und|ich|nicht|eine|für|mit|soll)\b/i.test(t)) return false;
    const en = (t.match(/\b(the|and|with|for|this|that|should|would|could|build|page|user|about|from|have|will)\b/gi) || []).length;
    return en >= 3;
  }

  /** DE desk: never return English. English → short German shell. */
  function germanizeThoughtForSpeech(text, label) {
    const clean = stripForSpeech(text);
    if (!clean) return "";
    if (uiLang === "en") return clean;
    if (looksMostlyEnglishClient(clean) || !looksMostlyGermanClient(clean)) {
      const who = label || "Agent";
      return (
        who +
        ". Kurzer Gedanke: ich priorisiere die User-Anfrage und bleibe knapp. " +
        "Details stehen in Box 2 und Box 3."
      );
    }
    return clean;
  }

  /** Split into speakable pieces (~sentence boundaries, max ~320 chars). */
  function chunkForSpeech(text) {
    const clean = stripForSpeech(text);
    if (!clean) return [];
    const max = 320;
    if (clean.length <= max) return [clean];
    const parts = [];
    let rest = clean;
    while (rest.length > max) {
      let cut = rest.lastIndexOf(". ", max);
      if (cut < max * 0.4) cut = rest.lastIndexOf(" ", max);
      if (cut < max * 0.3) cut = max;
      parts.push(rest.slice(0, cut + 1).trim());
      rest = rest.slice(cut + 1).trim();
    }
    if (rest) parts.push(rest);
    return parts.filter(Boolean);
  }

  function stopSpeech() {
    ttsQueue = [];
    ttsPumping = false;
    ttsPrepareInflight = {};
    try {
      if (window.speechSynthesis) window.speechSynthesis.cancel();
    } catch (_e) {
      /* ignore */
    }
    _pendingSpeech = "";
  }

  /** DE desk always de-DE. Never en-US when UI is German. */
  function pickTtsLang(_text) {
    if (uiLang === "en") return "en-US";
    return "de-DE";
  }

  function pickGermanVoice(lang) {
    const voices = window.speechSynthesis.getVoices() || [];
    if (!voices.length) return null;
    const want = (lang || "de-DE").slice(0, 2).toLowerCase();
    const match =
      voices.find(function (v) {
        return (v.lang || "").toLowerCase().indexOf(want) === 0;
      }) ||
      voices.find(function (v) {
        return (v.lang || "").toLowerCase().indexOf("de") === 0;
      });
    /* Never fall back to English voice on DE desk — better silence than EN voice */
    if (!match && uiLang !== "en") return null;
    return match || voices[0];
  }

  function alreadyQueuedOrSpoken(text) {
    const fp = speechFp(text);
    if (!fp) return true;
    if (ttsSpokenFp[fp]) return true;
    if (
      ttsQueue.some(function (q) {
        return speechFp(q) === fp;
      })
    ) {
      return true;
    }
    return false;
  }

  function markSpoken(text) {
    const fp = speechFp(text);
    if (!fp) return;
    ttsSpokenFp[fp] = Date.now();
    /* ring: keep last ~40 */
    const keys = Object.keys(ttsSpokenFp);
    if (keys.length > 40) {
      keys
        .sort(function (a, b) {
          return ttsSpokenFp[a] - ttsSpokenFp[b];
        })
        .slice(0, keys.length - 40)
        .forEach(function (k) {
          delete ttsSpokenFp[k];
        });
    }
  }

  /**
   * Speak exactly one queue item. Never cancels a previous utterance mid-stream
   * unless stopSpeech() was called. Next item starts only on onend.
   */
  function speakChunkNow(clean) {
    if (!window.speechSynthesis || !clean) {
      ttsPumping = false;
      pumpTtsQueue();
      return false;
    }
    /* Hard gate: DE desk must not utter English */
    let say = clean;
    if (uiLang !== "en" && looksMostlyEnglishClient(say)) {
      say = germanizeThoughtForSpeech(say, "Agent");
    }
    if (!say) {
      ttsPumping = false;
      pumpTtsQueue();
      return false;
    }
    try {
      const u = new SpeechSynthesisUtterance(say);
      u.lang = pickTtsLang(say);
      u.rate = 1.0;
      const match = pickGermanVoice(u.lang);
      if (match) u.voice = match;
      markSpoken(say);
      u.onstart = function () {
        ttsUnlocked = true;
      };
      u.onend = function () {
        ttsPumping = false;
        // Small pause between agents so speech does not blend
        setTimeout(function () {
          pumpTtsQueue();
        }, 180);
      };
      u.onerror = function (ev) {
        const err = (ev && ev.error) || "error";
        ttsPumping = false;
        if (err !== "interrupted" && err !== "canceled") {
          toast(
            uiLang === "de"
              ? "TTS blockiert — einmal in die Seite klicken"
              : "TTS blocked — click page once",
            "info"
          );
        }
        setTimeout(function () {
          pumpTtsQueue();
        }, 120);
      };
      window.speechSynthesis.speak(u);
      try {
        window.speechSynthesis.resume();
      } catch (_r) {
        /* ignore */
      }
      return true;
    } catch (_e) {
      ttsPumping = false;
      toast(
        uiLang === "de" ? "TTS fehlgeschlagen — Seite anklicken" : "TTS failed — click page",
        "info"
      );
      setTimeout(function () {
        pumpTtsQueue();
      }, 120);
      return false;
    }
  }

  /** Drain ttsQueue one utterance at a time (full finish before next). */
  function pumpTtsQueue() {
    if (ttsPumping) return;
    if (!window.speechSynthesis) return;
    if (window.speechSynthesis.speaking || window.speechSynthesis.pending) return;
    if (!ttsQueue.length) return;
    if (!ttsUnlocked) {
      /* Queue keeps the text — do NOT also copy into _pendingSpeech (was double). */
      const now = Date.now();
      if (now - ttsToastAt > 4000) {
        ttsToastAt = now;
        toast(
          uiLang === "de" ? "TTS: einmal klicken zum Hören" : "TTS: click anywhere to hear",
          "info"
        );
      }
      return;
    }
    const next = ttsQueue.shift();
    if (!next) return;
    ttsPumping = true;
    speakChunkNow(next);
  }

  /**
   * Enqueue already-prepared text (must be German when desk is DE).
   * Single queue only — never _pendingSpeech + queue (double speak bug).
   */
  function speakOrQueuePrepared(text) {
    let cleaned = stripForSpeech(text);
    if (!cleaned) return;
    if (uiLang !== "en") {
      if (looksMostlyEnglishClient(cleaned)) {
        cleaned = germanizeThoughtForSpeech(cleaned, "Agent");
      }
      if (!cleaned || looksMostlyEnglishClient(cleaned)) return;
    }
    const pieces = chunkForSpeech(cleaned);
    if (!pieces.length) return;
    pieces.forEach(function (p) {
      if (alreadyQueuedOrSpoken(p)) return;
      ttsQueue.push(p);
    });
    if (ttsUnlocked) {
      pumpTtsQueue();
    } else {
      const now = Date.now();
      if (now - ttsToastAt > 4000) {
        ttsToastAt = now;
        toast(
          uiLang === "de" ? "TTS: einmal klicken zum Hören" : "TTS: click anywhere to hear",
          "info"
        );
      }
    }
  }

  /**
   * DE desk: only German leaves the speaker.
   * Hub often already translated thoughts — skip prepare if already DE (no EN then DE).
   */
  function speakOrQueue(text) {
    const raw = String(text || "").trim();
    if (!raw) return;
    if (uiLang === "en") {
      speakOrQueuePrepared(raw);
      return;
    }
    /* Already German (hub translated) → speak once, no second prepare pass */
    if (looksMostlyGermanClient(raw) && !looksMostlyEnglishClient(raw)) {
      speakOrQueuePrepared(raw);
      return;
    }
    const fp = speechFp(raw);
    if (ttsPrepareInflight[fp] || alreadyQueuedOrSpoken(raw)) return;
    ttsPrepareInflight[fp] = true;
    api("POST", "/api/tts/prepare", { text: raw, lang: "de" })
      .then(function (r) {
        delete ttsPrepareInflight[fp];
        const de = stripForSpeech((r && r.text) || "");
        if (de && !looksMostlyEnglishClient(de)) {
          speakOrQueuePrepared(de);
        } else {
          speakOrQueuePrepared(germanizeThoughtForSpeech(raw, "Agent"));
        }
      })
      .catch(function () {
        delete ttsPrepareInflight[fp];
        /* Never speak English raw on DE desk */
        speakOrQueuePrepared(germanizeThoughtForSpeech(raw, "Agent"));
      });
  }

  /** Unlock + optional short DE line from a real click (no pending re-queue). */
  function speakNow(text) {
    ttsUnlocked = true;
    _pendingSpeech = "";
    if (text) {
      speakOrQueuePrepared(text);
    } else {
      pumpTtsQueue();
    }
    return true;
  }

  if (typeof window !== "undefined" && window.speechSynthesis) {
    try {
      window.speechSynthesis.getVoices();
      window.speechSynthesis.onvoiceschanged = function () {
        window.speechSynthesis.getVoices();
      };
    } catch (_e) {
      /* ignore */
    }
    document.addEventListener(
      "click",
      function () {
        /* Only unlock + drain queue. Never re-push pending (caused double TTS). */
        ttsUnlocked = true;
        _pendingSpeech = "";
        pumpTtsQueue();
      },
      true
    );
  }

  /**
   * TTS speaks agent *thoughts* (reasoning), not the written Box text / HTML.
   * Flex is handled by maybeSpeakFlexSupport (how/why support) — not listed here.
   */
  function maybeSpeakPipeline(p, snap) {
    const thoughts =
      (snap && snap.agent_thoughts) ||
      (p && p.agent_thoughts) ||
      lastAgentThoughts ||
      {};
    const thoughtKey = Object.keys(thoughts)
      .sort()
      .map(function (k) {
        const t = String(thoughts[k] || "");
        return k + ":" + t.length + ":" + t.slice(0, 24) + ":" + t.slice(-24);
      })
      .join("|");
    const key =
      (p.stage || "") +
      "|" +
      thoughtKey +
      "|" +
      ((p.worker_outputs && p.worker_outputs.length) || 0);
    if (key === lastSpokenKey) return;
    const de = uiLang !== "en";
    const labels = {
      brainstorm: "Brainstorm",
      memory: "Memory",
      coordinator: de ? "Koordinator" : "Coordinator",
      worker1: "Worker 1",
      worker2: "Worker 2",
      worker3: "Worker 3",
      worker4: "Worker 4",
    };
    /* flex omitted on purpose → maybeSpeakFlexSupport */
    const order = [
      "brainstorm",
      "memory",
      "coordinator",
      "worker1",
      "worker2",
      "worker3",
      "worker4",
    ];
    let any = false;
    order.forEach(function (agentId) {
      const a = findAgent(agentId);
      if (!a || !a.tts) return;
      const t = thoughts[agentId];
      if (!t || !String(t).trim()) return;
      any = true;
      const label = labels[agentId] || a.label || agentId;
      const body = stripForSpeech(String(t));
      if (!body) return;
      speakOrQueue(label + ". " + body);
    });
    if (any) lastSpokenKey = key;
  }

  /**
   * Flex TTS: user wants to hear HOW Flex supports them and WHY.
   * Prefer flex_notes (companion reasoning) over raw thought; DE only, once.
   */
  let lastFlexSupportKey = "";

  function maybeSpeakFlexSupport(p, snap) {
    const a = typeof findAgent === "function" ? findAgent("flex") : null;
    if (!a || !a.tts) return;
    p = p || {};
    const thoughts =
      (snap && snap.agent_thoughts) || lastAgentThoughts || {};
    const notes = stripForSpeech(p.flex_notes || "");
    const thought = stripForSpeech(thoughts.flex || "");
    /* Notes = was ich über dich weiß / für die Worker — the support story */
    let body = notes || thought;
    if (!body) return;
    body = body
      .replace(/^#+\s*/gm, "")
      .replace(/\*\*/g, "")
      .replace(/`+/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 500);
    if (!body) return;
    const key =
      "flex-support|" +
      (p.stage || "") +
      "|" +
      body.length +
      "|" +
      body.slice(0, 40) +
      "|" +
      body.slice(-40);
    if (key === lastFlexSupportKey) return;
    lastFlexSupportKey = key;

    /* Personal companion only — not product pitch */
    let spoken = "Flex, nur für dich. " + body;
    if (p.stage === "done") {
      spoken +=
        " Wenn du magst: sag mir kurz, ob das Ergebnis für dich passt.";
    }
    speakOrQueue(spoken);
  }

  /**
   * Flex panel in right Platzhalter (chat-mod-platz-r).
   * After done: quality feedback + learn / re-brainstorm / re-build.
   */
  let _lastFlexReviewKey = "";

  function applyFlexReview(panel, pipeline) {
    const root = document.getElementById("flex-review");
    const titleEl = document.getElementById("flex-review-title");
    const badgeEl = document.getElementById("flex-review-badge");
    const qEl = document.getElementById("flex-review-q");
    const btnsEl = document.getElementById("flex-review-btns");
    const hintEl = document.getElementById("flex-review-hint");
    if (!root || !btnsEl) return;

    const p = panel || {};
    const active = !!p.active;
    root.classList.toggle("is-active", active);
    root.classList.toggle("ring-1", active);
    root.classList.toggle("ring-gnom-flex/40", active);
    if (titleEl) titleEl.textContent = p.title || "Flex";
    if (badgeEl) {
      badgeEl.hidden = !active;
      badgeEl.textContent = active ? "Feedback" : "";
    }
    const qText =
      p.question ||
      "Nach einem Ergebnis fragt Flex hier nach Feedback.";
    if (qEl) qEl.textContent = qText;
    if (hintEl) {
      hintEl.textContent =
        p.hint || "Rechts = Flex lernt · Notiz + Button = Wunsch";
    }
    const noteRow = document.getElementById("flex-review-note-row");
    if (noteRow) noteRow.hidden = !active;

    btnsEl.innerHTML = "";
    const buttons = active ? p.buttons || [] : [];
    if (!active || !buttons.length) {
      _lastFlexReviewKey = "";
      return;
    }
    buttons.forEach(function (b) {
      if (!b || !b.id) return;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className =
        "flex-review-btn rounded-md border border-gnom-border bg-gnom-card px-2.5 py-1.5 " +
        "text-xs leading-tight text-gnom-text transition hover:border-gnom-flex hover:text-gnom-flex " +
        (String(b.action || "") === "execute"
          ? "border-gnom-ok/50 hover:border-gnom-ok hover:text-gnom-ok "
          : String(b.action || "") === "brainstorm"
            ? "border-gnom-accent/50 hover:border-gnom-accent hover:text-gnom-accent "
            : "");
      btn.dataset.id = String(b.id);
      btn.dataset.action = String(b.action || "learn");
      btn.textContent = String(b.label || b.id);
      btn.title = String(b.learn || b.prompt || b.label || "");
      btn.addEventListener("click", function () {
        onFlexFeedbackClick(b);
      });
      btnsEl.appendChild(btn);
    });

    /* Panel is visual only. Flex voice = maybeSpeakFlexSupport (how/why). */
    _lastFlexReviewKey =
      "flex-panel|" +
      String(p.question || "").slice(0, 80) +
      "|" +
      buttons
        .map(function (b) {
          return b.id;
        })
        .join(",");
  }

  async function onFlexFeedbackClick(btnSpec) {
    const id = (btnSpec && btnSpec.id) || "";
    const label = (btnSpec && btnSpec.label) || id;
    try {
      toast("Flex… " + label, "info");
      const noteEl = document.getElementById("flex-review-note");
      const note = (noteEl && noteEl.value ? noteEl.value : "").trim();
      const res = await api("POST", "/api/flex/feedback", {
        button_id: id,
        label: label,
        note: note,
      });
      if (noteEl && res.ok) noteEl.value = "";
      if (res.message) appendChat("system", res.message);
      // Flex answers by voice (DE) after each button
      if (res.message && typeof speakOrQueue === "function") {
        speakOrQueue("Flex. " + String(res.message));
      }
      if (res.learned && res.learn_text) {
        toast("Gelernt: " + String(res.learn_text).slice(0, 80), "ok");
      } else if (res.action === "learn") {
        toast(res.message || "Flex Feedback", "ok");
      }
      if (res.snapshot) {
        applySnapshot(res.snapshot);
      } else if (res.flex_review) {
        applyFlexReview(res.flex_review, null);
      }
      // Rebuild started as job
      if (res.job && res.job.job_id && typeof pollJob === "function") {
        setChatBusy(true);
        try {
          const job = await pollJob(res.job.job_id, 360000);
          const snap = job.snapshot || (await api("GET", "/api/state"));
          applySnapshot(snap);
          if (typeof focusBox3 === "function") focusBox3();
        } finally {
          setChatBusy(false);
        }
      }
      if (res.action === "brainstorm" && typeof focusBox3 === "function") {
        // Box 2 has new notes; user may hit Execute next via Flex rebuild
        toast("Brainstorm aktualisiert — bei Bedarf „Nochmal bauen“", "ok");
      }
    } catch (err) {
      toast("Flex Feedback: " + (err.message || err), "error");
    }
  }


  // Save free-text flag as Flex wish without rebuilding
  (function wireFlexNoteSave() {
    const btn = document.getElementById("flex-review-note-save");
    if (!btn || btn.dataset.wired) return;
    btn.dataset.wired = "1";
    btn.addEventListener("click", async function () {
      const noteEl = document.getElementById("flex-review-note");
      const note = (noteEl && noteEl.value ? noteEl.value : "").trim();
      if (!note) {
        toast("Notiz eingeben, dann Merken", "info");
        return;
      }
      try {
        const res = await api("POST", "/api/flex/feedback", {
          button_id: "custom_note",
          label: "Notiz",
          note: note,
        });
        if (res.message) appendChat("system", res.message);
        if (noteEl) noteEl.value = "";
        toast(res.learned ? "Wish gespeichert" : res.message || "Flex", "ok");
        if (res.snapshot) applySnapshot(res.snapshot);
      } catch (err) {
        toast("Merken: " + (err.message || err), "error");
      }
    });
  })();

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
      // Do NOT speak after await — gesture is gone (Chrome blocks it)
      renderCards();
      toast(on ? "TTS on: " + (a.label || id) : "TTS off: " + (a.label || id), on ? "ok" : "info");
    } catch (err) {
      appendChat("system", "TTS save failed: " + err.message);
      toast("TTS save failed", "error");
    }
  }

