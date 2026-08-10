/**
 * EXAMPLE ONLY — FlatCompat bridge (not used by npm run lint:js).
 *
 * Run:
 *   npx eslint -c eslint.flatcompat.example.js src/gnom_hub/ui/static/app.js
 *
 * Production config: eslint.config.js (native flat, no FlatCompat).
 * Docs: docs/ESLINT_FLATCOMPAT.md
 */
"use strict";

const js = require("@eslint/js");
const globals = require("globals");
const { FlatCompat } = require("@eslint/eslintrc");

const UI_FILES = ["src/gnom_hub/ui/static/**/*.js"];

const compat = new FlatCompat({
  baseDirectory: __dirname,
  // Required so "eslint:recommended" via compat resolves to @eslint/js
  recommendedConfig: js.configs.recommended,
  allConfig: js.configs.all,
});

/** Re-scope compat blocks so they don’t lint the whole repo */
function scopeToUi(configs) {
  return configs.map((block) => {
    if (block.ignores && !block.files && !block.rules && !block.languageOptions) {
      return block; // pure ignore blocks
    }
    return {
      ...block,
      files: block.files || UI_FILES,
      name: block.name ? `compat/${block.name}` : "compat/scoped",
    };
  });
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

  // ── Legacy-style extends via FlatCompat ──────────────────────────
  // Equivalent spirit of:
  //   extends: ["eslint:recommended", "plugin:promise/recommended"]
  //   env: { browser: true, es2021: true }
  ...scopeToUi(
    compat.config({
      env: { browser: true, es2021: true },
      extends: ["eslint:recommended", "plugin:promise/recommended"],
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: "script",
      },
      rules: {
        "no-console": "off",
        "promise/always-return": "off",
        "promise/catch-or-return": "warn",
      },
    }),
  ),

  // ── Native override layer (wins) ─────────────────────────────────
  {
    name: "example/native-overrides",
    files: UI_FILES,
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
    },
    rules: {
      "no-unused-vars": [
        "warn",
        {
          args: "none",
          caughtErrors: "none",
          varsIgnorePattern: "^_",
        },
      ],
      "no-var": "warn",
      "no-empty": ["warn", { "allowEmptyCatch": true }],
    },
  },
];
