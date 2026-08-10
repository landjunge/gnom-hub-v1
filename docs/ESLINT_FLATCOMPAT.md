# FlatCompat — Deep Dive

**FlatCompat** (`@eslint/eslintrc`) translates **legacy eslintrc** constructs into **flat config objects** so you can migrate piecemeal.

Gnom-Hub’s **production** config is **native flat** (`eslint.config.js`) — no FlatCompat at runtime.  
Use this when you must bridge old `extends` / share configs that only ship eslintrc format.

Related: [ESLINT.md](ESLINT.md) · [ESLINT_FLAT_MIGRATION.md](ESLINT_FLAT_MIGRATION.md)  
Example file: [`eslint.flatcompat.example.js`](../eslint.flatcompat.example.js)

---

## 1. What FlatCompat is (and is not)

| | |
|--|--|
| **Is** | Adapter: eslintrc API → array of flat config objects |
| **Is** | Escape hatch for `airbnb`, old `plugin:foo/recommended`, shared JSON configs |
| **Is not** | The long-term home for new rules (prefer native flat) |
| **Is not** | A second ESLint engine — still ESLint 9 flat pipeline |

```
eslintrc strings / objects
        │
        ▼
   FlatCompat.extends() / .config() / .env() / .plugins()
        │
        ▼
   Flat config objects[]  ──►  ESLint 9
```

---

## 2. Install

```bash
npm i -D @eslint/eslintrc eslint globals
# often also: @eslint/js  (for native recommended next to compat)
```

Pin majors with your ESLint 9 line (we use `@eslint/eslintrc@3.x`).

---

## 3. Constructor options

```js
const { FlatCompat } = require("@eslint/eslintrc");
const path = require("node:path");

const compat = new FlatCompat({
  baseDirectory: __dirname,           // REQUIRED for resolve of extends/plugins
  // optional:
  recommendedConfig: require("@eslint/js").configs.recommended,
  allConfig: require("@eslint/js").configs.all,
  resolvePluginsRelativeTo: __dirname, // if plugins live elsewhere
});
```

| Option | Role |
|--------|------|
| `baseDirectory` | Root for resolving `extends`, plugin names, relative paths — **almost always `__dirname`** |
| `recommendedConfig` | Object used when legacy asks for `eslint:recommended` |
| `allConfig` | Object used when legacy asks for `eslint:all` |
| `resolvePluginsRelativeTo` | Alternate node_modules root for plugins |

Without `baseDirectory`, resolution of `plugin:…` / `eslint-config-…` often fails mysteriously.

---

## 4. API surface

### 4.1 `compat.extends(...names)` → `FlatConfig[]`

Legacy `extends` array:

```js
// eslintrc: "extends": ["eslint:recommended", "plugin:promise/recommended"]
module.exports = [
  ...compat.extends(
    "eslint:recommended",
    "plugin:promise/recommended",
  ),
];
```

Each name becomes one or more flat objects (plugins + rules already wired).

### 4.2 `compat.config(eslintrcObject)` → `FlatConfig[]`

Whole eslintrc-style object (handy for copy-paste migration):

```js
module.exports = [
  ...compat.config({
    env: { browser: true, es2021: true },
    extends: ["eslint:recommended"],
    plugins: ["promise"],
    rules: {
      "no-console": "off",
      "promise/catch-or-return": "warn",
    },
    ignorePatterns: ["dist/**"],
  }),
];
```

### 4.3 `compat.env({ browser: true })` → `FlatConfig[]`

Only environment globals:

```js
...compat.env({ browser: true, es2021: true })
// ≈ languageOptions.globals from the old env map
```

### 4.4 `compat.plugins("foo", "bar")` → `FlatConfig[]`

Registers plugins by **legacy string name** (loads `eslint-plugin-foo`):

```js
...compat.plugins("promise", "no-unsanitized")
```

Native flat prefers:

```js
plugins: { promise: require("eslint-plugin-promise") }
```

---

## 5. Composition patterns

### Pattern A — Full legacy island (fast migrate)

```js
const { FlatCompat } = require("@eslint/eslintrc");
const js = require("@eslint/js");
const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: js.configs.recommended,
});

module.exports = [
  { ignores: ["**/node_modules/**"] },
  ...compat.config({
    env: { browser: true },
    extends: ["eslint:recommended", "plugin:promise/recommended"],
    rules: { "no-console": "off" },
  }),
];
```

### Pattern B — Hybrid (recommended for stepwise exit)

