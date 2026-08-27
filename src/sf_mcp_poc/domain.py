from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Entity(StrEnum):
    PER_PERSON = "PerPerson"
    PER_PERSONAL = "PerPersonal"
    PER_NATIONAL_ID = "PerNationalId"
    EMP_EMPLOYMENT = "EmpEmployment"
    EMP_JOB = "EmpJob"
    POSITION = "Position"
    FO_COMPANY = "FOCompany"
    FO_BUSINESS_UNIT = "FOBusinessUnit"
    FO_DIVISION = "FODivision"
    FO_DEPARTMENT = "FODepartment"


FOUNDATION_ENTITIES = {
    Entity.FO_COMPANY,
    Entity.FO_BUSINESS_UNIT,
    Entity.FO_DIVISION,
    Entity.FO_DEPARTMENT,
}

FIELD_ALLOWLIST: dict[Entity, frozenset[str]] = {
    Entity.PER_PERSON: frozenset({"personIdExternal"}),
    Entity.PER_PERSONAL: frozenset(
        {"personIdExternal", "firstName", "lastName", "effectiveStartDate"}
    ),
    Entity.PER_NATIONAL_ID: frozenset(
        {"personIdExternal", "country", "cardType", "isPrimary", "effectiveStartDate"}
    ),
    Entity.EMP_EMPLOYMENT: frozenset({"personIdExternal", "userId", "startDate", "endDate"}),
    Entity.EMP_JOB: frozenset(
        {
            "userId",
            "startDate",
            "endDate",
            "company",
            "businessUnit",
            "division",
            "department",
            "jobCode",
            "position",
            "managerId",
            "employmentStatus",
        }
    ),
    Entity.POSITION: frozenset(
        {
            "code",
            "externalName",
            "effectiveStartDate",
            "effectiveStatus",
            "company",
            "businessUnit",
            "division",
            "department",
            "jobCode",
            "parentPosition",
            "incumbent",
        }
    ),
    **{
        entity: frozenset({"code", "name", "status", "effectiveStartDate", "effectiveEndDate"})
        for entity in FOUNDATION_ENTITIES
    },
}

DENIED_FIELDS = frozenset(
    {
        "compensation",
        "salary",
        "bankInformation",
        "nationalId",
        "governmentId",
        "medicalData",
        "disabilityInformation",
        "emergencyContacts",
        "dependents",
        "homeAddress",
        "personalEmail",
        "personalPhone",
        "dateOfBirth",
        "gender",
        "maritalStatus",
    }
)


class Evidence(StrictModel):
    reference: str
    entity: Entity
    record: dict[str, Any]


class ToolResult(StrictModel):
    status: str = "ok"
    source: str
    records: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Finding(StrictModel):
    severity: str
    rule_id: str
    message: str
    evidence_references: list[str]


class ChatRequest(StrictModel):
    user_id: str
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    effective_date: date | None = None


class ChatResponse(StrictModel):
    answer: str
    session_id: str
    mode: str
    effective_date: date | None = None
    tools_used: list[str]
    evidence_references: list[str]
    evidence_records: list[dict[str, Any]] = Field(default_factory=list)
    delegation_trace: list[str] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    estimated_cost_usd: float | None = None
    authorization_status: str
    correlation_id: str
    warning_messages: list[str]
