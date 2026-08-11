"""web_search appears in prefetch plan for research language."""

from gnom_hub.tools.worker_prefetch import plan_prefetch, tool_calls_needed


def test_plan_prefetch_web_search_for_research():
    plan = plan_prefetch("Recherchiere aktuell was Tollgate API ist")
    names = [s.name for s in plan]
    assert "web_search" in names


def test_plan_prefetch_no_search_when_url_present():
    plan = plan_prefetch("Fetch https://example.com/docs and summarize")
    names = [s.name for s in plan]
    assert "web_fetch" in names
    assert "web_search" not in names


def test_tool_calls_needed_lists_search():
    needed = tool_calls_needed("search the web for latest news about local AI gateways")
    assert "web_search" in needed