```js
module.exports = [
  { ignores: ["**/node_modules/**", "**/parts/**"] },

  // Native: core
  {
    files: ["src/**/*.js"],
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: { ...require("globals").browser },
    },
  },

  // Compat: only what lacks flat configs
  ...compat.extends("airbnb-base").map((cfg) => ({
    ...cfg,
    files: ["src/**/*.js"], // re-scope!
  })),

  // Native overrides last (win on conflicts)
  {
    files: ["src/**/*.js"],
    rules: {
      "no-console": "off",
      "import/prefer-default-export": "off",
    },
  },
];
```

### Pattern C — Compat only for one package path

```js
module.exports = [
  ...nativeUiConfig,
  ...compat.extends("plugin:legacy-foo/recommended").map((c) => ({
    ...c,
    files: ["packages/legacy/**/*.js"],
  })),
];
```

**Always re-apply `files`** after `extends()` — some compat output is global and would lint Python-adjacent paths if you ever run `eslint .`.

---

## 6. Scoping & merge order

```
[0] ignores
[1] ...compat.extends("…")     // often broad
[2] native recommended
[3] project rules              // LAST → wins
```

Same as pure flat: **later array entries override** earlier for the same file+rule.

```js
// Force scope on every compat chunk
function scope(configs, files) {
  return configs.map((c) => (c.ignores ? c : { ...c, files }));
}

module.exports = [
  { ignores: ["**/node_modules/**"] },
  ...scope(compat.extends("plugin:promise/recommended"), UI_FILES),
];
```

---

## 7. `eslint:recommended` via compat

Two equivalent paths:

```js
// Native (prefer)
{ ...js.configs.recommended }

// Via compat (needs recommendedConfig in constructor)
...compat.extends("eslint:recommended")
```

If you see empty/missing recommended rules through compat, you forgot:

```js
new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: require("@eslint/js").configs.recommended,
})
```

---

## 8. Debugging FlatCompat

```bash
# Which rules ended up active?
npx eslint --print-config path/to/file.js | less

# Use the example bridge config explicitly
npx eslint -c eslint.flatcompat.example.js src/gnom_hub/ui/static/app.js
```

```js
// Temporary: log what extends expands to
const blocks = compat.extends("plugin:promise/recommended");
console.log(JSON.stringify(blocks, (k, v) => {
  if (k === "plugins" && v && typeof v === "object") {
    return Object.keys(v); // don’t dump rule implementations
  }
  return v;
}, 2));
```

| Failure | Likely cause |
|---------|----------------|
| Cannot find module `eslint-config-X` | missing dep or wrong `baseDirectory` |
| Plugin not found | not installed / `resolvePluginsRelativeTo` |
| `eslint:recommended` no-op | missing `recommendedConfig` |
| Rules apply to whole monorepo | forgot `files` after spread |
| Double plugins / weird severity | native + compat both define same rule — put overrides last |

---

## 9. Exit strategy (remove FlatCompat)

1. Replace each `compat.extends("plugin:foo/…")` with native:
   - `...require("eslint-plugin-foo").configs["flat/recommended"]`  
   - or manual `plugins` + `rules`  
2. Replace `compat.env` with `globals` package.  
3. Replace `compat.config({…})` with explicit flat blocks.  
4. Drop `@eslint/eslintrc` from `package.json`.  
5. Keep only `eslint.config.js` (Gnom-Hub end state).

Track in PRs: *“compat surface: N extends left”* → goal **0**.

---

## 10. When to use FlatCompat in Gnom-Hub

| Situation | Use FlatCompat? |
|-----------|-----------------|
| Current UI lint (`app.js`) | **No** — native flat already |
| Vendoring a legacy eslint-config only on eslintrc | **Yes**, scoped `files` |
| Spike / compare old rule set | **Yes**, `eslint.flatcompat.example.js` |
| New plugins with flat configs | **No** — use `configs.flat/*` |

---

## 11. Security / CI notes

- FlatCompat resolves and **loads** plugin code at config-eval time — same trust model as eslintrc.  
- Prefer `npm ci` lockfile.  
- Don’t enable FlatCompat in CI as the primary path unless the bridge is intentional and scoped.  
- Example config is **opt-in** via `-c`; default `npm run lint:js` stays native.

---



---

## 13. Override rules with FlatCompat

FlatCompat only **expands** legacy configs. **Your policy** still lives in later flat blocks.

### 13.1 Three places you can set rules

| Layer | Where | Wins when? |
|-------|--------|------------|
| **L1** Inside `compat.config({ rules })` | merged into expanded blocks | Early — can be overwritten |
| **L2** Map/patch after `extends()` | mutate each expanded object | Middle |
| **L3** Native flat block **last** | `{ files, rules: {…} }` | **Always preferred** |

