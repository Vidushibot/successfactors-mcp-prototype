from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from .domain import DENIED_FIELDS, FIELD_ALLOWLIST, Entity


class AuthorizationDenied(Exception):
    """A denial intentionally indistinguishable from a missing inaccessible record."""


@dataclass(frozen=True)
class Identity:
    user_id: str
    role: str
    allowed_tools: frozenset[str]
    employee_scope: frozenset[str] | None
    can_view_personal: bool = False
    can_view_audit_all: bool = False


ALL_TOOLS = frozenset(
    {
        "get_employee_basic_profile",
        "get_employee_job_information",
        "get_employment_information",
        "get_position",
        "search_positions",
        "get_foundation_object",
        "get_manager_relationship",
        "get_effective_dated_changes",
        "validate_employee_data",
        "validate_employee_population",
        "get_entity_metadata",
    }
)
POSITION_TOOLS = frozenset(
    {"get_position", "search_positions", "get_foundation_object", "get_entity_metadata"}
)

IDENTITIES = {
    "hr_admin_demo": Identity("hr_admin_demo", "HR Administrator", ALL_TOOLS, None, True, True),
    "hr_analyst_demo": Identity(
        "hr_analyst_demo",
        "HRIS Analyst",
        ALL_TOOLS - {"get_employee_basic_profile"},
        None,
        False,
        True,
    ),
    "position_specialist_demo": Identity(
        "position_specialist_demo", "Position Specialist", POSITION_TOOLS, None, False, False
    ),
    "restricted_user_demo": Identity(
        "restricted_user_demo",
        "Restricted User",
        frozenset(
            {
                "get_employee_job_information",
                "get_employment_information",
                "get_manager_relationship",
            }
        ),
        frozenset({"E1001", "E1002"}),
        False,
        False,
    ),
}


def resolve_identity(user_id: str) -> Identity:
    identity = IDENTITIES.get(user_id)
    if identity is None:
        raise AuthorizationDenied("Request is not authorized")
    return identity


def authorize(identity: Identity, tool: str, employee_id: str | None = None) -> None:
    if tool not in identity.allowed_tools:
        raise AuthorizationDenied("Request is not authorized or evidence is unavailable")
    if (
        employee_id
        and identity.employee_scope is not None
        and employee_id not in identity.employee_scope
    ):
        raise AuthorizationDenied("Request is not authorized or evidence is unavailable")


def sanitize(entity: Entity, record: dict[str, Any], identity: Identity) -> dict[str, Any]:
    allowed = FIELD_ALLOWLIST[entity]
    if entity == Entity.PER_PERSONAL and not identity.can_view_personal:
        allowed = frozenset({"personIdExternal", "effectiveStartDate"})
    return {
        key: value for key, value in record.items() if key in allowed and key not in DENIED_FIELDS
    }


SECRET_PATTERN = re.compile(
    r"(?i)(bearer\s+)[A-Za-z0-9._~-]+|((?:api[_-]?key|token|private[_-]?key)\s*[=:]\s*)\S+"
)


def redact(value: str) -> str:
    return SECRET_PATTERN.sub(lambda m: (m.group(1) or m.group(2) or "") + "[REDACTED]", value)


def key_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]
