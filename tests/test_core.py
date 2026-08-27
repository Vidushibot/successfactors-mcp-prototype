from datetime import date

import pytest

from sf_mcp_poc.domain import DENIED_FIELDS, FIELD_ALLOWLIST, FOUNDATION_ENTITIES, Entity
from sf_mcp_poc.provider import MockProvider, ODataQueryBuilder, build_mock_data
from sf_mcp_poc.security import AuthorizationDenied, authorize, redact, resolve_identity, sanitize


def test_entities_have_allowlists() -> None:
    assert set(FIELD_ALLOWLIST) == set(Entity)
    assert DENIED_FIELDS.isdisjoint(FIELD_ALLOWLIST[Entity.PER_PERSONAL])


def test_sanitizer_drops_unknown_and_denied() -> None:
    output = sanitize(
        Entity.PER_PERSONAL,
        {"firstName": "A", "salary": 10, "evil": "x"},
        resolve_identity("hr_admin_demo"),
    )
    assert output == {"firstName": "A"}


def test_expanded_mock_data_and_national_id_portlet_are_safe() -> None:
    data = build_mock_data()
    assert len(data[Entity.PER_PERSON]) == 50
    assert len(data[Entity.PER_PERSONAL]) == 50
    assert len(data[Entity.PER_NATIONAL_ID]) == 50
    assert len(data[Entity.EMP_EMPLOYMENT]) == 50
    assert len(data[Entity.EMP_JOB]) >= 50
    assert len(data[Entity.POSITION]) == 50
    assert all(len(data[entity]) == 50 for entity in FOUNDATION_ENTITIES)
    source = data[Entity.PER_NATIONAL_ID][0]
    sanitized = sanitize(Entity.PER_NATIONAL_ID, source, resolve_identity("hr_admin_demo"))
    assert "nationalId" in source
    assert "nationalId" not in sanitized
    assert sanitized["cardType"] in {"SIN", "SSN"}


def test_restricted_population_denied_without_existence() -> None:
    with pytest.raises(AuthorizationDenied, match="not authorized or evidence"):
        authorize(resolve_identity("restricted_user_demo"), "get_employee_job_information", "E9999")


@pytest.mark.parametrize(
    "value",
    ["x&$select=salary", "$filter=salary gt 0", "https://evil.test", "x&$expand=compensation"],
)
def test_odata_injection_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        ODataQueryBuilder().build(Entity.EMP_JOB, {"userId": value}, 20)


def test_odata_quote_escaped_and_limit_capped() -> None:
    _, params = ODataQueryBuilder(20).build(Entity.EMP_JOB, {"userId": "E'1001"}, 999)
    assert "E''1001" in params["$filter"]
    assert params["$top"] == "20"


def test_secret_redaction() -> None:
    value = redact("Authorization Bearer abc.secret token=hidden api_key=alsohidden")
    assert "abc.secret" not in value and "hidden" not in value and "alsohidden" not in value


@pytest.mark.asyncio
async def test_mock_provider_effective_date() -> None:
    rows = await MockProvider().get(Entity.EMP_JOB, "E1001", date(2024, 1, 1))
    assert len(rows) == 1
    assert rows[0]["userId"] == "E1001"
