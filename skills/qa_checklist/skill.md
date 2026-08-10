---
id: qa_checklist
name: QA checklist playbook
version: 0.1.0
enabled: true
description: Acceptance criteria + edge cases for plan_qa tasks
tags: [qa, checklist, testing]
agents: [coordinator, worker1, worker2, worker3, worker4]
triggers: [plan_qa, qa, checklist, acceptance, test plan]
---

# QA checklist

When the task is QA / acceptance / edge cases:

1. Happy path steps (numbered)
2. Empty / missing input cases
3. Error / failure modes
4. Regression risks after fix
5. Clear pass/fail criteria (observable)

No full product implementation unless explicitly asked.
