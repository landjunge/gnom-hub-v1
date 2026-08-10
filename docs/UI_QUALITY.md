# UI quality · colors · stability · speed

Stand: 2026-08-10 (polish pass)

## Color concept

One dark surface system + **agent identity accents** (not random neon):

| Token | Role |
|-------|------|
| `--bg` / `--bg-panel` / `--bg-elev` | surfaces |
| `--text` / `--text-muted` / `--border` | chrome |
| `--ok` / `--warn` / `--err` | status toasts & card status |
| `--c-brainstorm` … `--c-worker4` | agent identity (borders, cards) |

Agents stay **distinct** but share chroma/value so the desk feels one product.

## Stability

- Job poll: adaptive delay (fast at start, calmer mid-work; slower when tab hidden)
- Iframe Box 3: skip rebuild when payload unchanged (no white flash)
- Toasts: only fresh pipeline errors (no re-fire every snapshot)
- `prefers-reduced-motion`: disable infinite pulses

## Speed

- Early poll ~180ms for snappy stage updates
- Back-off to ~500–650ms during long worker runs (less CPU/network)
- Job timer DOM update 250ms (was 100ms)

## A11y

- `:focus-visible` ring on buttons, cards, inputs
- Touch targets on mobile (see ≤640px rules)

## Checklist after UI CSS changes

```bash
npm run lint:js
./scripts/quality_check.sh   # if server up: B1–B3
```
