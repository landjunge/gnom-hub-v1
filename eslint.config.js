/**
 * ESLint Flat Config (ESLint ≥ 9) — Gnom-Hub desktop UI
 *
 * Plugin integration pattern (see docs/ESLINT_PLUGIN_INTEGRATION.md):
 *   1. require plugin module
 *   2. pick flat config (configs.recommended / configs["flat/…"])
 *   3. integratePlugin(name, base, { files, rules }) → scoped block
 *   4. project overrides last (wins)
 *
 * Plugins:
 *   @eslint/js                  → js.configs.recommended
 *   eslint-plugin-no-unsanitized → XSS (innerHTML)
 *   eslint-plugin-promise       → promise/flat/recommended
 *
 * Lint target: built `app.js` (parts/ ignored — IIFE fragments).
 */
"use strict";

const js = require("@eslint/js");
const globals = require("globals");
const noUnsanitized = require("eslint-plugin-no-unsanitized");
const promise = require("eslint-plugin-promise");

/** @type {string[]} */
const UI_FILES = ["src/gnom_hub/ui/static/**/*.js"];

/**
 * Integrate a plugin's flat config into our array.
 *
 * @param {string} name block label (debug / --print-config)
 * @param {import("eslint").Linter.Config | import("eslint").Linter.Config[]} base
 *        plugin.configs.recommended or flat/recommended (object or array)
 * @param {object} [opts]
 * @param {string[]} [opts.files]
 * @param {import("eslint").Linter.RulesRecord} [opts.rules] overrides (merged last)
 * @param {import("eslint").Linter.Config["languageOptions"]} [opts.languageOptions]
 * @returns {import("eslint").Linter.Config[]}
 */
function integratePlugin(name, base, opts = {}) {
  const files = opts.files || UI_FILES;
  const ruleOverrides = opts.rules || {};
  const blocks = Array.isArray(base) ? base : [base];

  return blocks.map((block, i) => {
    const mergedRules = {
      ...(block.rules || {}),
      ...ruleOverrides,
    };
    /** @type {import("eslint").Linter.Config} */
    const out = {
      ...block,
      name: blocks.length > 1 ? `${name}/${i}` : name,
      files: block.files || files,
      rules: mergedRules,
    };
    if (opts.languageOptions) {
      out.languageOptions = {
        ...(block.languageOptions || {}),
        ...opts.languageOptions,
        globals: {
          ...((block.languageOptions && block.languageOptions.globals) || {}),
          ...((opts.languageOptions && opts.languageOptions.globals) || {}),
        },
      };
    }
    return out;
  });
}

/** @type {import("eslint").Linter.Config[]} */
module.exports = [
  // ── Global ignores ─────────────────────────────────────────────────
  {
    name: "gnom-hub/ignores",
    ignores: [
      "**/node_modules/**",
      "**/.venv/**",
      "**/venv/**",
      "**/data/**",
      "**/dist/**",
      "**/build/**",
      "src/gnom_hub/ui/static/parts/**",
      "**/vendor/**",
    ],
  },

  // ── @eslint/js (core “plugin” / official package) ──────────────────
  ...integratePlugin("gnom-hub/js-recommended", js.configs.recommended, {
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
    },
  }),

  // ── eslint-plugin-no-unsanitized ───────────────────────────────────
  // base already sets plugins: { "no-unsanitized": … } + rules
  ...integratePlugin("gnom-hub/no-unsanitized", noUnsanitized.configs.recommended, {
    rules: {
      // legacy UI builds HTML strings — warn until safeHtml helper exists
      "no-unsanitized/property": "warn",
      "no-unsanitized/method": "warn",
    },
  }),

  // ── eslint-plugin-promise ──────────────────────────────────────────
  ...integratePlugin("gnom-hub/promise", promise.configs["flat/recommended"], {
    rules: {
      "promise/always-return": "off",
      "promise/catch-or-return": "warn",
      "promise/no-nesting": "warn",
      "promise/no-return-in-finally": "warn",
    },
  }),

  // ── Override strategies (see docs/ESLINT_OVERRIDE_STRATEGIES.md) ──
  // Order: severity-core → quality-warn → domain-off → style-off (last wins per rule)

  {
    name: "strategy/linter-options",
    files: UI_FILES,
    linterOptions: {
      reportUnusedDisableDirectives: "warn",
    },
  },

  // S1/S2 — core severity + options (legacy-friendly warns)
  {
    name: "strategy/severity-core",
    files: UI_FILES,
    rules: {
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
      "no-empty": ["warn", { allowEmptyCatch: true }],
      "radix": ["warn", "as-needed"],
      "yoda": ["warn", "never"],
    },
  },

  // S1 — extra quality signals (warn, not CI-red)
  {
    name: "strategy/quality-warn",
    files: UI_FILES,
    rules: {
      "no-useless-escape": "warn",
      "no-useless-return": "warn",
      "no-useless-concat": "warn",
      "no-throw-literal": "warn",
      "no-return-assign": ["warn", "except-parens"],
      "no-sequences": "warn",
      "array-callback-return": ["warn", { allowImplicit: true }],
    },
  },

  // S3 — domain allows (hub UI reality)
  {
    name: "strategy/domain-off",
    files: UI_FILES,
    rules: {
      "no-console": "off",
      "no-alert": "off",
      "strict": "off",
    },
  },

  // S3 — formatting left to humans / future formatter
  {
    name: "strategy/style-off",
    files: UI_FILES,
    rules: {
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
