---
id: html_landing
name: Single-file HTML landing
version: 0.1.0
enabled: true
description: DoD for one complete HTML page (no section-split)
tags: [html, frontend, landing]
agents: [coordinator, worker1, worker2, worker3, worker4, brainstorm]
triggers: [full_page_html, html_page, landing, landingpage, seite, website]
---

# Single-file HTML page

Deliver **ONE** complete, self-contained HTML document.

## Binding DoD
- Starts with `<!DOCTYPE html>` and ends with `</html>`
- All CSS/JS inline or embedded — no broken external deps for MVP
- Clear hierarchy: hero, sections, footer (or app shell if todo/dashboard)
- Mobile-friendly layout (readable ~390px)
- Prefer dark theme if user/wishes say so
- Never truncate mid-tag; never invent “part 2 follows”

## Anti-patterns
- Splitting one page across multiple workers into incomplete partials
- Placeholder lorem without structure
- Claiming tools ran when they did not
