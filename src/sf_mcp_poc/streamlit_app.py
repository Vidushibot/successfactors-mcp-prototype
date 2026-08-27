from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="SAP SuccessFactors Multi-Agent MCP Prototype",
    page_icon=":material/shield:",
    layout="wide",
)
st.title("SAP SuccessFactors Multi-Agent MCP Prototype")
st.warning(
    "Demonstration using synthetic SuccessFactors-style data. Read-only prototype; not an SAP SuccessFactors system."
)


def api(method: str, path: str, user: str | None = None, **kwargs: Any) -> Any:
    headers = {"X-Prototype-User": user} if user else {}
    with httpx.Client(timeout=20) as client:
        response = client.request(method, f"{API_URL}{path}", headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()


try:
    users = api("GET", "/api/demo-users")
    config = api("GET", "/api/config/public")
except httpx.HTTPError:
    st.error("The FastAPI backend is unavailable. Start it on http://127.0.0.1:8000.")
    st.stop()

user_ids = [user["user_id"] for user in users]
selected = st.sidebar.selectbox("Synthetic prototype user", user_ids)
user = next(user for user in users if user["user_id"] == selected)
st.sidebar.metric("Mode", str(config["mode"]).title())
st.sidebar.write(f"Role: {user['role']}")
st.sidebar.write(f"Authorized scope: {user['employee_scope']}")

examples = [
    "Show the current job information for employee E1001.",
    "Who is the manager of employee E1001?",
    "Show position P100 and its incumbent.",
    "Find active vacant positions in department D100.",
    "Validate employee E1001 for data-quality issues.",
    "Compare the effective-dated job records for E1001.",
    "Show employee E9999 as the restricted user.",
]
if "messages" not in st.session_state:
    st.session_state.messages = []
for saved in st.session_state.messages:
    with st.chat_message(saved["role"]):
        st.write(saved["content"])
question = None
if not st.session_state.messages:
    question = st.pills("Example questions", examples, label_visibility="collapsed")
effective = st.date_input("Effective date", value=datetime.now(UTC).date())
prompt = st.chat_input("Ask a read-only Employee Central question", submit_mode="disable")
message = prompt or question

if message:
    st.session_state.messages.append({"role": "user", "content": message})
    with st.chat_message("user"):
        st.write(message)
    with st.chat_message("assistant"):
        try:
            payload = api(
                "POST",
                "/api/chat",
                json={
                    "user_id": selected,
                    "message": message,
                    "effective_date": effective.isoformat(),
                },
            )
            if payload["authorization_status"] == "denied":
                st.error(payload["answer"])
            else:
                st.write(payload["answer"])
            st.session_state.messages.append({"role": "assistant", "content": payload["answer"]})
            cols = st.columns(3)
            cols[0].caption(f"Mode: {payload['mode']}")
            cols[1].caption(f"Effective date: {payload.get('effective_date')}")
            cols[2].caption(f"Correlation ID: {payload['correlation_id']}")
            with st.expander("Tools used"):
                tools_used = payload["tools_used"]
                st.markdown(
                    "\n".join(f"- `{tool}`" for tool in tools_used)
                    if tools_used
                    else "No tools were used."
                )
            with st.expander("Delegation trace"):
                trace = payload["delegation_trace"]
                st.markdown(
                    "\n".join(f"{index}. {step}" for index, step in enumerate(trace, 1))
                    if trace
                    else "No specialist delegation was required."
                )
                usage = payload.get("usage", {})
                if usage:
                    st.caption(
                        f"Requests: {usage.get('requests', 0)} · "
                        f"Input tokens: {usage.get('input_tokens', 0):,} · "
                        f"Output tokens: {usage.get('output_tokens', 0):,} · "
                        f"Estimated cost: ${payload.get('estimated_cost_usd', 0):.6f}"
                    )
            with st.expander("Evidence references"):
                evidence = payload["evidence_references"]
                st.markdown(
                    "\n".join(f"- `{reference}`" for reference in evidence)
                    if evidence
                    else "No evidence returned."
                )
                if payload["evidence_records"]:
                    st.caption("Sanitized authorized records")
                    for record in payload["evidence_records"]:
                        st.json(record)
            if payload["warning_messages"]:
                st.warning("; ".join(payload["warning_messages"]))
        except httpx.HTTPError as exc:
            st.error(f"Request failed safely: {type(exc).__name__}")

st.divider()
st.subheader("Audit events")
if st.button("Refresh authorized audit events"):
    try:
        events = api("GET", "/api/audit/events", user=selected)
        if events:
            for event in events:
                label = f"{event['timestamp']} · {event['tool_name']} · {event['status']}"
                with st.expander(label):
                    st.json(event)
        else:
            st.info("No authorized audit events are available.")
    except httpx.HTTPError as exc:
        st.error(f"Audit retrieval failed safely: {type(exc).__name__}")
