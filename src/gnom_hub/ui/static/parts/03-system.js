/* part: 03-system.js — edit parts, run scripts/build_ui_js.py */
  function dockIntoBoxes(el) {
    const boxes = document.querySelector(".boxes");
    if (!el || !boxes) return;
    if (el.parentNode !== boxes) boxes.appendChild(el);
    el.classList.add("in-boxes");
  }

  function openTuneModal(id) {
    const a = findAgent(id);
    const layer = document.getElementById("tune-layer");
    if (!a || !layer) return;
    tuneAgentId = id;
    const title = document.getElementById("tune-title");
    if (title) title.textContent = a.label + " — Regler";
    const promptEl = document.getElementById("tune-prompt");
    if (promptEl)
      promptEl.value = a.system_prompt || DEFAULT_PROMPTS[id] || "";
    const modelEl = document.getElementById("tune-model");
    if (modelEl) modelEl.value = a.model || "deepseek-chat";
    const keyEl = document.getElementById("tune-key");
    if (keyEl) keyEl.value = "";
    const setRange = function (idEl, valEl, v, def, digits) {
      const el = document.getElementById(idEl);
      if (!el) return;
      const num = v != null ? Number(v) : def;
      el.value = String(num);
      const valNode = document.getElementById(valEl);
      if (valNode)
        valNode.textContent =
          digits === 0 ? String(Math.round(num)) : Number(num).toFixed(digits);
    };
    setRange("tune-temp", "tune-temp-val", a.temperature, SLIDER_DEFAULTS.temperature, 2);
    setRange("tune-topp", "tune-topp-val", a.top_p, SLIDER_DEFAULTS.top_p, 2);
    setRange("tune-maxtok", "tune-maxtok-val", a.max_tokens, SLIDER_DEFAULTS.max_tokens, 0);
    setRange("tune-freq", "tune-freq-val", a.frequency_penalty, SLIDER_DEFAULTS.frequency, 2);
    setRange("tune-pres", "tune-pres-val", a.presence_penalty, SLIDER_DEFAULTS.presence, 2);
    const tts = document.getElementById("tune-tts");
    if (tts) tts.checked = !!a.tts;
    layer.hidden = false;
    document.body.classList.add("tune-open");
    showSliderTip("temperature");
  }

  function closeTuneModal() {
    const layer = document.getElementById("tune-layer");
    if (layer) layer.hidden = true;
    document.body.classList.remove("tune-open");
    tuneAgentId = null;
  }

  function showSliderTip(key) {
    const tip = SLIDER_TIPS[key];
    if (!tip) return;
    // Box 1 layer "Regler" — dynamic info for active control
    if (typeof showInfoLayer === "function") showInfoLayer("tune");
    const title = document.getElementById("tune-tip-title");
    const how = document.getElementById("tune-tip-how");
    const ex = document.getElementById("tune-tip-example");
    const val = document.getElementById("tune-tip-value");
    if (title) title.textContent = "Regler: " + key;
    if (how) how.textContent = tip;
    if (ex)
      ex.textContent =
        "Schieber — Info live in Box 1. Regler-UI in Box 3.";
    // current value if range exists
    const map = {
      temperature: "tune-temp",
      top_p: "tune-topp",
      max_tokens: "tune-maxtok",
      frequency: "tune-freq",
      presence: "tune-pres",
    };
    const el = document.getElementById(map[key] || "");
    if (val && el) val.textContent = "Aktuell: " + el.value;
  }

  function resetSlider(key) {
    const map = {
      temperature: ["tune-temp", "tune-temp-val", 2],
      top_p: ["tune-topp", "tune-topp-val", 2],
      max_tokens: ["tune-maxtok", "tune-maxtok-val", 0],
      frequency: ["tune-freq", "tune-freq-val", 2],
      presence: ["tune-pres", "tune-pres-val", 2],
    };
    const spec = map[key];
    if (!spec || SLIDER_DEFAULTS[key] == null) return;
    const el = document.getElementById(spec[0]);
    const def = SLIDER_DEFAULTS[key];
    if (el) el.value = String(def);
    const valNode = document.getElementById(spec[1]);
    if (valNode)
      valNode.textContent =
        spec[2] === 0 ? String(Math.round(def)) : Number(def).toFixed(spec[2]);
    showSliderTip(key);
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
        const valNode = document.getElementById(p[1]);
        if (valNode)
          valNode.textContent =
            p[2] === 0 ? String(Math.round(n)) : n.toFixed(p[2]);
        showSliderTip(p[3]);
      });
      el.addEventListener("pointerdown", function () {
        showSliderTip(p[3]);
      });
    });
    document.querySelectorAll(".tune-reset").forEach(function (btn) {
      if (btn._bound) return;
      btn._bound = true;
      btn.addEventListener("click", function (ev) {
        ev.preventDefault();
        resetSlider(btn.getAttribute("data-reset"));
      });
    });
  }

  async function saveTuneModal() {
    if (!tuneAgentId) return;
    const ttsOn = !!document.getElementById("tune-tts").checked;
    const body = {
      // Don't persist UI placeholder hints as real system_prompt
      system_prompt: (function () {
        const v = (document.getElementById("tune-prompt").value || "").trim();
        const hint = (DEFAULT_PROMPTS[tuneAgentId] || "").trim();
        if (!v || v === hint || v.indexOf("(code default)") === 0) return "";
        // stale LOL default from older UI — drop it
        if (v.indexOf("Output 5") >= 0 && v.indexOf("bullet") >= 0) return "";
        return v;
      })(),
      model: document.getElementById("tune-model").value,
      temperature: Number(document.getElementById("tune-temp").value),
      top_p: Number(document.getElementById("tune-topp").value),
      max_tokens: Number(document.getElementById("tune-maxtok").value),
      frequency_penalty: Number(document.getElementById("tune-freq").value),
      presence_penalty: Number(document.getElementById("tune-pres").value),
      tts: ttsOn,
    };
    const key = document.getElementById("tune-key").value.trim();
    if (key) body.api_key = key;
    // Speak in the same click as Save (before await) — short DE only
    if (ttsOn) {
      const a = findAgent(tuneAgentId);
      speakNow("TTS an: " + ((a && a.label) || tuneAgentId) + ".");
    } else {
      stopSpeech();
    }
    const summary =
      "Speichern für " +
      tuneAgentId +
      ":\nTemperature " +
      body.temperature +
      " (niedrig=vorsichtig, hoch=kreativ)\nTop-P " +
      body.top_p +
      "\nMax Tokens " +
      body.max_tokens +
      "\nFrequency " +
      body.frequency_penalty +
      "\nPresence " +
      body.presence_penalty +
      "\nRegler geben keine Extra-Rechte.";
    if (!window.confirm(summary)) return;
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
    dockIntoBoxes(els.systemModal);
    try {
      const s = await api("GET", "/api/system");
      const parts = [];
      parts.push(s.deepseek ? "DeepSeek: an" : "DeepSeek: aus");
      parts.push(s.ollama ? "Ollama: an" : "Ollama: aus");
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
          const host = om.host ? " @ " + om.host : "";
          line.textContent = om.ok
            ? "Ollama-Modelle" + host + ": " + ((om.models || []).join(", ") || "(keine geladen)")
            : "Ollama offline" + host + " — ollama serve starten oder DeepSeek nutzen";
        }
      } catch (_e) {
        /* ignore */
      }
      document.getElementById("system-spend").textContent =
        "Ausgegeben: $" +
        (Number(s.spent_usd) || 0).toFixed(4) +
        " · Tokens " +
        ((s.prompt_tokens || 0) + (s.completion_tokens || 0));
      const langEl = document.getElementById("sys-lang");
      if (langEl) langEl.value = s.ui_lang || uiLang || "de";
      const ck = document.getElementById("system-ckpt");
      if (ck) {
        ck.textContent = s.checkpoint_exists
          ? "Checkpoint: vorhanden (Laden zum Fortsetzen)"
          : "Checkpoint: keiner";
      }
      // Worker presets
      try {
        const pl = await api("GET", "/api/worker-presets");
        const sel = document.getElementById("sys-preset-select");
        if (sel) {
          const cur = sel.value;
          sel.innerHTML = '<option value="">— Preset wählen —</option>';
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
      // Team presets + plan_mode
      try {
        const tp = await api("GET", "/api/team-presets");
        const tsel = document.getElementById("sys-team-select");
        if (tsel) {
          const cur = tsel.value;
          tsel.innerHTML = '<option value="">— Team wählen —</option>';
          (tp.presets || []).forEach(function (p) {
            const opt = document.createElement("option");
            opt.value = p.name || "";
            opt.textContent =
              (p.name || "?") +
              (p.plan_mode ? " · " + p.plan_mode : "");
            tsel.appendChild(opt);
          });
          if (cur) tsel.value = cur;
        }
        const pm = document.getElementById("sys-plan-mode");
        if (pm && tp.plan_mode) pm.value = tp.plan_mode;
      } catch (_te) {
        /* ignore */
      }
      const ap = document.getElementById("sys-auto-pack");
      if (ap) ap.checked = !!s.auto_pack_after_execute;
      const pm = document.getElementById("sys-pack-max");
      if (pm && s.pack_max != null) pm.value = String(s.pack_max);
      try {
        await renderHotList();
      } catch (_h) {
        /* ignore */
      }
      try {
        await renderWarmList();
      } catch (_w) {
        /* ignore */
      }
      // Session packs list
      try {
        await renderPackList(s.packs);
      } catch (_pe) {
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
            li.textContent = "(noch keine Backups)";
            ul.appendChild(li);
          } else {
            items.slice(0, 8).forEach(function (b) {
              const li = document.createElement("li");
              li.style.display = "flex";
              li.style.gap = "6px";
              li.style.alignItems = "center";
              const nameSpan = document.createElement("span");
              nameSpan.className = "ws-name";
              nameSpan.style.flex = "1";
              nameSpan.style.minWidth = "0";
              nameSpan.style.overflow = "hidden";
              nameSpan.style.textOverflow = "ellipsis";
              nameSpan.style.whiteSpace = "nowrap";
              nameSpan.textContent =
                (b.name || "") +
                " · " +
                (b.bytes != null ? Math.round(b.bytes / 1024) + " KB" : "");
              nameSpan.title = "Antippen zum Herunterladen";
              nameSpan.addEventListener("click", function () {
                window.location.href =
                  "/api/backups/" + encodeURIComponent(b.name) + "/download";
              });
              const rst = document.createElement("button");
              rst.type = "button";
              rst.className = "btn-ws-sm";
              rst.textContent = "Laden";
              rst.title = "HOT/WARM/Agenten aus diesem Backup laden";
              rst.addEventListener("click", function (ev) {
                ev.stopPropagation();
                restoreBackupByName(b.name);
              });
              const del = document.createElement("button");
              del.type = "button";
              del.className = "ws-action";
              del.textContent = "×";
              del.title = "Backup löschen";
              del.addEventListener("click", function (ev) {
                ev.stopPropagation();
                deleteBackupByName(b.name);
              });
              li.appendChild(nameSpan);
              li.appendChild(rst);
              li.appendChild(del);
              ul.appendChild(li);
            });
          }
        }
      } catch (_e3) {
        /* ignore */
      }
    } catch (err) {
      toast("System laden fehlgeschlagen: " + err.message, "error");
    }
    els.systemModal.hidden = false;
  }

  async function applySelectedPreset() {
    const sel = document.getElementById("sys-preset-select");
    const agent = document.getElementById("sys-preset-agent");
    const name = sel && sel.value;
    if (!name) {
      toast("Preset wählen", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/worker-presets/apply", {
        name: name,
        agent_id: (agent && agent.value) || "worker1",
      });
      applyAgentsFromServer([data]);
      toast("Preset übernommen: " + ((agent && agent.value) || "worker1"), "ok");
    } catch (err) {
      toast("Übernehmen fehlgeschlagen: " + err.message, "error");
    }
  }

  async function deleteSelectedPreset() {
    const sel = document.getElementById("sys-preset-select");
    const name = sel && sel.value;
    if (!name) {
      toast("Preset wählen", "info");
      return;
    }
    if (!confirm('Preset löschen: "' + name + '"?')) return;
    try {
      await api("POST", "/api/worker-presets/delete", {
        name: name,
        agent_id: "worker1",
      });
      toast("Preset gelöscht", "ok");
      openSystemModal();
    } catch (err) {
      toast("Löschen fehlgeschlagen: " + err.message, "error");
    }
  }

  async function applySelectedTeam() {
    const sel = document.getElementById("sys-team-select");
    const name = sel && sel.value;
    if (!name) {
      toast("Team wählen", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/team-presets/apply", { name: name });
      if (data.agents) applyAgentsFromServer(data.agents);
      else if (data.snapshot) applySnapshot(data.snapshot);
      const pm = document.getElementById("sys-plan-mode");
      if (pm && data.plan_mode) pm.value = data.plan_mode;
      appendChat(
        "system",
        "Team → " + name + " · Plan " + (data.plan_mode || "?")
      );
      toast("Team übernommen: " + name, "ok");
      renderCards();
    } catch (err) {
      toast("Team übernehmen fehlgeschlagen: " + err.message, "error");
    }
  }

  async function saveCurrentTeam() {
    const name = prompt("Team-Name:", "mein-team");
    if (!name || !String(name).trim()) return;
    try {
      const data = await api("POST", "/api/team-presets", {
        name: String(name).trim(),
      });
      toast(
        "Team gespeichert: " + ((data.preset && data.preset.name) || name),
        "ok"
      );
      openSystemModal();
    } catch (err) {
      toast("Team speichern fehlgeschlagen: " + err.message, "error");
    }
  }

  async function deleteSelectedTeam() {
    const sel = document.getElementById("sys-team-select");
    const name = sel && sel.value;
    if (!name) {
      toast("Team wählen", "info");
      return;
    }
    if (!confirm('Team löschen: "' + name + '"?')) return;
    try {
      await api("POST", "/api/team-presets/delete", { name: name });
      toast("Team gelöscht", "ok");
      openSystemModal();
    } catch (err) {
      toast("Team löschen fehlgeschlagen: " + err.message, "error");
    }
  }

  async function setPlanModeFromUi() {
    const pm = document.getElementById("sys-plan-mode");
    const mode = pm && pm.value;
    if (!mode) return;
    try {
      const data = await api("POST", "/api/plan-mode", { plan_mode: mode });
      toast("Plan → " + (data.plan_mode || mode), "ok");
    } catch (err) {
      toast("Plan fehlgeschlagen: " + err.message, "error");
    }
  }

  function closeSystemModal() {
    if (els.systemModal) els.systemModal.hidden = true;
  }

  async function saveSystemModal() {
    const budgetRaw = document.getElementById("sys-budget").value.trim();
    const langEl = document.getElementById("sys-lang");
    const apEl = document.getElementById("sys-auto-pack");
    const body = {
      free_only: !!document.getElementById("sys-free-only").checked,
      default_model: document.getElementById("sys-model").value.trim() || "deepseek-chat",
      max_budget_usd: budgetRaw === "" ? null : Number(budgetRaw),
      ui_lang: langEl ? langEl.value : "de",
      auto_pack_after_execute: apEl ? !!apEl.checked : false,
      pack_max: (function () {
        const el = document.getElementById("sys-pack-max");
        if (!el || el.value === "") return undefined;
        const n = parseInt(el.value);
        return Number.isFinite(n) ? n : undefined;
      })(),
    };
    try {
      const data = await api("POST", "/api/system", body);
      if (data && data.ok === false) {
        toast((data.status || "System nicht übernommen"), "error");
        return;
      }
      if (body.ui_lang) await loadTooltips(body.ui_lang);
      closeSystemModal();
      toast("System übernommen", "ok");
      const snap = await api("GET", "/api/state");
      applySnapshot(snap);
    } catch (err) {
      toast("System speichern fehlgeschlagen: " + err.message, "error");
    }
  }

  function closeVectorModal() {
    if (els.vectorModal) els.vectorModal.hidden = true;
  }

  function closeUsageModal() {
    if (els.usageModal) els.usageModal.hidden = true;
  }

