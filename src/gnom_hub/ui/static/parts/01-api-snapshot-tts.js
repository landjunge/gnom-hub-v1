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

    // TTS after brainstorm turn and after full execute
    if (p.stage === "done" || p.stage === "brainstorm") {
      maybeSpeakPipeline(p);
    }
  }

  function stripForSpeech(text) {
    let s = String(text || "");
    s = s.replace(/```[\s\S]*?```/g, " ");
    s = s.replace(/<!DOCTYPE[\s\S]*$/i, " ");
    s = s.replace(/<[^>]+>/g, " ");
    s = s.replace(/&[a-z]+;/gi, " ");
    s = s.replace(/\s+/g, " ").trim();
    return s.slice(0, 400);
  }

  function stopSpeech() {
    try {
      if (window.speechSynthesis) window.speechSynthesis.cancel();
    } catch (_e) {
      /* ignore */
    }
    pendingSpeech = "";
  }

  /** Must run inside a click/change handler — not after await. */
  function speakNow(text) {
    if (!window.speechSynthesis) {
      toast("TTS not available in this browser", "info");
      return false;
    }
    const clean = stripForSpeech(text);
    if (!clean) return false;
    try {
      // Do not cancel+speak in a broken way: cancel only if busy
      if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
        window.speechSynthesis.cancel();
      }
      const u = new SpeechSynthesisUtterance(clean);
      u.lang = /[äöüÄÖÜß]/.test(clean) ? "de-DE" : "en-US";
      u.rate = 1.05;
      const voices = window.speechSynthesis.getVoices() || [];
      if (voices.length) {
        const want = u.lang.slice(0, 2).toLowerCase();
        const match =
          voices.find(function (v) {
            return (v.lang || "").toLowerCase().indexOf(want) === 0;
          }) || voices[0];
        if (match) u.voice = match;
      }
      u.onstart = function () {
        ttsUnlocked = true;
      };
      u.onerror = function (ev) {
        const err = (ev && ev.error) || "error";
        if (err !== "interrupted" && err !== "canceled") {
          pendingSpeech = clean;
          toast("TTS blocked — click page once, then enable TTS again", "info");
        }
      };
      window.speechSynthesis.speak(u);
      // Some Chrome builds need resume after speak
      try {
        window.speechSynthesis.resume();
      } catch (_r) {
        /* ignore */
      }
      return true;
    } catch (_e) {
      pendingSpeech = clean;
      toast("TTS failed — click page and try again", "info");
      return false;
    }
  }

  function speakOrQueue(text) {
    const clean = stripForSpeech(text);
    if (!clean) return;
    if (ttsUnlocked) {
      speakNow(clean);
    } else {
      pendingSpeech = clean;
      toast("TTS: click anywhere to hear", "info");
    }
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
        if (pendingSpeech) {
          const t = pendingSpeech;
          pendingSpeech = "";
          speakNow(t);
        }
      },
      true
    );
  }

  function maybeSpeakPipeline(p) {
    const key =
      (p.stage || "") +
      "|" +
      (p.brainstorm_notes || "").slice(0, 48) +
      "|" +
      ((p.worker_results && p.worker_results[0]) || "").slice(0, 48) +
      "|" +
      ((p.worker_outputs && p.worker_outputs.length) || 0);
    if (key === lastSpokenKey) return;
    const chunks = [];
    const b = findAgent("brainstorm");
    if (b && b.tts && p.brainstorm_notes) {
      chunks.push("Brainstorm. " + stripForSpeech(p.brainstorm_notes));
    }
    const f = findAgent("flex");
    if (f && f.tts && p.flex_notes) {
      chunks.push("Flex. " + stripForSpeech(p.flex_notes));
    }
    (p.worker_outputs || []).forEach(function (o, i) {
      const a = findAgent(o.worker || "worker" + (i + 1));
      if (a && a.tts && o.result) {
        chunks.push(
          (a.label || o.worker || "Worker") + ". " + stripForSpeech(o.result)
        );
      }
    });
    if (!chunks.length && p.worker_results) {
      p.worker_results.forEach(function (r, i) {
        const a = findAgent("worker" + (i + 1));
        if (a && a.tts && r) {
          chunks.push((a.label || "Worker") + ". " + stripForSpeech(r));
        }
      });
    }
    if (chunks.length) {
      lastSpokenKey = key;
      speakOrQueue(chunks.join(" "));
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
      // Do NOT speak after await — gesture is gone (Chrome blocks it)
      renderCards();
      toast(on ? "TTS on: " + (a.label || id) : "TTS off: " + (a.label || id), on ? "ok" : "info");
    } catch (err) {
      appendChat("system", "TTS save failed: " + err.message);
      toast("TTS save failed", "error");
    }
  }

