# Gnom-Hub product website

Static marketing + SEO site for GitHub Pages.

**Live:** https://landjunge.github.io/gnom-hub-v1/

## SEO features

| Item | Where |
|------|--------|
| Title / description / keywords | `index.html`, `de.html`, `docs.html` |
| Open Graph + Twitter cards | head meta |
| Canonical + hreflang EN/DE | head links |
| JSON-LD `SoftwareApplication` + `FAQPage` + `WebSite` | index |
| `robots.txt` + `sitemap.xml` | site root |
| Image `alt` + screenshots | `assets/` |
| Semantic HTML | `main`, `section`, `article`, `nav` |

## Local preview

```bash
cd site && python3 -m http.server 8090
# http://127.0.0.1:8090
```

## Deploy

Push to `main` → workflow **Pages** (`.github/workflows/pages.yml`).  
First time: GitHub → Settings → Pages → Source: **GitHub Actions**.
