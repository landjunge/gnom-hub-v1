/* part: 04-tools.js — edit parts, run scripts/build_ui_js.py */
  function closeToolsModal() {
    if (els.toolsModal) els.toolsModal.hidden = true;
  }


  function _toolCallsMerged() {
    const pipe = (lastToolCalls || []).map(function (c, i) {
      return Object.assign({ _src: "pipeline", _i: i }, c || {});
    });
    const man = (manualToolCalls || []).map(function (c, i) {
      return Object.assign({ _src: "manual", _i: i }, c || {});
    });
    return pipe.concat(man);
  }


  function setToolsResult(sicht, codeObj) {
    lastToolsSicht = String(sicht || "");
    lastToolsCode =
      typeof codeObj === "string"
        ? codeObj
        : JSON.stringify(codeObj == null ? {} : codeObj, null, 2);
    paintToolsResult();
  }

  function paintToolsResult() {
    const pre = document.getElementById("tools-result");
    if (!pre) return;
    pre.textContent =
      toolsResultMode === "source" ? lastToolsCode || lastToolsSicht : lastToolsSicht || lastToolsCode;
    const btnS = document.getElementById("tools-result-sicht");
    const btnC = document.getElementById("tools-result-code");
    if (btnS) btnS.classList.toggle("is-on", toolsResultMode !== "source");
    if (btnC) btnC.classList.toggle("is-on", toolsResultMode === "source");
  }

  function formatToolCallGerman(c) {
    const name = (c && (c.name || c.tool)) || "Werkzeug";
    const ok = !c || c.ok !== false;
    const lines = [ok ? name + " — ok" : name + " — Fehler"];
    if (c && c.reason) lines.push("Grund: " + c.reason);
    if (c && c.error) lines.push("Fehler: " + c.error);
    const args = (c && c.args) || {};
    Object.keys(args)
      .slice(0, 6)
      .forEach(function (k) {
        lines.push(k + ": " + String(args[k]).slice(0, 120));
      });
    const res = (c && c.result) || {};
    if (typeof res === "string") {
      lines.push(res.slice(0, 800));
    } else if (res && typeof res === "object") {
      if (res.dry_run) lines.push("Trockenlauf — God-Badge oben für echte Steuerung");
      if (res.url) lines.push("URL: " + res.url);
      if (res.message) lines.push(String(res.message).slice(0, 400));
      if (res.package) lines.push("Paket: " + res.package);
      if (res.hits != null) lines.push("Treffer: " + res.hits);
      if (res.text_len != null) lines.push("Zeichen: " + res.text_len);
      if (res.status != null) lines.push("Status: " + res.status);
      if (res.text) lines.push(String(res.text).slice(0, 600));
      if (res.detail) lines.push(String(res.detail).slice(0, 400));
    }
    return lines.join("\n");
  }

  function formatCuGerman(data, kind) {
    if (data == null) return String(kind || "Computer") + " — keine Antwort";
    if (typeof data === "string") return data;
    const lines = [];
    if (data.dry_run) {
      lines.push("Trockenlauf — God-Badge oben für echte Steuerung");
    }
    if (data.ok === false) {
      lines.push((kind || "Aktion") + " — Fehler");
      if (data.error) lines.push("Fehler: " + data.error);
    } else {
      lines.push((kind || "Aktion") + " — ok");
    }
    if (data.detail) lines.push(String(data.detail));
    if (data.message) lines.push(String(data.message));
    if (data.capture && data.capture.ok) lines.push("Bildschirm gespeichert");
    return lines.join("\n");
  }

  function renderToolsDodFail(validation) {
    const host = document.getElementById("tools-dod-fail");
    if (!host) return;
    const v = validation && typeof validation === "object" ? validation : null;
    if (!v || (v.ok !== false && !(v.soft_issues && v.soft_issues.length))) {
      host.hidden = true;
      host.innerHTML = "";
      return;
    }
    const issues = (v.issues || []).concat(v.soft_issues || []);
    const uniq = [];
    issues.forEach(function (c) {
      if (c && uniq.indexOf(c) < 0) uniq.push(c);
    });
    host.hidden = false;
    host.removeAttribute("hidden");
    host.textContent =
      "DoD nicht erfüllt" +
      (v.score != null ? " · Wert " + v.score : "") +
      (v.retryable ? " · erneut möglich" : "") +
      (uniq.length ? ": " + uniq.slice(0, 6).join(", ") : "");
  }

  function renderToolsRunHistory(calls) {
    if (calls) {
      lastToolCalls = Array.isArray(calls) ? calls.slice() : [];
    }
    const ul = document.getElementById("tools-run-history");
    const sum = document.getElementById("tools-run-summary");
    if (!ul) return;
    const list = _toolCallsMerged();
    const nPipe = (lastToolCalls || []).length;
    const nMan = (manualToolCalls || []).length;
    let nOk = 0;
    let nFail = 0;
    list.forEach(function (c) {
      if (c && c.ok === false) nFail += 1;
      else nOk += 1;
    });
    if (sum) {
      sum.textContent =
        "Dieser Lauf: " +
        nPipe +
        " Pipeline" +
        (nMan ? " · " + nMan + " manuell" : "") +
        " · " +
        nOk +
        " ok / " +
        nFail +
        " Fehler" +
        (list.length ? " · Zeile antippen für Sicht" : "");
    }
    ul.innerHTML = "";
    if (!list.length) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent =
        "(noch keine Tool-Aufrufe — Arbeit starten mit URL / Memory / Install, oder unten Ausführen)";
      ul.appendChild(li);
      return;
    }
    list.slice(0, 40).forEach(function (c, i) {
      const li = document.createElement("li");
      const ok = !c || c.ok !== false;
      li.className = ok ? "tool-ok" : "tool-fail";
      li.setAttribute("data-idx", String(i));
      li.title = "Antippen zeigt Klartext in Sicht";
      const name = (c && (c.name || c.tool)) || "?";
      const why = (c && c.reason) || "";
      const err = (c && c.error) || "";
      const args = (c && c.args) || {};
      const argBits = Object.keys(args)
        .slice(0, 3)
        .map(function (k) {
          return k + "=" + String(args[k]).slice(0, 40);
        });
      const res = (c && c.result) || {};
      let resBit = "";
      if (res.url) resBit = String(res.url).slice(0, 48);
      else if (res.package) resBit = String(res.package);
      else if (res.hits != null) resBit = res.hits + " Treffer";
      else if (res.text_len != null) resBit = res.text_len + " Zeichen";
      else if (res.message) resBit = String(res.message).slice(0, 48);
      else if (res.status != null) resBit = "Status " + res.status;
      const src = c && c._src === "manual" ? "manuell" : "Lauf";
      const meta = [ok ? "ok" : "Fehler"]
        .concat(why ? ["Grund: " + String(why).slice(0, 80)] : [])
        .concat(argBits)
        .concat(resBit ? [resBit] : [])
        .concat(err ? ["Fehler: " + String(err).slice(0, 60)] : [])
        .join(" · ");
      li.title = why
        ? "Grund: " + why + " — antippen für Sicht"
        : "Antippen zeigt Klartext in Sicht";
      // eslint-disable-next-line no-unsanitized/property
      li.innerHTML =
        '<span class="tool-src">[' +
        src +
        "]</span>" +
        '<span class="tool-name">' +
        (i + 1) +
        ". " +
        name +
        '</span> <span class="tool-meta">' +
        meta +
        "</span>";
      li.addEventListener("click", function () {
        ul.querySelectorAll("li.selected").forEach(function (x) {
          x.classList.remove("selected");
        });
        li.classList.add("selected");
        const clean = Object.assign({}, c);
        delete clean._src;
        delete clean._i;
        toolsResultMode = "preview";
        setToolsResult(formatToolCallGerman(c), clean);
        // Prefill run form for re-call
        const sel = document.getElementById("tools-select");
        const argsEl = document.getElementById("tools-args");
        if (sel && name && name !== "?") {
          sel.value = name;
        }
        if (argsEl && args && Object.keys(args).length) {
          try {
            argsEl.value = JSON.stringify(args);
          } catch (_e) {
            argsEl.value = "";
          }
        }
      });
      ul.appendChild(li);
    });
  }

  function copyToolsHistory() {
    const list = _toolCallsMerged().map(function (c) {
      const o = Object.assign({}, c);
      delete o._src;
      delete o._i;
      return o;
    });
    const text = JSON.stringify(list, null, 2);
    function done() {
      if (typeof toast === "function") toast("Verlauf kopiert (" + list.length + ")", "ok");
    }
    function fallbackCopy() {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
        done();
      } catch (_e) {
        if (typeof toast === "function") toast("Kopieren fehlgeschlagen", "error");
      }
      document.body.removeChild(ta);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard
        .writeText(text)
        .then(function () {
          if (typeof toast === "function") {
            toast("Verlauf kopiert (" + list.length + ")", "ok");
          }
        })
        .catch(function () {
          fallbackCopy();
        });
    }
    fallbackCopy();
  }

  function recordManualToolCall(name, args, data) {
    const ok =
      data && typeof data === "object"
        ? data.ok !== false && !data.error
        : true;
    const entry = {
      name: name || "?",
      args: args || {},
      ok: ok,
      error: (data && data.error) || null,
      result:
        data && typeof data === "object"
          ? {
              ok: data.ok,
              error: data.error,
              message: data.message,
              status: data.status,
              url: data.url,
              package: data.package,
              text_len:
                data.text != null
                  ? String(data.text).length
                  : data.text_len,
            }
          : { raw: String(data).slice(0, 200) },
      at: new Date().toISOString(),
    };
    manualToolCalls.push(entry);
    if (manualToolCalls.length > 30) manualToolCalls = manualToolCalls.slice(-30);
    renderToolsRunHistory();
  }

  async function openToolsModal() {
    if (!els.toolsModal) return;
    dockIntoBoxes(els.toolsModal);
    els.toolsModal.hidden = false;
    try {
      const snap = lastSnapshot || null;
      const calls =
        snap && snap.pipeline && snap.pipeline.tool_calls
          ? snap.pipeline.tool_calls
          : lastToolCalls || [];
      renderToolsRunHistory(calls);
      renderToolsDodFail(snap && snap.pipeline ? snap.pipeline.validation : null);
    } catch (e) {
      renderToolsDodFail(null);
    }
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
        (god ? "an (echte Steuerung)" : "aus (nur Trockenlauf)") +
        " · Shell: " +
        allow.slice(0, 6).join(" ") +
        (allow.length > 6 ? "…" : "");
    } catch (_e) {
      line.textContent = "Computer-Nutzung: Status unbekannt";
    }
  }

  function showCuResult(obj, kind) {
    toolsResultMode = "preview";
    setToolsResult(formatCuGerman(obj, kind || "Computer"), obj);
  }

  async function cuInspect() {
    try {
      const data = await api("POST", "/api/computer-use/inspect");
      showCuResult(data, "Bildschirm");
      toast(
        data.dry_run
          ? "Trockenlauf — God-Badge oben für echte Steuerung"
          : data.capture && data.capture.ok
            ? "Bildschirm gespeichert"
            : "Bildschirm geprüft",
        data.dry_run ? "info" : "ok"
      );
    } catch (err) {
      toast("Prüfen fehlgeschlagen: " + err.message, "error");
    }
  }

  async function cuClick() {
    const x = Number((document.getElementById("cu-x") || {}).value || 0);
    const y = Number((document.getElementById("cu-y") || {}).value || 0);
    try {
      const data = await api("POST", "/api/computer-use/click", { x: x, y: y });
      showCuResult(data, "Klick");
      toast(
        data.dry_run
          ? "Trockenlauf — God-Badge oben für echte Steuerung"
          : "Klick " + x + "," + y,
        data.dry_run ? "info" : "ok"
      );
    } catch (err) {
      toast("Klick fehlgeschlagen: " + err.message, "error");
    }
  }

  async function cuType() {
    const text = String((document.getElementById("cu-type") || {}).value || "");
    if (!text.trim()) {
      toast("Text zum Tippen fehlt", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/computer-use/type", { text: text });
      showCuResult(data, "Tippen");
      toast(
        data.dry_run ? "Trockenlauf — God-Badge oben für echte Steuerung" : "Getippt",
        data.dry_run ? "info" : "ok"
      );
    } catch (err) {
      toast("Tippen fehlgeschlagen: " + err.message, "error");
    }
  }

  async function cuShell() {
    const cmd = String((document.getElementById("cu-shell") || {}).value || "");
    if (!cmd.trim()) {
      toast("Shell-Befehl fehlt", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/computer-use/shell", { cmd: cmd });
      showCuResult(data, "Shell");
      toast(
        data.dry_run
          ? "Trockenlauf — God-Badge oben für echte Steuerung"
          : data.detail || (data.ok ? "Shell ok" : "Shell Fehler"),
        data.ok || data.dry_run ? "ok" : "error"
      );
    } catch (err) {
      toast("Shell fehlgeschlagen: " + err.message, "error");
    }
  }

  async function refreshToolsModal(opts) {
    const doReload = !!(opts && opts.reload);
    const ul = document.getElementById("tools-list");
    const sel = document.getElementById("tools-select");
    const countEl = document.getElementById("tools-count");
    try {
      // Hot-reload: re-scan plugins/ + re-import handlers (core tools untouched)
      const data = doReload
        ? await api("POST", "/api/plugins/reload")
        : await api("GET", "/api/plugins");
      const tools = data.tools || [];
      if (doReload) {
        const errs = data.errors || [];
        const nPlug = data.plugins ? data.plugins.length : 0;
        toast(
          "Plugins neu: " +
            nPlug +
            " · Werkzeuge " +
            tools.length +
            (errs.length ? " · Fehler " + errs.length : ""),
          errs.length ? "info" : "ok"
        );
      }
      const disk = data.disk || [];
      const errs = data.errors || [];
      const plugs = data.plugins || [];
      if (countEl) {
        const loadedN = plugs.length || disk.filter(function (d) {
          return d.status === "loaded";
        }).length;
        const diskN = disk.length;
        countEl.textContent =
          "Werkzeuge: " +
          tools.length +
          " · Plugins geladen: " +
          loadedN +
          (diskN ? " · auf Datenträger: " + diskN : "") +
          (errs.length ? " · Fehler: " + errs.length : "");
      }
      if (ul) {
        ul.innerHTML = "";
        // Drop-in inventory first (what is on disk)
        if (disk.length) {
          const head = document.createElement("li");
          head.className = "muted";
          head.style.fontWeight = "600";
          head.textContent = "Plugins auf Datenträger (Drop-in)";
          ul.appendChild(head);
          disk.forEach(function (d) {
            const li = document.createElement("li");
            const st = d.status || "?";
            li.textContent =
              (d.id || d.folder || "?") +
              " · " +
              st +
              (d.version ? " v" + d.version : "") +
              (d.tool_count != null
                ? " · " + d.tool_count + " Werkzeuge"
                : d.tool_count_declared != null
                  ? " · " + d.tool_count_declared + " gemeldet"
                  : "");
            if (d.description) li.title = String(d.description);
            if (d.error) li.title = (li.title ? li.title + " · " : "") + d.error;
            if (st === "error" || st === "no_manifest") {
              li.style.opacity = "0.85";
            }
            ul.appendChild(li);
          });
        }
        if (errs.length) {
          const headE = document.createElement("li");
          headE.className = "muted";
          headE.style.fontWeight = "600";
          headE.textContent = "Ladefehler";
          ul.appendChild(headE);
          errs.forEach(function (e) {
            const li = document.createElement("li");
            li.textContent =
              (e.plugin || e.path || "?") + " — " + String(e.error || "").slice(0, 120);
            li.title = JSON.stringify(e);
            ul.appendChild(li);
          });
        }
        const headT = document.createElement("li");
        headT.className = "muted";
        headT.style.fontWeight = "600";
        headT.textContent = "Registrierte Werkzeuge";
        ul.appendChild(headT);
        if (!tools.length) {
          const li = document.createElement("li");
          li.className = "muted";
          li.textContent = "(keine Werkzeuge)";
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
      toast("Werkzeuge laden fehlgeschlagen: " + err.message, "error");
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
    const name = sel ? sel.value : "";
    if (!name) {
      toast("Werkzeug wählen", "info");
      return;
    }
    let argumentsObj = {};
    try {
      argumentsObj = parseToolArgs(name, argsEl ? argsEl.value : "");
    } catch (err) {
      toast("Args ungültig: " + err.message, "error");
      return;
    }
    try {
      const data = await api("POST", "/api/tools/call", {
        name: name,
        arguments: argumentsObj,
      });
      const result = data.result;
      const sicht =
        typeof result === "string"
          ? result
          : formatToolCallGerman({ name: name, args: argumentsObj, ok: true, result: result });
      toolsResultMode = "preview";
      setToolsResult(sicht, result);
      if (typeof recordManualToolCall === "function") {
        recordManualToolCall(name, argumentsObj, result);
      }
      toast(name + " ok", "ok");
    } catch (err) {
      toolsResultMode = "preview";
      setToolsResult("Fehler: " + err.message, { error: String(err.message || err) });
      toast("Werkzeug fehlgeschlagen: " + err.message, "error");
    }
  }

  async function runQuickFetch() {
    const urlEl = document.getElementById("tools-fetch-url");
    let url = urlEl ? String(urlEl.value || "").trim() : "";
    if (!url) {
      toast("URL fehlt", "info");
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
      const sicht =
        typeof data.result === "string"
          ? data.result
          : formatToolCallGerman({
              name: "web_fetch",
              args: { url: url },
              ok: true,
              result: data.result,
            });
      toolsResultMode = "preview";
      setToolsResult(sicht, data.result);
      if (typeof recordManualToolCall === "function") {
        recordManualToolCall(
          "web_fetch",
          { url: url, max_chars: 6000 },
          data.result
        );
      }
      toast("Holen ok", "ok");
    } catch (err) {
      toolsResultMode = "preview";
      setToolsResult("Holen fehlgeschlagen: " + err.message, { error: String(err.message || err) });
      toast("Holen fehlgeschlagen: " + err.message, "error");
    }
  }


