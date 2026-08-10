# ESLint Flat Config (UI JavaScript)

Gnom-Hub uses **ESLint 9 flat config** (`eslint.config.js`) for the desktop UI.

Python stays on **Ruff**. DoD deliverables use **DoD-Lint**. This doc is **JS only**.

## Why flat config?

| Legacy (`.eslintrc.*`) | Flat (`eslint.config.js`) |
|------------------------|---------------------------|
| Cascading JSON/YAML | One JS/TS module, explicit array |
| `extends` magic | Import configs as objects |
| `env` / `globals` split | `languageOptions.globals` |
| ESLint ≤8 default | ESLint ≥9 **default** |

Export shape:

```js
module.exports = [
  { ignores: [ ... ] },
  { files: ["..."], languageOptions: { ... }, rules: { ... } },
];
```

Each array entry is a **config object**. Later entries override earlier ones for matching files.

## What we lint

| Path | Linted? | Why |
|------|---------|-----|
| `src/gnom_hub/ui/static/app.js` | **yes** | Full IIFE bundle |
| `src/gnom_hub/ui/static/parts/*.js` | **no** | Fragments of one IIFE → false `no-undef` |
| Python / plugins | no | Ruff |

Edit **parts**, rebuild with `python scripts/build_ui_js.py`, then lint **app.js**.

## Commands

```bash
# once
npm install

npm run lint:js          # app.js (warnings ok)
npm run lint:js:fix     # zero warnings (strict CI optional)
```

No Docker. Node 20+ only for this dev tool.

## Rule groups (our policy)

### Error — real bugs

`no-undef`, `no-unreachable`, `use-isnan`, `valid-typeof`, `no-debugger`,
dupe keys/cases, unsafe finally/negation, class/const assign, …

### Warn — fix gradually

| Rule | Intent |
|------|--------|
| `eqeqeq` (smart) | `===` except null-ish smart cases |
| `no-var` / `prefer-const` | block scope |
| `no-unused-vars` | dead code (`_` prefix ignored) |
| `no-use-before-define` | vars/classes (functions allowed) |
| `array-callback-return` | map/filter callbacks return |
| `no-return-assign` | `return x = y` footgun |
| `no-throw-literal` | throw Error objects |
| `no-unused-expressions` | allow `&&` / ternary |

### Off — style / hub reality

- `no-console`, `no-alert` — UI debug + confirm dialogs  
- `strict` — IIFE already has `"use strict"`  
- `quotes` / `semi` / `indent` / `max-len` — no Prettier war  
- `prefer-arrow-callback` / `prefer-template` — large legacy style OK  

## Anatomy of `eslint.config.js`

```js
const globals = require("globals");

module.exports = [
  { name: "gnom-hub/ignores", ignores: ["**/node_modules/**", "parts/**"] },
  {
    name: "gnom-hub/ui-static",
    files: ["src/gnom_hub/ui/static/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",       // not "module"
      globals: { ...globals.browser, ...globals.es2021 },
    },
    rules: { "no-undef": "error", /* ... */ },
  },
];
```

### Useful flat-config fields

| Field | Role |
|-------|------|
| `name` | Label in debug output |
| `files` / `ignores` | Glob scope (minimatch) |
| `languageOptions.ecmaVersion` | Syntax year |
| `languageOptions.sourceType` | `script` \| `module` |
| `languageOptions.globals` | `readonly` / `writable` map (`globals` package) |
| `linterOptions.reportUnusedDisableDirectives` | catch dead `eslint-disable` |
| `rules` | `"off"` \| `"warn"` \| `"error"` or `["level", options]` |
| `plugins` | not used yet (vanilla UI) |

## Adding a rule

1. Edit `rules` in `eslint.config.js`.  
2. Run `npm run lint:js` on `app.js`.  
3. Prefer **warn** first for noisy rules on the 6k-line bundle.  
4. Document non-obvious choices here.

## CI (optional)

Lint job can add (Node cache, no Python):

```yaml
- uses: actions/setup-node@v4
  with: { node-version: "22", cache: npm }
- run: npm ci
- run: npm run lint:js
```

Not required for app runtime deploy (Python/Vercel path). Enable when `lint:js` is clean enough for the team.

## Related

- Build UI: `scripts/build_ui_js.py`  
- Python lint: Ruff in `.github/workflows/ci.yml`  
- DoD lint: `docs/DOD_LINT.md`  
