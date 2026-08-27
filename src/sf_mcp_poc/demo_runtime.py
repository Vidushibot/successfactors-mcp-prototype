from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .agents import AgentContext, SafeTraceHooks, build_agents, permitted_tool_filter
from .config import Settings

_budget_lock = asyncio.Lock()
_daily_usage: dict[str, int] = {}


@dataclass
class DemoResult:
    answer: str
    trace: list[str]
    tools_used: list[str]
    usage: dict[str, int]
    estimated_cost_usd: float


def estimate_cost(settings: Settings, input_tokens: int, output_tokens: int) -> float:
    total = input_tokens * settings.openai_input_cost_per_1m
    total += output_tokens * settings.openai_output_cost_per_1m
    return round(total / 1_000_000, 6)


async def run_demo_chat(
    message: str,
    identity: Any,
    session_id: str,
    correlation_id: str,
    settings: Settings,
) -> DemoResult:
    from agents import ModelSettings, RunConfig, Runner
    from agents.mcp import MCPServerStreamableHttp

    today = datetime.now(UTC).date().isoformat()
    async with _budget_lock:
        if _daily_usage.get(today, 0) >= settings.demo_daily_token_budget:
            raise RuntimeError("The configured daily demo token budget has been reached")

    context = AgentContext(identity.user_id, identity.role, session_id, correlation_id)
    server = MCPServerStreamableHttp(
        name="SuccessFactors read-only MCP",
        params={
            "url": f"http://{settings.mcp_host}:{settings.mcp_port}/mcp",
            "headers": {
                "x-mcp-internal-token": settings.mcp_internal_token,
                "x-prototype-user": context.user_id,
                "x-session-id": session_id,
                "x-correlation-id": correlation_id,
            },
        },
        cache_tools_list=True,
        tool_filter=permitted_tool_filter,
        use_structured_content=True,
    )
    model_settings = ModelSettings(
        max_tokens=settings.demo_max_output_tokens,
        include_usage=True,
        store=False,
        parallel_tool_calls=False,
    )
    async with server:
        result = await Runner.run(
            build_agents(settings.openai_model, server, model_settings),
            message,
            context=context,
            max_turns=settings.demo_max_turns,
            hooks=SafeTraceHooks(),
            run_config=RunConfig(
                workflow_name="SF HR Demo",
                group_id=session_id,
                tracing_disabled=not settings.enable_openai_tracing,
                trace_include_sensitive_data=False,
            ),
        )
    usage_obj = result.context_wrapper.usage
    usage = {
        key: int(getattr(usage_obj, key, 0))
        for key in ("requests", "input_tokens", "output_tokens", "total_tokens")
    }
    async with _budget_lock:
        _daily_usage[today] = _daily_usage.get(today, 0) + usage["total_tokens"]
    return DemoResult(
        str(result.final_output),
        context.trace,
        context.tools_used,
        usage,
        estimate_cost(settings, usage["input_tokens"], usage["output_tokens"]),
    )
