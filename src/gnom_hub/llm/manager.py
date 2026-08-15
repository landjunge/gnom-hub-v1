"""LLM-Manager: DeepSeek + Ollama + Tollgate-routed free/paid paths."""

from __future__ import annotations

import os
from collections.abc import Callable

from gnom_hub.config.auth import key_fingerprint, keys_auth_snapshot
from gnom_hub.config.keys import is_usable_api_key
from gnom_hub.llm.deepseek import DEFAULT_MODEL, DeepSeekClient, estimate_cost_usd
from gnom_hub.llm.ollama import DEFAULT_MODEL as OLLAMA_DEFAULT
from gnom_hub.llm.ollama import OllamaClient
from gnom_hub.llm.types import (
    AuthError,
    BudgetExceededError,
    FreeOnlyError,
    LLMError,
    LLMMessage,
    LLMResult,
    MissingKeyError,
    RateLimitError,
)

# Free when free_only: all ollama/* local models
FREE_MODELS: frozenset[str] = frozenset(
    {
        "ollama",
        OLLAMA_DEFAULT,
        "llama3.2",
        "llama3.1",
        "llama3",
        "mistral",
        "qwen2.5",
        "phi3",
        "gemma2",
    }
)

ClientFactory = Callable[[str], DeepSeekClient]

_PROTECT_NEEDLES = (
    "budget",
    "tool-loop",
    "tool loop",
    "tool_call",
    "blocked",
    "quota",
    "frozen",
    "freeze",
    "rate limit",
    "agent protection",
    "max_tokens_request",
    "max_usd",
    "max_calls",
    "max_requests_minute",
    "max_tool_calls",
    "policy_deny",
    "policy deny",
    "admission",
    "fail-closed",
    "ledger corrupt",
    "protection",
)


def raise_tollgate_chat_error(out: dict) -> None:
    """Map a failed Tollgate chat payload to the matching LLM exception."""
    err = str(out.get("error") or out.get("detail") or "tollgate chat failed")
    if isinstance(out.get("error"), dict):
        err = str(out["error"].get("message") or err)
    raw = out.get("raw_openai") if isinstance(out.get("raw_openai"), dict) else out
    if isinstance(raw.get("error"), dict):
        err = str(raw["error"].get("message") or err)
        tg = raw["error"].get("tollgate") if isinstance(raw["error"].get("tollgate"), dict) else {}
        if tg.get("message"):
            err = str(tg["message"])
    low = err.lower()
    if "key" in low or "missing" in low or "no provider" in low or "no free provider" in low:
        raise MissingKeyError(err)
    if "rate" in low or "429" in low:
        raise RateLimitError(err)
    if "auth" in low or "401" in low or "403" in low:
        raise AuthError(err)
    if any(x in low for x in _PROTECT_NEEDLES):
        raise BudgetExceededError(err)
    raise LLMError(err)


