# ESLint Flat Config — Migration Guide

Practical guide: **`.eslintrc.*` → `eslint.config.js`** (ESLint 9+).

Gnom-Hub is already on flat config — see [ESLINT.md](ESLINT.md) and root `eslint.config.js`.  
This doc is the **how-to migrate** (generic + our choices).

---

## 0. Why migrate?

| | Legacy eslintrc | Flat config |
|--|-----------------|-------------|
| Default in ESLint | ≤ 8 | **≥ 9** |
| Config format | JSON/YAML/JS + cascading | **One array of objects** |
| `extends` | string magic (`"eslint:recommended"`) | **import + spread** real objects |
| Plugins | `"plugins": ["foo"]` | `plugins: { foo: require("…") }` |
| Ignores | `.eslintignore` + `ignorePatterns` | `ignores` in config |
| Overrides | nested `overrides[]` | separate array entries with `files` |

ESLint 9 still can load eslintrc via `ESLINT_USE_FLAT_CONFIG=false`, but that path is deprecated. New work = flat.

---

## 1. Checklist (order of operations)

1. **Upgrade** to ESLint 9 + Node ≥ 18 (we pin 20+).  
2. **Inventory** current config: `.eslintrc*`, `.eslintignore`, `package.json#eslintConfig`.  
3. **List** `extends`, `plugins`, `env`, `globals`, `rules`, `overrides`.  
4. Create **`eslint.config.js`** (or `.mjs` / `eslint.config.mjs` for pure ESM).  
5. Map each piece (tables below).  
6. Delete eslintrc + `.eslintignore` when parity is OK.  
7. Update CI scripts (`eslint .` still works).  
8. Run on real files; demote noisy rules to `warn` first.

---

## 2. Side-by-side mapping

### 2.1 Root structure

**Before (eslintrc):**

```json
{
  "root": true,
  "env": { "browser": true, "es2021": true },
  "extends": ["eslint:recommended", "plugin:promise/recommended"],
  "plugins": ["promise"],
  "parserOptions": { "ecmaVersion": 2022, "sourceType": "script" },
  "rules": { "no-console": "off" },
  "ignorePatterns": ["node_modules/", "dist/"]
}
```

**After (flat):**

```js
"use strict";
const js = require("@eslint/js");
const globals = require("globals");
const promise = require("eslint-plugin-promise");

module.exports = [
  { ignores: ["**/node_modules/**", "**/dist/**"] },
  {
    files: ["**/*.js"],
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: { ...globals.browser, ...globals.es2021 },
    },
  },
  {
    files: ["**/*.js"],
    ...promise.configs["flat/recommended"],
  },
  {
    files: ["**/*.js"],
    rules: { "no-console": "off" },
  },
];
```

### 2.2 Field map

| eslintrc | Flat config |
|----------|-------------|
| `root: true` | *(implicit — one config file)* |
| `env.browser` | `languageOptions.globals = { ...globals.browser }` |
| `env.node` | `...globals.node` |
| `env.es2021` | `...globals.es2021` **or** `ecmaVersion` |
| `parserOptions.ecmaVersion` | `languageOptions.ecmaVersion` |
| `parserOptions.sourceType` | `languageOptions.sourceType` |
| `parserOptions.parser` | `languageOptions.parser` |
| `globals` | `languageOptions.globals` (`"readonly"` / `"writable"`) |
| `extends: ["eslint:recommended"]` | `...require("@eslint/js").configs.recommended` |
| `plugins: ["foo"]` | `plugins: { foo: require("eslint-plugin-foo") }` |
| `rules` | `rules` (same names) |
| `overrides: [{ files, … }]` | **new array item** with `files` |
| `ignorePatterns` / `.eslintignore` | `{ ignores: ["**/…"] }` |
| `settings` | `settings` (same) |
| `processor` | `processor` on the block |
| `noInlineConfig` | `linterOptions.noInlineConfig` |
| `reportUnusedDisableDirectives` | `linterOptions.reportUnusedDisableDirectives` |

### 2.3 `extends` → imports

| Old extend string | Flat equivalent |
|-------------------|-----------------|
| `eslint:recommended` | `...require("@eslint/js").configs.recommended` |
| `eslint:all` | `...require("@eslint/js").configs.all` (rarely) |
| `plugin:promise/recommended` | `...require("eslint-plugin-promise").configs["flat/recommended"]` |
| `plugin:foo/recommended` | Check plugin docs for `configs.flat` / `configs["flat/recommended"]` / `configs.recommended` |
| `prettier` (eslint-config-prettier) | `...require("eslint-config-prettier")` if it exports flat array/object |

If a plugin only has **eslintrc** recommended:

```js
const foo = require("eslint-plugin-foo");
// Manual:
{
  plugins: { foo },
  rules: {
    "foo/some-rule": "error",
    // copy from plugin README eslintrc block
  },
}
```

Optional bridge (temporary): `@eslint/eslintrc` `FlatCompat` — use only as a stepping stone, then remove.

→ Deep dive: [ESLINT_FLATCOMPAT.md](ESLINT_FLATCOMPAT.md) · example: `eslint.flatcompat.example.js`

```js
const { FlatCompat } = require("@eslint/eslintrc");
const compat = new FlatCompat({ baseDirectory: __dirname });
module.exports = [...compat.extends("airbnb-base")];
```

---

## 3. Ignores migration

**Before:** `.eslintignore`

```
node_modules
dist
src/**/parts
```

**After:** first config object (or any block with only `ignores`):

```js
{
  name: "ignores",
  ignores: [
    "**/node_modules/**",
    "**/dist/**",
    "src/**/parts/**",
  ],
}
```

