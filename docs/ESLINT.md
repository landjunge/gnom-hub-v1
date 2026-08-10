# ESLint Flat Config (UI JavaScript)

Gnom-Hub uses **ESLint 9 flat config** (`eslint.config.js`) for the desktop UI.

Python stays on **Ruff**. DoD deliverables use **DoD-Lint**. This doc is **JS only**.

## Why flat config?

| Legacy (`.eslintrc.*`) | Flat (`eslint.config.js`) |
|------------------------|---------------------------|
| Cascading JSON/YAML | One JS module, explicit **array** |
| `extends` magic | Import configs / plugins as objects |
| `env` / `globals` split | `languageOptions.globals` |
| ESLint ≤8 default | ESLint ≥9 **default** |

```js
module.exports = [
  { ignores: [ ... ] },
  { files: ["..."], languageOptions: { ... }, rules: { ... } },
  // plugin recommended blocks…
];
```

## Plugins (how flat config uses them)

### 1. Register a plugin

```js
const noUnsanitized = require("eslint-plugin-no-unsanitized");

{
  plugins: {
    "no-unsanitized": noUnsanitized,  // name → plugin module
  },
  rules: {
    "no-unsanitized/property": "warn",  // pluginName/ruleName
  },
}
```

In flat config there is **no** `"plugins": ["no-unsanitized"]` string list like eslintrc — you always pass the **module object**.

### 2. Prefer the plugin’s flat `configs.*`

Many plugins ship ready-made flat blocks:

```js
const js = require("@eslint/js");
const promise = require("eslint-plugin-promise");
const noUnsanitized = require("eslint-plugin-no-unsanitized");

module.exports = [
  { files: UI_FILES, ...js.configs.recommended, languageOptions: { ... } },
  { files: UI_FILES, ...noUnsanitized.configs.recommended, rules: { /* overrides */ } },
  { files: UI_FILES, ...promise.configs["flat/recommended"], rules: { /* overrides */ } },
];
```

| Plugin | Config key | Role |
|--------|------------|------|
| `@eslint/js` | `js.configs.recommended` | Core correctness |
| `eslint-plugin-no-unsanitized` | `configs.recommended` | DOM XSS (`innerHTML`, …) |
| `eslint-plugin-promise` | `configs["flat/recommended"]` | Promise hygiene |

Always re-scope with `files:` after spreading a recommended config (recommended blocks are often global).

### 3. Override plugin rules after spread

```js
{
  files: UI_FILES,
  ...noUnsanitized.configs.recommended,
  rules: {
    ...noUnsanitized.configs.recommended.rules,
    "no-unsanitized/property": "warn",  // demote until sanitized helpers exist
    "no-unsanitized/method": "warn",
  },
}
```

Order in the array: **later entries win** for the same file+rule.

### 4. Adding another plugin (recipe)

1. `npm i -D eslint-plugin-foo`  
2. `const foo = require("eslint-plugin-foo")`  
3. If `foo.configs.flat/recommended` (or similar) exists → spread it with `files`  
4. Else:

```js
{
  files: UI_FILES,
  plugins: { foo },
  rules: {
    "foo/some-rule": "warn",
  },
}
```

5. Document here + run `npm run lint:js`.

### Plugins we intentionally skip (for now)

| Plugin | Why not |
|--------|---------|
| `eslint-plugin-react` / `jsx-a11y` | UI is vanilla DOM, not React |
| `typescript-eslint` | No TS in static UI yet |
| `eslint-plugin-import` | Classic script, no ESM imports |
| `unicorn` | Too noisy on 6k-line legacy IIFE |

## What we lint

| Path | Linted? | Why |
|------|---------|-----|
| `src/gnom_hub/ui/static/app.js` | **yes** | Full IIFE bundle |
| `src/gnom_hub/ui/static/parts/*.js` | **no** | Fragments → false `no-undef` |
| Python / plugins | no | Ruff |

Edit **parts** → `python scripts/build_ui_js.py` → `npm run lint:js`.

## Commands

```bash
npm install
npm run lint:js          # app.js (warnings ok)
npm run lint:js:fix     # zero warnings (strict)
```

## Our plugin rule policy

### `@eslint/js` recommended

Errors for real bugs (`no-undef`, `no-unreachable`, …). Baseline.

### `no-unsanitized/*` → **warn**

Flags unsafe `innerHTML` / `outerHTML` / `document.write`.  
Legacy UI still builds HTML strings → **warn** until a shared `safeHtml` / `textContent` helper lands; then promote to **error**.

### `promise/*`

| Rule | Level | Note |
|------|-------|------|
| `promise/param-names` | error (from recommended) | `resolve`/`reject` naming |
| `promise/catch-or-return` | warn | fire-and-forget common |
| `promise/always-return` | **off** | toast/fetch paths |
| `promise/no-nesting` | warn | |
| `promise/no-callback-in-promise` | warn | |

### Project overrides

`eqeqeq`, `no-var`, `prefer-const`, `no-unused-vars`, …  
Style rules off (`quotes`/`semi`/`indent`).

## Anatomy checklist

| Field | Role |
|-------|------|
| `name` | Label in debug / `--print-config` |
| `files` / `ignores` | Scope |
| `languageOptions` | ecmaVersion, sourceType, globals |
| `plugins` | `{ name: pluginModule }` |
| `rules` | `"off"` \| `"warn"` \| `"error"` \| `[level, opts]` |
| spread `configs.*` | Plugin-provided flat blocks |

Debug which config applies:

```bash
npx eslint --print-config src/gnom_hub/ui/static/app.js | head
```

## Related

- Config: `eslint.config.js`  
- Build UI: `scripts/build_ui_js.py`  
- Python lint: Ruff · DoD: `docs/DOD_LINT.md`  
