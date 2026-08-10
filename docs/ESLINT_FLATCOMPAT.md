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
