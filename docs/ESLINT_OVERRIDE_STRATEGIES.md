# Flat Config — Override Strategies

How to **reshape** recommended/plugin rules without fighting ESLint’s merge model.

Live: [`eslint.config.js`](../eslint.config.js)  
Related: [ESLINT_PLUGIN_INTEGRATION.md](ESLINT_PLUGIN_INTEGRATION.md) · [ESLINT_FLATCOMPAT.md](ESLINT_FLATCOMPAT.md) §13

---

## 1. Golden rule

> **Later matching blocks win** for the same `files` + rule id.  
> Path “specificity” does **not** auto-win (unlike some eslintrc mental models).

```
ignores
recommended / plugins
plugin-local overrides   (inside integratePlugin)
strategy blocks          (named, ordered)
final “law” block        ★ if needed
```

---

## 2. Strategy catalog

### S1 — Severity ladder (debt → strict)

| Stage | Level | When |
|-------|-------|------|
| Discover | `"warn"` | New rule on large legacy code |
| Enforce in PR notes | `"warn"` + CI soft | Team sees noise |
| Gate | `"error"` or `--max-warnings 0` | Debt paid |
| Kill | `"off"` | Wrong for this codebase |

**Gnom-Hub:** `no-unsanitized/*` = **warn** until `safeHtml` exists → then **error**.

```js
// integratePlugin(…, { rules: { "no-unsanitized/property": "warn" } })
// later:
// { rules: { "no-unsanitized/property": "error" } }  // promote
```

### S2 — Options without changing severity

```js
"no-unused-vars": ["warn", {
  args: "none",
  varsIgnorePattern: "^_",
  caughtErrors: "none",
}],
"eqeqeq": ["warn", "smart"],
"no-empty": ["warn", { allowEmptyCatch: true }],
```

Use when the rule is right but defaults are wrong for IIFE/UI code.

### S3 — Disable by domain (hub reality)

Turn **off** rules that conflict with product UX:

| Rule | Why off |
|------|---------|
| `no-console` | debug + ops in desktop UI |
| `no-alert` | confirm dialogs |
| `promise/always-return` | fire-and-forget fetch/toast |
| `strict` | IIFE already `"use strict"` |
| style (`quotes`/`semi`/`indent`) | no Prettier war |

```js
{ name: "strategy/domain-off", files: UI_FILES, rules: {
  "no-console": "off",
  "promise/always-return": "off",
}}
```

### S4 — File-globe overrides (layered)

```js
{ files: ["src/**/*.js"], rules: { "no-console": "error" } },
{ files: ["scripts/**/*.js"], rules: { "no-console": "off" } },  // later → scripts win
```

Order matters more than glob “narrowness”. Put **exceptions after** general policy.

### S5 — Plugin-local vs global project overrides

| Where | Use for |
|-------|---------|
| `integratePlugin(…, { rules })` | Policy **tied to that plugin** (XSS, promise) |
| Final `strategy/*` blocks | Core rules + cross-cutting style |
| Inline `eslint-disable` | One-off lines (last resort) |

Prefer config overrides over file comments so policy is reviewable in one place.

### S6 — Warn-first rollout (new plugin)

```js
// 1) add plugin recommended as-is (may error)
// 2) immediately demote noisy rules to warn
...integratePlugin("gnom-hub/foo", foo.configs.recommended, {
  rules: Object.fromEntries(
    ["foo/a", "foo/b"].map((r) => [r, "warn"])
  ),
}),
// 3) fix code over time
// 4) remove demotions / set error
```

### S7 — Baseline freeze (`--max-warnings`)

| Script | Strategy |
|--------|----------|
| `lint:js` | allow warnings (current debt) |
| `lint:js:fix` | `--max-warnings 0` (optional hard gate) |

Don’t set CI to strict until warning count is near zero or ratcheted.

### S8 — Ignore vs override

| Goal | Tool |
|------|------|
| Never lint path | `ignores: ["parts/**"]` |
| Lint path but soft rules | `files` + warn/off |
| Generated file | `ignores` (not overrides) |

`parts/**` are IIFE fragments → **ignore**, don’t override `no-undef` away.

### S9 — Named strategy blocks (readable diffs)

Prefer several small named blocks over one mega-`rules` object:

```js
{ name: "strategy/severity-core", rules: { "no-var": "warn", … } },
{ name: "strategy/domain-off", rules: { "no-console": "off", … } },
{ name: "strategy/style-off", rules: { "quotes": "off", … } },
```

`name` shows up in debug tooling and PR review.

### S10 — Override only deltas

Don’t restate all of `eslint:recommended` as `"error"`.  
Only list **changes** from the plugin default.

---

## 3. Precedence cheat sheet

| Conflict | Winner |
|----------|--------|
| Same rule, two blocks | **Later** block |
| Plugin recommended + integratePlugin rules | integratePlugin `opts.rules` |
| integratePlugin + strategy block | strategy if later |
| Config rule vs `/* eslint-disable */` | disable comment (file-local) |
| CLI `--rule` | CLI (avoid in CI) |

---

## 4. Gnom-Hub applied map

| Strategy | Where |
|----------|-------|
| S1 warn XSS | `integratePlugin(no-unsanitized)` |
| S3 promise always-return off | `integratePlugin(promise)` |
| S2 unused-vars / eqeqeq options | `strategy/severity-core` |
| S3 console/alert off | `strategy/domain-off` |
| S3 style off | `strategy/style-off` |
| S8 ignore parts | top-level `ignores` |
| S7 soft CI | `npm run lint:js` (strict optional) |

---

## 5. Anti-patterns

| Don’t | Do instead |
|-------|------------|
| Override **before** plugin recommended | Plugin first, override after |
| `"off"` everything noisy forever | Track promote-to-error tickets |
| Duplicate same rule in 4 blocks | One strategy block per concern |
| Disable `no-undef` to silence parts | Ignore fragments / lint bundle |
| Mega PR: 20 new error rules | S1 warn-first |

---

## 6. Debug overrides

```bash
# Effective rule value
npx eslint --print-config src/gnom_hub/ui/static/app.js \
  | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{
    const r=JSON.parse(d).rules;
    for (const k of ['no-console','promise/always-return','no-unsanitized/property'])
      console.log(k, r[k]);
  })"

# Count by rule
npm run lint:js 2>&1 | sed -n 's/.*  \(.*\)$/\1/p' | sort | uniq -c | sort -rn
```

---

## 7. Decision tree

```
Need to change a rule?
├─ Wrong path entirely? → ignores (S8)
├─ Plugin-specific? → integratePlugin opts.rules (S5)
├─ Options only? → ["level", options] (S2)
├─ Too noisy now? → warn (S1) or off + ticket (S3)
└─ Cross-cutting core/style? → named strategy/* block (S9)
```

---

## 8. Related

- Plugin wiring: [ESLINT_PLUGIN_INTEGRATION.md](ESLINT_PLUGIN_INTEGRATION.md)  
- FlatCompat L1–L3: [ESLINT_FLATCOMPAT.md](ESLINT_FLATCOMPAT.md)  
- Migration: [ESLINT_FLAT_MIGRATION.md](ESLINT_FLAT_MIGRATION.md)  
