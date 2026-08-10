# Flat Config — Plugin Integration

How Gnom-Hub wires ESLint plugins in **flat config** (ESLint 9).

Live code: [`eslint.config.js`](../eslint.config.js)  
Also: [ESLINT.md](ESLINT.md) · [ESLINT_FLAT_MIGRATION.md](ESLINT_FLAT_MIGRATION.md) · [ESLINT_FLATCOMPAT.md](ESLINT_FLATCOMPAT.md)

---

## 1. Mental model

```
plugin package
   │  rules + (optional) configs.recommended / configs["flat/…"]
   ▼
require("eslint-plugin-foo")
   │
   ▼
integratePlugin("label", plugin.configs.…, { files, rules })
   │  → adds files scope
   │  → merges rule overrides
   │  → keeps plugins: map from base
   ▼
module.exports = [ ignores, ...pluginBlocks, projectOverrides ]
```

| Concept | Flat config |
|---------|-------------|
| Plugin module | real object from `require` / `import` |
| Plugin name | key in `plugins: { "foo": module }` |
| Rule id | `"foo/rule-name"` |
| Recommended set | `plugin.configs.recommended` or `configs["flat/recommended"]` |
| Scope | every block should set `files` (or global `ignores`) |

There is **no** `"plugins": ["foo"]` string list like eslintrc.

---

## 2. Integration recipe (copy-paste)

### Step 1 — Install

```bash
npm i -D eslint-plugin-foo
```

### Step 2 — Load

```js
const foo = require("eslint-plugin-foo");
```

### Step 3 — Prefer shipped flat config

```js
// Inspect:
// console.log(Object.keys(foo.configs || {}));
```

| Common keys | Use |
|-------------|-----|
| `recommended` | often already flat (object with `plugins` + `rules`) |
| `flat/recommended` | promise-style |
| `flat.recommended` | some plugins |
| only eslintrc shape | use FlatCompat **or** manual `plugins`+`rules` |

### Step 4 — Integrate (Gnom-Hub helper)

```js
...integratePlugin("gnom-hub/foo", foo.configs.recommended, {
  files: UI_FILES,
  rules: {
    "foo/some-rule": "warn",  // local policy
  },
}),
```

`integratePlugin` (in `eslint.config.js`):

1. Accepts one config object **or** an array of them  
2. Sets `name` + `files`  
3. Merges `rules`: base first, **overrides win**  
4. Optionally merges `languageOptions` / `globals`

### Step 5 — Project block last

```js
{
  name: "gnom-hub/ui-overrides",
  files: UI_FILES,
  rules: { /* core deltas only — plugins already registered */ },
}
```

You usually **do not** re-list `plugins` here unless defining rules that need a plugin not loaded yet.

---

## 3. Manual integration (no recommended config)

```js
{
  name: "gnom-hub/foo-manual",
  files: UI_FILES,
  plugins: {
    foo, // short key ⇒ rules are foo/…
  },
  rules: {
    "foo/bar": "error",
    "foo/baz": ["warn", { option: true }],
  },
}
```

Plugin key must match the prefix in rule ids (`foo` → `foo/bar`).

Some packages expect a scoped name:

```js
plugins: { "no-unsanitized": noUnsanitized }
// rules: "no-unsanitized/property"
```

---

## 4. What each of our plugins contributes

| Package | Config used | Registers | Our overrides |
|---------|-------------|-----------|---------------|
| `@eslint/js` | `configs.recommended` | core rules | + browser `languageOptions` |
| `eslint-plugin-no-unsanitized` | `configs.recommended` | plugin + 2 rules | both → **warn** |
| `eslint-plugin-promise` | `configs["flat/recommended"]` | plugin + promise/* | `always-return` off; catch warn |

Order in `eslint.config.js`:

1. ignores  
2. js recommended (+ globals)  
3. no-unsanitized  
4. promise  
5. ui-overrides  

---

## 5. `integratePlugin` contract

```js
function integratePlugin(name, base, opts = {}) {
  const files = opts.files || UI_FILES;
  const blocks = Array.isArray(base) ? base : [base];
  return blocks.map((block, i) => ({
    ...block,
    name: blocks.length > 1 ? `${name}/${i}` : name,
    files: block.files || files,
    rules: { ...(block.rules || {}), ...(opts.rules || {}) },
    // languageOptions merged when opts.languageOptions set
  }));
}
```

| Input | Behavior |
|-------|----------|
| `base` object | one flat block |
| `base` array | one block per entry (some plugins export arrays) |
| `opts.rules` | override severities/options |
| `opts.files` | default `UI_FILES` |
| `opts.languageOptions` | shallow merge + `globals` merge |

---

## 6. Array order & rule precedence

```
earlier plugin recommended
        ↓
later plugin recommended   (other rules; same rule → overwrite)
        ↓
ui-overrides               ★ final say
```

Debug:

```bash
npx eslint --print-config src/gnom_hub/ui/static/app.js \
  | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{
    const j=JSON.parse(d); console.log(j.rules['promise/always-return']);
    console.log(Object.keys(j.plugins||{}));
  })"
```

---

## 7. Plugin types cheat sheet

| Kind | Example | Flat integration |
|------|---------|------------------|
| Official core | `@eslint/js` | `...integratePlugin(…, js.configs.recommended)` |
| Rules plugin | `promise`, `no-unsanitized` | flat recommended or manual |
| Config-only shareable | `eslint-config-prettier` | often `...require("…")` if array export |
| Parser | `@typescript-eslint/parser` | `languageOptions.parser` |
| Processor | `eslint-plugin-markdown` | `processor: "…"`, `files: ["**/*.md"]` |
| Legacy-only | old airbnb | [FlatCompat](ESLINT_FLATCOMPAT.md) temporarily |

---

## 8. Do / Don’t

| Do | Don’t |
|----|--------|
| Scope every plugin block with `files` | Rely on global apply for monorepos |
| Override severities in one place (helper or final block) | Scatter same rule in 5 blocks |
| Keep production free of FlatCompat | Use FlatCompat for plugins that already ship flat configs |
| Ignore IIFE `parts/**`, lint `app.js` | Lint fragments → fake `no-undef` |
| Pin plugin majors in package.json | Floating `*` in CI |

---

## 9. Adding a plugin to Gnom-Hub (checklist)

1. `npm i -D eslint-plugin-…`  
2. `require` in `eslint.config.js`  
3. `...integratePlugin("gnom-hub/…", …configs…, { rules })`  
4. Document overrides in [ESLINT.md](ESLINT.md)  
5. `npm run lint:js` — 0 errors baseline  
6. Optional: promote warns → errors when debt is paid  

---

## 10. Related commands

```bash
npm run lint:js           # production flat + plugins
npm run lint:js:compat    # FlatCompat example only
npx eslint --print-config src/gnom_hub/ui/static/app.js | head
```
