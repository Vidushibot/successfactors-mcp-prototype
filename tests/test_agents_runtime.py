from types import SimpleNamespace

import pytest

from sf_mcp_poc.agents import SPECIALIST_TOOLS, permitted_tool_filter
from sf_mcp_poc.config import Settings
from sf_mcp_poc.demo_runtime import estimate_cost
from sf_mcp_poc.mcp_server import mcp


@pytest.mark.asyncio
async def test_mcp_identity_is_not_model_callable() -> None:
    for tool in await mcp.list_tools():
        fields = tool.inputSchema.get("properties", {})
        assert "prototype_user_id" not in fields
        assert "session_id" not in fields
        assert "correlation_id" not in fields
        assert "mcp_internal_token" not in fields


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_name", SPECIALIST_TOOLS)
async def test_specialists_receive_only_permitted_tools(agent_name: str) -> None:
    context = SimpleNamespace(agent=SimpleNamespace(name=agent_name))
    for candidate in {name for names in SPECIALIST_TOOLS.values() for name in names}:
        allowed = await permitted_tool_filter(context, SimpleNamespace(name=candidate))
        assert allowed is (candidate in SPECIALIST_TOOLS[agent_name])


def test_configurable_cost_estimate() -> None:
    settings = Settings(
        openai_input_cost_per_1m=1.0,
        openai_output_cost_per_1m=4.0,
    )
    assert estimate_cost(settings, 1_000, 500) == 0.003
