"""Brave Search — always through Tollgate gateway (limits + ledger + circuit)."""

from __future__ import annotations

from typing import Any

from tollgate.gateway.context import RequestClass, RequestContext
from tollgate.gateway.entry import gateway_call


def brave_web_search(
    query: str,
    *,
    count: int = 5,
    country: str = "DE",
    search_lang: str = "de",
) -> dict[str, Any]:
    """
    Search the web via Brave Search API through Tollgate admission.

    Returns {ok, query, results:[{title,url,description}], rate?, error?, admit?}.
    """
    q = " ".join(str(query or "").split()).strip()
    if not q:
        return {"ok": False, "error": "empty query", "results": []}
    # Ensure Key.txt is in process env (hub already loads; tools may be called alone)
    try:
        from tollgate.secrets import ensure_env_from_key_txt, load_keys

        ensure_env_from_key_txt()
        load_keys()
    except Exception:  # noqa: BLE001
        pass
    return gateway_call(
        "brave",
        "search",
        ctx=RequestContext(
            request_class=RequestClass.INTERACTIVE,
            agent_id="tool:web_search",
        ),
        query=q,
        count=int(count or 5),
        country=str(country or "DE"),
        search_lang=str(search_lang or "de"),
    )
