#!/usr/bin/env node
/**
 * ESLint Flat Config — override specificity self-test
 *
 * Proves:
 *   1) Later blocks win for the same rule (synthetic config)
 *   2) Production eslint.config.js applies expected strategy levels
 *
 * Exit 0 = pass. Docs: docs/ESLINT_OVERRIDE_STRATEGIES.md
 *
 *   node scripts/eslint_override_specificity.mjs
 *   npm run lint:js:specificity
 */
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { ESLint } = require("eslint");

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const APP_JS = path.join(ROOT, "src/gnom_hub/ui/static/app.js");

/** @param {unknown} entry */
function severity(entry) {
  if (entry === undefined || entry === null) return null;
  if (typeof entry === "number") return entry;
  if (typeof entry === "string") {
    if (entry === "off") return 0;
    if (entry === "warn") return 1;
    if (entry === "error") return 2;
    return null;
  }
  if (Array.isArray(entry)) return severity(entry[0]);
  return null;
}

function assert(cond, msg) {
  if (!cond) {
    const err = new Error(msg);
    err.name = "AssertError";
    throw err;
  }
}

/** Synthetic flat config: same files, two rule layers — later must win. */
async function testLaterBlockWins() {
  const eslint = new ESLint({
    cwd: ROOT,
    overrideConfigFile: true,
    overrideConfig: [
      {
        name: "spec/early",
        files: ["**/*.js"],
        rules: {
          "no-console": "error",
          "no-debugger": "error",
          "eqeqeq": "off",
        },
      },
      {
        name: "spec/late",
        files: ["**/*.js"],
        rules: {
          "no-console": "off", // must win
          "eqeqeq": ["warn", "smart"], // must win
          // no-debugger intentionally omitted → stays error from early
        },
      },
    ],
  });

  const cfg = await eslint.calculateConfigForFile(APP_JS);
  const rules = cfg.rules || {};

  assert(severity(rules["no-console"]) === 0, `later no-console off, got ${JSON.stringify(rules["no-console"])}`);
  assert(severity(rules["eqeqeq"]) === 1, `later eqeqeq warn, got ${JSON.stringify(rules["eqeqeq"])}`);
  assert(severity(rules["no-debugger"]) === 2, `early no-debugger error kept, got ${JSON.stringify(rules["no-debugger"])}`);

  // option payload for eqeqeq
  const eq = rules["eqeqeq"];
  assert(Array.isArray(eq) && eq[1] === "smart", `eqeqeq options smart, got ${JSON.stringify(eq)}`);

  return {
    name: "later-block-wins",
    noConsole: severity(rules["no-console"]),
    eqeqeq: rules["eqeqeq"],
    noDebugger: severity(rules["no-debugger"]),
  };
}

/** Glob order: second matching block wins even if first glob is “narrower” path-wise. */
async function testOrderBeatsPerceivedSpecificity() {
  const eslint = new ESLint({
    cwd: ROOT,
    overrideConfigFile: true,
    overrideConfig: [
      {
        name: "spec/narrow-first",
        files: ["src/gnom_hub/ui/static/**/*.js"],
        rules: { "no-alert": "error" },
      },
      {
        name: "spec/broad-second",
        files: ["**/*.js"],
        rules: { "no-alert": "off" },
      },
    ],
  });
  const cfg = await eslint.calculateConfigForFile(APP_JS);
  assert(
    severity(cfg.rules?.["no-alert"]) === 0,
    `broad-later must win over narrow-earlier, got ${JSON.stringify(cfg.rules?.["no-alert"])}`,
  );
  return { name: "order-beats-specificity", noAlert: 0 };
}

/** Production strategy map from ESLINT_OVERRIDE_STRATEGIES.md */
async function testProductionStrategies() {
  const eslint = new ESLint({ cwd: ROOT });
  const cfg = await eslint.calculateConfigForFile(APP_JS);
  const rules = cfg.rules || {};
  const plugins = Object.keys(cfg.plugins || {});

  const expect = [
    ["no-console", 0, "strategy/domain-off"],
    ["no-alert", 0, "strategy/domain-off"],
    ["strict", 0, "strategy/domain-off"],
    ["quotes", 0, "strategy/style-off"],
    ["semi", 0, "strategy/style-off"],
    ["promise/always-return", 0, "integratePlugin promise"],
    ["no-unsanitized/property", 1, "integratePlugin XSS warn"],
    ["no-unsanitized/method", 1, "integratePlugin XSS warn"],
    ["no-var", 1, "strategy/severity-core"],
    ["eqeqeq", 1, "strategy/severity-core"],
  ];

  const checked = [];
  for (const [id, sev, why] of expect) {
    const got = severity(rules[id]);
    assert(
      got === sev,
      `production ${id}: expected severity ${sev} (${why}), got ${got} ${JSON.stringify(rules[id])}`,
    );
    checked.push({ id, severity: got, why });
  }

  // eqeqeq smart option
  assert(
    Array.isArray(rules["eqeqeq"]) && rules["eqeqeq"][1] === "smart",
    `eqeqeq smart option missing: ${JSON.stringify(rules["eqeqeq"])}`,
  );

  // plugins registered
  for (const p of ["promise", "no-unsanitized"]) {
    assert(plugins.includes(p), `plugin ${p} not registered: ${plugins.join(",")}`);
  }

  return { name: "production-strategies", checked, plugins };
}

async function main() {
  const results = [];
  results.push(await testLaterBlockWins());
  results.push(await testOrderBeatsPerceivedSpecificity());
  results.push(await testProductionStrategies());

  console.log("ESLint override specificity: PASS");
  for (const r of results) {
    console.log(`  ✓ ${r.name}`);
  }
  // machine-readable summary
  if (process.argv.includes("--json")) {
    console.log(JSON.stringify({ ok: true, results }, null, 2));
  }
}

main().catch((err) => {
  console.error("ESLint override specificity: FAIL");
  console.error(err && err.message ? err.message : err);
  process.exit(1);
});
