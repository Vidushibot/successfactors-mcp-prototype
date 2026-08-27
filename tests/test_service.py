import pytest

from sf_mcp_poc.audit import AuditRepository
from sf_mcp_poc.provider import MockProvider
from sf_mcp_poc.service import HRToolService


@pytest.mark.asyncio
async def test_each_tool_authorization_and_sanitization() -> None:
    service = HRToolService(MockProvider(), AuditRepository("sqlite:///:memory:"))
    result = await service.call(
        "get_employee_basic_profile", "hr_admin_demo", "s", "c", person_id_external="E1001"
    )
    assert result.records[0]["firstName"] == "Avery"
    assert "dateOfBirth" not in result.records[0]
    denied = await service.call(
        "get_employee_basic_profile", "hr_analyst_demo", "s", "c", person_id_external="E1001"
    )
    assert denied.status == "denied"


@pytest.mark.asyncio
async def test_quality_rules_find_intentional_issues() -> None:
    service = HRToolService(MockProvider(), AuditRepository("sqlite:///:memory:"))
    result = await service.call(
        "validate_employee_data", "hr_admin_demo", "s", "c", employee_id="E1004"
    )
    assert any(row["rule_id"] == "DQ_POSITION_NOT_FOUND" for row in result.records)


@pytest.mark.asyncio
async def test_search_limit_is_capped() -> None:
    service = HRToolService(MockProvider(), AuditRepository("sqlite:///:memory:"), 2)
    result = await service.call("search_positions", "hr_admin_demo", "s", "c", limit=999)
    assert len(result.records) <= 2