```
compat.extends / compat.config     ← L1 (legacy defaults + inline rules)
        │
        ▼
scope + optional patchRules()      ← L2
        │
        ▼
{ name: "overrides", rules: … }    ← L3  ★ put project policy here
```

### 13.2 L3 — Native overrides (recommended)

```js
module.exports = [
  ...scopeToUi(compat.extends("plugin:promise/recommended")),
  {
    name: "overrides/promise-policy",
    files: UI_FILES,
    rules: {
      // demote
      "promise/catch-or-return": "warn",
      // disable for hub fire-and-forget
      "promise/always-return": "off",
      // tighten
      "promise/param-names": "error",
    },
  },
];
```

Same rule name as compat → **later entry wins**. You do **not** need to re-register the plugin if an earlier block already did.

### 13.3 L1 — Rules inside `compat.config`

```js
compat.config({
  extends: ["eslint:recommended", "plugin:promise/recommended"],
  rules: {
    "no-console": "off",           // legacy-style override
    "promise/always-return": "off",
  },
});
```

Good for 1:1 eslintrc paste. Still add L3 for anything you consider **project law**, so future `extends` changes don’t silently re-enable a rule.

### 13.4 L2 — Patch helper after expand

```js
function withRuleOverrides(configs, rules, files = UI_FILES) {
  return [
    ...configs.map((c) => ({
      ...c,
      files: c.files || files,
    })),
    {
      name: "overrides/patched",
      files,
      rules,
    },
  ];
}

module.exports = [
  { ignores: ["**/node_modules/**"] },
  ...withRuleOverrides(
    compat.extends("eslint:recommended", "plugin:promise/recommended"),
    {
      "no-unused-vars": "warn",
      "promise/always-return": "off",
      "no-console": "off",
    },
  ),
];
```

### 13.5 File-scoped overrides (like eslintrc `overrides[]`)

Legacy:

```json
{
  "rules": { "no-console": "error" },
  "overrides": [
    { "files": ["scripts/**"], "rules": { "no-console": "off" } }
  ]
}
```

Flat + compat:

```js
[
  ...scope(compat.extends("eslint:recommended"), ["**/*.js"]),
  {
    name: "overrides/default",
    files: ["**/*.js"],
    rules: { "no-console": "error" },
  },
  {
    name: "overrides/scripts",
    files: ["scripts/**/*.js"],
    rules: { "no-console": "off" },
  },
]
```

More specific paths don’t auto-win by specificity — **array order** does. Put special cases **after** general overrides.

### 13.6 Severity recipe (hub policy)

| Goal | Example |
|------|---------|
| Turn off legacy noise | `"rule": "off"` |
| Keep signal, don’t fail CI | `"rule": "warn"` |
| Must never ship | `"rule": "error"` |
| Options without changing severity | `["warn", { allowEmptyCatch: true }]` |

Gnom-Hub UI baseline (production native config):

- XSS plugin rules → **warn** (until sanitizer helper)
- `promise/always-return` → **off**
- `promise/catch-or-return` → **warn**
- core `no-undef` etc. → **error** (from recommended)

### 13.7 Override conflict debug

```bash
npx eslint --print-config src/gnom_hub/ui/static/app.js | grep -A2 '"promise/always-return"'
```

If severity is wrong: a **later** block re-set it, or compat expand order put recommended after your L1 rules (fix with L3).

### 13.8 What not to do

| Anti-pattern | Why |
|--------------|-----|
| Only L1, no L3 | Next `extends` bump resurrects rules |
| Overrides **before** compat spread | Compat overwrites you |
| Re-`plugins: {}` empty in override | Can wipe plugin refs in some merges — only set `rules` in L3 |
| Assume path specificity | Flat config is **not** eslintrc cascade-by-path depth |

### 13.9 Gnom-Hub example file

`eslint.flatcompat.example.js` demonstrates:

1. L1 rules inside `compat.config`  
2. `scopeToUi` (files scoping)  
3. L3 `example/overrides/*` blocks for promise + style policy  

```bash
npm run lint:js:compat
```


## 12. Quick reference

```js
const { FlatCompat } = require("@eslint/eslintrc");
const js = require("@eslint/js");
const path = require("node:path");

const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: js.configs.recommended,
  allConfig: js.configs.all,
});

// extends / config / env / plugins → FlatConfig[]
compat.extends("eslint:recommended", "plugin:promise/recommended");
compat.config({ env: { browser: true }, rules: { semi: "off" } });
compat.env({ node: true });
compat.plugins("promise");
```

Official ESLint migration guide still mentions FlatCompat as the bridge:  
[Configuration Migration Guide](https://eslint.org/docs/latest/use/configure/migration-guide#using-eslintrc-configs-in-flat-config)