Notes:

- Prefer `**/` prefixes for clarity.  
- A config object that has **only** `ignores` applies globally.  
- `files` + `ignores` on the same block = ignore within that block’s match.  
- `.eslintignore` is **not** read in pure flat mode.

---

## 4. Overrides → multiple blocks

**Before:**

```json
{
  "rules": { "no-console": "error" },
  "overrides": [
    {
      "files": ["scripts/**/*.js"],
      "env": { "node": true },
      "rules": { "no-console": "off" }
    }
  ]
}
```

**After:**

```js
[
  {
    files: ["**/*.js"],
    languageOptions: { globals: { ...globals.browser } },
    rules: { "no-console": "error" },
  },
  {
    files: ["scripts/**/*.js"],
    languageOptions: { globals: { ...globals.node } },
    rules: { "no-console": "off" },
  },
]
```

**Cascade rule:** for a given file, all matching blocks merge; **later wins** on conflicts.

---

## 5. Plugins (flat pattern)

```js
const noUnsanitized = require("eslint-plugin-no-unsanitized");

// A) Use shipped flat config
{
  files: ["src/**/*.js"],
  ...noUnsanitized.configs.recommended,
  rules: {
    ...noUnsanitized.configs.recommended.rules,
    "no-unsanitized/property": "warn", // local policy
  },
}

// B) Manual register
{
  files: ["src/**/*.js"],
  plugins: { "no-unsanitized": noUnsanitized },
  rules: {
    "no-unsanitized/method": "warn",
  },
}
```

Gnom-Hub uses A for `no-unsanitized` + `promise`, plus `@eslint/js`.

---

## 6. ESM vs CJS config file

| File | Style |
|------|--------|
| `eslint.config.js` + `"type": "commonjs"` / no `"type":"module"` | `require` / `module.exports` ← **we use this** |
| `eslint.config.mjs` | `import` / `export default` |
| `eslint.config.js` in `"type":"module"` package | ESM only |

ESM example:

```js
import js from "@eslint/js";
import globals from "globals";
export default [
  { ignores: ["**/node_modules/**"] },
  { files: ["**/*.js"], ...js.configs.recommended,
    languageOptions: { globals: globals.browser } },
];
```

---

## 7. package.json scripts

```json
{
  "scripts": {
    "lint:js": "eslint \"src/gnom_hub/ui/static/app.js\"",
    "lint:js:fix": "eslint \"src/gnom_hub/ui/static/app.js\" --max-warnings 0"
  }
}
```

CLI flags unchanged (`--fix`, `--max-warnings`, `-f unix`).  
Config discovery: ESLint walks up looking for `eslint.config.*`.

Force flat (default 9): do **not** set `ESLINT_USE_FLAT_CONFIG=false`.

---

## 8. Gnom-Hub migration snapshot (done)

| Legacy (if we had it) | Actual flat setup |
|-----------------------|-------------------|
| `env: browser` | `globals.browser` + `es2021` |
| `eslint:recommended` | `@eslint/js` → `js.configs.recommended` |
| promise plugin | `promise.configs["flat/recommended"]` |
| DOM XSS | `no-unsanitized.configs.recommended` (warn) |
| ignore parts/ | `ignores: ["src/gnom_hub/ui/static/parts/**"]` |
| lint surface | **built** `app.js` only |

No `.eslintrc` remains in the repo by design.

---

## 9. Common pitfalls

| Symptom | Cause | Fix |
|---------|--------|-----|
| `no-undef` on every browser API | missing `globals.browser` | add `languageOptions.globals` |
| Plugin rules “Definition for rule … not found” | plugin not in `plugins` and not via configs spread | register plugin module |
| `extends` does nothing | flat has no `extends` key | import + spread |
| Ignores ignored | still using `.eslintignore` only | move to `ignores` |
| Config not loaded | wrong filename / ESM-CJS mismatch | `eslint.config.js` + matching module type |
| Double recommended noise | spread recommended **and** re-list all rules as error | override only deltas |
| Fragment files explode | linting IIFE **parts** alone | lint bundle; ignore parts |
| `FlatCompat` forever | temporary bridge left in | replace with native flat |

---

## 10. Verify migration

```bash
# 1) Config resolves
npx eslint --print-config src/gnom_hub/ui/static/app.js | head -n 40

# 2) Same files as before
npm run lint:js

# 3) Optional: compare to old eslintrc branch
#    git stash; run old; git stash pop; run new; diff counts
```

Acceptance:

- [ ] No `.eslintrc*` / `.eslintignore`  
- [ ] ESLint 9 without `ESLINT_USE_FLAT_CONFIG=false`  
- [ ] Plugins load (no “rule not found”)  
- [ ] CI script green or known warn baseline documented  
- [ ] Team knows: edit parts → rebuild → lint `app.js`  

---

## 11. Minimal template (copy-paste)

```js
"use strict";
const js = require("@eslint/js");
const globals = require("globals");

module.exports = [
  { ignores: ["**/node_modules/**", "**/dist/**"] },
  {
    files: ["**/*.{js,mjs,cjs}"],
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module", // or "script"
      globals: { ...globals.browser },
    },
    rules: {
      // project deltas only
    },
  },
];
```

---

## 12. Related

- Live config: [`eslint.config.js`](../eslint.config.js)  
- Policy & plugins: [ESLINT.md](ESLINT.md)  
- Official: [ESLint — Configuration Migration Guide](https://eslint.org/docs/latest/use/configure/migration-guide)  
- DoD / Python: `DOD_LINT.md`, Ruff in CI  
