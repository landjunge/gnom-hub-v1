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
      try {
        const j = await res.json();
        detail = j.detail || JSON.stringify(j);
      } catch (e) { /* ignore */ }
      toast(String(detail), "error");
      throw new Error(detail);
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
      const ok = ds || ol;
      const tok =
        (snap.llm.prompt_tokens || 0) + (snap.llm.completion_tokens || 0);
      let label = "LLM: stub";
      if (ds && ol) label = "LLM: DeepSeek+Ollama";
      else if (ds) label = "LLM: DeepSeek";
      else if (ol) label = "LLM: Ollama";
      els.llmBadge.textContent = ok ? label + " · " + tok + " tok" : label;
      els.llmBadge.classList.toggle("has-key", ok);
      els.llmBadge.title =
        "prompt=" +
        (snap.llm.prompt_tokens || 0) +
        " completion=" +
        (snap.llm.completion_tokens || 0);
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
    if (els.vecBadge && snap.vectors) {
      els.vecBadge.textContent = "Vec: " + (snap.vectors.count || 0);
      const coldN = snap.cold && snap.cold.count != null ? snap.cold.count : "—";
      els.vecBadge.title = "Click: vector store · docs=" + (snap.vectors.count || 0) + " · cold=" + coldN;
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
    }
  }

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

  /** If model still emits English thoughts, prefer a short German fallback for voice. */
  function germanizeThoughtForSpeech(text, label) {
    const clean = stripForSpeech(text);
    if (!clean) return "";
    const looksEn =
      /\b(the|and|with|for|this|that|should|would|build|page|user)\b/i.test(clean) &&
      !/[äöüÄÖÜß]/.test(clean) &&
      !/\b(der|die|das|und|ich|nicht|eine|für|mit|soll)\b/i.test(clean);
    if (looksEn && (uiLang === "de" || uiLang !== "en")) {
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
    try {
      if (window.speechSynthesis) window.speechSynthesis.cancel();
    } catch (_e) {
      /* ignore */
    }
    pendingSpeech = "";
  }

  /**
   * Prefer German TTS.
   * Default de-DE unless UI is explicitly English and text looks English-only.
   */
  function pickTtsLang(text) {
    const clean = String(text || "");
    if (uiLang === "de" || /[äöüÄÖÜß]/.test(clean)) return "de-DE";
    if (/\b(der|die|das|und|ich|nicht|eine|für|mit)\b/i.test(clean)) return "de-DE";
    if (uiLang === "en") return "en-US";
    return "de-DE";
  }

  function pickGermanVoice(lang) {
    const voices = window.speechSynthesis.getVoices() || [];
    if (!voices.length) return null;
    const want = (lang || "de-DE").slice(0, 2).toLowerCase();
    return (
      voices.find(function (v) {
        return (v.lang || "").toLowerCase().indexOf(want) === 0;
      }) ||
      voices.find(function (v) {
        return (v.lang || "").toLowerCase().indexOf("de") === 0;
      }) ||
      voices[0]
    );
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
    try {
      const u = new SpeechSynthesisUtterance(clean);
      u.lang = pickTtsLang(clean);
      u.rate = 1.0;
      const match = pickGermanVoice(u.lang);
      if (match) u.voice = match;
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
      pendingSpeech = ttsQueue[0] || pendingSpeech;
      toast(
        uiLang === "de" ? "TTS: einmal klicken zum Hören" : "TTS: click anywhere to hear",
        "info"
      );
      return;
    }
    const next = ttsQueue.shift();
    if (!next) return;
    ttsPumping = true;
    speakChunkNow(next);
  }

  /**
   * Enqueue already-prepared text (must be German when desk is DE).
   * Does NOT cancel current speech.
   */
  function speakOrQueuePrepared(text) {
    const pieces = chunkForSpeech(text);
    if (!pieces.length) return;
    pieces.forEach(function (p) {
      ttsQueue.push(p);
    });
    if (ttsUnlocked) {
      pumpTtsQueue();
    } else {
      pendingSpeech = pieces[0];
      toast(
        uiLang === "de" ? "TTS: einmal klicken zum Hören" : "TTS: click anywhere to hear",
        "info"
      );
    }
  }

  /**
   * Translate via hub (EN→DE) then enqueue. Always translate-before-TTS on DE desk.
   */
  function speakOrQueue(text) {
    const raw = String(text || "").trim();
    if (!raw) return;
    const wantDe = uiLang !== "en";
    if (!wantDe) {
      speakOrQueuePrepared(raw);
      return;
    }
    // Server: English agent thoughts → German, then speech
    api("POST", "/api/tts/prepare", { text: raw, lang: "de" })
      .then(function (r) {
        const de = (r && r.text) || raw;
        speakOrQueuePrepared(de);
      })
      .catch(function () {
        // Offline fallback: short DE shell if still looks English
        speakOrQueuePrepared(germanizeThoughtForSpeech(raw, "Agent") || raw);
      });
  }

  /** Immediate speak from a real click handler (unlock + optional text). */
  function speakNow(text) {
    ttsUnlocked = true;
    if (text) {
      const pieces = chunkForSpeech(text);
      pieces.forEach(function (p) {
        ttsQueue.push(p);
      });
    }
    // If something is pending from autoplay block, enqueue it
    if (pendingSpeech) {
      const p = pendingSpeech;
      pendingSpeech = "";
      chunkForSpeech(p).forEach(function (c) {
        ttsQueue.push(c);
      });
    }
    pumpTtsQueue();
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
        ttsUnlocked = true;
        if (pendingSpeech) {
          const t = pendingSpeech;
          pendingSpeech = "";
          chunkForSpeech(t).forEach(function (c) {
            ttsQueue.push(c);
          });
        }
        pumpTtsQueue();
      },
      true
    );
  }

  /**
   * TTS speaks agent *thoughts* (reasoning), not the written Box text / HTML.
   * Each agent is a separate queue item so speech finishes fully before the next.
   */
  function maybeSpeakPipeline(p, snap) {
    const thoughts =
      (snap && snap.agent_thoughts) ||
      (p && p.agent_thoughts) ||
      lastAgentThoughts ||
      {};
    const thoughtKey = Object.keys(thoughts)
      .map(function (k) {
        return k + ":" + String(thoughts[k] || "").slice(0, 40);
      })
      .join("|");
    const key =
      (p.stage || "") +
      "|" +
      thoughtKey +
      "|" +
      ((p.worker_outputs && p.worker_outputs.length) || 0);
    if (key === lastSpokenKey) return;
    const de = uiLang === "de";
    const labels = {
      brainstorm: de ? "Brainstorm" : "Brainstorm",
      memory: de ? "Memory" : "Memory",
      flex: "Flex",
      coordinator: de ? "Koordinator" : "Coordinator",
      worker1: de ? "Worker 1" : "Worker 1",
      worker2: "Worker 2",
      worker3: "Worker 3",
      worker4: "Worker 4",
    };
    const order = [
      "brainstorm",
      "memory",
      "flex",
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
      // One agent = queue item(s); never speak English monologues on a DE desk
      const spoken = germanizeThoughtForSpeech(String(t), label);
      if (spoken) speakOrQueue(spoken);
    });
    if (any) lastSpokenKey = key;
  }

  /**
   * Flex panel in right Platzhalter (chat-mod-platz-r).
   * After done: quality feedback + learn / re-brainstorm / re-build.
   */
  let lastFlexReviewKey = "";

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
      lastFlexReviewKey = "";
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

    // Flex speaks the review question once (German, after translate pipeline)
    const speakKey =
      "flex|" +
      String(p.question || "").slice(0, 80) +
      "|" +
      buttons.map(function (b) {
        return b.id;
      }).join(",");
    if (speakKey !== lastFlexReviewKey) {
      lastFlexReviewKey = speakKey;
      const labels = buttons
        .slice(0, 5)
        .map(function (b) {
          return b.label;
        })
        .join(", ");
      const spoken =
        "Flex. " +
        String(qText).replace(/\n/g, " ") +
        " Wähle: " +
        labels +
        ".";
      if (typeof speakOrQueue === "function") {
        speakOrQueue(spoken);
      }
    }
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

