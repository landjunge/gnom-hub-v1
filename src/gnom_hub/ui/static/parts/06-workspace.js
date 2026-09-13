/* part: 06-workspace.js — edit parts, run scripts/build_ui_js.py */
  async function openWorkspaceModal() {
    if (!els.workspaceModal) return;
    dockIntoBoxes(els.workspaceModal);
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
      toast("Workspace laden fehlgeschlagen: " + err.message, "error");
    }
  }

  async function downloadWorkspaceZip(zone) {
    try {
      const data = await api(
        "POST",
        "/api/workspace/export?zone=" + encodeURIComponent(zone || "all")
      );
      if (!data || data.ok === false || !data.name) {
        toast("Zip fehlgeschlagen", "error");
        return;
      }
      window.location.href =
        "/api/workspace/exports/" + encodeURIComponent(data.name);
      toast(
        "Zip bereit" +
          (data.bytes != null ? " · " + Math.round(data.bytes / 1024) + " KB" : ""),
        "ok"
      );
    } catch (err) {
      toast("Zip fehlgeschlagen: " + err.message, "error");
    }
  }

  function wsEmpty(text) {
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = text;
    return li;
  }

  function renderWorkspaceLists(snap) {
    const tempUl = document.getElementById("ws-temp-list");
    const permUl = document.getElementById("ws-perm-list");
    const selUl = document.getElementById("ws-selected-list");
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
      tempUl.appendChild(wsEmpty("(leer — Arbeit starten füllt Temp)"));
    }
    if (!(snap.perm || []).length) {
      permUl.appendChild(wsEmpty("(leer — aus Temp übernehmen)"));
    }
    if (selUl) {
      selUl.innerHTML = "";
      (snap.selected || []).forEach(function (f) {
        selUl.appendChild(wsListItem(f, "selected"));
      });
      if (!(snap.selected || []).length) {
        selUl.appendChild(wsEmpty("(leer — Behalten in Box 3)"));
      }
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
      promo.textContent = "↑ dauerhaft";
      promo.title = "Nach Dauerhaft übernehmen";
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
    del.title = "Löschen";
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

  function wsZoneLabel(zone) {
    if (zone === "perm") return "Dauerhaft";
    if (zone === "selected") return "Behalten";
    return "Temp";
  }

  function paintWsPreview() {
    const pre = document.getElementById("ws-preview");
    const frame = document.getElementById("ws-preview-frame");
    const btnS = document.getElementById("ws-preview-sicht");
    const btnC = document.getElementById("ws-preview-code");
    if (btnS) btnS.classList.toggle("is-on", wsPreviewMode !== "source");
    if (btnC) btnC.classList.toggle("is-on", wsPreviewMode === "source");
    const showPage = wsPreviewIsHtml && wsPreviewMode !== "source";
    if (frame) {
      frame.hidden = !showPage;
      if (showPage && typeof wrapHtmlDocument === "function") {
        frame.srcdoc = wrapHtmlDocument(wsPreviewCode);
      }
    }
    if (pre) {
      pre.hidden = showPage;
      if (!showPage) pre.textContent = wsPreviewCode || "(leer)";
    }
  }

  async function previewWs(zone, name) {
    const title = document.getElementById("ws-preview-title");
    const pre = document.getElementById("ws-preview");
    if (title) title.textContent = wsZoneLabel(zone) + " / " + name;
    try {
      const data = await api(
        "GET",
        "/api/workspace/file?zone=" +
          encodeURIComponent(zone) +
          "&name=" +
          encodeURIComponent(name)
      );
      const raw = data.content || "";
      const html =
        typeof extractHtml === "function" ? extractHtml(raw) : "";
      wsPreviewIsHtml = !!html;
      wsPreviewCode = raw;
      wsPreviewMode = "preview";
      paintWsPreview();
    } catch (err) {
      wsPreviewIsHtml = false;
      wsPreviewCode = "Vorschau fehlgeschlagen: " + err.message;
      wsPreviewMode = "source";
      paintWsPreview();
      if (pre) pre.hidden = false;
    }
  }

  async function promoteWs(name) {
    try {
      const data = await api(
        "POST",
        "/api/workspace/promote/" + encodeURIComponent(name)
      );
      if (!data || data.ok === false) {
        toast((data && data.status) || "Übernehmen fehlgeschlagen", "error");
        return;
      }
      renderWorkspaceLists(data.workspace || (await api("GET", "/api/workspace")));
      toast("Nach Dauerhaft übernommen", "ok");
    } catch (err) {
      toast("Übernehmen fehlgeschlagen: " + err.message, "error");
    }
  }

  async function deleteWs(zone, name) {
    if (!window.confirm("Datei löschen: " + name + "?")) return;
    try {
      const data = await api(
        "POST",
        "/api/workspace/delete?zone=" +
          encodeURIComponent(zone) +
          "&name=" +
          encodeURIComponent(name)
      );
      if (!data || data.ok === false) {
        toast("Löschen fehlgeschlagen", "error");
        return;
      }
      renderWorkspaceLists(data.workspace || (await api("GET", "/api/workspace")));
      toast("Gelöscht: " + name, "ok");
    } catch (err) {
      toast("Löschen fehlgeschlagen: " + err.message, "error");
    }
  }

  async function clearTempWs() {
    if (!confirm("Alle Temp-Dateien im Workspace leeren?")) return;
    try {
      const data = await api("POST", "/api/workspace/clear-temp");
      if (!data || data.ok === false) {
        toast("Temp leeren fehlgeschlagen", "error");
        return;
      }
      renderWorkspaceLists(data.workspace || { temp: [], perm: [], selected: [] });
      toast("Temp geleert (" + (data.removed || 0) + ")", "ok");
    } catch (err) {
      toast("Temp leeren fehlgeschlagen: " + err.message, "error");
    }
  }

