/**
 * ESLint Flat Config (ESLint ≥ 9) — Gnom-Hub desktop UI
 *
 * Lint target: built bundle `src/gnom_hub/ui/static/app.js`
 * (parts/*.js are IIFE fragments — lint the built file only.)
 *
 * Docs: docs/ESLINT.md
 */
"use strict";

const globals = require("globals");

/** @type {import("eslint").Linter.Config[]} */
module.exports = [
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
      // generated / vendor-ish
      "**/vendor/**",
    ],
  },
  {
    name: "gnom-hub/ui-static",
    files: ["src/gnom_hub/ui/static/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script", // browser classic script, not ESM
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
    },
    linterOptions: {
      reportUnusedDisableDirectives: "warn",
    },
    rules: {
      // ── Correctness (error) ────────────────────────────────────
      "no-undef": "error",
      "no-unreachable": "error",
      "no-unsafe-finally": "error",
      "no-unsafe-negation": "error",
      "use-isnan": "error",
      "valid-typeof": "error",
      "no-debugger": "error",
      "no-dupe-args": "error",
      "no-dupe-keys": "error",
      "no-duplicate-case": "error",
      "no-empty-character-class": "error",
      "no-ex-assign": "error",
      "no-extra-boolean-cast": "error",
      "no-func-assign": "error",
      "no-import-assign": "error",
      "no-inner-declarations": "error",
      "no-invalid-regexp": "error",
      "no-obj-calls": "error",
      "no-sparse-arrays": "error",
      "no-unexpected-multiline": "error",
      "constructor-super": "error",
      "no-const-assign": "error",
      "no-new-native-nonconstructor": "error",
      "no-this-before-super": "error",
      "no-class-assign": "error",

      // ── Bug magnets (warn → tighten over time) ─────────────────
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
      "no-shadow-restricted-names": "error",
      "no-redeclare": "warn",
      "no-self-assign": "warn",
      "no-self-compare": "warn",
      "no-template-curly-in-string": "warn",
      "array-callback-return": ["warn", { allowImplicit: true }],
      "no-caller": "error",
      "no-extend-native": "error",
      "no-extra-bind": "warn",
      "no-implied-eval": "error",
      "no-iterator": "error",
      "no-labels": "error",
      "no-lone-blocks": "warn",
      "no-loop-func": "warn",
      "no-multi-str": "warn",
      "no-new-func": "error",
      "no-new-wrappers": "warn",
      "no-octal": "error",
      "no-proto": "error",
      "no-return-assign": ["warn", "except-parens"],
      "no-sequences": "warn",
      "no-throw-literal": "warn",
      "no-unmodified-loop-condition": "warn",
      "no-unused-expressions": [
        "warn",
        { allowShortCircuit: true, allowTernary: true },
      ],
      "no-useless-call": "warn",
      "no-useless-concat": "warn",
      "no-useless-escape": "warn",
      "no-useless-return": "warn",
      "no-with": "error",
      "radix": ["warn", "as-needed"],
      "yoda": ["warn", "never"],

      // ── Style (light — no Prettier fight) ───────────────────────
      "no-console": "off", // hub UI uses console for debug
      "no-alert": "off",
      "strict": "off", // IIFE already "use strict"
      "no-empty": ["warn", { allowEmptyCatch: true }],
      "curly": "off",
      "brace-style": "off",
      "quotes": "off",
      "semi": "off",
      "indent": "off",
      "comma-dangle": "off",
      "max-len": "off",

      // ── Prefer modern where easy ───────────────────────────────
      "prefer-arrow-callback": "off", // many classic functions intentional
      "object-shorthand": "off",
      "prefer-template": "off",
      "no-useless-rename": "warn",
      "no-useless-computed-key": "warn",
      "rest-spread-spacing": "off",
    },
  },
];
