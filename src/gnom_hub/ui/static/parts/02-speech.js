/* part: 02-speech.js — edit parts, run scripts/build_ui_js.py */
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

  const AGENT_TTS_ORDER = [
    "brainstorm",
    "flex",
    "coordinator",
    "memory",
    "worker1",
    "worker2",
    "worker3",
    "worker4",
  ];

  function agentTtsIndex(agentId) {
    const i = AGENT_TTS_ORDER.indexOf(String(agentId || ""));
    return i >= 0 ? i : 0;
  }

  function voicesForLang(lang) {
    const voices = window.speechSynthesis.getVoices() || [];
    const want = (lang || "de-DE").slice(0, 2).toLowerCase();
    const matched = voices.filter(function (v) {
      return (v.lang || "").toLowerCase().indexOf(want) === 0;
    });
    if (matched.length) return matched;
    if (uiLang !== "en") {
      return voices.filter(function (v) {
        return (v.lang || "").toLowerCase().indexOf("de") === 0;
      });
    }
    return voices;
  }

  function pickVoiceForAgent(agentId, lang) {
    const list = voicesForLang(lang);
    if (!list.length) return pickGermanVoice(lang);
    return list[agentTtsIndex(agentId) % list.length];
  }

  function pitchForAgent(agentId) {
    return 0.88 + (agentTtsIndex(agentId) % 6) * 0.05;
  }

  function queueItemText(item) {
    if (typeof item === "string") return item;
    return String((item && item.text) || "");
  }

  function alreadyQueuedOrSpoken(text) {
    const fp = speechFp(text);
    if (!fp) return true;
    if (ttsSpokenFp[fp]) return true;
    if (
      ttsQueue.some(function (q) {
        return speechFp(queueItemText(q)) === fp;
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
  function speakChunkNow(item) {
    const clean = queueItemText(item);
    const agentId = item && typeof item === "object" ? item.agentId : "";
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
      u.pitch = pitchForAgent(agentId);
      const match = pickVoiceForAgent(agentId, u.lang);
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
  function speakOrQueuePrepared(text, agentId) {
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
      ttsQueue.push({ text: p, agentId: String(agentId || "") });
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
  function speakOrQueue(text, agentId) {
    const raw = String(text || "").trim();
    if (!raw) return;
    if (uiLang === "en") {
      speakOrQueuePrepared(raw, agentId);
      return;
    }
    /* Already German (hub translated) → speak once, no second prepare pass */
    if (looksMostlyGermanClient(raw) && !looksMostlyEnglishClient(raw)) {
      speakOrQueuePrepared(raw, agentId);
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
          speakOrQueuePrepared(de, agentId);
        } else {
          speakOrQueuePrepared(germanizeThoughtForSpeech(raw, "Agent"), agentId);
        }
      })
      .catch(function () {
        delete ttsPrepareInflight[fp];
        /* Never speak English raw on DE desk */
        speakOrQueuePrepared(germanizeThoughtForSpeech(raw, "Agent"), agentId);
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
      speakOrQueue(label + ". " + body, agentId);
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
    speakOrQueue(spoken, "flex");
  }

  /**
   * Flex panel in Box 1 (placeholder area stays).
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
    root.hidden = !active;
    if (typeof markOwner === "function") markOwner(root, "flex");
    else root.dataset.agent = "flex";
    root.classList.toggle("is-active", active);
    root.classList.toggle("ring-1", active);
    root.classList.toggle("ring-gnom-flex/40", active);
    // Ensure Box1 live layer is visible when Flex wants feedback
    if (active) {
      try {
        const live = document.getElementById("box1-layer-live");
        if (live && typeof showInfoLayer === "function") {
          showInfoLayer("live");
        } else if (live) {
          document.querySelectorAll("#box1-content .info-layer").forEach(function (l) {
            l.hidden = l !== live;
            l.classList.toggle("is-active", l === live);
          });
        }
      } catch (_e) {
        /* ignore */
      }
    }
    if (titleEl) titleEl.textContent = p.title || "Flex";
    if (badgeEl) {
      badgeEl.hidden = !active;
      badgeEl.textContent = active ? "Rückmeldung" : "";
    }
    const qText =
      p.question ||
      "Nach einem Ergebnis fragt Flex hier nach Rückmeldung.";
    if (qEl) qEl.textContent = qText;
    if (hintEl) {
      hintEl.textContent =
        p.hint || "Box 1 = Flex lernt · Notiz + Button = Wunsch";
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
        "flex-review-btn border border-gnom-border bg-gnom-card px-2.5 py-1.5 " +
        "text-xs leading-tight text-gnom-text transition hover:border-gnom-flex hover:text-gnom-flex " +
        (String(b.action || "") === "start_work"
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
      } else if (res.action === "start_work") {
        toast(res.message || "Flex fragt in Box 1 — erst Ja, dann bauen", "ok");
      }
      if (res.snapshot) {
        applySnapshot(res.snapshot);
      } else if (res.flex_review) {
        applyFlexReview(res.flex_review, null);
      }
      if (res.action === "brainstorm" && typeof focusBox3 === "function") {
        // Box 2 has new notes; „Nochmal bauen“ asks Box 1, does not Execute
        toast("Brainstorm aktualisiert — bei Bedarf „Nochmal bauen“ (Box 1)", "ok");
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

