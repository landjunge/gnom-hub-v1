/* part: 04-boxes.js  lines 3682-4267 of app.js — edit parts, run scripts/build_ui_js.py */

  /**
   * Dynamic presentation inside a box/panel:
   * HTML → live preview (+ Source), code fence → code view, JSON → pretty, else text.
   * Fills the host; host must be a flex column with min-height:0.
   */
  function renderDynamicContent(host, raw, opts) {
    opts = opts || {};
    const text = String(raw || "");
    host.innerHTML = "";
    host.classList.add("dyn-host");

    const html = extractHtml(text);
    if (html) {
      host.dataset.kind = "html";
      const bar = document.createElement("div");
      bar.className = "dyn-bar";
      const kind = document.createElement("span");
      kind.className = "dyn-kind";
      kind.textContent = "HTML";
      bar.appendChild(kind);
      const modes = document.createElement("div");
      modes.className = "worker-panel-modes";
      const btnPrev = document.createElement("button");
      btnPrev.type = "button";
      btnPrev.className = "worker-mode-btn is-active";
      btnPrev.textContent = "Preview";
      btnPrev.dataset.mode = "preview";
      const btnSrc = document.createElement("button");
      btnSrc.type = "button";
      btnSrc.className = "worker-mode-btn";
      btnSrc.textContent = "Source";
      btnSrc.dataset.mode = "source";
      modes.appendChild(btnPrev);
      modes.appendChild(btnSrc);
      bar.appendChild(modes);
      host.appendChild(bar);

      const stage = document.createElement("div");
      stage.className = "dyn-stage";
      const frame = document.createElement("iframe");
      frame.className = "worker-preview-frame dyn-frame";
      frame.setAttribute(
        "sandbox",
        "allow-same-origin allow-forms allow-popups allow-modals"
      );
      frame.setAttribute("title", opts.title || "preview");
      frame.setAttribute("scrolling", "no"); /* pure box — no scroll */
      frame.srcdoc = wrapHtmlDocument(html);
      const pre = document.createElement("pre");
      pre.className = "result-block worker-source dyn-source";
      pre.textContent = text;
      pre.hidden = true;
      stage.appendChild(frame);
      stage.appendChild(pre);
      host.appendChild(stage);

      modes.querySelectorAll(".worker-mode-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
          modes.querySelectorAll(".worker-mode-btn").forEach(function (b) {
            b.classList.remove("is-active");
          });
          btn.classList.add("is-active");
          if (btn.dataset.mode === "preview") {
            frame.hidden = false;
            pre.hidden = true;
          } else {
            frame.hidden = true;
            pre.hidden = false;
          }
        });
      });
      return "html";
    }

    // fenced code ```lang ... ```
    const fence = text.match(/```([a-zA-Z0-9_+-]*)\s*\n([\s\S]*?)```/);
    if (fence && fence[2] && fence[2].trim().length > 0) {
      host.dataset.kind = "code";
      const bar = document.createElement("div");
      bar.className = "dyn-bar";
      const kind = document.createElement("span");
      kind.className = "dyn-kind";
      kind.textContent = (fence[1] || "code").toUpperCase();
      bar.appendChild(kind);
      host.appendChild(bar);
      const stage = document.createElement("div");
      stage.className = "dyn-stage";
      const pre = document.createElement("pre");
      pre.className = "result-block dyn-source dyn-code";
      pre.textContent = fence[2].replace(/\n$/, "");
      stage.appendChild(pre);
      // if more text outside fence, append note
      const rest = text.replace(fence[0], "").trim();
      if (rest) {
        const note = document.createElement("pre");
        note.className = "result-block dyn-note";
        note.textContent = rest;
        stage.appendChild(note);
      }
      host.appendChild(stage);
      return "code";
    }

    // JSON object/array
    const t = text.trim();
    if (
      (t.startsWith("{") && t.endsWith("}")) ||
      (t.startsWith("[") && t.endsWith("]"))
    ) {
      try {
        const pretty = JSON.stringify(JSON.parse(t), null, 2);
        host.dataset.kind = "json";
        const bar = document.createElement("div");
        bar.className = "dyn-bar";
        const kind = document.createElement("span");
        kind.className = "dyn-kind";
        kind.textContent = "JSON";
        bar.appendChild(kind);
        host.appendChild(bar);
        const stage = document.createElement("div");
        stage.className = "dyn-stage";
        const pre = document.createElement("pre");
        pre.className = "result-block dyn-source dyn-code";
        pre.textContent = pretty;
        stage.appendChild(pre);
        host.appendChild(stage);
        return "json";
      } catch (_e) {
        /* fall through */
      }
    }

    host.dataset.kind = "text";
    const stage = document.createElement("div");
    stage.className = "dyn-stage";
    const pre = document.createElement("pre");
    pre.className = "result-block dyn-source";
    pre.textContent = text;
    stage.appendChild(pre);
    host.appendChild(stage);
    return "text";
  }

  function setBox2(htmlOrText) {
    const body =
      (typeof getAgentBoxBody === "function" && getAgentBoxBody(2, "brainstorm")) ||
      document.getElementById("box2-content");
    if (!body) return;
    renderDynamicContent(body, htmlOrText || "", { title: "Brainstorm" });
  }

  /** Write text into a specific agent layer in box 2 (e.g. flex notes). */
  function setBox2Agent(agentId, htmlOrText, title) {
    const body =
      (typeof getAgentBoxBody === "function" && getAgentBoxBody(2, agentId)) ||
      document.getElementById("box2-" + agentId);
    if (!body) return;
    renderDynamicContent(body, htmlOrText || "", { title: title || agentId });
  }

  /**
   * Extract real HTML documents for Preview iframes.
   * Strict on purpose: QA/a11y notes often mention tags (e.g. </html>) and must
   * stay as plain text — not empty/broken preview frames.
   */
  function extractHtml(raw) {
    const s = String(raw || "");
    // Explicit ```html fence with a real document or substantial markup
    const fenceHtml = s.match(/```html\s*([\s\S]*?)```/i);
    if (fenceHtml && fenceHtml[1]) {
      const body = fenceHtml[1].trim();
      if (/<!DOCTYPE\s+html|<html[\s>]/i.test(body)) return body;
      if (body.startsWith("<") && (body.match(/<\w+/g) || []).length >= 4) return body;
    }
    // Full document with doctype + closing html (preferred)
    const fullDoc = s.match(/(<!DOCTYPE\s+html[\s\S]*?<\/html>)/i);
    if (fullDoc) return fullDoc[1].trim();
    // Open doctype document (truncated mid-file still previewable)
    const doctypeOpen = s.match(/(<!DOCTYPE\s+html[\s\S]{120,})$/i);
    if (doctypeOpen && /<(html|head|body)[\s>]/i.test(doctypeOpen[1])) {
      return doctypeOpen[1].trim();
    }
    const htmlTag = s.match(/(<html[\s\S]*?<\/html>)/i);
    if (htmlTag) return htmlTag[1].trim();
    // Markup-first fragment only: must start with tag, enough structure, high density
    const trimmed = s.trim();
    if (
      trimmed.startsWith("<") &&
      /<\/(div|section|body|main|header|footer|article|html)>/i.test(trimmed)
    ) {
      const tags = (trimmed.match(/<\w+/g) || []).length;
      const prose = trimmed.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
      // Prefer markup over prose (avoids checklists that quote a few tags)
      if (tags >= 6 && prose.length < trimmed.length * 0.55) return trimmed;
    }
    return null;
  }

  /**
   * Box 3: dynamic — one panel per worker result (all outputs, not only first).
   * HTML → Preview + Source; plain text → pre. Panels share height equally.
   */
  function updateBox3Toolbar() {
    // Box 3 toolbar intentionally minimal (no history/diff chrome)
  }

  function showBox3ResultStage(out, idx) {
    const stage = document.getElementById("box3-result-stage");
    const body = document.getElementById("box3-result-body");
    const label = document.getElementById("box3-result-label");
    if (!stage || !body) return false;
    const raw = (out && out.result) != null ? String(out.result) : "";
    if (!raw.trim()) {
      stage.hidden = true;
      stage.classList.remove("is-open");
      return false;
    }
    body.innerHTML = "";
    body.classList.add("box3-dynamic", "box3-result-split");
    const name = (out && (out.name || out.worker)) || "Worker";
    const html = extractHtml(raw);
    if (label) {
      label.textContent =
        name +
        " · " +
        raw.length +
        " Zeichen" +
        (html ? " · HTML-Preview" : " · Text") +
        (lastWorkerOutputs.length > 1
          ? " · " + lastWorkerOutputs.length + " Worker"
          : "");
    }

    /*
     * Split view: ALWAYS show readable source + optional live preview.
     * iframe-only looked "only white" when CSS was broken / height collapsed.
     */
    const split = document.createElement("div");
    split.className = "box3-split";

    if (html) {
      const prevWrap = document.createElement("div");
      prevWrap.className = "box3-split-preview";
      const frame = document.createElement("iframe");
      frame.className = "worker-preview-frame box3-live-frame";
      frame.setAttribute("title", name + " Preview");
      frame.setAttribute(
        "sandbox",
        "allow-same-origin allow-scripts allow-forms allow-popups allow-modals"
      );
      // blob URL is more reliable than srcdoc on some Chromium builds
      try {
        const blob = new Blob([wrapHtmlDocument(html)], {
          type: "text/html;charset=utf-8",
        });
        frame.src = URL.createObjectURL(blob);
        frame._blobUrl = frame.src;
      } catch (_e) {
        frame.srcdoc = wrapHtmlDocument(html);
      }
      prevWrap.appendChild(frame);
      split.appendChild(prevWrap);
    }

    const srcWrap = document.createElement("div");
    srcWrap.className = "box3-split-source";
    const srcHead = document.createElement("div");
    srcHead.className = "box3-split-source-h";
    srcHead.textContent = html ? "Quelltext (Worker-Ausgabe)" : "Worker-Ausgabe";
    const pre = document.createElement("pre");
    pre.className = "result-block box3-result-pre";
    pre.textContent = raw.slice(0, 30000);
    srcWrap.appendChild(srcHead);
    srcWrap.appendChild(pre);
    split.appendChild(srcWrap);

    body.appendChild(split);
    stage.hidden = false;
    stage.removeAttribute("hidden");
    stage.classList.add("is-open");

    const fs = document.getElementById("box3-result-fs");
    if (fs && !fs._bound) {
      fs._bound = true;
      fs.addEventListener("click", function () {
        const cur = lastWorkerOutputs[box3FocusIdx] || out;
        const raw2 = (cur && cur.result) || "";
        const html2 = extractHtml(raw2) || "";
        if (typeof openWorkerFullscreen === "function") {
          openWorkerFullscreen(cur, raw2, html2);
        } else if (html2) {
          openWorkerInTab(html2);
        }
      });
    }
    return true;
  }

  function hideBox3ResultStage() {
    const stage = document.getElementById("box3-result-stage");
    const body = document.getElementById("box3-result-body");
    if (body) body.innerHTML = "";
    if (stage) {
      stage.hidden = true;
      stage.classList.remove("is-open");
    }
  }

  function renderBox3Workers(pipeline) {
    const outputs = normalizeWorkerOutputs(pipeline);
    lastWorkerOutputs = outputs;
    updateBox3Toolbar();

    /* clear each worker agent layer in box 3 */
    ["worker1", "worker2", "worker3", "worker4"].forEach(function (wid) {
      const body =
        (typeof getAgentBoxBody === "function" && getAgentBoxBody(3, wid)) ||
        document.getElementById("box3-" + wid);
      if (!body) return;
      body.innerHTML = "";
      body.classList.add("box3-dynamic");
      const empty = document.createElement("p");
      empty.className = "muted empty-hint";
      if (pipeline && pipeline.stage === "work") {
        empty.textContent = "Workers laufen…";
      } else {
        empty.textContent = wid + " — noch kein Ergebnis";
      }
      body.appendChild(empty);
    });

    if (!outputs.length) {
      hideBox3ResultStage();
      return;
    }

    /* each worker → agent layer body */
    let firstAgentId = "worker1";
    let best = outputs[0];
    let bestLen = 0;
    outputs.forEach(function (out, idx) {
      const wid =
        (out && (out.worker || out.id || out.name) || "").toString().toLowerCase();
      let agentId = null;
      if (/worker\s*1|w1/.test(wid) || wid === "worker1") agentId = "worker1";
      else if (/worker\s*2|w2/.test(wid) || wid === "worker2") agentId = "worker2";
      else if (/worker\s*3|w3/.test(wid) || wid === "worker3") agentId = "worker3";
      else if (/worker\s*4|w4/.test(wid) || wid === "worker4") agentId = "worker4";
      else agentId = "worker" + Math.min(idx + 1, 4);
      if (idx === 0) firstAgentId = agentId;
      const raw = String((out && out.result) || "");
      if (raw.length > bestLen) {
        bestLen = raw.length;
        best = out;
        firstAgentId = agentId;
      }

      const body =
        (typeof getAgentBoxBody === "function" && getAgentBoxBody(3, agentId)) ||
        document.getElementById("box3-" + agentId);
      if (!body) return;
      body.innerHTML = "";
      body.classList.add("box3-dynamic");
      renderDynamicContent(body, raw, {
        title: ((out && out.name) || agentId) + " preview",
      });
    });

    // PRIMARY: always-open result stage (what the user looks at)
    const shown = showBox3ResultStage(best, 0);
    if (!shown) {
      // Fallback text if renderDynamicContent failed somehow
      const body = document.getElementById("box3-result-body");
      const stage = document.getElementById("box3-result-stage");
      if (body && stage && best) {
        body.innerHTML = "";
        const pre = document.createElement("pre");
        pre.className = "result-block";
        pre.textContent = String(best.result || "").slice(0, 20000);
        body.appendChild(pre);
        stage.hidden = false;
        stage.classList.add("is-open");
      }
    }

    if (typeof activateAgentLayer === "function") {
      try {
        activateAgentLayer(firstAgentId, false);
      } catch (_e) {
        /* ignore */
      }
    }

    box3FocusIdx = 0;
    bindBoxLayerControls();
    if (typeof focusBox3 === "function") {
      try {
        focusBox3();
      } catch (_e) {
        /* ignore */
      }
    }
  }

  /** Save one worker HTML into personal WS (WS-gnom-hub-v1/selected/). */
  async function keepWorkerToPersonalWs(out, idx) {
    const raw = (out && out.result) || "";
    const html = extractHtml(raw);
    if (!html) {
      toast("No HTML to keep — only HTML goes to personal WS", "info");
      return;
    }
    const name =
      ((out && (out.worker || out.name)) || "worker" + (idx + 1))
        .toString()
        .replace(/[^\w.-]+/g, "_") + ".html";
    try {
      const data = await api("POST", "/api/workspace/keep", {
        content: html,
        name: name,
        worker: (out && out.worker) || null,
      });
      toast(
        "Saved → " + (data.path || "personal WS/selected/") + " (Clear won't delete this)",
        "ok"
      );
      // optional clipboard convenience
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(html).catch(function () {});
      }
    } catch (err) {
      toast("Keep failed: " + (err.message || err), "error");
    }
  }

  function copyAllWorkerResults() {
    if (!lastWorkerOutputs.length) {
      toast("No worker results to copy", "info");
      return;
    }
    // Keep each HTML result into personal WS (only chosen outputs that are HTML)
    var kept = 0;
    lastWorkerOutputs.forEach(function (o, i) {
      if (extractHtml(o.result || "")) {
        kept += 1;
        keepWorkerToPersonalWs(o, i);
      }
    });
    if (!kept) {
      toast("No HTML among worker results to keep", "info");
      return;
    }
    const parts = lastWorkerOutputs.map(function (o, i) {
      const label = o.name || "Worker " + (i + 1);
      return "=== " + label + " ===\n" + (o.result || "");
    });
    const text = parts.join("\n\n");
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () {
          toast("Kept HTML to personal WS + clipboard (" + text.length + " chars)", "ok");
        },
        function () {
          toast("Copy failed", "error");
        }
      );
    } else {
      toast("Clipboard not available", "error");
    }
  }

  /**
   * Simple line LCS unified-style diff (capped for large texts).
   * Returns array of {type: same|add|del|meta, text}.
   */
  function computeLineDiff(textA, textB) {
    const MAX = 400;
    let a = String(textA || "").split("\n");
    let b = String(textB || "").split("\n");
    let truncated = false;
    if (a.length > MAX) {
      a = a.slice(0, MAX);
      truncated = true;
    }
    if (b.length > MAX) {
      b = b.slice(0, MAX);
      truncated = true;
    }
    const n = a.length;
    const m = b.length;
    // DP LCS lengths
    const dp = [];
    for (let i = 0; i <= n; i++) {
      dp[i] = new Array(m + 1).fill(0);
    }
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        if (a[i] === b[j]) dp[i][j] = dp[i + 1][j + 1] + 1;
        else dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
    const lines = [];
    let i = 0;
    let j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) {
        lines.push({ type: "same", text: "  " + a[i] });
        i++;
        j++;
      } else if (dp[i + 1][j] >= dp[i][j + 1]) {
        lines.push({ type: "del", text: "- " + a[i] });
        i++;
      } else {
        lines.push({ type: "add", text: "+ " + b[j] });
        j++;
      }
    }
    while (i < n) {
      lines.push({ type: "del", text: "- " + a[i] });
      i++;
    }
    while (j < m) {
      lines.push({ type: "add", text: "+ " + b[j] });
      j++;
    }
    if (truncated) {
      lines.push({
        type: "meta",
        text: "… truncated to first " + MAX + " lines per side",
      });
    }
    return lines;
  }

  function closeDiffOverlay() {
    const el = document.getElementById("diff-overlay");
    if (el) el.remove();
  }

  function openWorkerDiff() {
    if (lastWorkerOutputs.length < 2) {
      toast("Need at least two worker results to diff", "info");
      return;
    }
    closeDiffOverlay();
    closeWorkerFullscreen();
    const a = lastWorkerOutputs[0];
    const b = lastWorkerOutputs[1];
    const nameA = a.name || "Worker 1";
    const nameB = b.name || "Worker 2";
    const rows = computeLineDiff(a.result || "", b.result || "");

    const overlay = document.createElement("div");
    overlay.id = "diff-overlay";
    overlay.className = "diff-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-label", "Worker diff");

    const bar = document.createElement("div");
    bar.className = "diff-bar";
    const title = document.createElement("span");
    title.className = "diff-title";
    title.textContent = "Diff: " + nameA + " → " + nameB;
    const actions = document.createElement("div");
    actions.className = "worker-fs-actions";
    const btnCopy = document.createElement("button");
    btnCopy.type = "button";
    btnCopy.className = "worker-mode-btn";
    btnCopy.textContent = "Copy diff";
    btnCopy.addEventListener("click", function () {
      const text = rows.map(function (r) {
        return r.text;
      }).join("\n");
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(
          function () {
            toast("Diff copied", "ok");
          },
          function () {
            toast("Copy failed", "error");
          }
        );
      }
    });
    const btnClose = document.createElement("button");
    btnClose.type = "button";
    btnClose.className = "worker-mode-btn";
    btnClose.textContent = "Close · Esc";
    btnClose.addEventListener("click", closeDiffOverlay);
    actions.appendChild(btnCopy);
    actions.appendChild(btnClose);
    bar.appendChild(title);
    bar.appendChild(actions);

    const body = document.createElement("div");
    body.className = "diff-body";
    const meta = document.createElement("span");
    meta.className = "diff-line diff-meta";
    meta.textContent =
      "− " + nameA + "   + " + nameB + "   (" + rows.length + " lines)";
    body.appendChild(meta);
    rows.forEach(function (r) {
      const span = document.createElement("span");
      span.className = "diff-line diff-" + r.type;
      span.textContent = r.text;
      body.appendChild(span);
    });

    overlay.appendChild(bar);
    overlay.appendChild(body);
    overlay.addEventListener("click", function (ev) {
      if (ev.target === overlay) closeDiffOverlay();
    });
    document.body.appendChild(overlay);
  }

  function normalizeWorkerOutputs(pipeline) {
    const p = pipeline || {};
    if (p.worker_outputs && p.worker_outputs.length) {
      return p.worker_outputs.map(function (o, i) {
        return {
          worker: o.worker || "worker" + (i + 1),
          name: o.name || "Worker " + (i + 1),
          task: o.task || "",
          result: o.result != null ? String(o.result) : "",
          index: o.index != null ? o.index : i + 1,
        };
      });
    }
    if (p.worker_results && p.worker_results.length) {
      return p.worker_results.map(function (r, i) {
        return {
          worker: "worker" + (i + 1),
          name: "Worker " + (i + 1),
          task: "",
          result: String(r),
          index: i + 1,
        };
      });
    }
    return [];
  }

  let box3FocusIdx = 0;
  let box3FrontSlot = "a"; // which dual-layer slot is front
  let box3BlendBusy = false;

  function updateBox3WorkerLabel(idx, n) {
    /* label UI removed — pure box frame */
    void idx;
    void n;
  }

  function paintWorkerIntoSlot(slotEl, out, idx) {
    if (!slotEl) return;
    slotEl.innerHTML = "";
    slotEl.dataset.workerIdx = String(idx);
    const wrap = document.createElement("div");
    wrap.className = "worker-panel-body dual-slot-body";
    renderDynamicContent(wrap, (out && out.result) || "", {
      title: ((out && out.name) || "Worker") + " preview",
    });
    // copy control lives on box layer-controls; keep content clean
    slotEl.appendChild(wrap);
  }

  function focusBox3Worker(idx) {
    const dual = document.getElementById("box3-dual");
    if (!dual || !lastWorkerOutputs.length) return;
    if (box3BlendBusy) return;
    const n = lastWorkerOutputs.length;
    const nextIdx = ((idx % n) + n) % n;
    if (nextIdx === box3FocusIdx && dual.querySelector(".layer-slot.is-front .dual-slot-body")) {
      updateBox3WorkerLabel(box3FocusIdx, n);
      return;
    }

    const front = dual.querySelector(".layer-slot.is-front");
    const back = dual.querySelector(".layer-slot:not(.is-front)");
    if (!front || !back) return;

    // paint next worker into back layer, then crossfade
    paintWorkerIntoSlot(back, lastWorkerOutputs[nextIdx], nextIdx);
    box3BlendBusy = true;
    // force reflow so transition runs
    void back.offsetWidth;
    front.classList.remove("is-front");
    front.classList.add("is-back");
    back.classList.remove("is-back");
    back.classList.add("is-front");
    box3FocusIdx = nextIdx;
    box3FrontSlot = back.dataset.slot || box3FrontSlot;
    updateBox3WorkerLabel(box3FocusIdx, n);

    window.setTimeout(function () {
      box3BlendBusy = false;
      // clear old front to free memory (large HTML)
      const old = dual.querySelector(".layer-slot:not(.is-front)");
      if (old) old.innerHTML = "";
    }, 380);
  }

  function bindBoxLayerControls() {
    /* box chrome buttons removed — pure frame */
  }

  function wrapHtmlDocument(html) {
    let doc = html || "";
    if (!/<!DOCTYPE/i.test(doc) && !/<html/i.test(doc)) {
      doc =
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">" +
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">" +
        "<style>body{font-family:system-ui,sans-serif;margin:12px;}</style>" +
        "</head><body>" +
        doc +
        "</body></html>";
    }
    return doc;
  }

  function workerFileBase(out) {
    return (out.name || out.worker || "worker")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "worker";
  }

  function downloadWorkerResult(out, raw, html) {
    const isHtml = !!html;
    const blob = new Blob([isHtml ? wrapHtmlDocument(html) : raw || ""], {
      type: isHtml ? "text/html;charset=utf-8" : "text/plain;charset=utf-8",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = workerFileBase(out) + (isHtml ? ".html" : ".txt");
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 500);
    toast("Downloaded " + a.download, "ok");
  }

  function openWorkerInTab(html) {
    const doc = wrapHtmlDocument(html);
    const blob = new Blob([doc], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const win = window.open(url, "_blank");
    if (!win) {
      toast("Popup blocked — allow popups for new tab", "error");
      URL.revokeObjectURL(url);
      return;
    }
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 60000);
    toast("Opened in new tab", "ok");
  }

  async function saveWorkerToWorkspace(out, raw, html, zone) {
    const isHtml = !!html;
    const z = zone === "perm" ? "perm" : "temp";
    const name =
      workerFileBase(out) +
      "_" +
      Date.now().toString(36) +
      (isHtml ? ".html" : ".txt");
    const content = isHtml ? wrapHtmlDocument(html) : raw || "";
    try {
      const data = await api("POST", "/api/workspace/write", {
        zone: z,
        name: name,
        content: content,
      });
      const label = z === "perm" ? "perm" : "temp";
      toast("Saved → " + label + ": " + name, "ok");
      appendChat(
        "system",
        "Workspace[" + label + "] ← " + name + (data.path ? " (" + data.path + ")" : "")
      );
    } catch (err) {
      toast("Workspace save failed: " + err.message, "error");
    }
  }

  function closeWorkerFullscreen() {
    const el = document.getElementById("worker-fs-overlay");
    if (el) el.remove();
    document.body.classList.remove("worker-fs-open");
  }

  function openWorkerFullscreen(out, raw, html) {
    closeWorkerFullscreen();
    const overlay = document.createElement("div");
    overlay.id = "worker-fs-overlay";
    overlay.className = "worker-fs-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-label", "Fullscreen preview");

    const bar = document.createElement("div");
    bar.className = "worker-fs-bar";
    const title = document.createElement("span");
    title.className = "worker-fs-title";
    title.textContent = (out.name || "Worker") + " · fullscreen";
    const actions = document.createElement("div");
    actions.className = "worker-fs-actions";

    const btnDl = document.createElement("button");
    btnDl.type = "button";
    btnDl.className = "worker-mode-btn";
    btnDl.textContent = "Download";
    btnDl.addEventListener("click", function () {
      downloadWorkerResult(out, raw, html);
    });

    const btnClose = document.createElement("button");
    btnClose.type = "button";
    btnClose.className = "worker-mode-btn";
    btnClose.textContent = "Close · Esc";
    btnClose.addEventListener("click", closeWorkerFullscreen);

    actions.appendChild(btnDl);
    actions.appendChild(btnClose);
    bar.appendChild(title);
    bar.appendChild(actions);

    const body = document.createElement("div");
    body.className = "worker-fs-body";
    if (html) {
      const frame = document.createElement("iframe");
      frame.className = "worker-fs-frame";
      frame.setAttribute(
        "sandbox",
        "allow-same-origin allow-forms allow-popups allow-modals"
      );
      frame.setAttribute("title", (out.name || "Worker") + " fullscreen");
      frame.srcdoc = wrapHtmlDocument(html);
      body.appendChild(frame);
    } else {
      const pre = document.createElement("pre");
      pre.className = "worker-fs-source";
      pre.textContent = raw || "";
      body.appendChild(pre);
    }

    overlay.appendChild(bar);
    overlay.appendChild(body);
    overlay.addEventListener("click", function (ev) {
      if (ev.target === overlay) closeWorkerFullscreen();
    });
    document.body.appendChild(overlay);
    document.body.classList.add("worker-fs-open");
  }

  /** Scroll Box 3 into view and flash highlight after Execute. */
  function focusBox3() {
    const box = document.getElementById("box3");
    if (!box) return;
    try {
      box.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (_e) {
      box.scrollIntoView();
    }
    box.classList.add("box3-flash");
    setTimeout(function () {
      box.classList.remove("box3-flash");
    }, 1200);
  }

  function setBox3(htmlOrText) {
    // Legacy plain-text path (tests / external hooks)
    renderBox3Workers({
      stage: "done",
      worker_results: htmlOrText ? [String(htmlOrText)] : [],
    });
  }

  async function bootstrap() {
    restoreChatLog();
    try {
      // Ensure all pipeline agents are ON (Worker 1+2 included)
      try {
        const allOn = await api("POST", "/api/agents/enable-all");
        if (allOn.agents) applyAgentsFromServer(allOn.agents);
      } catch (_e) {
        /* older server without endpoint */
      }
      const snap = await api("GET", "/api/state");
      await loadTooltips((snap && snap.ui_lang) || "en");
      applySnapshot(snap);
      const defaultModel = (snap.llm && snap.llm.default_model) || "deepseek-chat";
      AGENTS.forEach(function (a) {
        if (!a.model || a.model === "—") a.model = defaultModel;
      });
      // phase3 UI chrome (god/cold/vec badges)
      if (snap.features && snap.features.phase3 === false) {
        document.body.classList.add("phase3-off");
      } else {
        document.body.classList.remove("phase3-off");
      }
      renderCards();
    } catch (err) {
      console.warn("[GnomHub] offline / no API yet:", err.message);
    }
  }

