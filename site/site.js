/* Gnom-Hub product site */
(function () {
  const reveals = document.querySelectorAll(".reveal");
  if (reveals.length && "IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("visible");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.1 }
    );
    reveals.forEach((el) => io.observe(el));
  } else {
    reveals.forEach((el) => el.classList.add("visible"));
  }

  const y = document.getElementById("year");
  if (y) y.textContent = String(new Date().getFullYear());

  let toastEl = null;
  function toast(msg) {
    if (!toastEl) {
      toastEl = document.createElement("div");
      toastEl.className = "toast";
      toastEl.setAttribute("role", "status");
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastEl._t);
    toastEl._t = setTimeout(() => toastEl.classList.remove("show"), 1600);
  }

  async function copyText(text) {
    text = (text || "").trim();
    if (!text) return false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (_) {}
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.cssText = "position:fixed;left:-9999px";
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (_) {}
    document.body.removeChild(ta);
    return ok;
  }

  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const sel = btn.getAttribute("data-copy");
      const el = sel ? document.querySelector(sel) : null;
      const text = el ? el.innerText : btn.getAttribute("data-text") || "";
      const ok = await copyText(text);
      const prev = btn.textContent;
      btn.textContent = ok ? "Copied" : "Select + ⌘C";
      btn.classList.toggle("copied", ok);
      toast(ok ? "Copied" : "Select the text and copy");
      setTimeout(() => {
        btn.textContent = prev;
        btn.classList.remove("copied");
      }, 1400);
    });
  });

  document.querySelectorAll("[data-copy-href]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const ok = await copyText(btn.getAttribute("data-copy-href") || "");
      toast(ok ? "Link copied" : "Copy failed");
    });
  });

  const input = document.getElementById("doc-filter");
  if (input) {
    input.addEventListener("input", () => {
      const q = (input.value || "").toLowerCase();
      document.querySelectorAll("[data-doc]").forEach((c) => {
        const hay = (c.getAttribute("data-doc") || "").toLowerCase();
        c.style.display = !q || hay.includes(q) ? "" : "none";
      });
    });
  }
})();
