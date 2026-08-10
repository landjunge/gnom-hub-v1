"""web_design plugin — palette, WCAG contrast, HTML scaffold, CSS tokens.

No network, no third-party deps. For HTML/landing workers.
"""

from __future__ import annotations

import colorsys
import re
from typing import Any

from gnom_hub.plugins.sdk import fail, ok

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")

_PRESETS: dict[str, str] = {
    "dark": "#5b8def",
    "light": "#2563eb",
    "brand": "#7c3aed",
    "ocean": "#0ea5e9",
    "forest": "#16a34a",
    "sunset": "#f97316",
    "rose": "#e11d48",
    "slate": "#64748b",
}


def _parse_hex(value: str, default: str = "#5b8def") -> tuple[int, int, int]:
    raw = (value or "").strip()
    key = raw.lower().lstrip("#")
    if key in _PRESETS:
        raw = _PRESETS[key]
    m = _HEX_RE.match(raw if raw.startswith("#") else f"#{raw}")
    if not m:
        m = _HEX_RE.match(default)
    assert m is not None
    h = m.group(1)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"


def _rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    return colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)


def _hsl_to_rgb(h: float, l: float, s: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return round(r * 255), round(g * 255), round(b * 255)


def _rel_luminance(r: int, g: int, b: int) -> float:
    def chan(c: int) -> float:
        x = c / 255.0
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4

    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def _contrast(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    l1 = _rel_luminance(*fg)
    l2 = _rel_luminance(*bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def color_palette(seed: str = "dark", count: int = 5) -> dict[str, Any]:
    n = max(1, min(int(count or 5), 8))
    r, g, b = _parse_hex(seed)
    h, l, s = _rgb_to_hsl(r, g, b)
    shades: list[str] = []
    # Generate around seed lightness
    for i in range(n):
        # 0.18 .. 0.82
        li = 0.18 + (0.64 * i / max(n - 1, 1))
        shades.append(_to_hex(*_hsl_to_rgb(h, li, max(0.25, min(0.75, s)))))
    primary = _to_hex(r, g, b)
    accent = _to_hex(*_hsl_to_rgb((h + 0.12) % 1.0, min(0.55, l + 0.05), min(0.7, s + 0.1)))
    surface = _to_hex(*_hsl_to_rgb(h, 0.08 if l > 0.45 else 0.94, 0.15))
    surface2 = _to_hex(*_hsl_to_rgb(h, 0.12 if l > 0.45 else 0.90, 0.12))
    text = "#e6edf3" if l > 0.45 or _rel_luminance(r, g, b) < 0.35 else "#0f172a"
    muted = "#94a3b8" if text.startswith("#e") else "#64748b"
    border = _to_hex(*_hsl_to_rgb(h, 0.22 if text.startswith("#e") else 0.85, 0.12))
    css = (
        f":root {{\n"
        f"  --color-primary: {primary};\n"
        f"  --color-accent: {accent};\n"
        f"  --color-surface: {surface};\n"
        f"  --color-surface-2: {surface2};\n"
        f"  --color-text: {text};\n"
        f"  --color-muted: {muted};\n"
        f"  --color-border: {border};\n"
        f"}}\n"
    )
    return ok(
        seed=seed or "dark",
        primary=primary,
        accent=accent,
        surface=surface,
        surface_2=surface2,
        text=text,
        muted=muted,
        border=border,
        shades=shades,
        css=css,
    )


def contrast_check(fg: str = "", bg: str = "") -> dict[str, Any]:
    if not str(fg).strip() or not str(bg).strip():
        return fail("fg and bg required (hex)")
    try:
        f = _parse_hex(fg)
        b = _parse_hex(bg)
    except Exception:  # noqa: BLE001
        return fail("invalid hex color")
    ratio = round(_contrast(f, b), 2)
    return ok(
        fg=_to_hex(*f),
        bg=_to_hex(*b),
        ratio=ratio,
        aa_normal=ratio >= 4.5,
        aa_large=ratio >= 3.0,
        aaa_normal=ratio >= 7.0,
        aaa_large=ratio >= 4.5,
        grade=(
            "AAA"
            if ratio >= 7.0
            else "AA"
            if ratio >= 4.5
            else "AA-large"
            if ratio >= 3.0
            else "fail"
        ),
    )


def html_scaffold(
    kind: str = "landing",
    title: str = "Page",
    seed: str = "dark",
) -> dict[str, Any]:
    k = (kind or "landing").strip().lower()
    if k not in ("landing", "dashboard", "form", "article"):
        k = "landing"
    pal = color_palette(seed=seed or "dark", count=5)
    if not pal.get("ok"):
        return pal
    title_s = (title or "Page").strip()[:80] or "Page"
    body = {
        "landing": """
  <header class="wrap">
    <nav><strong>Brand</strong> · <a href="#features">Features</a> · <a href="#cta">Start</a></nav>
  </header>
  <main class="wrap">
    <section class="hero">
      <h1>Headline that states the value</h1>
      <p class="lead">One sentence benefit. No filler.</p>
      <a class="btn" href="#cta" id="cta">Get started</a>
    </section>
    <section id="features" class="grid">
      <article><h2>Feature A</h2><p>Concrete outcome.</p></article>
      <article><h2>Feature B</h2><p>Concrete outcome.</p></article>
      <article><h2>Feature C</h2><p>Concrete outcome.</p></article>
    </section>
  </main>
  <footer class="wrap muted">© Brand</footer>
""",
        "dashboard": """
  <div class="layout">
    <aside class="side"><strong>App</strong><nav>Overview · Items · Settings</nav></aside>
    <main class="wrap">
      <h1>Dashboard</h1>
      <div class="grid">
        <div class="card"><h2>Metric</h2><p class="big">—</p></div>
        <div class="card"><h2>Metric</h2><p class="big">—</p></div>
        <div class="card"><h2>Metric</h2><p class="big">—</p></div>
      </div>
      <section class="card"><h2>Recent</h2><p class="muted">Empty state</p></section>
    </main>
  </div>
""",
        "form": """
  <main class="wrap narrow">
    <h1>Form</h1>
    <form class="card" action="#" method="post">
      <label>Name <input name="name" required /></label>
      <label>Email <input type="email" name="email" required /></label>
      <label>Message <textarea name="msg" rows="4"></textarea></label>
      <button class="btn" type="submit">Submit</button>
    </form>
  </main>
""",
        "article": """
  <main class="wrap narrow">
    <article>
      <header><p class="muted">Category · Date</p><h1>Article title</h1></header>
      <p class="lead">Lead paragraph.</p>
      <p>Body…</p>
    </article>
  </main>
""",
    }[k]
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title_s}</title>
  <style>
{pal["css"]}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; font-family: system-ui, sans-serif;
      background: var(--color-surface); color: var(--color-text);
      line-height: 1.5;
    }}
    a {{ color: var(--color-accent); }}
    .wrap {{ max-width: 960px; margin: 0 auto; padding: 1.25rem; }}
    .narrow {{ max-width: 40rem; }}
    .muted {{ color: var(--color-muted); }}
    .btn {{
      display: inline-block; background: var(--color-primary); color: #fff;
      padding: 0.65rem 1.1rem; border-radius: 8px; text-decoration: none; border: 0;
      font-weight: 600; cursor: pointer;
    }}
    .grid {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }}
    .card, .hero, article {{
      background: var(--color-surface-2); border: 1px solid var(--color-border);
      border-radius: 12px; padding: 1.25rem;
    }}
    .hero h1 {{ font-size: clamp(1.6rem, 4vw, 2.4rem); margin: 0 0 0.5rem; }}
    .lead {{ font-size: 1.1rem; color: var(--color-muted); }}
    .layout {{ display: grid; grid-template-columns: 200px 1fr; min-height: 100vh; }}
    .side {{ background: var(--color-surface-2); border-right: 1px solid var(--color-border); padding: 1rem; }}
    .big {{ font-size: 1.8rem; font-weight: 700; margin: 0; }}
    label {{ display: block; margin-bottom: 0.85rem; }}
    input, textarea {{
      width: 100%; margin-top: 0.25rem; padding: 0.5rem 0.65rem;
      border-radius: 8px; border: 1px solid var(--color-border);
      background: var(--color-surface); color: var(--color-text);
    }}
    @media (max-width: 720px) {{ .layout {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""
    return ok(kind=k, title=title_s, palette=pal, html=html)


def css_tokens(seed: str = "dark") -> dict[str, Any]:
    pal = color_palette(seed=seed or "dark", count=5)
    if not pal.get("ok"):
        return pal
    css = f"""{pal["css"]}
:root {{
  /* spacing */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.5rem;
  --space-6: 2rem;
  --space-8: 3rem;
  /* radius */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-full: 999px;
  /* type */
  --font-sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: ui-monospace, "Cascadia Code", Consolas, monospace;
  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-md: 1rem;
  --text-lg: 1.125rem;
  --text-xl: 1.35rem;
  --text-2xl: 1.75rem;
  /* elevation */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.2);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.25);
}}
"""
    return ok(seed=seed or "dark", css=css, palette=pal)


__all__ = ["color_palette", "contrast_check", "css_tokens", "html_scaffold"]
