/* part: 07-system-skills.js — edit parts, run scripts/build_ui_js.py */
  async function onFlexSelectChange() {
    if (!els.flexSelect) return;
    els.flexSelect.value = "personal";
    toast("Flex is fixed — personal companion only", "info");
  }



  function closeSkillsModal() {
    if (els.skillsModal) els.skillsModal.hidden = true;
  }

  async function openSkillsModal() {
    if (!els.skillsModal) return;
    els.skillsModal.hidden = false;
    await refreshSkillsModal();
  }

  async function refreshSkillsModal() {
    const ul = document.getElementById("skills-list");
    const countEl = document.getElementById("skills-count");
    const catEl = document.getElementById("skills-catalog");
    try {
      const data = await api("GET", "/api/skills");
      const skills = data.skills || [];
      if (countEl) {
        const en = skills.filter(function (s) { return s.enabled !== false; }).length;
        countEl.textContent = "Skills: " + en + "/" + skills.length + " enabled";
      }
      if (ul) {
        ul.innerHTML = "";
        if (!skills.length) {
          const li = document.createElement("li");
          li.className = "muted";
          li.textContent = "(no skills loaded)";
          ul.appendChild(li);
        } else {
          skills.forEach(function (s) {
            const li = document.createElement("li");
            li.style.display = "flex";
            li.style.gap = "6px";
            li.style.alignItems = "center";
            const lab = document.createElement("span");
            lab.style.flex = "1";
            lab.textContent =
              (s.enabled === false ? "○ " : "● ") +
              (s.id || "?") +
              " · " +
              (s.name || "") +
              " [" +
              (s.source || "?") +
              "]";
            lab.title = (s.description || "") + " · triggers: " + ((s.triggers || []).join(", ") || "—");
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "btn-ws-sm";
            btn.textContent = s.enabled === false ? "Enable" : "Disable";
            btn.addEventListener("click", function () {
              toggleSkill(s.id, s.enabled === false);
            });
            li.appendChild(lab);
            li.appendChild(btn);
            ul.appendChild(li);
          });
        }
      }
      if (catEl) {
        const cat = data.catalog;
        if (cat && cat.entries) {
          catEl.textContent = cat.entries
            .map(function (e) {
              return (e.trust || "?") + " · " + e.id + " v" + (e.version || "") + " — " + (e.path || "");
            })
            .join("\n");
        } else {
          catEl.textContent = "No catalog";
        }
      }
    } catch (err) {
      toast("Skills load failed: " + err.message, "error");
    }
  }

  async function toggleSkill(id, enable) {
    try {
      await api("POST", "/api/skills/" + encodeURIComponent(id) + "/enable", {
        enabled: !!enable,
      });
      toast((enable ? "Enabled " : "Disabled ") + id, "ok");
      await refreshSkillsModal();
    } catch (err) {
      toast("Skill toggle failed: " + err.message, "error");
    }
  }

  async function reloadSkills() {
    try {
      const data = await api("POST", "/api/skills/reload");
      toast("Skills reloaded: " + ((data.skills || []).length), "ok");
      await refreshSkillsModal();
    } catch (err) {
      toast("Skills reload failed: " + err.message, "error");
    }
  }

  async function installSkillPath() {
    const input = document.getElementById("skills-install-path");
    const path = input ? String(input.value || "").trim() : "";
    if (!path) {
      toast("Enter a local skill folder path", "info");
      return;
    }
    try {
      const data = await api("POST", "/api/skills/install", { path: path });
      toast("Installed skill: " + (data.id || path), "ok");
      if (input) input.value = "";
      await refreshSkillsModal();
    } catch (err) {
      toast("Install failed: " + err.message, "error");
    }
  }


  async function learnSkillFromLast() {
    try {
      const data = await api("POST", "/api/skills/learn_from_last");
      toast("Skill gespeichert: " + (data.id || "learned"), "ok");
      await refreshSkillsModal();
    } catch (err) {
      toast("Learn failed: " + err.message, "error");
    }
  }


  async function installNeuralEmbedder() {
    toast("Installing neural embeddings…", "info");
    try {
      const data = await api("POST", "/api/vector/embedder/install");
      if (data && data.ok === false) {
        toast("Install failed: " + (data.error || "unknown"), "error");
        return;
      }
      toast("Neural package OK — pick fastembed + Apply", "ok");
      await refreshVectorList();
    } catch (err) {
      toast("Install failed: " + err.message, "error");
    }
  }


  function closeDocsModal() {
    if (els.docsModal) els.docsModal.hidden = true;
  }

  async function openDocsModal() {
    if (!els.docsModal) return;
    els.docsModal.hidden = false;
    const q = document.getElementById("docs-query");
    if (q) {
      q.focus();
      if (q.value) await runDocsSearch();
    }
  }

  async function runDocsSearch() {
    const qEl = document.getElementById("docs-query");
    const ul = document.getElementById("docs-hits");
    const hint = document.getElementById("docs-hint");
    const q = qEl ? String(qEl.value || "").trim() : "";
    if (!ul) return;
    if (!q) {
      ul.innerHTML = "";
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = "Type a query — e.g. skills, plan_mode, install";
      ul.appendChild(li);
      return;
    }
    try {
      const data = await api(
        "GET",
        "/api/docs/search?q=" + encodeURIComponent(q) + "&limit=16"
      );
      const hits = data.hits || [];
      ul.innerHTML = "";
      if (!hits.length) {
        const li = document.createElement("li");
        li.className = "muted";
        li.textContent = "No hits for: " + q;
        ul.appendChild(li);
        return;
      }
      hits.forEach(function (h) {
        const li = document.createElement("li");
        li.style.display = "flex";
        li.style.flexDirection = "column";
        li.style.gap = "2px";
        li.style.padding = "6px 0";
        const top = document.createElement("span");
        top.innerHTML = "";
        const title = document.createElement("strong");
        title.textContent =
          (h.score != null ? h.score + " · " : "") + (h.title || h.file || "?");
        top.appendChild(title);
        const meta = document.createElement("span");
        meta.className = "muted";
        meta.style.fontSize = "0.9em";
        meta.textContent =
          (h.path || h.file || "") +
          " · " +
          (h.topic || "") +
          " · " +
          ((h.keywords || []).slice(0, 6).join(", ") || "—");
        li.appendChild(top);
        li.appendChild(meta);
        ul.appendChild(li);
      });
      if (hint) {
        hint.textContent =
          hits.length +
          " hits · local catalog · rebuild: python scripts/build_docs_index.py";
      }
    } catch (err) {
      toast("Docs search failed: " + err.message, "error");
    }
  }
