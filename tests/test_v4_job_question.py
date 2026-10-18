"""V4 must release busy polling on a clarification, like the legacy desk."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(
    shutil.which("node") is None, reason="Node required for actual UI function probe"
)
def test_v4_clarification_returns_without_polling_until_timeout():
    root = Path(__file__).resolve().parents[1]
    source = root / "src/gnom_hub/ui/static/v4.js"
    script = r"""
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[1], 'utf8');
const start = source.indexOf('  async function pollJob(jobId)');
const end = source.indexOf('  async function consumeMaybeJob', start);
let now = 0, calls = 0;
const context = {
  Date:{now:()=>now}, snapshot:{}, renderAll:()=>{},
  api:async()=>{calls++;return {status:'clarify',finished:true,snapshot:{pipeline:{stage:'clarify'}}};},
  setTimeout:resolve=>{now=300001;resolve();}
};
vm.createContext(context);
vm.runInContext(source.slice(start,end), context);
context.pollJob('synthetic-job').then(result=>{
  assert.equal(result.pipeline.stage,'clarify');
  assert.equal(calls,1);
}).catch(error=>{console.error(error.message);process.exitCode=1;});
"""
    result = subprocess.run(
        ["node", "-e", script, str(source)], capture_output=True, text=True, timeout=5, check=False
    )
    assert result.returncode == 0, result.stderr
