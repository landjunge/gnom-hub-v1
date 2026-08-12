# Google Search Console — Indexing checklist (Tollgate + Gnom-Hub)

Do this once per property. Goal: get **GitHub Pages** into Google’s index (repos alone are not enough for product discovery).

**Date template:** fill after each step.

---

## 1) Properties to add

| Property type | Value |
|---------------|--------|
| URL-prefix | `https://landjunge.github.io/tollgate/` |
| URL-prefix | `https://landjunge.github.io/gnom-hub-v1/` |
| Optional | `https://github.com/landjunge/tollgate` (GitHub often already indexed) |

**Verify:** preferred = HTML file upload **or** DNS (if you later add a custom domain).  
For `github.io` prefix properties, use the **HTML meta tag** or **Google Analytics** method if available; easiest is often:

1. Search Console → Add property → **URL prefix**
2. Verification: **HTML tag** → paste into `site/index.html` head once, deploy Pages, verify, then you may keep the tag.

Meta tag example (replace with the token GSC gives you):

```html
<meta name="google-site-verification" content="PASTE_TOKEN_HERE"/>
```

---

## 2) Submit sitemaps

| Property | Sitemap URL |
|----------|-------------|
| Tollgate Pages | `https://landjunge.github.io/tollgate/sitemap.xml` |
| Gnom-Hub Pages | `https://landjunge.github.io/gnom-hub-v1/sitemap.xml` |

Sitemaps → Add new sitemap → paste path relative to property root (`sitemap.xml`).

Also public:

- robots: `https://landjunge.github.io/tollgate/robots.txt`
- robots: `https://landjunge.github.io/gnom-hub-v1/robots.txt`

---

## 3) Request indexing (URL Inspection)

Inspect + **Request indexing** for each (priority order):

### Tollgate
1. `https://landjunge.github.io/tollgate/`
2. `https://landjunge.github.io/tollgate/de.html`
3. `https://landjunge.github.io/tollgate/blog/checklist.html`
4. `https://landjunge.github.io/tollgate/blog/launch.html`
5. `https://landjunge.github.io/tollgate/blog/launch-de.html`
6. `https://landjunge.github.io/tollgate/docs.html`
7. `https://landjunge.github.io/tollgate/ecosystem.html`
8. `https://landjunge.github.io/tollgate/press/`
9. `https://landjunge.github.io/tollgate/llms.txt`

### Gnom-Hub
1. `https://landjunge.github.io/gnom-hub-v1/`
2. `https://landjunge.github.io/gnom-hub-v1/de.html`
3. `https://landjunge.github.io/gnom-hub-v1/blog/launch.html`
4. `https://landjunge.github.io/gnom-hub-v1/docs.html`
5. `https://landjunge.github.io/gnom-hub-v1/ecosystem.html`
6. `https://landjunge.github.io/gnom-hub-v1/press/`
7. `https://landjunge.github.io/gnom-hub-v1/llms.txt`

Quota is limited (~10–20 URL requests/day). Spread over 2 days if needed.

---

## 4) Self-test queries (after 3–14 days)

Brand (should start working first):

```text
Tollgate landjunge
"landjunge/tollgate"
site:landjunge.github.io/tollgate
Gnom-Hub landjunge
site:landjunge.github.io/gnom-hub-v1
```

Problem keywords (harder; expect slow progress):

```text
AI agent safety checklist production
AI agent tool loop budget freeze
local multi-agent desk execute
```

Disambiguation (should not rank OpenTollGate for these):

```text
Tollgate AI agent safety
landjunge tollgate Protect Route Prove
```

---

## 5) External index fuel (do in parallel)

GSC alone is slow without mentions:

| Action | Status |
|--------|--------|
| Paste `docs/DEVTO_ARTICLE.md` to Dev.to (canonical = launch post) | ☐ |
| Show HN (one primary link) | ☐ |
| Awesome-list PRs merge | open — do not re-spam |
| Resilience challenge replies | Discussion #12 |
| GHCR package **Public** | one click in package settings |

---

## 6) Name collision (already in site SEO)

Titles/descriptions now stress:

- **landjunge/tollgate**
- **AI agent safety**
- **Not OpenTollGate / road tolls**

Keep that wording in any future social posts so Google associates the brand correctly.

---

## 7) Optional: Bing Webmaster

Same sitemaps → https://www.bing.com/webmasters  
Often indexes GitHub Pages faster than Google.

---

## Done when

- [ ] GSC property verified for both Pages roots  
- [ ] Both sitemaps show “Success” / URLs discovered  
- [ ] `site:landjunge.github.io/tollgate` returns the homepage  
- [ ] Brand query `Tollgate landjunge` shows **Pages** (not only random GitHub trees)
