/**
 * EXAMPLE ONLY — FlatCompat + override layers (not used by npm run lint:js).
 *
 * Override layers (later wins):
 *   L1  rules inside compat.config({ rules })
 *   L2  scopeToUi / withRuleOverrides helper
 *   L3  native flat { name: "overrides/…", rules }  ← project policy
 *
 * Run:
 *   npm run lint:js:compat
 *   npx eslint -c eslint.flatcompat.example.js src/gnom_hub/ui/static/app.js
 *
 * Production: eslint.config.js (native flat, no FlatCompat).
 * Docs: docs/ESLINT_FLATCOMPAT.md §13
 */
"use strict";

const js = require("@eslint/js");
const globals = require("globals");
const { FlatCompat } = require("@eslint/eslintrc");

const UI_FILES = ["src/gnom_hub/ui/static/**/*.js"];

const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: js.configs.recommended,
  allConfig: js.configs.all,
});

/** Re-scope compat blocks so they don’t lint the whole repo (L2 scope). */
function scopeToUi(configs) {
  return configs.map((block) => {
    if (block.ignores && !block.files && !block.rules && !block.languageOptions) {
      return block;
    }
    return {
      ...block,
      files: block.files || UI_FILES,
      name: block.name ? `compat/${block.name}` : "compat/scoped",
    };
  });
}

/**
 * L2 helper: expand compat configs, then append a dedicated override block.
 * @param {import("eslint").Linter.Config[]} configs
 * @param {import("eslint").Linter.RulesRecord} rules
 * @param {string} name
 */
function withRuleOverrides(configs, rules, name = "overrides/patched") {
  return [
    ...scopeToUi(configs),
    {
      name,
      files: UI_FILES,
      rules,
    },
  ];
}

/** @type {import("eslint").Linter.Config[]} */
module.exports = [
  {
    name: "example/ignores",
    ignores: [
      "**/node_modules/**",
      "**/.venv/**",
      "**/data/**",
      "**/dist/**",
      "src/gnom_hub/ui/static/parts/**",
      "**/vendor/**",
    ],
  },

  // ══════════════════════════════════════════════════════════════════
  // L1 — legacy extends + inline rules (eslintrc paste zone)
  // ══════════════════════════════════════════════════════════════════
  ...scopeToUi(
    compat.config({
      env: { browser: true, es2021: true },
      extends: ["eslint:recommended", "plugin:promise/recommended"],
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: "script",
      },
      // L1 overrides (can still be beaten by L3)
      rules: {
        "no-console": "off",
        "promise/always-return": "off",
        "promise/catch-or-return": "warn",
      },
    }),
  ),

  // ══════════════════════════════════════════════════════════════════
  // L2 example — same effect as appending one override block
  // (shown as explicit block below; withRuleOverrides is equivalent)
  // ══════════════════════════════════════════════════════════════════
  // ...withRuleOverrides(compat.extends("plugin:promise/recommended"), {
  //   "promise/no-nesting": "warn",
  // }),

  // ══════════════════════════════════════════════════════════════════
  // L3 — native override layers (project law — always last)
  // ══════════════════════════════════════════════════════════════════
  {
    name: "overrides/language",
    files: UI_FILES,
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
    },
  },
  {
    name: "overrides/core-severity",
    files: UI_FILES,
    rules: {
      // demote recommended noise for large legacy IIFE
      "no-unused-vars": [
        "warn",
        {
          args: "none",
          caughtErrors: "none",
          ignoreRestSiblings: true,
          varsIgnorePattern: "^_",
        },
      ],
      "no-empty": ["warn", { allowEmptyCatch: true }],
      "no-var": "warn",
      "prefer-const": "off", // not from compat; explicit off for demo
    },
  },
  {
    name: "overrides/promise-policy",
    files: UI_FILES,
    rules: {
      // Re-assert / refine plugin rules after compat expand
      "promise/always-return": "off",
      "promise/catch-or-return": "warn",
      "promise/no-nesting": "warn",
      "promise/no-callback-in-promise": "warn",
      "promise/param-names": "error",
      "promise/no-return-wrap": "warn",
    },
  },
  {
    name: "overrides/hub-style",
    files: UI_FILES,
    rules: {
      "no-alert": "off",
      "no-console": "off",
      "eqeqeq": ["warn", "smart"],
      "radix": ["warn", "as-needed"],
    },
  },
];
