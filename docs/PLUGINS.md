# Plugins — catalog & desk details

Trust model: [PLUGIN_SECURITY.md](PLUGIN_SECURITY.md) · MCP: [MCP_ARCHITECTURE.md](MCP_ARCHITECTURE.md)

## How drop-in works

1. Folder `plugins/<id>/plugin.json` (+ `main.py`)
2. Boot / `POST /api/plugins/reload` → validate → register tools
3. `GET /api/plugins` → `{ plugins, disk, tools, errors }`
4. Tools modal lists **Plugins on disk** then **Registered tools**

Skip: `_template`, `.*` folders. Disabled: `"enabled": false` in manifest.

## Bundled plugins

| Id | Tools | Role |
|----|-------|------|
| `echo` | `echo` | Demo / on_load smoke |
| `text_stats` | `text_stats` | Word/line/char counts |
| `file_ops` | list/read/write (jailed) | Workspace file IO |
| `git_ops` | status/diff (God for write-ish) | Local git inspect |
| `shell_safe` | allowlisted shell | Desk shell under God-Mode |
| `install_tool` | `tool_ensure` / package ensure | Optional deps for workers |
| `playwright_browser` | browser_open / click / … | Live browser automation |
| `web_design` | palette / scaffold helpers | Worker design prefetch |
| `embeddings_lite` | `embeddings_status`, `embeddings_use`, `embeddings_reindex` | Switch vector embedder |

## embeddings_lite

Default VectorStore stays **bow** (BM25 + unigram cosine) — USB / offline safe.

| Backend | What | When |
|---------|------|------|
| `bow` | bag-of-words unigrams | default, rank-eval gold |
| `char_ngram` | char 3-grams + unigrams | short DE/EN facts, typos |
| `hashing` | hashing trick 128-dim | fixed feature space |

```bash
# optional env at hub start
export GNOM_EMBEDDINGS=char_ngram
export GNOM_EMBEDDINGS_REINDEX=1   # recompute stored vecs once
```

Tools (Tools modal or worker TOOL_CALL):

```
TOOL_CALL embeddings_status={}
TOOL_CALL embeddings_use={"backend":"char_ngram","reindex":true}
TOOL_CALL embeddings_reindex={}
```

Neural models (sentence-transformers, etc.) are **not** bundled. Install extras yourself and:

```python
hub.vectors.set_embedder("sbert", fn=my_fn, reindex=True)
```

## Authoring

```bash
python scripts/new_plugin.py my_tool
# edit plugins/my_tool/{plugin.json,main.py}
# Tools modal → Reload plugins
```

Rules: no core tool name clash · only trusted code · God-Mode gates for shell/GUI.

## API

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/plugins` | loaded + **disk** inventory + tools + errors |
| POST | `/api/plugins/reload` | full rescan; `?plugin_id=` for one |
| GET | `/api/mcp/tools` | MCP-lite list |
