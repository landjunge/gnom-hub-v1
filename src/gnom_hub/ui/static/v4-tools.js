(() => {
  "use strict";

  const manifest = Array.isArray(window.GNOM_TOOL_MANIFEST)
    ? window.GNOM_TOOL_MANIFEST
    : [];

  const $ = (q) => document.querySelector(q);
  const els = {
    toggle: $("#tools-toggle"),
    module: $("#tool-module"),
    grid: $("#tool-grid"),
    viewer: $("#tool-viewer"),
    title: $("#tool-view-title"),
    meta: $("#tool-view-meta"),
    frame: $("#tool-frame"),
    external: $("#tool-open-external"),
    back: $("#tool-back"),
    desk: $(".desk-grid"),
    composer: $(".composer"),
  };

  let activeKey = "";

  function typingTarget(target) {
    if (!target) return false;
    const tag = String(target.tagName || "").toLowerCase();
    return (
      target.isContentEditable ||
      tag === "input" ||
      tag === "textarea" ||
      tag === "select"
    );
  }

  function setDeskVisible(visible) {
    if (els.desk) els.desk.hidden = !visible;
    if (els.composer) els.composer.hidden = !visible;
    if (els.module) els.module.hidden = visible;
    if (els.toggle) els.toggle.setAttribute("aria-pressed", visible ? "false" : "true");
  }

  function closeTool() {
    activeKey = "";
    if (els.frame) {
      els.frame.removeAttribute("src");
      els.frame.hidden = true;
    }
    if (els.viewer) els.viewer.hidden = true;
    if (els.grid) els.grid.hidden = false;
    setDeskVisible(true);
  }

  function showLauncher() {
    activeKey = "";
    if (els.viewer) els.viewer.hidden = true;
    if (els.grid) els.grid.hidden = false;
    setDeskVisible(false);
  }

  function openTool(tool) {
    if (!tool) return;
    if (activeKey === tool.key) {
      closeTool();
      return;
    }
    if (tool.home) {
      closeTool();
      return;
    }
    activeKey = tool.key;
    setDeskVisible(false);
    if (els.grid) els.grid.hidden = true;
    if (els.viewer) els.viewer.hidden = false;
    if (els.title) els.title.textContent = tool.name;
    if (els.meta) els.meta.textContent = tool.key + " · " + tool.role;
    if (els.external) {
      els.external.href = tool.url || "#";
      els.external.hidden = !tool.url;
    }
    if (els.frame && tool.url) {
      els.frame.title = tool.name;
      els.frame.src = tool.url;
      els.frame.hidden = false;
    }
  }

  function makeLogo(tool) {
    const wrap = document.createElement("span");
    wrap.className = "tool-logo";
    const img = document.createElement("img");
    img.alt = "";
    img.src = tool.logo;
    const fallback = document.createElement("span");
    fallback.className = "tool-logo-fallback";
    fallback.textContent = tool.fallback;
    fallback.hidden = true;
    img.addEventListener("error", () => {
      img.hidden = true;
      fallback.hidden = false;
    });
    wrap.append(img, fallback);
    return wrap;
  }

  function renderCards() {
    if (!els.grid) return;
    els.grid.textContent = "";
    manifest.forEach((tool) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "tool-card";
      button.dataset.toolKey = tool.key;
      button.dataset.toolId = tool.id;
      button.setAttribute("aria-label", tool.name + " öffnen, Taste " + tool.key);

      const key = document.createElement("kbd");
      key.textContent = tool.key;
      const logo = makeLogo(tool);
      const copy = document.createElement("span");
      copy.className = "tool-card-copy";
      const name = document.createElement("strong");
      name.textContent = tool.name;
      const role = document.createElement("small");
      role.textContent = tool.role;
      copy.append(name, role);
      button.append(key, logo, copy);
      button.addEventListener("click", () => openTool(tool));
      els.grid.appendChild(button);
    });
  }

  if (els.toggle) {
    els.toggle.addEventListener("click", () => {
      if (els.module && !els.module.hidden) closeTool();
      else showLauncher();
    });
  }
  if (els.back) els.back.addEventListener("click", showLauncher);

  document.addEventListener("keydown", (event) => {
    const isTyping = typingTarget(event.target);

    if (isTyping) {
      if (event.key === "Escape") {
        event.preventDefault();
        event.target.blur();
      }
      return;
    }

    if (event.metaKey || event.ctrlKey || event.altKey) return;

    if (event.code === "Space") {
      const input = document.querySelector("#chat-input");
      if (input) {
        event.preventDefault();
        if (els.module && !els.module.hidden) closeTool();
        input.focus();
      }
      return;
    }

    if (event.key === "Escape" && els.module && !els.module.hidden) {
      event.preventDefault();
      closeTool();
      return;
    }
    const tool = manifest.find((item) => item.key === event.key);
    if (!tool) return;
    event.preventDefault();
    openTool(tool);
  });

  renderCards();
  setDeskVisible(true);
})();
