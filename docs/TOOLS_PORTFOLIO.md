# Tools portfolio (Computer-Use + hub)

Stand: 2026-08-06 · Research + installed optional stack.

## Already in hub (core)

| Tool | Role |
|------|------|
| `hub_status` | status string |
| `memory_search` | HOT/vector search |
| `pipeline_do` | full pipeline |
| `web_fetch` | public URL fetch |
| Computer-use API | inspect / click / type / shell (UI: **Tools** modal) |
| God-Mode | unlocks real mouse/keyboard/shell |

## Install (this machine)

```bash
source .venv/bin/activate
pip install -e ".[computer]"
# OCR binary (macOS):
# brew install tesseract
# Browser automation:
python -m playwright install chromium
```

## Downloaded into venv (portfolio)

| Package | Why |
|---------|-----|
| **pyautogui** | mouse click + type (ActionModule) |
| **Pillow** | images / ImageGrab fallback |
| **mss** | fast multi-monitor screenshots (~10–30× faster than PIL on mac) |
| **pytesseract** | OCR on screenshots (needs `tesseract` OS binary) |
| **pynput** | alt keyboard/mouse (unicode typing later) |
| **beautifulsoup4 + lxml** | cleaner HTML→text for web tools |
| **playwright** | real browser automation (already in env) |

## Research: good fit vs skip

| Candidate | Verdict |
|-----------|---------|
| mss + Pillow + pyautogui | **in** — capture + control baseline |
| pytesseract / Tesseract | **in** — light OCR for screen text |
| Playwright | **in** — browser control (better than Selenium for agents) |
| pynput | **in** — backup for typing / special keys |
| PaddleOCR / EasyOCR / Surya | **skip for now** — heavy GPU/models |
| OmniParser / OpenManus / full agent frameworks | **skip** — second runtime, overkill |
| Selenium | **skip** — Playwright covers it |
| OpenCV | **skip until needed** — pre-process for OCR |

## How you use it

1. Restart hub  
2. **Tools** button → Computer use  
3. **God** badge **ON** for real mouse/keyboard  
4. Inspect → screenshot under `data/computer_use/`  
5. Click / Type / Shell (allowlist)

Without God-Mode: dry-run only (safe).

## Automated proof (not docs-only)

Playwright scenario **S5** exercises Tools + computer-use so the portfolio is not dead:

```bash
python scripts/user_scenarios_e2e.py --only 5
# or default suite (S1 + S5):
python scripts/user_scenarios_e2e.py
```

See [`BASIC_USER_TEST.md`](BASIC_USER_TEST.md).
