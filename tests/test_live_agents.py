import os

import httpx
import pytest


@pytest.mark.live
def test_live_delegation_and_usage() -> None:
    if os.getenv("RUN_LIVE_AGENT_TESTS", "false").lower() != "true":
        pytest.skip("Set RUN_LIVE_AGENT_TESTS=true to incur one controlled live request")
    response = httpx.post(
        os.getenv("LIVE_API_URL", "http://127.0.0.1:8000") + "/api/chat",
        json={
            "user_id": "hr_analyst_demo",
            "message": "Ask the Position Management specialist how many active positions exist.",
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    assert payload["mode"] == "demo"
    assert payload["usage"]["total_tokens"] > 0
    assert any("Position Management Agent" in event for event in payload["delegation_trace"])
    assert payload["tools_used"]
