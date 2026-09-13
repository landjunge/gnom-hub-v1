/* part: 05-system-ops.js — edit parts, run scripts/build_ui_js.py */
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
        "Ausgegeben: $" + spent.toFixed(4),
        "Tokens: " + pt + " Prompt + " + ct + " Antwort",
        "Budget: " + (budget != null && !isNaN(budget) ? "$" + budget.toFixed(2) : "keins"),
        "Nur kostenlos: " + (usage.free_only ? "ja" : "nein"),
        "",
        "Nach Agent:",
      ];
      const by = usage.by_agent || {};
      const keys = Object.keys(by);
      if (!keys.length) {
        lines.push("(noch keine LLM-Aufrufe)");
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
          li.textContent = "(noch keine Jobs)";
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
              btn.textContent = "Abbrechen";
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
      if (body) body.textContent = "Kosten laden fehlgeschlagen: " + err.message;
    }
  }

  async function cancelJobById(id) {
    if (!id) return;
    try {
      await api("POST", "/api/jobs/" + encodeURIComponent(id) + "/cancel");
      toast("Abbruch angefordert", "ok");
      await refreshUsageModal();
    } catch (err) {
      toast("Abbruch fehlgeschlagen: " + err.message, "error");
    }
  }

  async function resetUsageCounters() {
    if (!confirm("Sitzungszähler auf null setzen?")) return;
    try {
      await api("POST", "/api/usage/reset");
      toast("Zähler geleert", "ok");
      await refreshUsageModal();
      // refresh cost badge via state
      try {
        const st = await api("GET", "/api/state");
        applySnapshot(st);
      } catch (_e) {
        /* ignore */
      }
    } catch (err) {
      toast("Zähler leeren fehlgeschlagen: " + err.message, "error");
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
    const embSel = document.getElementById("vector-embedder");
    try {
      const data = await api("GET", "/api/vector?limit=40");
      const emb =
        (data.embedder && (data.embedder.active || data.embedder.embedder)) ||
        "bow";
      if (countEl) {
        countEl.textContent =
          "Docs: " + (data.count || 0) + " · embedder: " + emb;
      }
      if (embSel && emb) {
        try {
          embSel.value = emb;
        } catch (e) {}
        const nav =
          data.embedder && data.embedder.neural_available
            ? data.embedder.neural_available
            : null;
        if (nav && embSel.options) {
          Array.prototype.forEach.call(embSel.options, function (opt) {
            if (opt.value === "fastembed") {
              opt.disabled = !(nav.fastembed);
              opt.textContent = nav.fastembed
                ? "fastembed (neural)"
                : "fastembed (not installed)";
            }
            if (opt.value === "sbert") {
              opt.disabled = !(nav.sentence_transformers);
              opt.textContent = nav.sentence_transformers
                ? "sbert (neural)"
                : "sbert (not installed)";
            }
          });
        }
      }
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

  async function applyVectorEmbedder() {
    const embSel = document.getElementById("vector-embedder");
    const backend = embSel ? String(embSel.value || "bow") : "bow";
    try {
      const data = await api("POST", "/api/vector/embedder", {
        backend: backend,
        reindex: true,
      });
      toast(
        "Embedder: " +
          ((data.embedder && data.embedder.active) || backend) +
          " · reindexed " +
          (data.reindexed != null ? data.reindexed : "?"),
        "ok"
      );
      await refreshVectorList();
    } catch (err) {
      toast("Embedder switch failed: " + err.message, "error");
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
      toast("Checkpoint gespeichert", "ok");
      const ck = document.getElementById("system-ckpt");
      if (ck) ck.textContent = "Checkpoint: " + (data.path || "gespeichert");
    } catch (err) {
      toast("Checkpoint speichern fehlgeschlagen: " + err.message, "error");
    }
  }

  async function loadCheckpoint() {
    try {
      const snap = await api("POST", "/api/checkpoint/load");
      applySnapshot(snap);
      toast("Checkpoint geladen", "ok");
      closeSystemModal();
    } catch (err) {
      toast("Checkpoint laden fehlgeschlagen: " + err.message, "error");
    }
  }

  async function runCleanState() {
    if (
      !confirm(
        "Zustand leeren: HOT, Temp-Workspace, Pipeline und Checkpoint. WARM bleibt. Weiter?"
      )
    ) {
      return;
    }
    try {
      const snap = await api("POST", "/api/clean");
      applySnapshot(snap);
      toast(
        "Zustand geleert (Temp: " +
          ((snap.clean && snap.clean.temp_removed) || 0) +
          ")",
        "ok"
      );
    } catch (err) {
      toast("Leeren fehlgeschlagen: " + err.message, "error");
    }
  }

  async function runBackup() {
    try {
      const data = await api("POST", "/api/backup");
      if (!data || data.ok === false) {
        toast("Backup fehlgeschlagen", "error");
        return;
      }
      toast("Backup gespeichert", "ok");
      appendChat("system", "Backup gespeichert: " + (data.path || ""));
    } catch (err) {
      toast("Backup fehlgeschlagen: " + err.message, "error");
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

