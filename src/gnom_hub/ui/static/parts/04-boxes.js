/* part: 04-boxes.js  lines 3682-4267 of app.js — edit parts, run scripts/build_ui_js.py */

  let box3FocusIdx = 0;
  let lastBox3StageKey = "";
  let box2ReplyAgent = "";

  function box2AgentTabLabel(role) {
    const id = String(role || "").toLowerCase();
    if (id === "brainstorm") return "Brain";
    if (id === "flex") return "Flex";
    if (id === "coordinator") return "Coord";
    if (id === "memory") return "Mem";
    const wm = /^worker(\d+)$/.exec(id);
    if (wm) return "A" + wm[1];
    return "Antw";
  }

  function box2AgentTabTitle(role) {
    const id = String(role || "").toLowerCase();
    if (id === "brainstorm") return "Brainstorm";
    if (id === "flex") return "Flex";
    if (id === "coordinator") return "Koordinator";
    if (id === "memory") return "Memory";
    const wm = /^worker(\d+)$/.exec(id);
    if (wm) return "Arbeiter " + wm[1];
    return "Antwort";
  }

  function showBox2ReplyLayer(agentId) {
    const stack = document.getElementById("box2-layers");
    if (!stack) return;
    const aid = String(agentId || "brainstorm").toLowerCase();
    stack.querySelectorAll(".agent-layer").forEach(function (layer) {
      const on = layer.getAttribute("data-agent") === aid;
      layer.classList.toggle("is-active", on);
      layer.hidden = !on;
    });
  }

  function renderBox2ReplyTabs(turns) {
    const host = document.getElementById("box2-reply-tabs");
    if (!host) return;
    const answers = [];
    const seen = {};
    function addAnswer(role) {
      const id = String(role || "").toLowerCase();
      if (!id || id === "user" || id === "you" || id === "du") return;
      if (seen[id]) return;
      seen[id] = true;
      answers.push(id);
    }
    (Array.isArray(turns) ? turns : []).forEach(function (t) {
      addAnswer(t && t.role);
    });
    const pipe =
      (typeof lastSnapshot !== "undefined" &&
        lastSnapshot &&
        lastSnapshot.pipeline) ||
      {};
    if (pipe.flex_notes) addAnswer("flex");
    if (pipe.distilled_requirements && pipe.distilled_requirements.length) {
      addAnswer("coordinator");
    }
    const box = document.getElementById("box2");
    host.textContent = "";
    if (!answers.length) {
      host.hidden = true;
      box2ReplyAgent = "";
      if (box) box.classList.remove("box2-has-tabs");
      return;
    }
    host.hidden = false;
    if (box) box.classList.add("box2-has-tabs");
    const pick =
      box2ReplyAgent && seen[box2ReplyAgent] ? box2ReplyAgent : answers[0];
    if (box2ReplyAgent) showBox2ReplyLayer(pick);
    answers.forEach(function (role) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "box2-reply-tab" + (role === pick ? " is-on" : "");
      btn.setAttribute("role", "tab");
      btn.setAttribute("aria-selected", role === pick ? "true" : "false");
      btn.textContent = box2AgentTabLabel(role);
      btn.title = box2AgentTabTitle(role);
      if (typeof markOwner === "function") {
        markOwner(btn, role);
      } else if (typeof COLOR_HEX !== "undefined" && COLOR_HEX[role]) {
        btn.style.setProperty("--owner-color", COLOR_HEX[role]);
      }
      btn.addEventListener("click", function () {
        box2ReplyAgent = role;
        const stage = document.getElementById("box2-page-stage");
        if (stage && !stage.hidden && typeof closeBox2Page === "function") {
          closeBox2Page();
        }
        showBox2ReplyLayer(role);
        host.querySelectorAll(".box2-reply-tab").forEach(function (el) {
          const on = el === btn;
          el.classList.toggle("is-on", on);
          el.setAttribute("aria-selected", on ? "true" : "false");
        });
      });
      host.appendChild(btn);
    });
  }

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
      btnPrev.textContent = "Sicht";
      btnPrev.dataset.mode = "preview";
      const btnSrc = document.createElement("button");
      btnSrc.type = "button";
      btnSrc.className = "worker-mode-btn";
      btnSrc.textContent = "Code";
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
        "allow-same-origin allow-scripts allow-forms allow-popups allow-modals"
      );
      frame.setAttribute("title", opts.title || "Vorschau");
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

  function paintHtmlPage(host, html, title) {
    if (!host) return;
    revokeBox3Blobs(host);
    host.innerHTML = "";
    host.classList.add("box-page-host");
    const frame = document.createElement("iframe");
    frame.className = "worker-preview-frame box-page-frame box3-live-frame";
    frame.setAttribute("title", title || "Seite");
    frame.setAttribute(
      "sandbox",
      "allow-same-origin allow-scripts allow-forms allow-popups allow-modals"
    );
    const docHtml = wrapHtmlDocument(html);
    try {
      const blob = new Blob([docHtml], { type: "text/html;charset=utf-8" });
      frame.src = URL.createObjectURL(blob);
      frame._blobUrl = frame.src;
    } catch (_e) {
      frame.srcdoc = docHtml;
    }
    host.appendChild(frame);
  }

  function closeBox2Page() {
    /* Overlay off → answer in Box 2. Chat is untouched. */
    const stage = document.getElementById("box2-page-stage");
    const body = document.getElementById("box2-page-body");
    if (body) {
      revokeBox3Blobs(body);
      body.innerHTML = "";
    }
    if (stage) {
      stage.hidden = true;
      stage.classList.remove("is-open");
    }
    const boxes = document.querySelector(".boxes");
    if (boxes) boxes.classList.remove("pages-expanded");
  }

  function showBox2Page(out, raw, html) {
    const stage = document.getElementById("box2-page-stage");
    const body = document.getElementById("box2-page-body");
    const label = document.getElementById("box2-page-label");
    if (!stage || !body) {
      if (html) setBox2(String(raw || html));
      return;
    }
    const name = (out && (out.name || out.worker)) || "Seite";
    if (label) {
      label.textContent =
        name + " · Seite in Box 2" + (html ? " · HTML" : " · Text");
    }
    if (html) {
      paintHtmlPage(body, html, name);
    } else {
      body.innerHTML = "";
      const pre = document.createElement("pre");
      pre.className = "result-block box3-result-pre";
      pre.textContent = String(raw || "").slice(0, 30000);
      body.appendChild(pre);
    }
    stage.hidden = false;
    stage.removeAttribute("hidden");
    stage.classList.add("is-open");
    const boxes = document.querySelector(".boxes");
    if (boxes) boxes.classList.add("pages-expanded");
    const closeBtn = document.getElementById("box2-page-close");
    if (closeBtn && !closeBtn._bound) {
      closeBtn._bound = true;
      closeBtn.addEventListener("click", closeBox2Page);
    }
  }

  /** Focused worker → Box3; second HTML worker → Box2 page. */
  function syncWorkerPagesToBoxes() {
    const outs = lastWorkerOutputs || [];
    if (!outs.length) {
      closeBox2Page();
      return;
    }
    const focusIdx =
      typeof box3FocusIdx === "number" && box3FocusIdx >= 0 ? box3FocusIdx : 0;
    const htmlIdx = [];
    outs.forEach(function (o, i) {
      if (extractHtml(String((o && o.result) || ""))) htmlIdx.push(i);
    });
    let side = -1;
    for (let i = 0; i < htmlIdx.length; i++) {
      if (htmlIdx[i] !== focusIdx) {
        side = htmlIdx[i];
        break;
      }
    }
    if (side >= 0) {
      const o = outs[side];
      const raw = String((o && o.result) || "");
      showBox2Page(o, raw, extractHtml(raw));
    } else {
      const stage = document.getElementById("box2-page-stage");
      if (stage && stage.classList.contains("is-open") && htmlIdx.length === 1) {
        const o = outs[htmlIdx[0]];
        const raw = String((o && o.result) || "");
        showBox2Page(o, raw, extractHtml(raw));
      } else if (htmlIdx.length === 0) {
        closeBox2Page();
      }
    }
  }

  function currentBox3Worker() {
    const outs = lastWorkerOutputs || [];
    const idx =
      typeof box3FocusIdx === "number" &&
      box3FocusIdx >= 0 &&
      box3FocusIdx < outs.length
        ? box3FocusIdx
        : 0;
    return { out: outs[idx] || null, idx: idx };
  }

  function box3WorkerTabLabel(out, i) {
    const raw = String((out && (out.worker || out.name)) || "").toLowerCase();
    const wm = /worker\s*(\d+)/.exec(raw);
    if (wm) return "A" + wm[1];
    return "A" + (i + 1);
  }

  function box3WorkerTabTitle(out, i) {
    return String((out && (out.name || out.worker)) || "Arbeiter " + (i + 1));
  }

  function renderBox3WorkerTabs() {
    const tabs = document.getElementById("box3-worker-tabs");
    if (!tabs) return;
    const outs = lastWorkerOutputs || [];
    tabs.innerHTML = "";
    if (outs.length < 1) {
      tabs.hidden = true;
      return;
    }
    tabs.hidden = false;
    outs.forEach(function (o, i) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className =
        "box3-worker-tab" + (i === box3FocusIdx ? " is-active" : "");
      btn.setAttribute("role", "tab");
      btn.setAttribute("aria-selected", i === box3FocusIdx ? "true" : "false");
      btn.textContent = box3WorkerTabLabel(o, i);
      btn.title = box3WorkerTabTitle(o, i);
      if (typeof markOwner === "function") {
        markOwner(btn, (o && o.worker) || "worker" + (i + 1));
      }
      btn.addEventListener("click", function () {
        focusBox3WorkerResult(i);
      });
      tabs.appendChild(btn);
    });
  }

  function focusBox3WorkerResult(idx) {
    const outs = lastWorkerOutputs || [];
    if (!outs.length) return;
    const next = Math.max(0, Math.min(outs.length - 1, idx | 0));
    box3FocusIdx = next;
    const out = outs[next];
    lastBox3StageKey = "";
    showBox3ResultStage(out, next);
    renderBox3WorkerTabs();
    try {
      syncWorkerPagesToBoxes();
    } catch (_e) {
      /* ignore */
    }
    try {
      const wid = String((out && out.worker) || "").toLowerCase();
      let agentId = null;
      if (/worker\s*1|w1/.test(wid) || wid === "worker1") agentId = "worker1";
      else if (/worker\s*2|w2/.test(wid) || wid === "worker2") agentId = "worker2";
      else if (/worker\s*3|w3/.test(wid) || wid === "worker3") agentId = "worker3";
      else if (/worker\s*4|w4/.test(wid) || wid === "worker4") agentId = "worker4";
      else agentId = "worker" + Math.min(next + 1, 4);
      if (agentId) highlightWorkerResult(agentId);
    } catch (_e) {
      /* ignore */
    }
  }

  function bindBox3ResultActions() {
    function withCurrent(fn) {
      return function (ev) {
        const cur = currentBox3Worker();
        if (!cur.out) {
          toast("Kein Worker-Ergebnis", "info");
          return;
        }
        const raw = String(cur.out.result || "");
        const html = extractHtml(raw) || "";
        fn(cur.out, cur.idx, raw, html, ev);
      };
    }
    const copy = document.getElementById("box3-btn-copy");
    if (copy && !copy._bound) {
      copy._bound = true;
      copy.addEventListener(
        "click",
        withCurrent(function (out, idx, raw) {
          const text = raw || "";
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard
              .writeText(text)
              .then(function () {
                toast("Kopiert", "ok");
              })
              .catch(function () {
                toast("Clipboard failed", "error");
              });
          } else {
            toast("Clipboard not available", "error");
          }
        })
      );
    }
    const dl = document.getElementById("box3-btn-dl");
    if (dl && !dl._bound) {
      dl._bound = true;
      dl.addEventListener(
        "click",
        withCurrent(function (out, idx, raw, html) {
          downloadWorkerResult(out, raw, html);
        })
      );
    }
    const open = document.getElementById("box3-btn-open");
    if (open && !open._bound) {
      open._bound = true;
      open.addEventListener(
        "click",
        withCurrent(function (out, idx, raw, html, ev) {
          if (!html) {
            toast("Kein HTML — lade Text herunter", "info");
            downloadWorkerResult(out, raw, html);
            return;
          }
          const forceTab = !!(ev && ev.shiftKey);
          openWorkerInTab(html, forceTab);
        })
      );
    }
    const keep = document.getElementById("box3-btn-keep");
    if (keep && !keep._bound) {
      keep._bound = true;
      keep.addEventListener(
        "click",
        withCurrent(function (out, idx) {
          keepWorkerToPersonalWs(out, idx);
        })
      );
    }
    const prev = document.getElementById("box3-btn-prev");
    if (prev && !prev._bound) {
      prev._bound = true;
      prev.addEventListener("click", function () {
        if (typeof focusBox3WorkerResult === "function") {
          focusBox3WorkerResult(Math.max(0, (box3FocusIdx || 0) - 1));
        }
      });
    }
    const next = document.getElementById("box3-btn-next");
    if (next && !next._bound) {
      next._bound = true;
      next.addEventListener("click", function () {
        const n = (lastWorkerOutputs && lastWorkerOutputs.length) || 0;
        if (typeof focusBox3WorkerResult === "function") {
          focusBox3WorkerResult(Math.min(n - 1, (box3FocusIdx || 0) + 1));
        }
      });
    }
    const away = document.getElementById("box3-btn-away");
    if (away && !away._bound) {
      away._bound = true;
      away.addEventListener("click", function () {
        const i = box3FocusIdx || 0;
        if (!lastWorkerOutputs || !lastWorkerOutputs[i]) return;
        const gone = lastWorkerOutputs[i];
        resultTrash.unshift(gone);
        lastWorkerOutputs.splice(i, 1);
        const tname =
          ((gone && (gone.worker || gone.name)) || "result")
            .toString()
            .replace(/[^\w.-]+/g, "_") + ".txt";
        if (typeof api === "function") {
          api("POST", "/api/workspace/write", {
            zone: "trash",
            name: tname,
            content: (gone && gone.result) || "",
          }).catch(function () {
            /* keep in-memory trash */
          });
        }
        toast("Weg — im Papierkorb, wiederherstellbar", "info");
        if (lastWorkerOutputs.length) {
          focusBox3WorkerResult(Math.min(i, lastWorkerOutputs.length - 1));
        } else {
          const stage = document.getElementById("box3-result-stage");
          if (stage) {
            stage.hidden = true;
            stage.classList.remove("is-open");
          }
          const emptyEl = document.getElementById("box3-empty");
          if (emptyEl) emptyEl.hidden = false;
          renderBox3WorkerTabs();
        }
      });
    }
    const neu = document.getElementById("box3-btn-new");
    if (neu && !neu._bound) {
      neu._bound = true;
      neu.addEventListener("click", function () {
        const i = box3FocusIdx || 0;
        const src = lastWorkerOutputs && lastWorkerOutputs[i];
        if (!src) return;
        const copy = {};
        Object.keys(src).forEach(function (k) {
          copy[k] = src[k];
        });
        copy.name = (src.name || src.worker || "Ergebnis") + " Variante";
        copy.variant_of = src.worker || i;
        lastWorkerOutputs.splice(i + 1, 0, copy);
        toast("Neu — Original bleibt, Variante daneben", "ok");
        focusBox3WorkerResult(i + 1);
      });
    }
    const temp = document.getElementById("box3-btn-temp");
    if (temp && !temp._bound) {
      temp._bound = true;
      temp.addEventListener(
        "click",
        withCurrent(function (out, idx, raw, html) {
          _saveWorkerToWorkspace(out, raw, html, "temp");
        })
      );
    }
    const perm = document.getElementById("box3-btn-perm");
    if (perm && !perm._bound) {
      perm._bound = true;
      perm.addEventListener(
        "click",
        withCurrent(function (out, idx, raw, html) {
          _saveWorkerToWorkspace(out, raw, html, "perm");
        })
      );
    }
  }

  /**
   * Extract real HTML documents for Preview iframes.
   * Strict on purpose: QA/a11y notes often mention tags (e.g. </html>) and must
   * stay as plain text — not empty/broken preview frames.
   */
  function extractHtml(raw) {
    const s = String(raw || "");
    // Closed ```html fence
    const fenceHtml = s.match(/```html\s*([\s\S]*?)```/i);
    if (fenceHtml && fenceHtml[1]) {
      const body = fenceHtml[1].trim();
      // Tiny fences (e.g. "ends") must not beat a later full <!DOCTYPE> document.
      if (body.length >= 80 && /<!DOCTYPE\s+html|<html[\s>]/i.test(body)) return body;
      if (
        body.length >= 80 &&
        body.startsWith("<") &&
        (body.match(/<\w+/g) || []).length >= 4
      ) {
        return body;
      }
    }
    // Open fence (worker cut off before closing ```) — common failure mode
    const fenceOpen = s.match(/```html\s*([\s\S]+)$/i);
    if (fenceOpen && fenceOpen[1]) {
      const body = fenceOpen[1].replace(/```\s*$/, "").trim();
      if (/<!DOCTYPE\s+html|<html[\s>]/i.test(body) && body.length >= 80) {
        return body;
      }
    }
    // Full document with doctype + closing html (preferred)
    const fullDoc = s.match(/(<!DOCTYPE\s+html[\s\S]*?<\/html>)/i);
    if (fullDoc) return fullDoc[1].trim();
    // Open doctype document (truncated mid-file still previewable)
    const doctypeOpen = s.match(/(<!DOCTYPE\s+html[\s\S]{80,})$/i);
    if (doctypeOpen && /<(html|head|body)[\s>]/i.test(doctypeOpen[1])) {
      return doctypeOpen[1].trim();
    }
    const htmlTag = s.match(/(<html[\s\S]*?<\/html>)/i);
    if (htmlTag) return htmlTag[1].trim();
    const htmlOpen = s.match(/(<html[\s\S]{80,})$/i);
    if (htmlOpen) return htmlOpen[1].trim();
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

  /** True when document has no usable body content (truncated mid-CSS etc.). */
  function htmlBodyIsEmpty(html) {
    const s = String(html || "");
    const m = s.match(/<body[^>]*>([\s\S]*)/i);
    if (!m) return true;
    const inner = m[1]
      .replace(/<\/body>[\s\S]*$/i, "")
      .replace(/<script[\s\S]*?<\/script>/gi, "")
      .replace(/<!--[\s\S]*?-->/g, "")
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    return inner.length < 12;
  }

  /**
   * Heal truncated worker HTML so the iframe shows a page, not a black void.
   * Workers often cut off mid-<style> with no </html>.
   */
  function healTruncatedHtml(html) {
    let doc = String(html || "").trim();
    if (!doc) return doc;
    const _incomplete =
      !/<\/html>/i.test(doc) ||
      htmlBodyIsEmpty(doc) ||
      (/<style[\s>]/i.test(doc) && !/<\/style>/i.test(doc));
    void _incomplete;

    if (/<style[\s>]/i.test(doc) && !/<\/style>/i.test(doc)) {
      doc += "\n</style>";
    }
    if (/<script[\s>](?![^<]*<\/script>)/i.test(doc) && !/<\/script>\s*$/i.test(doc)) {
      /* crude: if last script unclosed */
      if ((doc.match(/<script[\s>]/gi) || []).length > (doc.match(/<\/script>/gi) || []).length) {
        doc += "\n</script>";
      }
    }
    if (/<head[\s>]/i.test(doc) && !/<\/head>/i.test(doc)) {
      doc += "\n</head>";
    }

    if (!/<body[\s>]/i.test(doc) || htmlBodyIsEmpty(doc)) {
      /* Inject a visible page so user never sees "empty top / code bottom" only */
      const stub =
        '<body style="margin:0;font-family:system-ui,sans-serif;background:#12141a;color:#e8eaed;">' +
        '<main style="max-width:42rem;margin:0 auto;padding:1.5rem 1.25rem;">' +
        "<h1 style=\"font-size:1.35rem;margin:0 0 .75rem;\">Vorschau — Seite unvollständig</h1>" +
        "<p style=\"line-height:1.45;margin:0 0 .75rem;color:#b8bcc4;\">" +
        "Der Worker hat die HTML-Datei abgeschnitten (oft mitten im CSS, ohne sichtbaren Inhalt). " +
        "Unten siehst du den Quelltext. Bitte im Flex-Panel „Nochmal bauen“ oder „HTML reparieren“, dann in Box 1 mit Ja bestätigen." +
        "</p>" +
        "<p style=\"margin:0;font-size:.9rem;color:#8b909a;\">" +
        "Zeichen geliefert: " +
        String(doc.length) +
        " · kein fertiges &lt;body&gt;-Layout</p>" +
        "</main></body>";
      if (/<body[\s>]/i.test(doc)) {
        doc = doc.replace(/<body[^>]*>[\s\S]*$/i, stub);
      } else {
        doc += "\n" + stub;
      }
    } else if (!/<\/body>/i.test(doc)) {
      doc += "\n</body>";
    }
    if (!/<\/html>/i.test(doc)) {
      doc += "\n</html>";
    }
    if (!/<!DOCTYPE/i.test(doc) && !/<html/i.test(doc)) {
      return wrapHtmlDocument(doc);
    }
    if (!/<!DOCTYPE/i.test(doc) && /<html/i.test(doc)) {
      doc = "<!DOCTYPE html>\n" + doc;
    }
    return doc;
  }

  /**
   * Box 3: dynamic — one panel per worker result (all outputs, not only first).
   * HTML → Preview + Source; plain text → pre. Panels share height equally.
   */
  function updateBox3Toolbar() {
    // Box 3 toolbar intentionally minimal (no history/diff chrome)
  }

  /** Skip iframe rebuild when snapshot polls same worker payload (avoids white flash). */
  
  let lastBox3RenderKey = "";

  function box3OutputsKey(outputs, stage) {
    return (
      String(stage || "") +
      "|" +
      (outputs || [])
        .map(function (o) {
          const r = String((o && o.result) || "");
          return (
            String((o && (o.worker || o.name)) || "") +
            ":" +
            r.length +
            ":" +
            r.slice(0, 120) +
            ":" +
            r.slice(-120)
          );
        })
        .join("||")
    );
  }

  function revokeBox3Blobs(root) {
    if (!root) return;
    root.querySelectorAll("iframe").forEach(function (frame) {
      if (frame._blobUrl) {
        try {
          URL.revokeObjectURL(frame._blobUrl);
        } catch (_e) {
          /* ignore */
        }
        frame._blobUrl = null;
      }
    });
  }

  /**
   * Highlight which worker result is shown — without switching Box1/Box2 layers
   * or chat. Global activateAgentLayer(worker) was wiping brainstorm from Box2.
   */
  function highlightWorkerResult(agentId) {
    if (!agentId) return;
    document.querySelectorAll("#box3-layers .agent-layer").forEach(function (layer) {
      const on = layer.getAttribute("data-agent") === agentId;
      layer.classList.toggle("is-active", on);
      layer.hidden = !on;
    });
    /* Card ring = which deliverable; do not touch Box1/2 layers or lastClickedAgentId */
    document.querySelectorAll(".agent-card").forEach(function (card) {
      card.classList.toggle(
        "is-layer-active",
        card.dataset.agentId === agentId
      );
    });
    const hex =
      typeof COLOR_HEX !== "undefined" && COLOR_HEX[agentId]
        ? COLOR_HEX[agentId]
        : null;
    const mod = document.querySelector(".boxes");
    if (mod) {
      mod.style.setProperty("--boxes-mod-color", hex || "var(--border)");
    }
    const chatMod = document.getElementById("chat-mod");
    if (chatMod && hex) {
      chatMod.style.setProperty("--chat-mod-color", hex);
    }
  }


  /** Compact DoD checklist under Box 3 bar — only when gate failed / soft issues. */
  function renderDodChecklist(validation) {
    const host = document.getElementById("box3-dod-checklist");
    if (!host) return;
    const v = validation && typeof validation === "object" ? validation : null;
    const soft = (v && Array.isArray(v.soft_issues) && v.soft_issues.length) || false;
    const hardFail = v && v.ok === false;
    if (!v || (!hardFail && !soft)) {
      host.hidden = true;
      host.innerHTML = "";
      return;
    }
    const checklist = Array.isArray(v.checklist) ? v.checklist : [];
    const failed = checklist.filter(function (c) {
      return c && c.pass === false;
    });
    // Fallback: issues[] if checklist empty
    const rows =
      failed.length > 0
        ? failed
        : (v.issues || []).map(function (code) {
            return {
              id: code,
              label: code,
              severity: "must",
              pass: false,
            };
          });
    if (!rows.length && !soft) {
      host.hidden = true;
      host.innerHTML = "";
      return;
    }
    host.hidden = false;
    host.removeAttribute("hidden");
    host.innerHTML = "";
    const head = document.createElement("div");
    head.className = "box3-dod-head";
    const score = v.score != null ? v.score : "?";
    const bits = ["DoD", "score " + score];
    if (v.retryable) bits.push("retryable");
    if (hardFail) bits.push("fail");
    else if (soft) bits.push("soft");
    head.textContent = bits.join(" · ");
    host.appendChild(head);
    const ul = document.createElement("ul");
    ul.className = "box3-dod-list";
    rows.slice(0, 8).forEach(function (c) {
      const li = document.createElement("li");
      const sev = (c.severity || "must") === "should" ? "should" : "must";
      li.className = "box3-dod-item is-" + sev;
      const mark = document.createElement("span");
      mark.className = "box3-dod-mark";
      mark.textContent = "✗";
      const lab = document.createElement("span");
      lab.className = "box3-dod-lab";
      lab.textContent =
        (c.id || "item") +
        (c.label && c.label !== c.id ? " — " + String(c.label).slice(0, 90) : "");
      li.appendChild(mark);
      li.appendChild(lab);
      ul.appendChild(li);
    });
    host.appendChild(ul);
    if (Array.isArray(v.hints) && v.hints.length) {
      const hint = document.createElement("div");
      hint.className = "box3-dod-hint";
      hint.textContent = String(v.hints[0]).slice(0, 160);
      host.appendChild(hint);
    }
  }

  function showBox3ResultStage(out, idx) {
    const stage = document.getElementById("box3-result-stage");
    const body = document.getElementById("box3-result-body");
    const label = document.getElementById("box3-result-label");
    if (!stage || !body) return false;
    const emptyEl = document.getElementById("box3-empty");
    const raw = (out && out.result) != null ? String(out.result) : "";
    if (!raw.trim()) {
      lastBox3StageKey = "";
      revokeBox3Blobs(body);
      stage.hidden = true;
      stage.classList.remove("is-open");
      if (emptyEl) emptyEl.hidden = false;
      return false;
    }
    if (emptyEl) emptyEl.hidden = true;
    const name = (out && (out.name || out.worker)) || "Worker";
    const html = extractHtml(raw);
    let val = out && out.validation && typeof out.validation === "object" ? out.validation : null;
    if (!val && typeof lastSnapshot !== "undefined" && lastSnapshot && lastSnapshot.pipeline) {
      val =
        lastSnapshot.pipeline.validation &&
        typeof lastSnapshot.pipeline.validation === "object"
          ? lastSnapshot.pipeline.validation
          : null;
    }
    const valKey = val
      ? String(val.ok) +
        ":" +
        String(val.score) +
        ":" +
        (val.issues || []).join(",")
      : "";
    const stageKey =
      name +
      "|" +
      raw.length +
      "|" +
      raw.slice(0, 160) +
      "|" +
      raw.slice(-160) +
      "|" +
      (html ? "h" : "t") +
      "|" +
      valKey;
    /* Same payload already painted — keep iframe (no white flash on poll). */
    if (
      stageKey === lastBox3StageKey &&
      stage.classList.contains("is-open") &&
      body.childNodes.length
    ) {
      renderDodChecklist(val);
      return true;
    }
    lastBox3StageKey = stageKey;
    renderDodChecklist(val);
    revokeBox3Blobs(body);
    body.innerHTML = "";
    body.classList.add("box3-dynamic", "box3-result-split");
    // Honest FEHLER surface (worker body or DoD fail)
    stage.classList.remove("box3-fehler");
    const isFehler =
      /FEHLER/i.test(raw.slice(0, 400)) || (val && val.ok === false);
    if (isFehler) {
      stage.classList.add("box3-fehler");
      const banner = document.createElement("div");
      banner.className = "fehler-banner";
      const line = raw
        .split("\n")
        .find(function (ln) {
          return /FEHLER/i.test(ln);
        });
      banner.textContent = (
        line ||
        (val && val.ok === false
          ? "FEHLER — DoD fail" +
            (val.score != null ? " (score " + val.score + ")" : "")
          : "FEHLER")
      ).slice(0, 200);
      body.appendChild(banner);
    }
    if (label) {
      label.textContent = box3WorkerTabLabel(out, idx || 0);
      label.title = name;
    }

    const host = document.createElement("div");
    host.className = "dyn-host box3-dyn";
    if (html) {
      const bar = document.createElement("div");
      bar.className = "dyn-bar";
      const modes = document.createElement("div");
      modes.className = "worker-panel-modes";
      const btnPrev = document.createElement("button");
      btnPrev.type = "button";
      btnPrev.className = "worker-mode-btn is-active";
      btnPrev.textContent = "Sicht";
      btnPrev.dataset.mode = "preview";
      const btnSrc = document.createElement("button");
      btnSrc.type = "button";
      btnSrc.className = "worker-mode-btn";
      btnSrc.textContent = "Code";
      btnSrc.dataset.mode = "source";
      modes.appendChild(btnPrev);
      modes.appendChild(btnSrc);
      bar.appendChild(modes);
      host.appendChild(bar);
      const vis = document.createElement("div");
      vis.className = "dyn-stage";
      const frame = document.createElement("iframe");
      frame.className = "worker-preview-frame box3-live-frame dyn-frame";
      frame.setAttribute("title", name + " Sicht");
      frame.setAttribute(
        "sandbox",
        "allow-same-origin allow-scripts allow-forms allow-popups allow-modals"
      );
      const docHtml = wrapHtmlDocument(html);
      try {
        const blob = new Blob([docHtml], {
          type: "text/html;charset=utf-8",
        });
        frame.src = URL.createObjectURL(blob);
        frame._blobUrl = frame.src;
      } catch (_e) {
        frame.srcdoc = docHtml;
      }
      const pre = document.createElement("pre");
      pre.className = "result-block worker-source dyn-source box3-result-pre";
      pre.textContent = raw.slice(0, 30000);
      pre.hidden = true;
      vis.appendChild(frame);
      vis.appendChild(pre);
      host.appendChild(vis);
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
    } else {
      const vis = document.createElement("div");
      vis.className = "dyn-stage";
      const pre = document.createElement("pre");
      pre.className = "result-block dyn-source box3-result-pre";
      pre.textContent = raw.slice(0, 30000);
      vis.appendChild(pre);
      host.appendChild(vis);
    }
    body.appendChild(host);
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
    lastBox3StageKey = "";
    /* lastBox3RenderKey owned by renderBox3Workers */
    revokeBox3Blobs(body);
    if (body) body.innerHTML = "";
    if (stage) {
      stage.hidden = true;
      stage.classList.remove("is-open");
    }
    const strip = document.getElementById("box3-tool-strip");
    if (strip) {
      strip.hidden = true;
      strip.innerHTML = "";
    }
    const dod = document.getElementById("box3-dod-checklist");
    if (dod) {
      dod.hidden = true;
      dod.innerHTML = "";
    }
  }

  function renderToolStrip(toolLog, qualityNotes) {
    const strip = document.getElementById("box3-tool-strip");
    if (!strip) return;
    const log = Array.isArray(toolLog) ? toolLog : [];
    if (!log.length) {
      // fallback: quality_notes may list tools
      if (qualityNotes && /tool/i.test(String(qualityNotes))) {
        strip.hidden = false;
        strip.textContent = String(qualityNotes).slice(0, 220);
        return;
      }
      strip.hidden = true;
      strip.innerHTML = "";
      return;
    }
    strip.hidden = false;
    strip.innerHTML = "";
    log.slice(-16).forEach(function (e) {
      if (!e) return;
      const chip = document.createElement("span");
      const mode = String(e.mode || "");
      chip.className = "box3-tool-chip";
      if (mode === "dry-run") chip.classList.add("is-dry");
      else if (mode === "blocked") chip.classList.add("is-blocked");
      else if (e.ok === false || mode === "error") chip.classList.add("is-err");
      const ok = e.ok === false ? "✗" : "✓";
      const why = e.reason ? String(e.reason) : "";
      chip.textContent =
        ok +
        " " +
        (e.tool || e.name || "?") +
        (mode ? " · " + mode : "") +
        (why ? " · " + why.slice(0, 36) : "");
      chip.title = why
        ? "Why: " + why + "\n" + JSON.stringify(e)
        : JSON.stringify(e);
      strip.appendChild(chip);
    });
  }

  function renderBox3Workers(pipeline) {
    const outputs = normalizeWorkerOutputs(pipeline);
    const prevFocusName =
      lastWorkerOutputs && lastWorkerOutputs[box3FocusIdx]
        ? lastWorkerOutputs[box3FocusIdx].worker
        : null;
    lastWorkerOutputs = outputs;
    stageResultsRecovery(outputs);
    updateBox3Toolbar();
    if (pipeline) {
      renderToolStrip(pipeline.tool_log || [], pipeline.quality_notes || "");
    }

    const stageName = pipeline && pipeline.stage;
    const renderKey = box3OutputsKey(outputs, stageName);
    const stageEl = document.getElementById("box3-result-stage");
    /* Poll with unchanged worker output: do not wipe DOM / flash white. */
    if (
      outputs.length &&
      renderKey === lastBox3RenderKey &&
      stageEl &&
      stageEl.classList.contains("is-open")
    ) {
      // Still refresh DoD checklist (validation may arrive after first paint)
      const cur = outputs[typeof box3FocusIdx === "number" ? box3FocusIdx : 0] || outputs[0];
      if (typeof renderDodChecklist === "function") {
        const v =
          (cur && cur.validation) ||
          (pipeline && pipeline.validation) ||
          null;
        renderDodChecklist(v);
      }
      renderBox3WorkerTabs();
      return;
    }

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
      lastBox3RenderKey = renderKey;
      hideBox3ResultStage();
      return;
    }

    /* each worker → agent layer body (secondary; result stage is primary) */
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

    const contentChanged = renderKey !== lastBox3RenderKey;
    lastBox3RenderKey = renderKey;

    // Preserve focus across progressive worker arrivals
    let focusIdx = 0;
    if (contentChanged && prevFocusName) {
      const keepIdx = outputs.findIndex(function (o) {
        return o && o.worker === prevFocusName;
      });
      if (keepIdx !== -1) focusIdx = keepIdx;
    } else if (!contentChanged && typeof box3FocusIdx === "number") {
      focusIdx = Math.max(0, Math.min(outputs.length - 1, box3FocusIdx));
    } else {
      // first paint: prefer first HTML, else longest (best)
      let pick = 0;
      for (let i = 0; i < outputs.length; i++) {
        if (extractHtml(String((outputs[i] && outputs[i].result) || ""))) {
          pick = i;
          break;
        }
      }
      if (pick === 0 && best) {
        const bi = outputs.indexOf(best);
        if (bi >= 0) pick = bi;
      }
      focusIdx = pick;
    }
    box3FocusIdx = focusIdx;
    const focused = outputs[focusIdx] || best;

    // PRIMARY: always-open result stage (what the user looks at)
    const shown = showBox3ResultStage(focused, focusIdx);
    if (!shown) {
      const body = document.getElementById("box3-result-body");
      const stage = document.getElementById("box3-result-stage");
      if (body && stage && focused) {
        revokeBox3Blobs(body);
        body.innerHTML = "";
        const pre = document.createElement("pre");
        pre.className = "result-block box3-result-pre";
        pre.textContent = String(focused.result || "").slice(0, 20000);
        body.appendChild(pre);
        stage.hidden = false;
        stage.removeAttribute("hidden");
        stage.classList.add("is-open");
      }
    }

    renderBox3WorkerTabs();
    bindBox3ResultActions();
    try {
      syncWorkerPagesToBoxes();
    } catch (_e) {
      /* ignore */
    }

    /* Box3-only highlight — never activateAgentLayer(worker): that hid Box2 brainstorm */
    try {
      const wid = String((focused && focused.worker) || "").toLowerCase();
      let agentId = firstAgentId;
      if (/worker\s*1|w1/.test(wid) || wid === "worker1") agentId = "worker1";
      else if (/worker\s*2|w2/.test(wid) || wid === "worker2") agentId = "worker2";
      else if (/worker\s*3|w3/.test(wid) || wid === "worker3") agentId = "worker3";
      else if (/worker\s*4|w4/.test(wid) || wid === "worker4") agentId = "worker4";
      highlightWorkerResult(agentId);
    } catch (_e) {
      /* ignore */
    }

    bindBoxLayerControls();
    if (contentChanged && typeof focusBox3 === "function") {
      try {
        focusBox3();
      } catch (_e) {
        /* ignore */
      }
    }
  }

  let lastRecoveryKey = "";
  function stageResultsRecovery(outputs) {
    const list = Array.isArray(outputs) ? outputs : [];
    if (!list.length || typeof api !== "function") return;
    const key = list
      .map(function (o) {
        return String((o && (o.worker || o.name)) || "") + ":" + String((o && o.result) || "").length;
      })
      .join("|");
    if (key === lastRecoveryKey) return;
    lastRecoveryKey = key;
    list.forEach(function (o, i) {
      const raw = (o && o.result) || "";
      if (!raw) return;
      const name =
        ((o && (o.worker || o.name)) || "worker" + (i + 1))
          .toString()
          .replace(/[^\w.-]+/g, "_") + ".txt";
      api("POST", "/api/workspace/write", {
        zone: "recovery",
        name: name,
        content: raw,
      }).catch(function () {
        /* recovery is best-effort */
      });
    });
  }

  /** Save one worker result: HTML → selected/, other text → perm/. */
  async function keepWorkerToPersonalWs(out, idx, overwrite) {
    const raw = (out && out.result) || "";
    if (!String(raw).trim()) {
      toast("Nichts zum Behalten", "info");
      return;
    }
    const html = extractHtml(raw);
    const base =
      ((out && (out.worker || out.name)) || "worker" + (idx + 1))
        .toString()
        .replace(/[^\w.-]+/g, "_");
    const name = base + (html ? ".html" : ".txt");
    try {
      const data = await api("POST", "/api/workspace/keep", {
        content: html || raw,
        name: name,
        worker: (out && out.worker) || null,
        overwrite: !!overwrite,
      });
      if (data && data.ok === false && data.error === "exists") {
        const go = window.confirm(
          "Datei existiert schon:\n" +
            (data.path || name) +
            "\nÜberschreiben? Abbrechen belässt den Wiederherstellungsspeicher."
        );
        if (go) return keepWorkerToPersonalWs(out, idx, true);
        toast(data.status || "nicht überschrieben", "info");
        return;
      }
      if (!data || data.ok === false) {
        toast((data && data.status) || "Speichern fehlgeschlagen", "error");
        return;
      }
      toast(
        (data.status || "Behalten") +
          " · " +
          (data.path || name) +
          (data.kept_at ? " · " + data.kept_at : "") +
          (data.result_id ? " · " + data.result_id : ""),
        "ok"
      );
    } catch (err) {
      toast("Speichern fehlgeschlagen: " + (err.message || err), "error");
    }
  }

  function copyAllWorkerResults() {
    if (!lastWorkerOutputs.length) {
      toast("No worker results to copy", "info");
      return;
    }
    lastWorkerOutputs.forEach(function (o, i) {
      keepWorkerToPersonalWs(o, i);
    });
    const parts = lastWorkerOutputs.map(function (o, i) {
      const label = o.name || "Worker " + (i + 1);
      return "=== " + label + " ===\n" + (o.result || "");
    });
    const text = parts.join("\n\n");
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard
        .writeText(text)
        .then(function () {
          toast("Behalten + Zwischenablage (" + text.length + " Zeichen)", "ok");
        })
        .catch(function () {
          toast("Copy failed", "error");
        });
    }
    toast("Clipboard not available", "error");
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
        return navigator.clipboard
          .writeText(text)
          .then(function () {
            toast("Diff copied", "ok");
          })
          .catch(function () {
            toast("Copy failed", "error");
          });
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
          validation: o.validation && typeof o.validation === "object" ? o.validation : null,
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

  function _focusBox3Worker(idx) {
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

  function hideScrollbarCss() {
    return (
      "*{scrollbar-width:none;-ms-overflow-style:none}" +
      "*::-webkit-scrollbar{width:0;height:0}" +
      "html,body{overflow:auto}"
    );
  }

  function withHiddenScrollbars(doc) {
    const html = String(doc || "");
    if (!html) return html;
    if (html.indexOf("scrollbar-width:none") >= 0) return html;
    const style = "<style>" + hideScrollbarCss() + "</style>";
    if (/<head[\s>]/i.test(html)) {
      return html.replace(/<head([^>]*)>/i, "<head$1>" + style);
    }
    if (/<html[\s>]/i.test(html)) {
      return html.replace(/<html([^>]*)>/i, "<html$1><head>" + style + "</head>");
    }
    return style + html;
  }

  function wrapHtmlDocument(html) {
    let doc = html || "";
    /* Prefer healed full documents (truncated workers) */
    if (/<!DOCTYPE/i.test(doc) || /<html[\s>]/i.test(doc)) {
      return withHiddenScrollbars(healTruncatedHtml(doc));
    }
    /* Dark shell so fragments are not a blinding white box in the desk */
    doc =
      "<!DOCTYPE html><html><head><meta charset=\"utf-8\">" +
      "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">" +
      "<style>" +
      "html,body{margin:0;min-height:100%;background:#111;color:#e8eaed;" +
      "font-family:system-ui,sans-serif;overflow:auto;}" +
      "body{padding:12px;box-sizing:border-box;}" +
      "a{color:#7db7ff;}" +
      hideScrollbarCss() +
      "</style>" +
      "</head><body>" +
      doc +
      "</body></html>";
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

  function openWorkerInTab(html, forceExternal) {
    // Default: real page in Box 2 + Box 3 (no popup). Shift / force → browser tab.
    if (!forceExternal) {
      const cur = currentBox3Worker();
      const out = (cur && cur.out) || { name: "Seite" };
      const raw = (cur && cur.out && cur.out.result) || html;
      showBox2Page(out, raw, html);
      if (cur && cur.out && typeof showBox3ResultStage === "function") {
        lastBox3StageKey = "";
        showBox3ResultStage(out, cur.idx);
      }
      try {
        focusBox3();
      } catch (_e) {
        /* ignore */
      }
      toast("Seite in Box 2 + 3 — kein Popup", "ok");
      return;
    }
    const doc = wrapHtmlDocument(html);
    const blob = new Blob([doc], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const win = window.open(url, "_blank");
    if (!win) {
      toast("Popup blockiert — Seite bleibt in Box 2/3", "info");
      URL.revokeObjectURL(url);
      openWorkerInTab(html, false);
      return;
    }
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 60000);
    toast("Im Browser-Tab geöffnet", "ok");
  }

  async function _saveWorkerToWorkspace(out, raw, html, zone) {
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
    overlay.className = "worker-fs-overlay in-boxes";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-label", "Seiten-Ansicht in Boxen");

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
    const boxes = document.querySelector(".boxes");
    if (boxes) {
      boxes.appendChild(overlay);
      boxes.classList.add("pages-expanded");
    } else {
      document.body.appendChild(overlay);
    }
    document.body.classList.add("worker-fs-open");
    if (html) {
      try {
        showBox2Page(out, raw, html);
      } catch (_e) {
        /* ignore */
      }
    }
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

