/**
 * ESLint Flat Config (ESLint ≥ 9) — Gnom-Hub desktop UI
 *
 * Plugins (flat-native):
 *   @eslint/js              → js.configs.recommended
 *   eslint-plugin-no-unsanitized → XSS on innerHTML / document.write
 *   eslint-plugin-promise   → promise/flat/recommended
 *
 * Lint target: built bundle `src/gnom_hub/ui/static/app.js`
 * (parts/*.js are IIFE fragments — lint the built file only.)
 *
 * Docs: docs/ESLINT.md
 */
"use strict";

const js = require("@eslint/js");
const globals = require("globals");
const noUnsanitized = require("eslint-plugin-no-unsanitized");
const promise = require("eslint-plugin-promise");

/** Shared file scope for UI static scripts */
const UI_FILES = ["src/gnom_hub/ui/static/**/*.js"];

/** @type {import("eslint").Linter.Config[]} */
module.exports = [
  // ── Global ignores (flat: top-level ignores entry) ─────────────────
  {
    name: "gnom-hub/ignores",
    ignores: [
      "**/node_modules/**",
      "**/.venv/**",
      "**/venv/**",
      "**/data/**",
      "**/dist/**",
      "**/build/**",
      // fragments share one IIFE — do not lint in isolation
      "src/gnom_hub/ui/static/parts/**",
      "**/vendor/**",
    ],
  },

  // ── @eslint/js recommended (core) ──────────────────────────────────
  // Spread recommended, then narrow to UI files + browser languageOptions.
  {
    name: "gnom-hub/js-recommended",
    files: UI_FILES,
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
    },
  },

  // ── eslint-plugin-no-unsanitized (DOM XSS) ─────────────────────────
  // configs.recommended already registers the plugin + two rules.
  {
    name: "gnom-hub/no-unsanitized",
    files: UI_FILES,
    ...noUnsanitized.configs.recommended,
    // Large legacy UI assigns HTML strings often — warn first, promote to error later
    rules: {
      ...noUnsanitized.configs.recommended.rules,
      "no-unsanitized/property": "warn",
      "no-unsanitized/method": "warn",
    },
  },

  // ── eslint-plugin-promise (flat recommended) ───────────────────────
  {
    name: "gnom-hub/promise",
    files: UI_FILES,
    ...promise.configs["flat/recommended"],
    rules: {
      ...promise.configs["flat/recommended"].rules,
      // fire-and-forget fetch/toast paths are common in this UI
      "promise/always-return": "off",
      "promise/catch-or-return": "warn",
      "promise/no-nesting": "warn",
      "promise/no-return-in-finally": "warn",
    },
  },

  // ── Project overrides (hub-specific) ───────────────────────────────
  {
    name: "gnom-hub/ui-overrides",
    files: UI_FILES,
    linterOptions: {
      reportUnusedDisableDirectives: "warn",
    },
    // plugins already registered by previous blocks; re-declare if adding local rules
    plugins: {
      "no-unsanitized": noUnsanitized,
      promise,
    },
    rules: {
      // Core extras beyond recommended (or tighten)
      "eqeqeq": ["warn", "smart"],
      "no-var": "warn",
      "prefer-const": ["warn", { destructuring: "all" }],
      "no-unused-vars": [
        "warn",
        {
          args: "none",
          caughtErrors: "none",
          ignoreRestSiblings: true,
          varsIgnorePattern: "^_",
        },
      ],
      "no-use-before-define": [
        "warn",
        { functions: false, classes: true, variables: true },
      ],
      "no-console": "off",
      "no-alert": "off",
      "no-empty": ["warn", { allowEmptyCatch: true }],
      "no-useless-escape": "warn",
      "no-useless-return": "warn",
      "no-useless-concat": "warn",
      "no-throw-literal": "warn",
      "no-return-assign": ["warn", "except-parens"],
      "no-sequences": "warn",
      "array-callback-return": ["warn", { allowImplicit: true }],
      "radix": ["warn", "as-needed"],
      "yoda": ["warn", "never"],

      // Style off — no Prettier fight
      "strict": "off",
      "curly": "off",
      "quotes": "off",
      "semi": "off",
      "indent": "off",
      "comma-dangle": "off",
      "max-len": "off",
      "prefer-arrow-callback": "off",
      "object-shorthand": "off",
      "prefer-template": "off",
    },
  },
];
