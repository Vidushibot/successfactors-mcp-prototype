from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from .config import get_settings
from .domain import ChatRequest, ChatResponse
from .runtime import get_service
from .security import IDENTITIES, AuthorizationDenied, Identity, resolve_identity

app = FastAPI(
    title="SAP SuccessFactors Multi-Agent MCP Prototype",
    description="Demonstration using synthetic SuccessFactors-style data. Read-only prototype.",
    version="0.1.0",
)

INJECTION_PATTERNS = re.compile(
    r"(?i)(ignore (?:all |your )?instructions|pretend i am|oauth token|api key|hidden (?:system )?prompt|raw (?:odata|url)|\$filter|\$select|compensation|salary|bank|national id|date of birth)"
)


def current_identity(x_prototype_user: str = Header(default="restricted_user_demo")) -> Identity:
    try:
        return resolve_identity(x_prototype_user)
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=403, detail="Request is not authorized") from exc


AuditIdentity = Annotated[Identity, Depends(current_identity)]


@app.get("/")
async def root() -> dict[str, object]:
    return {
        "application": "SAP SuccessFactors Multi-Agent MCP Prototype",
        "notice": "Demonstration using synthetic SuccessFactors-style data.",
        "read_only": True,
        "health": "/health",
        "api_documentation": "/docs",
        "streamlit_ui": "http://127.0.0.1:8501",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    get_service()
    return {"status": "ready"}


@app.get("/api/config/public")
async def public_config() -> dict[str, object]:
    settings = get_settings()
    return {
        "mode": settings.app_mode,
        "read_only": True,
        "label": "Demonstration using synthetic SuccessFactors-style data.",
    }


@app.get("/api/demo-users")
async def demo_users() -> list[dict[str, object]]:
    return [
        {
            "user_id": item.user_id,
            "role": item.role,
            "employee_scope": sorted(item.employee_scope)
            if item.employee_scope
            else "all authorized synthetic records",
            "allowed_tools": sorted(item.allowed_tools),
        }
        for item in IDENTITIES.values()
    ]


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    identity = resolve_identity(request.user_id)
    session_id = request.session_id or str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    if INJECTION_PATTERNS.search(request.message):
        return ChatResponse(
            answer="The request was rejected because it asks for prohibited data or attempts to alter the application security boundary.",
            session_id=session_id,
            mode=get_settings().app_mode,
            effective_date=request.effective_date,
            tools_used=[],
            evidence_references=[],
            evidence_records=[],
            delegation_trace=["Security Review: request rejected"],
            authorization_status="denied",
            correlation_id=correlation_id,
            warning_messages=["Security policy rejection"],
        )
    settings = get_settings()
    if settings.app_mode == "demo":
        from .demo_runtime import run_demo_chat

        try:
            demo_result = await run_demo_chat(
                request.message, identity, session_id, correlation_id, settings
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Live agent request failed safely. Correlation ID: {correlation_id}",
            ) from exc
        return ChatResponse(
            answer=demo_result.answer,
            session_id=session_id,
            mode="demo",
            effective_date=request.effective_date or datetime.now(UTC).date(),
            tools_used=demo_result.tools_used,
            evidence_references=[],
            evidence_records=[],
            delegation_trace=demo_result.trace,
            usage=demo_result.usage,
            estimated_cost_usd=demo_result.estimated_cost_usd,
            authorization_status="allowed",
            correlation_id=correlation_id,
            warning_messages=[],
        )
    if is_compound_review_request(request.message):
        return await run_compound_review(request, session_id, correlation_id)
    tool, values = route_message(request.message, request.effective_date)
    if tool is None:
        return ChatResponse(
            answer="Please include an employee identifier such as E1001 or a position identifier such as P100 and state what you want to retrieve.",
            session_id=session_id,
            mode=get_settings().app_mode,
            effective_date=request.effective_date,
            tools_used=[],
            evidence_references=[],
            evidence_records=[],
            delegation_trace=[],
            authorization_status="clarification_required",
            correlation_id=correlation_id,
            warning_messages=[],
        )
    result = await get_service().call(tool, request.user_id, session_id, correlation_id, **values)
    answer = render_answer(
        tool,
        result.records,
        result.status,
        result.source,
        request.effective_date,
        request.message,
    )
    return ChatResponse(
        answer=answer,
        session_id=session_id,
        mode=get_settings().app_mode,
        effective_date=request.effective_date or datetime.now(UTC).date(),
        tools_used=[tool],
        evidence_references=result.evidence,
        evidence_records=result.records,
        delegation_trace=delegation_for(tool),
        authorization_status="allowed" if result.status == "ok" else result.status,
        correlation_id=correlation_id,
        warning_messages=result.warnings,
    )


def route_message(message: str, effective_date: date | None) -> tuple[str | None, dict[str, Any]]:
    text = message.lower()
    employee = re.search(r"\bE\d{4,}\b", message.upper())
    position = re.search(r"\bP\d{3,}\b", message.upper())
    common = {"as_of_date": effective_date}
    if (
        "which employees" in text
        and ("overlap" in text or "overlapping" in text)
        and ("job" in text or "record" in text)
    ):
        return "validate_employee_population", {
            **common,
            "rule_ids": ["DQ_OVERLAPPING_RECORDS"],
        }
    if (
        "position" in text
        and "parent" in text
        and ("without" in text or "missing" in text or "no parent" in text)
    ):
        return "search_positions", {
            **common,
            "missing_parent_position": True,
            "limit": 20,
        }
    if "position" in text and "department" in text and ("without" in text or "missing" in text):
        return "search_positions", {
            **common,
            "missing_department": True,
            "limit": 20,
        }
    if "position" in text and ("how many" in text or "total" in text or "count" in text):
        return "search_positions", {**common, "limit": 20}
    if ("data quality" in text or "data-quality" in text or "quality issues" in text) and (
        "all employees" in text or "employees" in text and not employee
    ):
        return "validate_employee_population", {**common, "rule_ids": []}
    if (
        "which employees" in text
        and "position" in text
        and ("missing" in text or "invalid" in text)
    ):
        return "validate_employee_population", {
            **common,
            "rule_ids": ["DQ_MISSING_POSITION", "DQ_POSITION_NOT_FOUND"],
        }
    if "vacant" in text or "search position" in text or "find" in text and "position" in text:
        department = re.search(r"\bD\d{3,}\b", message.upper())
        return "search_positions", {
            **common,
            "department_code": department.group() if department else None,
            "status": "A" if "active" in text else None,
            "vacancy_indicator": "vacant" in text,
            "missing_department": None,
            "missing_parent_position": None,
            "limit": 10,
        }
    if position:
        return "get_position", {**common, "position_code": position.group()}
    if employee:
        key = employee.group()
        if "validate" in text or "quality" in text:
            return "validate_employee_data", {**common, "employee_id": key}
        if "manager" in text:
            return "get_manager_relationship", {**common, "employee_id": key}
        if "profile" in text or "name" in text:
            return "get_employee_basic_profile", {**common, "person_id_external": key}
        if "employment" in text and "job" not in text:
            return "get_employment_information", {**common, "person_id_external": key}
        if "compare" in text or "changes" in text or "history" in text:
            return "get_effective_dated_changes", {
                "entity_type": "EmpJob",
                "business_key": key,
                "start_date": date(2020, 1, 1),
                "end_date": date(2030, 12, 31),
            }
        return "get_employee_job_information", {**common, "employee_id": key}
    return None, {}


def render_answer(
    tool: str,
    records: list[dict[str, Any]],
    status: str,
    source: str,
    effective_date: date | None,
    question: str,
) -> str:
    if status == "denied":
        return "The request is not authorized or sufficient evidence is unavailable. No record existence is disclosed."
    when = effective_date or datetime.now(UTC).date()
    text = question.lower()
    prefix = f"Using {source} as of {when.isoformat()}: "
    if (
        tool == "search_positions"
        and "department" in text
        and ("without" in text or "missing" in text)
    ):
        return f"{prefix}there are **{len(records)} positions without a department**."
    if (
        tool == "search_positions"
        and "parent" in text
        and ("without" in text or "missing" in text or "no parent" in text)
    ):
        codes = ", ".join(str(row.get("code")) for row in records)
        suffix = f": **{codes}**" if codes else ""
        noun = "position" if len(records) == 1 else "positions"
        verb = "is" if len(records) == 1 else "are"
        return f"{prefix}there {verb} **{len(records)} {noun} without a parent position**{suffix}."
    if tool == "search_positions" and ("how many" in text or "total" in text or "count" in text):
        return f"{prefix}there are **{len(records)} positions** in the authorized result set."
    if not records:
        return "Insufficient authorized evidence was available to answer the question."
    first = records[0]

    if tool == "get_employee_job_information":
        employee = first.get("userId", "the employee")
        requested_fields = {
            "department": "department",
            "company": "company",
            "business unit": "businessUnit",
            "division": "division",
            "job code": "jobCode",
            "position": "position",
            "status": "employmentStatus",
        }
        for phrase, field in requested_fields.items():
            if phrase in text:
                value = first.get(field)
                if value:
                    return f"{prefix}employee {employee} is assigned to {phrase} **{value}**."
                return f"{prefix}the authorized record does not contain a value for {phrase}."
        details = ", ".join(
            f"{label}: {first.get(field)}"
            for label, field in (
                ("company", "company"),
                ("business unit", "businessUnit"),
                ("division", "division"),
                ("department", "department"),
                ("job code", "jobCode"),
                ("position", "position"),
                ("manager", "managerId"),
                ("status", "employmentStatus"),
            )
            if first.get(field)
        )
        return f"{prefix}employee {employee} has {details}."
    if tool == "get_manager_relationship":
        manager = first.get("managerId") or "not recorded"
        return f"{prefix}employee {first.get('userId')} reports to manager **{manager}**."
    if tool == "get_position":
        incumbent = first.get("incumbent") or "vacant"
        return f"{prefix}position {first.get('code')} is **{first.get('externalName')}**; incumbent: **{incumbent}**; department: **{first.get('department')}**."
    if tool == "search_positions":
        codes = ", ".join(str(row.get("code")) for row in records)
        return f"{prefix}found {len(records)} authorized position(s): **{codes}**."
    if tool == "get_employee_basic_profile":
        name = " ".join(str(first.get(part, "")) for part in ("firstName", "lastName")).strip()
        return f"{prefix}employee {first.get('personIdExternal')} is **{name}**."
    if tool == "get_employment_information":
        return f"{prefix}employee {first.get('personIdExternal')} has employment start date **{first.get('startDate')}** and end date **{first.get('endDate')}**."
    if tool == "validate_employee_data":
        errors = sum(row.get("severity") == "error" for row in records)
        warnings = sum(row.get("severity") == "warning" for row in records)
        return f"{prefix}validation found **{errors} error(s)** and **{warnings} warning(s)**. Review the evidence below for each rule."
    if tool == "validate_employee_population":
        employees = sorted({str(row.get("employeeId")) for row in records})
        if "overlap" in text:
            return f"{prefix}employees with overlapping effective-dated job records: **{', '.join(employees)}**."
        if "all employees" in text or "quality issues" in text:
            errors = sum(row.get("severity") == "error" for row in records)
            warnings = sum(row.get("severity") == "warning" for row in records)
            return f"{prefix}population validation found **{len(records)} finding(s)** affecting **{len(employees)} employee(s)**: **{errors} error(s)** and **{warnings} warning(s)**. Affected employees: **{', '.join(employees)}**."
        return f"{prefix}employees with missing or invalid positions: **{', '.join(employees)}**. Review the evidence below for the confirmed rule findings."
    if tool == "get_effective_dated_changes":
        return (
            f"{prefix}found **{len(records)} effective-dated record(s)** in the requested period."
        )
    return f"{prefix}`{tool}` returned {len(records)} authorized record(s)."


def delegation_for(tool: str) -> list[str]:
    specialist = {
        "get_employee_basic_profile": "Employee Central specialist",
        "get_employee_job_information": "Employee Central specialist",
        "get_employment_information": "Employee Central specialist",
        "get_manager_relationship": "Employee Central specialist",
        "get_effective_dated_changes": "Employee Central specialist",
        "get_position": "Position Management specialist",
        "search_positions": "Position Management specialist",
        "get_foundation_object": "Position Management specialist",
        "validate_employee_data": "Data Quality specialist",
        "validate_employee_population": "Data Quality specialist",
        "get_entity_metadata": "Security Review specialist",
    }.get(tool, "HR specialist")
    return [
        "HR Orchestrator (deterministic mock router)",
        specialist,
        tool,
        "HR Orchestrator final answer",
    ]


def is_compound_review_request(message: str) -> bool:
    text = message.lower()
    return bool(
        re.search(r"\bE\d{4,}\b", message.upper())
        and "job" in text
        and "position" in text
        and ("validate" in text or "quality" in text)
        and ("restricted" in text or "security" in text or "exposure" in text)
    )


async def run_compound_review(
    request: ChatRequest, session_id: str, correlation_id: str
) -> ChatResponse:
    employee_match = re.search(r"\bE\d{4,}\b", request.message.upper())
    if employee_match is None:
        raise HTTPException(status_code=422, detail="Employee identifier is required")
    employee_id = employee_match.group()
    service = get_service()
    job = await service.call(
        "get_employee_job_information",
        request.user_id,
        session_id,
        correlation_id,
        employee_id=employee_id,
        as_of_date=request.effective_date,
    )
    if job.status != "ok":
        return ChatResponse(
            answer="The request is not authorized or sufficient evidence is unavailable.",
            session_id=session_id,
            mode=get_settings().app_mode,
            effective_date=request.effective_date,
            tools_used=["get_employee_job_information"],
            evidence_references=job.evidence,
            evidence_records=job.records,
            delegation_trace=[
                "HR Orchestrator",
                "Employee Central specialist",
                "Authorization denial",
            ],
            authorization_status=job.status,
            correlation_id=correlation_id,
            warning_messages=job.warnings,
        )
    position_code = str(job.records[0].get("position", "")) if job.records else ""
    position = await service.call(
        "get_position",
        request.user_id,
        session_id,
        correlation_id,
        position_code=position_code,
        as_of_date=request.effective_date,
    )
    quality = await service.call(
        "validate_employee_data",
        request.user_id,
        session_id,
        correlation_id,
        employee_id=employee_id,
        as_of_date=request.effective_date,
    )
    findings = quality.records
    errors = sum(row.get("severity") == "error" for row in findings)
    warnings = sum(row.get("severity") == "warning" for row in findings)
    position_summary = (
        f"position {position_code} was found as {position.records[0].get('externalName')}"
        if position.records
        else f"assigned position {position_code} was not found"
    )
    answer = (
        f"Using {service.provider.source} as of "
        f"{(request.effective_date or datetime.now(UTC).date()).isoformat()}: "
        f"employee {employee_id} is assigned to {position_code}; {position_summary}. "
        f"Data-quality validation found {errors} error(s) and {warnings} warning(s). "
        "Security review confirmed that the returned evidence contains only approved fields."
    )
    return ChatResponse(
        answer=answer,
        session_id=session_id,
        mode=get_settings().app_mode,
        effective_date=request.effective_date or datetime.now(UTC).date(),
        tools_used=[
            "get_employee_job_information",
            "get_position",
            "validate_employee_data",
        ],
        evidence_references=job.evidence + position.evidence + quality.evidence,
        evidence_records=job.records + position.records + quality.records,
        delegation_trace=[
            "HR Orchestrator (deterministic mock plan)",
            "Employee Central specialist → get_employee_job_information",
            "Position Management specialist → get_position",
            "Data Quality specialist → validate_employee_data",
            "Security Review specialist → approved-field verification",
            "HR Orchestrator → final evidence-based answer",
        ],
        authorization_status="allowed",
        correlation_id=correlation_id,
        warning_messages=job.warnings + position.warnings + quality.warnings,
    )


@app.get("/api/audit/events")
async def audit_events(
    identity: AuditIdentity, limit: int = Query(50, ge=1, le=100)
) -> list[dict[str, object]]:
    return get_service().audit.list_for(
        None if identity.can_view_audit_all else identity.user_id, limit
    )


@app.get("/api/audit/events/{event_id}")
async def audit_event(event_id: str, identity: AuditIdentity) -> dict[str, object]:
    event = get_service().audit.get(event_id)
    if not event or (not identity.can_view_audit_all and event["user_id"] != identity.user_id):
        raise HTTPException(status_code=404, detail="Audit event not found")
    return event
