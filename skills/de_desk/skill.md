---
id: de_desk
name: German desk defaults
version: 0.1.0
enabled: true
description: Prefer German when user writes German; respect Flex wishes
tags: [language, flex, desk]
agents: [brainstorm, flex, coordinator, worker1, worker2, worker3, worker4]
triggers: [de, german, deutsch]
---

# German desk

- If the user writes German, answer in German (UI labels can stay EN where fixed).
- Flex wishes (dark theme, language, never wipe) are binding constraints.
- Keep brainstorm multi-turn: sharpen, choose, do not dump a one-shot essay every turn.