class LLMManager:
    """
    Chat completions via DeepSeek (cloud) and/or Ollama (local).

    Model routing:
    - prefix ``ollama/`` or ``ollama:`` → Ollama
    - env/default DeepSeek when key present
    - if no DeepSeek key but Ollama is up → auto Ollama
    """

    def __init__(
        self,
        keys: dict[str, str] | None = None,
        *,
        free_only: bool | None = None,
        max_budget_usd: float | None = None,
        default_model: str = DEFAULT_MODEL,
        client_factory: ClientFactory | None = None,
        ollama_base: str | None = None,
    ) -> None:
        self._keys = dict(keys or {})
        if free_only is None:
            free_only = os.getenv("GNOM_FREE_ONLY", "0").strip() in ("1", "true", "yes")
        if max_budget_usd is None:
            raw = os.getenv("GNOM_MAX_BUDGET_USD", "").strip()
            max_budget_usd = float(raw) if raw else None

        self.free_only = free_only
        self.max_budget_usd = max_budget_usd
        # Key.txt / env DEEPSEEK_MODEL overrides default (e.g. deepseek-v4-flash)
        env_model = (self._keys.get("DEEPSEEK_MODEL") or os.getenv("DEEPSEEK_MODEL") or "").strip()
        self.default_model = env_model or default_model
        self._spent_usd = 0.0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._by_agent: dict[str, dict[str, float | int]] = {}
        self._client_factory = client_factory or (lambda key: DeepSeekClient(key))
        self._ollama = OllamaClient(base_url=ollama_base)
        self._ollama_ok: bool | None = None
        # Session blocklist after 401/403 — avoid hammering dead keys
        self._auth_blocked: set[str] = set()

    @property
    def spent_usd(self) -> float:
        return self._spent_usd

    @property
    def prompt_tokens(self) -> int:
        return self._prompt_tokens

    @property
    def completion_tokens(self) -> int:
        return self._completion_tokens

    def usage_snapshot(self) -> dict:
        return {
            "spent_usd": self._spent_usd,
            "prompt_tokens": self._prompt_tokens,
            "completion_tokens": self._completion_tokens,
            "by_agent": {k: dict(v) for k, v in self._by_agent.items()},
        }

    def reset_usage(self) -> dict:
        """Clear session spend counters (not invoice history)."""
        self._spent_usd = 0.0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._by_agent = {}
        return self.usage_snapshot()

    def _usable_or_empty(self, raw: str) -> str:
        s = (raw or "").strip()
        if not is_usable_api_key(s):
            return ""
        fp = key_fingerprint(s)
        if fp and fp in self._auth_blocked:
            return ""
        return s

    def deepseek_key(self, override: str | None = None) -> str:
        if override and override.strip():
            return self._usable_or_empty(override)
        return self._usable_or_empty(self._keys.get("DEEPSEEK_API_KEY", ""))

    def worker_key(self, override: str | None = None) -> str:
        """Worker key, then fall back to system DeepSeek key."""
        if override and override.strip():
            return self._usable_or_empty(override)
        wrk = self._usable_or_empty(self._keys.get("WORKER_API_KEY", ""))
        if wrk:
            return wrk
        return self.deepseek_key()

    def note_auth_failure(self, key: str | None = None) -> None:
        """Block a key for this process after provider 401/403."""
        for candidate in (
            key,
            self._keys.get("DEEPSEEK_API_KEY"),
            self._keys.get("WORKER_API_KEY"),
        ):
            s = (candidate or "").strip()
            if is_usable_api_key(s):
                self._auth_blocked.add(key_fingerprint(s))
                break
        # if key passed was the failing one
        if key and is_usable_api_key(key):
            self._auth_blocked.add(key_fingerprint(key))

    def clear_auth_blocks(self) -> None:
        self._auth_blocked.clear()

    def auth_snapshot(self) -> dict:
        snap = keys_auth_snapshot(self._keys)
        snap["session_auth_blocked"] = len(self._auth_blocked) > 0
        snap["session_blocked_n"] = len(self._auth_blocked)
        # effective readiness after blocklist
        snap["deepseek_live"] = self.has_provider("deepseek")
        return snap

    def ollama_available(self, *, force: bool = False) -> bool:
        if self._ollama_ok is not None and not force:
            return self._ollama_ok
        self._ollama_ok = self._ollama.available()
        return self._ollama_ok

    def has_provider(self, name: str = "deepseek") -> bool:
        if name == "deepseek":
            return bool(self.deepseek_key())
        if name == "ollama":
            return self.ollama_available()
        if name in ("any", "llm"):
            return bool(self.deepseek_key()) or self.ollama_available()
        return False

    def providers_snapshot(self) -> dict:
        models: list[str] = []
        if self.ollama_available():
            try:
                models = self._ollama.list_models()
            except Exception:  # noqa: BLE001
                models = []
        return {
            "deepseek": self.has_provider("deepseek"),
            "ollama": self.ollama_available(),
            "ollama_host": self._ollama.base_url,
            "ollama_models": models,
            "default_model": self.default_model,
        }

    def list_ollama_models(self) -> list[str]:
        if not self.ollama_available(force=True):
            return []
        try:
            return self._ollama.list_models()
        except Exception:  # noqa: BLE001
            return []

    def chat(
        self,
        messages: list[LLMMessage] | list[dict[str, str]],
        *,
        model: str | None = None,
        api_key: str | None = None,
        agent: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        provider: str | None = None,
        thinking: bool | None = None,
    ) -> LLMResult:
        model_name = model or self.default_model
        prov, bare_model = self._resolve_route(model_name, provider)
        msgs = self._normalize_messages(messages)
        agent_key = (agent or "system").strip() or "system"

        # Explicit local Ollama route
        if prov == "ollama":
            result = self._ollama.chat(
                msgs,
                model=bare_model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )
            return self._account(result, agent_key)

        # free_only: block paid DeepSeek; optional free via Tollgate (env) or ollama/*
        if self.free_only:
            if os.getenv("GNOM_FREE_TOLLGATE", "1").strip() not in ("0", "false", "no"):
                try:
                    result = self._chat_via_tollgate(
                        msgs,
                        model="" if prov in ("deepseek", "tollgate", "") else bare_model,
                        provider=None if prov in ("deepseek", "tollgate", "") else prov,
                        agent=agent_key,
                        temperature=temperature,
                        max_tokens=max_tokens or 1024,
                        prefer_free=True,
                    )
                    return self._account(result, agent_key)
                except (MissingKeyError, AuthError, RateLimitError, LLMError):
                    pass  # fall through to FreeOnlyError
            raise FreeOnlyError(
                f"Model '{model_name}' is not free and free_only is enabled. "
                "Use ollama/* or set GNOM_FREE_ONLY=0 (or enable free Tollgate route)."
            )

        # Default: all cloud LLM through Tollgate (admit + meter + failover).
        # Opt out: GNOM_TOLLGATE_LLM=0  |  HTTP mode: TOLLGATE_URL=http://127.0.0.1:8787
        force_tg_raw = os.getenv("GNOM_TOLLGATE_LLM", "1").strip().lower()
        force_tg = force_tg_raw not in ("0", "false", "no", "off")
        via_tg = (
            force_tg
            or prov in ("opencode_zen", "openrouter", "nvidia", "tollgate")
            or bool((os.getenv("TOLLGATE_URL") or "").strip())
        )
        if via_tg and prov != "ollama":
            prefer_free = self.free_only or not self.deepseek_key(api_key)
            # workers stay on worker/deepseek when key present
            if agent_key.startswith("worker") and self.worker_key(api_key):
                tg_provider = "worker"
                tg_model = bare_model or model_name
                prefer_free = False
            elif prov in ("deepseek",) and self.deepseek_key(api_key) and not prefer_free:
                tg_provider = "deepseek"
                tg_model = bare_model or model_name
            elif prov in ("opencode_zen", "openrouter", "nvidia"):
                tg_provider = prov
                tg_model = bare_model
            else:
                tg_provider = None
                tg_model = "" if prov in ("deepseek", "tollgate", "") else bare_model
            try:
                result = self._chat_via_tollgate(
                    msgs,
                    model=tg_model or "",
                    provider=tg_provider,
                    agent=agent_key,
                    temperature=temperature,
                    max_tokens=max_tokens or 1024,
                    prefer_free=prefer_free,
                )
                return self._account(result, agent_key)
            except BudgetExceededError:
                # F-03: Protect / budget / freeze is never bypassed by legacy DeepSeek
                raise
            except (MissingKeyError, AuthError, RateLimitError, FreeOnlyError, LLMError):
                # GNOM_TOLLGATE_LLM=1 (force_tg): hard fail — no silent paid spillover
                # as consumer "anonymous" via legacy client.
                if force_tg:
                    raise
                # Optional Tollgate path only: allow legacy DeepSeek when key present
                if not self.deepseek_key(api_key):
                    raise
                # fall through to legacy DeepSeek
            except Exception as e:
                if force_tg:
                    raise LLMError(str(e)) from e
                if not self.deepseek_key(api_key):
                    raise LLMError(str(e)) from e

        # No DeepSeek key: Tollgate free, then Ollama
        no_cloud_key = not self.deepseek_key(api_key) and not (
            agent_key.startswith("worker") and self.worker_key(api_key)
        )
        if no_cloud_key:
            try:
                result = self._chat_via_tollgate(
                    msgs,
                    model="",
                    provider=None,
                    agent=agent_key,
                    temperature=temperature,
                    max_tokens=max_tokens or 1024,
                    prefer_free=True,
                )
                return self._account(result, agent_key)
            except (MissingKeyError, AuthError, RateLimitError, LLMError) as e:
                if self.ollama_available():
                    result = self._ollama.chat(
                        msgs,
                        model=os.getenv("OLLAMA_MODEL", OLLAMA_DEFAULT),
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                    )
                    return self._account(result, agent_key)
                raise MissingKeyError(
                    "DEEPSEEK_API_KEY missing, Tollgate free route failed, Ollama not reachable."
                ) from e
            except Exception as e:
                if self.ollama_available():
                    result = self._ollama.chat(
                        msgs,
                        model=os.getenv("OLLAMA_MODEL", OLLAMA_DEFAULT),
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                    )
                    return self._account(result, agent_key)
                raise MissingKeyError(
                    "DEEPSEEK_API_KEY missing, Tollgate free route failed, "
                    f"Ollama not reachable ({e})."
                ) from e

        if api_key:
            key = self.deepseek_key(api_key) or self.worker_key(api_key)
        elif agent_key.startswith("worker"):
            key = self.worker_key()
        else:
            key = self.deepseek_key() or self.worker_key()
        if not key:
            raise MissingKeyError("DEEPSEEK_API_KEY / WORKER_API_KEY missing")

        if self.max_budget_usd is not None:
            rough = estimate_cost_usd(bare_model, 1000, 1000)
            if self._spent_usd + rough > self.max_budget_usd and self._spent_usd > 0:
                raise BudgetExceededError(
                    f"Budget exceeded: spent ${self._spent_usd:.4f} / "
                    f"max ${self.max_budget_usd:.4f}"
                )
        tg_provider = "worker" if agent_key.startswith("worker") else "deepseek"
        self._tollgate_admit(tg_provider, bare_model, agent=agent_key)
        client = self._client_factory(key)
        try:
            result = client.chat(
                msgs,
                model=bare_model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                thinking=thinking,
            )
        except AuthError:
            self.note_auth_failure(key)
            raise
        except RateLimitError:
            raise
        self._tollgate_record(
            tg_provider,
            bare_model,
            result.prompt_tokens,
            result.completion_tokens,
            result.cost_usd,
        )
        return self._account(result, agent_key)

    def _account(self, result: LLMResult, agent_key: str) -> LLMResult:
        self._spent_usd += result.cost_usd
        self._prompt_tokens += result.prompt_tokens
        self._completion_tokens += result.completion_tokens
        bucket = self._by_agent.setdefault(
            agent_key,
            {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0, "calls": 0},
        )
        bucket["prompt_tokens"] = int(bucket["prompt_tokens"]) + result.prompt_tokens
        bucket["completion_tokens"] = int(bucket["completion_tokens"]) + result.completion_tokens
        bucket["cost_usd"] = float(bucket["cost_usd"]) + result.cost_usd
        bucket["calls"] = int(bucket["calls"]) + 1
        return result

    def _chat_via_tollgate(
        self,
        messages: list[LLMMessage],
        *,
        model: str,
        provider: str | None,
        agent: str,
        temperature: float,
        max_tokens: int,
        prefer_free: bool,
    ) -> LLMResult:
        payload = [{"role": m.role, "content": m.content} for m in messages]
        intent = "free_llm" if prefer_free else "llm"
        if (provider or "") == "worker":
            intent = "paid_llm"
        base = (os.getenv("TOLLGATE_URL") or "").strip().rstrip("/")
        try:
            if base:
                from tollgate.client import TollgateClient

                client = TollgateClient(
                    base_url=base,
                    consumer=os.getenv("TOLLGATE_CONSUMER", "gnom"),
                )
                out = client.chat(
                    payload,
                    intent=intent,
                    provider=provider or "",
                    model=model or ("tollgate/free" if prefer_free else "tollgate/auto"),
                    max_tokens=max_tokens,
                    temperature=temperature,
                    agent_id=f"gnom:{agent}",
                )
            else:
                from tollgate import routed_chat

                out = routed_chat(
                    payload,
                    intent=intent,
                    model=model or "",
                    provider=provider or "",
                    max_tokens=max_tokens,
                    temperature=temperature,
                    agent_id=f"gnom:{agent}",
                    prefer_free=prefer_free,
                )
        except ModuleNotFoundError as e:
            raise LLMError("tollgate package not installed") from e
        if not out.get("ok") and "choices" not in out:
            raise_tollgate_chat_error(out)
        pt = int(out.get("prompt_tokens") or (out.get("usage") or {}).get("prompt_tokens") or 0)
        ct = int(
            out.get("completion_tokens") or (out.get("usage") or {}).get("completion_tokens") or 0
        )
        content = str(out.get("content") or "")
        mid = str(out.get("model") or model or "tollgate")
        cost = float(out.get("cost") or 0.0)
        if cost <= 0 and pt + ct > 0 and not prefer_free:
            cost = estimate_cost_usd(mid, pt, ct)
        return LLMResult(
            content=content,
            model=mid,
            prompt_tokens=pt,
            completion_tokens=ct,
            cost_usd=cost,
            raw=out,
        )

    def _tollgate_admit(self, provider: str, model: str, *, agent: str) -> None:
        """In-process admit for legacy path. Fail-closed when Tollgate is forced."""
        force_tg = os.getenv("GNOM_TOLLGATE_LLM", "1").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )
        consumer = (os.getenv("TOLLGATE_CONSUMER") or "gnom").strip() or "gnom"
        try:
            from tollgate.gateway.admit import admit
            from tollgate.gateway.context import RequestClass, RequestContext

            d = admit(
                provider,
                op="chat",
                tokens_est=512,
                model=model,
                ctx=RequestContext(
                    agent_id=f"gnom:{agent}",
                    consumer=consumer,
                    request_class=RequestClass.INTERACTIVE,
                ),
            )
            if not d.allowed:
                raise BudgetExceededError(d.reason or "tollgate admit denied")
        except BudgetExceededError:
            raise
        except Exception as e:
            # F-03: never silent-pass when Protect is on
            if force_tg:
                raise BudgetExceededError(f"tollgate admit failed — fail-closed ({e})") from e

    def _tollgate_record(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
    ) -> None:
        consumer = (os.getenv("TOLLGATE_CONSUMER") or "gnom").strip() or "gnom"
        try:
            from tollgate.usage_ledger import record_usage

            record_usage(
                provider,
                op="chat",
                tokens_in=int(prompt_tokens or 0),
                tokens_out=int(completion_tokens or 0),
                usd=float(cost_usd or 0),
                consumer=consumer,
                meta={"model": model, "source": "gnom.llm_manager"},
            )
        except Exception:  # noqa: BLE001
            pass

    def _resolve_route(self, model: str, provider: str | None) -> tuple[str, str]:
        m = (model or self.default_model).strip()
        p = (provider or "").strip().lower()
        if p == "ollama" or m.lower().startswith("ollama/") or m.lower().startswith("ollama:"):
            bare = m.split("/", 1)[-1]
            if bare.lower().startswith("ollama:"):
                bare = bare.split(":", 1)[-1]
            if bare.lower().startswith("ollama/"):
                bare = bare.split("/", 1)[-1]
            return "ollama", bare or OLLAMA_DEFAULT
        if p in ("opencode_zen", "zen"):
            return "opencode_zen", m.removeprefix("opencode/") or "deepseek-v4-flash-free"
        if p == "openrouter" or m.startswith("openrouter/") or m.endswith(":free"):
            return "openrouter", m
        if p == "nvidia":
            return "nvidia", m
        if p in ("tollgate", "free"):
            return "tollgate", m
        if p == "deepseek":
            return "deepseek", m
        # Auto: no DeepSeek key → Ollama if available
        if not self.deepseek_key() and self.ollama_available():
            if m.startswith("deepseek"):
                return "ollama", os.getenv("OLLAMA_MODEL", OLLAMA_DEFAULT)
            return "ollama", m if m else OLLAMA_DEFAULT
        return "deepseek", m

    def _check_free_only(self, model: str, provider: str) -> None:
        if not self.free_only:
            return
        if provider == "ollama":
            return  # local always free
        bare = model.split("/")[-1]
        if model not in FREE_MODELS and bare not in FREE_MODELS:
            raise FreeOnlyError(
                f"Model '{model}' is not free and free_only is enabled. "
                "Use ollama/* or set GNOM_FREE_ONLY=0."
            )

    @staticmethod
    def _normalize_messages(
        messages: list[LLMMessage] | list[dict[str, str]],
    ) -> list[LLMMessage]:
        out: list[LLMMessage] = []
        for m in messages:
            if isinstance(m, LLMMessage):
                out.append(m)
            else:
                out.append(LLMMessage(role=m["role"], content=m["content"]))
        return out
