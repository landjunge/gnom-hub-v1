"""HTTP routes: agents."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from gnom_hub.api.models import AgentLlmBody, AgentTuneBody, FlexBody
from gnom_hub.hub import get_hub

router = APIRouter()


@router.get("/api/agents")
def agents() -> dict[str, Any]:
    hub = get_hub()
    return {"agents": [hub._agent_dict(a) for a in hub.agents.list_agents()]}


@router.post("/api/agents/{agent_id}/toggle")
def toggle(agent_id: str) -> dict[str, Any]:
    try:
        return get_hub().toggle_agent(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/agents/enable-all")
def enable_all_agents() -> dict[str, Any]:
    hub = get_hub()
    hub.agents.enable_all()
    return {
        "ok": True,
        "agents": [hub._agent_dict(a) for a in hub.agents.list_agents()],
    }


@router.post("/api/agents/flex/preset")
def flex_preset(body: FlexBody) -> dict[str, Any]:
    try:
        return get_hub().set_flex_preset(body.preset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/agents/{agent_id}/llm")
def agent_llm(agent_id: str, body: AgentLlmBody) -> dict[str, Any]:
    try:
        return get_hub().set_agent_llm(agent_id, model=body.model, api_key=body.api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/agents/{agent_id}/tune")
def agent_tune(agent_id: str, body: AgentTuneBody) -> dict[str, Any]:
    try:
        return get_hub().set_agent_tune(agent_id, body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
