"""Pydantic request bodies for the HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatBody(BaseModel):
    text: str = Field(min_length=1)
    target: str = "brainstorm"


class ClarifyBody(BaseModel):
    option: str = Field(min_length=1)


class FlexBody(BaseModel):
    preset: str = Field(min_length=1)


class AgentLlmBody(BaseModel):
    model: str | None = None
    api_key: str | None = None


class AgentTuneBody(BaseModel):
    model: str | None = None
    api_key: str | None = None
    system_prompt: str | None = None
    tts: bool | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None


class SystemBody(BaseModel):
    free_only: bool | None = None
    max_budget_usd: float | None = None
    default_model: str | None = None
    ui_lang: str | None = None
    auto_pack_after_execute: bool | None = None
    pack_max: int | None = None


class WorkerPresetBody(BaseModel):
    name: str = Field(min_length=1)
    agent_id: str = "worker1"


class TeamPresetBody(BaseModel):
    name: str = Field(min_length=1)


class PlanModeBody(BaseModel):
    plan_mode: str = Field(min_length=1)


class WarmFactBody(BaseModel):
    text: str = Field(min_length=1)


class HotFactBody(BaseModel):
    text: str = Field(min_length=1)


class WorkspaceWriteBody(BaseModel):
    zone: str = "temp"
    name: str = Field(min_length=1)
    content: str = ""


class KeepSelectedBody(BaseModel):
    """Copy one chosen result: HTML → selected/, other text → perm/."""

    content: str | None = None
    name: str | None = None
    worker: str | None = None
    overwrite: bool = False


class TelegramInBody(BaseModel):
    text: str = Field(min_length=1)
    chat_id: int | None = None


class TtsPrepareBody(BaseModel):
    text: str = ""
    lang: str | None = "de"


class FlexFeedbackBody(BaseModel):
    button_id: str = ""
    label: str = ""
    note: str = ""


class FlexAskBody(BaseModel):
    agent_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    job_id: str = ""
    task_id: str = ""
    component: str = "yes_no"
    options: list[str] | None = None


class FlexAnswerBody(BaseModel):
    question_id: str = Field(min_length=1)
    value: Any = ""
    job_id: str = ""


class GodModeBody(BaseModel):
    enabled: bool
    reason: str = "user"
    assignment_id: str = ""


class VectorAddBody(BaseModel):
    text: str = Field(min_length=1)
    meta: dict[str, Any] | None = None


class VectorSearchBody(BaseModel):
    query: str = Field(min_length=1)
    limit: int = 5


class VectorEmbedderBody(BaseModel):
    backend: str = Field(min_length=1, max_length=64)
    reindex: bool = False


class SkillEnableBody(BaseModel):
    enabled: bool = True


class SkillInstallBody(BaseModel):
    path: str = Field(min_length=1, max_length=500)


class SkillLearnBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=12000)
    tags: list[str] | None = None
    triggers: list[str] | None = None
    description: str = ""


class ToolCallBody(BaseModel):
    name: str = Field(min_length=1)
    arguments: dict[str, Any] | None = None


class ColdLabelBody(BaseModel):
    label: str = ""


class SessionPackBody(BaseModel):
    pack: dict[str, Any]
    include_warm: bool = True
    include_agents: bool = True
    store: bool = False


class PackRenameBody(BaseModel):
    label: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=200)


class PackExportBody(BaseModel):
    label: str | None = None
    notes: str | None = None
    persist: bool = True
    include_workspace: bool = True
    ui_chat_log: list[dict[str, Any]] | None = None
    ui_result_history: list[dict[str, Any]] | None = None
    ui_prefs: dict[str, Any] | None = None


class ReexecuteBody(BaseModel):
    user_text: str = ""
    brainstorm_notes: str = ""
    brainstorm_turns: list[dict[str, Any]] | None = None


class ActionClickBody(BaseModel):
    x: int
    y: int


class ActionTypeBody(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class ShellBody(BaseModel):
    cmd: str = Field(min_length=1, max_length=200)
