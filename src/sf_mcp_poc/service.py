from __future__ import annotations

import time
import uuid
from datetime import UTC, date, datetime
from itertools import pairwise
from typing import Any

from .audit import AuditRepository, safe_input_summary
from .domain import FOUNDATION_ENTITIES, Entity, Finding, ToolResult
from .provider import SuccessFactorsProvider
from .security import AuthorizationDenied, authorize, key_fingerprint, resolve_identity, sanitize


def utc_today() -> date:
    return datetime.now(UTC).date()


class HRToolService:
    def __init__(
        self, provider: SuccessFactorsProvider, audit: AuditRepository, max_page_size: int = 20
    ) -> None:
        self.provider = provider
        self.audit = audit
        self.max_page_size = max_page_size

    async def call(
        self, tool: str, user_id: str, session_id: str, correlation_id: str, **inputs: Any
    ) -> ToolResult:
        started = time.perf_counter()
        identity = resolve_identity(user_id)
        employee_id = inputs.get("employee_id") or inputs.get("person_id_external")
        entity = ""
        try:
            authorize(identity, tool, employee_id)
            records, entity_type, warnings = await self._execute(tool, identity, inputs)
            entity = entity_type.value if entity_type else ""
            sanitized = (
                [sanitize(entity_type, row, identity) for row in records]
                if entity_type
                else records
            )
            references = [
                f"{entity or 'validation'}:{key_fingerprint(str(employee_id or inputs.get('position_code') or i))}:{i + 1}"
                for i in range(len(sanitized))
            ]
            result = ToolResult(
                source=self.provider.source,
                records=sanitized,
                evidence=references,
                warnings=warnings,
            )
            outcome, status, error = "allowed", "success", ""
        except AuthorizationDenied:
            result = ToolResult(
                status="denied",
                source=self.provider.source,
                warnings=["Request is not authorized or evidence is unavailable."],
            )
            outcome, status, error = "denied", "failure", "authorization_denial"
        except (ValueError, KeyError) as exc:
            result = ToolResult(status="invalid", source=self.provider.source, warnings=[str(exc)])
            outcome, status, error = "allowed", "failure", "validation_error"
        self.audit.add(
            correlation_id=correlation_id,
            session_id=session_id,
            user_id=user_id,
            role=identity.role,
            agent_name="deterministic-tool-service",
            tool_name=tool,
            input_summary=safe_input_summary(inputs),
            entity=entity,
            business_key_hash=key_fingerprint(
                str(employee_id or inputs.get("position_code") or "")
            ),
            authorization_outcome=outcome,
            record_count=len(result.records),
            duration_ms=int((time.perf_counter() - started) * 1000),
            data_source_mode=self.provider.source,
            status=status,
            error_category=error,
        )
        return result

    async def _execute(
        self, tool: str, identity: Any, inputs: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], Entity | None, list[str]]:
        as_of = inputs.get("as_of_date")
        if isinstance(as_of, str):
            as_of = date.fromisoformat(as_of)
        if tool == "get_employee_basic_profile":
            key = inputs["person_id_external"]
            rows = await self.provider.get(Entity.PER_PERSONAL, key, as_of)
            return rows, Entity.PER_PERSONAL, []
        if tool == "get_employee_job_information":
            rows = await self.provider.get(
                Entity.EMP_JOB, inputs["employee_id"], as_of or utc_today()
            )
            return rows, Entity.EMP_JOB, []
        if tool == "get_employment_information":
            rows = await self.provider.get(
                Entity.EMP_EMPLOYMENT, inputs["person_id_external"], as_of
            )
            return rows, Entity.EMP_EMPLOYMENT, []
        if tool == "get_position":
            rows = await self.provider.get(
                Entity.POSITION, inputs["position_code"], as_of or utc_today()
            )
            return rows, Entity.POSITION, []
        if tool == "search_positions":
            filters = {
                k: v
                for k, v in {
                    "company": inputs.get("company_code"),
                    "department": inputs.get("department_code"),
                    "effectiveStatus": inputs.get("status"),
                }.items()
                if v is not None
            }
            limit = min(max(int(inputs.get("limit", 10)), 1), self.max_page_size)
            rows = await self.provider.search(Entity.POSITION, filters, as_of or utc_today(), limit)
            vacancy = inputs.get("vacancy_indicator")
            if vacancy is not None:
                rows = [row for row in rows if (not row.get("incumbent")) is bool(vacancy)]
            if inputs.get("missing_department") is True:
                rows = [row for row in rows if not row.get("department")]
            if inputs.get("missing_parent_position") is True:
                rows = [row for row in rows if not row.get("parentPosition")]
            return rows, Entity.POSITION, []
        if tool == "get_foundation_object":
            entity = Entity(inputs["object_type"])
            if entity not in FOUNDATION_ENTITIES:
                raise ValueError("Unsupported foundation object type")
            return await self.provider.get(entity, inputs["object_code"], as_of), entity, []
        if tool == "get_manager_relationship":
            jobs = await self.provider.get(
                Entity.EMP_JOB, inputs["employee_id"], as_of or utc_today()
            )
            rows = [
                {
                    "userId": row["userId"],
                    "managerId": row.get("managerId"),
                    "startDate": row["startDate"],
                    "endDate": row["endDate"],
                }
                for row in jobs
            ]
            return rows, Entity.EMP_JOB, []
        if tool == "get_effective_dated_changes":
            entity = Entity(inputs["entity_type"])
            if entity not in {Entity.EMP_JOB, Entity.EMP_EMPLOYMENT, Entity.POSITION}:
                raise ValueError("Entity is not enabled for change history")
            rows = await self.provider.get(entity, inputs["business_key"], None)
            start_value, end_value = inputs["start_date"], inputs["end_date"]
            start = (
                start_value
                if isinstance(start_value, date)
                else date.fromisoformat(str(start_value))
            )
            end = end_value if isinstance(end_value, date) else date.fromisoformat(str(end_value))
            if start > end:
                raise ValueError("start_date must not be after end_date")
            rows = [
                row
                for row in rows
                if start
                <= date.fromisoformat(str(row.get("startDate") or row.get("effectiveStartDate")))
                <= end
            ][: self.max_page_size]
            return rows, entity, []
        if tool == "validate_employee_data":
            findings = await self.validate_employee(inputs["employee_id"], as_of)
            return [finding.model_dump() for finding in findings], None, []
        if tool == "validate_employee_population":
            jobs = await self.provider.search(
                Entity.EMP_JOB, {}, as_of or utc_today(), self.max_page_size
            )
            employee_ids = sorted({str(row["userId"]) for row in jobs if row.get("userId")})
            if identity.employee_scope is not None:
                employee_ids = [item for item in employee_ids if item in identity.employee_scope]
            requested_rules = set(inputs.get("rule_ids") or [])
            results: list[dict[str, Any]] = []
            for employee_id in employee_ids:
                findings = await self.validate_employee(employee_id, as_of)
                for finding in findings:
                    if requested_rules and finding.rule_id not in requested_rules:
                        continue
                    results.append({"employeeId": employee_id, **finding.model_dump(mode="json")})
            return results[: self.max_page_size], None, []
        if tool == "get_entity_metadata":
            entity = Entity(inputs["entity_name"])
            return [await self.provider.metadata(entity)], None, []
        raise ValueError("Unsupported tool")

    async def validate_employee(self, employee_id: str, as_of: date | None) -> list[Finding]:
        jobs = await self.provider.get(Entity.EMP_JOB, employee_id, None)
        findings: list[Finding] = []
        if not jobs:
            return [
                Finding(
                    severity="error",
                    rule_id="DQ_RECORD_MISSING",
                    message="Authorized job evidence is unavailable.",
                    evidence_references=[],
                )
            ]
        current = [row for row in jobs if _covers(row, as_of or utc_today())]
        for row in current or jobs[-1:]:
            ref = [f"EmpJob:{key_fingerprint(employee_id)}"]
            for field in ("company", "department", "jobCode", "position"):
                if not row.get(field):
                    findings.append(
                        Finding(
                            severity="error",
                            rule_id=f"DQ_MISSING_{field.upper()}",
                            message=f"Required field {field} is missing.",
                            evidence_references=ref,
                        )
                    )
            if row.get("position") and not await self.provider.get(
                Entity.POSITION, row["position"], as_of or utc_today()
            ):
                findings.append(
                    Finding(
                        severity="error",
                        rule_id="DQ_POSITION_NOT_FOUND",
                        message="Assigned position was not found.",
                        evidence_references=ref,
                    )
                )
            positions = await self.provider.get(
                Entity.POSITION, row.get("position", ""), as_of or utc_today()
            )
            if positions and positions[0].get("department") != row.get("department"):
                findings.append(
                    Finding(
                        severity="warning",
                        rule_id="DQ_POSITION_DEPARTMENT_MISMATCH",
                        message="Job and position departments differ.",
                        evidence_references=ref,
                    )
                )
            if row.get("managerId") and not await self.provider.get(
                Entity.EMP_JOB, row["managerId"], as_of or utc_today()
            ):
                findings.append(
                    Finding(
                        severity="warning",
                        rule_id="DQ_MANAGER_NOT_FOUND",
                        message="Manager job record was not found.",
                        evidence_references=ref,
                    )
                )
        ordered = sorted(jobs, key=lambda row: row["startDate"])
        for previous, following in pairwise(ordered):
            if date.fromisoformat(following["startDate"]) <= date.fromisoformat(
                previous["endDate"]
            ):
                findings.append(
                    Finding(
                        severity="error",
                        rule_id="DQ_OVERLAPPING_RECORDS",
                        message="Effective-dated job records overlap.",
                        evidence_references=[f"EmpJob:{key_fingerprint(employee_id)}"],
                    )
                )
        return findings


def _covers(row: dict[str, Any], value: date) -> bool:
    return date.fromisoformat(row["startDate"]) <= value <= date.fromisoformat(row["endDate"])


def ids() -> tuple[str, str]:
    return str(uuid.uuid4()), str(uuid.uuid4())
