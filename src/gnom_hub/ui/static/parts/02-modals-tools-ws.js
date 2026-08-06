/* part: 02-modals-tools-ws.js  lines 705-1949 of app.js — edit parts, run scripts/build_ui_js.py */
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
    const ttsOn = !!document.getElementById("tune-tts").checked;
    const body = {
      system_prompt: document.getElementById("tune-prompt").value,
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
    // Speak in the same click as Save (before await)
    if (ttsOn) {
      const a = findAgent(tuneAgentId);
      speakNow(
        "Gedanken an für " +
          ((a && a.label) || tuneAgentId) +
          ". Ich spreche den Denkprozess, nicht den Text."
      );
    } else {
      stopSpeech();
    }
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
      // Team presets + plan_mode
      try {
        const tp = await api("GET", "/api/team-presets");
        const tsel = document.getElementById("sys-team-select");
        if (tsel) {
          const cur = tsel.value;
          tsel.innerHTML = '<option value="">— select team —</option>';
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
            li.textContent = "(no backups yet)";
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
              nameSpan.title = "Click to download";
              nameSpan.addEventListener("click", function () {
                window.location.href =
                  "/api/backups/" + encodeURIComponent(b.name) + "/download";
              });
              const rst = document.createElement("button");
              rst.type = "button";
              rst.className = "btn-ws-sm";
              rst.textContent = "Rest";
              rst.title = "Restore HOT/WARM/agents from this backup";
              rst.addEventListener("click", function (ev) {
                ev.stopPropagation();
                restoreBackupByName(b.name);
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

  async function applySelectedTeam() {
    const sel = document.getElementById("sys-team-select");
    const name = sel && sel.value;
    if (!name) {
      toast("Select a team preset", "info");
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
        "Team preset → " + name + " · plan_mode=" + (data.plan_mode || "?")
      );
      toast("Team applied: " + name, "ok");
      renderCards();
    } catch (err) {
      toast("Team apply failed: " + err.message, "error");
    }
  }

  async function saveCurrentTeam() {
    const name = prompt("Team preset name:", "my-team");
    if (!name || !String(name).trim()) return;
    try {
      const data = await api("POST", "/api/team-presets", {
        name: String(name).trim(),
      });
      toast(
        "Team saved: " + ((data.preset && data.preset.name) || name),
        "ok"
      );
      openSystemModal();
    } catch (err) {
      toast("Team save failed: " + err.message, "error");
    }
  }

  async function deleteSelectedTeam() {
    const sel = document.getElementById("sys-team-select");
    const name = sel && sel.value;
    if (!name) {
      toast("Select a team preset", "info");
      return;
    }
    if (!confirm('Delete team preset "' + name + '"?')) return;
    try {
      await api("POST", "/api/team-presets/delete", { name: name });
      toast("Team deleted", "ok");
      openSystemModal();
    } catch (err) {
      toast("Team delete failed: " + err.message, "error");
    }
  }

  async function setPlanModeFromUi() {
    const pm = document.getElementById("sys-plan-mode");
    const mode = pm && pm.value;
    if (!mode) return;
    try {
      const data = await api("POST", "/api/plan-mode", { plan_mode: mode });
      toast("plan_mode → " + (data.plan_mode || mode), "ok");
    } catch (err) {
      toast("plan_mode failed: " + err.message, "error");
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
      ui_lang: langEl ? langEl.value : "en",
      auto_pack_after_execute: apEl ? !!apEl.checked : false,
      pack_max: (function () {
        const el = document.getElementById("sys-pack-max");
        if (!el || el.value === "") return undefined;
        const n = parseInt(el.value, 10);
        return Number.isFinite(n) ? n : undefined;
      })(),
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

  function closeVectorModal() {
    if (els.vectorModal) els.vectorModal.hidden = true;
  }

  function closeUsageModal() {
    if (els.usageModal) els.usageModal.hidden = true;
  }

  function closeToolsModal() {
    if (els.toolsModal) els.toolsModal.hidden = true;
  }

  async function openToolsModal() {
    if (!els.toolsModal) return;
    els.toolsModal.hidden = false;
    await refreshToolsModal();
    await refreshComputerUseLine();
  }

  async function refreshComputerUseLine() {
    const line = document.getElementById("cu-god-line");
    if (!line) return;
    try {
      const data = await api("GET", "/api/computer-use");
      const god = !!(data.god_mode && data.god_mode.enabled);
      const allow =
        (data.computer &&
          data.computer.action &&
          data.computer.action.shell_allow) ||
        [];
      line.textContent =
        "God-Mode: " +
        (god ? "ON (real control)" : "off (dry-run only)") +
        " · shell: " +
        allow.slice(0, 6).join(" ") +
        (allow.length > 6 ? "…" : "");
    } catch (_e) {
      line.textContent = "Computer use: status unavailable";
    }
  }

  function showCuResult(obj) {
    const pre = document.getElementById("tools-result");
    if (!pre) return;
    pre.textContent =
      typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
  }

  async function cuInspect() {
    try {
      const data = await api("POST", "/api/computer-use/inspect");
      showCuResult(data);
      toast(
        data.capture && data.capture.ok
          ? "Screenshot saved"
          : "Inspect done (maybe stub capture)",
        "ok"
      );
    } catch (err) {
      toast("Inspect failed: " + err.message, "error");
    }
  }

  async function cuClick() {
    const x = Number((document.getElementById("cu-x") || {}).value || 0);
    const y = Number((document.getElementById("cu-y") || {}).value || 0);
    try {
      const data = await api("POST", "/api/computer-use/click", { x: x, y: y });
      showCuResult(data);
      toast(
        data.dry_run
          ? "Dry-run click — enable God badge first"
          : "Clicked " + x + "," + y,
        data.dry_run ? "info" : "ok"
      );
    } catch (err) {
      toast("Click failed: " + err.message, "error");
    }
  }

  async function cuType() {
    const text = String((document.getElementById("cu-type") || {}).value || "");
    if (!text.trim()) {
      toast("Enter text to type", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/computer-use/type", { text: text });
      showCuResult(data);
      toast(
        data.dry_run ? "Dry-run type — enable God badge first" : "Typed",
        data.dry_run ? "info" : "ok"
      );
    } catch (err) {
      toast("Type failed: " + err.message, "error");
    }
  }

  async function cuShell() {
    const cmd = String((document.getElementById("cu-shell") || {}).value || "");
    if (!cmd.trim()) {
      toast("Enter shell command", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/computer-use/shell", { cmd: cmd });
      showCuResult(data);
      toast(
        data.dry_run ? "Dry-run shell — enable God badge first" : data.detail,
        data.ok || data.dry_run ? "ok" : "error"
      );
    } catch (err) {
      toast("Shell failed: " + err.message, "error");
    }
  }

  async function refreshToolsModal() {
    const ul = document.getElementById("tools-list");
    const sel = document.getElementById("tools-select");
    const countEl = document.getElementById("tools-count");
    try {
      const data = await api("GET", "/api/plugins");
      const tools = data.tools || [];
      if (countEl) {
        countEl.textContent =
          "Tools: " +
          tools.length +
          " · plugins: " +
          (data.plugins ? data.plugins.length : 0);
      }
      if (ul) {
        ul.innerHTML = "";
        if (!tools.length) {
          const li = document.createElement("li");
          li.className = "muted";
          li.textContent = "(no tools)";
          ul.appendChild(li);
        } else {
          tools.forEach(function (t) {
            const li = document.createElement("li");
            li.textContent =
              (t.name || "?") +
              " [" +
              (t.plugin || "core") +
              "] — " +
              String(t.description || "").slice(0, 100);
            li.title = JSON.stringify(t.input_schema || {}, null, 0);
            li.style.cursor = "pointer";
            li.addEventListener("click", function () {
              if (sel) sel.value = t.name;
            });
            ul.appendChild(li);
          });
        }
      }
      if (sel) {
        const prev = sel.value;
        sel.innerHTML = "";
        tools.forEach(function (t) {
          const opt = document.createElement("option");
          opt.value = t.name;
          opt.textContent = t.name;
          sel.appendChild(opt);
        });
        if (prev) sel.value = prev;
      }
    } catch (err) {
      toast("Tools load failed: " + err.message, "error");
    }
  }

  function parseToolArgs(name, raw) {
    const text = String(raw || "").trim();
    if (!text) return {};
    if (text.charAt(0) === "{") {
      return JSON.parse(text);
    }
    if (name === "web_fetch") return { url: text };
    if (name === "memory_search") return { query: text };
    if (name === "pipeline_do") return { text: text };
    if (name === "hub_status") return {};
    return { text: text };
  }

  async function runSelectedTool() {
    const sel = document.getElementById("tools-select");
    const argsEl = document.getElementById("tools-args");
    const out = document.getElementById("tools-result");
    const name = sel ? sel.value : "";
    if (!name) {
      toast("Select a tool", "info");
      return;
    }
    let argumentsObj = {};
    try {
      argumentsObj = parseToolArgs(name, argsEl ? argsEl.value : "");
    } catch (err) {
      toast("Invalid args JSON: " + err.message, "error");
      return;
    }
    try {
      const data = await api("POST", "/api/tools/call", {
        name: name,
        arguments: argumentsObj,
      });
      const result = data.result;
      const text =
        typeof result === "string"
          ? result
          : JSON.stringify(result, null, 2);
      if (out) out.textContent = text;
      toast("Tool " + name + " ok", "ok");
    } catch (err) {
      if (out) out.textContent = "Error: " + err.message;
      toast("Tool failed: " + err.message, "error");
    }
  }

  async function runQuickFetch() {
    const urlEl = document.getElementById("tools-fetch-url");
    const out = document.getElementById("tools-result");
    let url = urlEl ? String(urlEl.value || "").trim() : "";
    if (!url) {
      toast("Enter a URL", "info");
      return;
    }
    if (url.indexOf("http://") !== 0 && url.indexOf("https://") !== 0) {
      url = "https://" + url;
    }
    try {
      const data = await api("POST", "/api/tools/call", {
        name: "web_fetch",
        arguments: { url: url, max_chars: 6000 },
      });
      if (out) {
        out.textContent =
          typeof data.result === "string"
            ? data.result
            : JSON.stringify(data.result, null, 2);
      }
      toast("Fetch ok", "ok");
    } catch (err) {
      if (out) out.textContent = "Fetch error: " + err.message;
      toast("Fetch failed: " + err.message, "error");
    }
  }


  async function openUsageModal() {
    if (!els.usageModal) return;
    els.usageModal.hidden = false;
    await refreshUsageModal();
  }

  async function refreshUsageModal() {
    const body = document.getElementById("usage-body");
    const ul = document.getElementById("usage-jobs");
    try {
      const [usage, jobsData] = await Promise.all([
        api("GET", "/api/usage"),
        api("GET", "/api/jobs?limit=12"),
      ]);
      const spent = Number(usage.spent_usd || 0);
      const pt = Number(usage.prompt_tokens || 0);
      const ct = Number(usage.completion_tokens || 0);
      const budget =
        usage.max_budget_usd != null && usage.max_budget_usd !== ""
          ? Number(usage.max_budget_usd)
          : null;
      const lines = [
        "spent: $" + spent.toFixed(4),
        "tokens: " + pt + " prompt + " + ct + " completion",
        "budget: " + (budget != null && !isNaN(budget) ? "$" + budget.toFixed(2) : "none"),
        "free_only: " + !!usage.free_only,
        "",
        "by agent:",
      ];
      const by = usage.by_agent || {};
      const keys = Object.keys(by);
      if (!keys.length) {
        lines.push("(no LLM calls yet)");
      } else {
        keys.forEach(function (aid) {
          const b = by[aid] || {};
          lines.push(
            "  " +
              aid +
              ": $" +
              Number(b.cost_usd || 0).toFixed(4) +
              " · calls=" +
              (b.calls || 0) +
              " · tok=" +
              (Number(b.prompt_tokens || 0) + Number(b.completion_tokens || 0))
          );
        });
      }
      if (body) body.textContent = lines.join(String.fromCharCode(10));

      if (ul) {
        ul.innerHTML = "";
        const jobs = jobsData.jobs || [];
        if (!jobs.length) {
          const li = document.createElement("li");
          li.className = "muted";
          li.textContent = "(no jobs yet)";
          ul.appendChild(li);
        } else {
          jobs.forEach(function (j) {
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
            lab.textContent =
              (j.id || "") +
              " · " +
              (j.name || "") +
              " · " +
              (j.status || "") +
              "/" +
              (j.stage || "");
            lab.title = (j.error || j.started_at || "");
            li.appendChild(lab);
            if (j.status === "running") {
              const btn = document.createElement("button");
              btn.type = "button";
              btn.className = "btn-ws-sm";
              btn.textContent = "Cancel";
              btn.addEventListener("click", function () {
                cancelJobById(j.id);
              });
              li.appendChild(btn);
            }
            ul.appendChild(li);
          });
        }
      }
    } catch (err) {
      if (body) body.textContent = "Usage load failed: " + err.message;
    }
  }

  async function cancelJobById(id) {
    if (!id) return;
    try {
      await api("POST", "/api/jobs/" + encodeURIComponent(id) + "/cancel");
      toast("Cancel requested", "ok");
      await refreshUsageModal();
    } catch (err) {
      toast("Cancel failed: " + err.message, "error");
    }
  }

  async function resetUsageCounters() {
    if (!confirm("Reset session usage counters to zero?")) return;
    try {
      await api("POST", "/api/usage/reset");
      toast("Usage reset", "ok");
      await refreshUsageModal();
      // refresh cost badge via state
      try {
        const st = await api("GET", "/api/state");
        applySnapshot(st);
      } catch (_e) {
        /* ignore */
      }
    } catch (err) {
      toast("Usage reset failed: " + err.message, "error");
    }
  }


  async function openVectorModal() {
    if (!els.vectorModal) return;
    els.vectorModal.hidden = false;
    await refreshVectorList();
  }

  async function refreshVectorList() {
    const ul = document.getElementById("vector-list");
    const countEl = document.getElementById("vector-count");
    try {
      const data = await api("GET", "/api/vector?limit=40");
      if (countEl) countEl.textContent = "Docs: " + (data.count || 0);
      if (!ul) return;
      ul.innerHTML = "";
      const docs = data.docs || [];
      if (!docs.length) {
        const li = document.createElement("li");
        li.className = "muted";
        li.textContent = "(empty — add text or run Execute to index requirements)";
        ul.appendChild(li);
        return;
      }
      docs.forEach(function (d) {
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
        lab.textContent = (d.id || "?") + ": " + (d.text || "");
        lab.title = d.text || "";
        const del = document.createElement("button");
        del.type = "button";
        del.className = "btn-ws-sm";
        del.textContent = "Del";
        del.addEventListener("click", function () {
          deleteVectorDoc(d.id);
        });
        li.appendChild(lab);
        li.appendChild(del);
        ul.appendChild(li);
      });
    } catch (err) {
      toast("Vector list failed: " + err.message, "error");
    }
  }

  async function searchVectors() {
    const qEl = document.getElementById("vector-query");
    const hitsEl = document.getElementById("vector-hits");
    const q = qEl ? String(qEl.value || "").trim() : "";
    if (!q) {
      toast("Enter a search query", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/vector/search", {
        query: q,
        limit: 8,
      });
      const hits = data.hits || [];
      if (!hitsEl) return;
      if (!hits.length) {
        hitsEl.textContent = "No hits for: " + q;
        return;
      }
      hitsEl.textContent = hits
        .map(function (h) {
          return (
            (h.score != null ? h.score : "?") +
            " · " +
            (h.id || "") +
            " — " +
            String(h.text || "").slice(0, 160)
          );
        })
        .join("\n");
    } catch (err) {
      toast("Vector search failed: " + err.message, "error");
    }
  }

  async function addVectorDoc() {
    const input = document.getElementById("vector-add-input");
    const text = input ? String(input.value || "").trim() : "";
    if (!text) {
      toast("Enter text to add", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/vector/add", {
        text: text,
        meta: { source: "ui" },
      });
      if (input) input.value = "";
      if (data.docs) {
        // re-render from response
        const countEl = document.getElementById("vector-count");
        if (countEl) countEl.textContent = "Docs: " + (data.count || 0);
      }
      await refreshVectorList();
      toast("Vector doc " + (data.id || "added"), "ok");
    } catch (err) {
      toast("Vector add failed: " + err.message, "error");
    }
  }

  async function deleteVectorDoc(id) {
    if (!id || !confirm('Delete vector doc "' + id + '"?')) return;
    try {
      await api("DELETE", "/api/vector/" + encodeURIComponent(id));
      await refreshVectorList();
      toast("Deleted " + id, "ok");
    } catch (err) {
      toast("Vector delete failed: " + err.message, "error");
    }
  }

  async function clearVectorStore() {
    if (!confirm("Clear ALL vector docs?")) return;
    try {
      await api("POST", "/api/vector/clear");
      await refreshVectorList();
      const hitsEl = document.getElementById("vector-hits");
      if (hitsEl) hitsEl.textContent = "Search hits appear here.";
      toast("Vector store cleared", "ok");
    } catch (err) {
      toast("Vector clear failed: " + err.message, "error");
    }
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

  async function downloadWorkspaceZip(zone) {
    try {
      const data = await api(
        "POST",
        "/api/workspace/export?zone=" + encodeURIComponent(zone || "all")
      );
      if (!data.name) {
        toast("Export failed", "error");
        return;
      }
      window.location.href =
        "/api/workspace/exports/" + encodeURIComponent(data.name);
      toast(
        "Workspace zip ready (" +
          (data.bytes != null ? Math.round(data.bytes / 1024) + " KB" : data.name) +
          ")",
        "ok"
      );
    } catch (err) {
      toast("Workspace export failed: " + err.message, "error");
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

