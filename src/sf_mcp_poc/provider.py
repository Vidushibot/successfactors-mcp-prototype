from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

import httpx

from .domain import FIELD_ALLOWLIST, Entity


class ProviderError(Exception):
    pass


class SuccessFactorsProvider(ABC):
    source: str

    @abstractmethod
    async def get(
        self, entity: Entity, key: str, as_of: date | None = None
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def search(
        self, entity: Entity, filters: dict[str, Any], as_of: date | None, limit: int
    ) -> list[dict[str, Any]]: ...

    async def metadata(self, entity: Entity) -> dict[str, Any]:
        return {"entity": entity.value, "fields": sorted(FIELD_ALLOWLIST[entity]), "readOnly": True}


def _active(record: dict[str, Any], as_of: date) -> bool:
    start_text = record.get("startDate") or record.get("effectiveStartDate")
    end_text = record.get("endDate") or record.get("effectiveEndDate")
    start = date.fromisoformat(start_text) if start_text else date.min
    end = date.fromisoformat(end_text) if end_text else date.max
    return start <= as_of <= end


class MockProvider(SuccessFactorsProvider):
    source = "synthetic SuccessFactors-style mock data"

    def __init__(self) -> None:
        self.data = build_mock_data()

    async def get(
        self, entity: Entity, key: str, as_of: date | None = None
    ) -> list[dict[str, Any]]:
        key_field = (
            "code"
            if entity
            in {
                Entity.POSITION,
                Entity.FO_COMPANY,
                Entity.FO_BUSINESS_UNIT,
                Entity.FO_DIVISION,
                Entity.FO_DEPARTMENT,
            }
            else ("userId" if entity == Entity.EMP_JOB else "personIdExternal")
        )
        rows = [row.copy() for row in self.data[entity] if row.get(key_field) == key]
        if as_of:
            rows = [row for row in rows if _active(row, as_of)]
        return sorted(
            rows, key=lambda row: row.get("startDate") or row.get("effectiveStartDate") or ""
        )

    async def search(
        self, entity: Entity, filters: dict[str, Any], as_of: date | None, limit: int
    ) -> list[dict[str, Any]]:
        rows = [row.copy() for row in self.data[entity]]
        for key, value in filters.items():
            if value is not None:
                rows = [row for row in rows if row.get(key) == value]
        if as_of:
            rows = [row for row in rows if _active(row, as_of)]
        return rows[:limit]


class ODataQueryBuilder:
    def __init__(self, max_page_size: int = 20) -> None:
        self.max_page_size = max_page_size

    @staticmethod
    def escape_literal(value: str) -> str:
        if any(
            part in value.lower()
            for part in ("$filter", "$select", "$expand", "http://", "https://", "&$")
        ):
            raise ValueError("OData fragments and URLs are not accepted")
        return value.replace("'", "''")

    def build(
        self, entity: Entity, filters: dict[str, str], limit: int
    ) -> tuple[str, dict[str, str]]:
        top = min(max(limit, 1), self.max_page_size)
        clauses = [
            f"{name} eq '{self.escape_literal(value)}'" for name, value in sorted(filters.items())
        ]
        return entity.value, {
            "$select": ",".join(sorted(FIELD_ALLOWLIST[entity])),
            "$filter": " and ".join(clauses),
            "$top": str(top),
            "$format": "json",
        }


class ODataProvider(SuccessFactorsProvider):
    source = "configured SuccessFactors test tenant"

    def __init__(
        self,
        base_url: str,
        token_provider: TokenProvider,
        timeout: int,
        verify_tls: bool,
        max_page_size: int,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token_provider = token_provider
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.builder = ODataQueryBuilder(max_page_size)

    async def get(
        self, entity: Entity, key: str, as_of: date | None = None
    ) -> list[dict[str, Any]]:
        key_field = (
            "code"
            if entity == Entity.POSITION or entity.value.startswith("FO")
            else ("userId" if entity == Entity.EMP_JOB else "personIdExternal")
        )
        return await self.search(entity, {key_field: key}, as_of, 20)

    async def search(
        self, entity: Entity, filters: dict[str, Any], as_of: date | None, limit: int
    ) -> list[dict[str, Any]]:
        safe_filters = {key: str(value) for key, value in filters.items() if value is not None}
        path, params = self.builder.build(entity, safe_filters, limit)
        token = await self.token_provider.get_token()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=self.verify_tls) as client:
                response = await client.get(
                    f"{self.base_url}/{path}",
                    params=params,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderError("SuccessFactors request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("SuccessFactors connection failed") from exc
        payload = response.json()
        return list(payload.get("d", {}).get("results", []))[:limit]


class TokenProvider(ABC):
    @abstractmethod
    async def get_token(self) -> str: ...


class MockTokenProvider(TokenProvider):
    async def get_token(self) -> str:
        return "mock-token-never-logged"


class ConfiguredOAuthTokenProvider(TokenProvider):
    """Tenant-specific signed-assertion acquisition must be configured and validated."""

    async def get_token(self) -> str:
        raise ProviderError("OAuth flow requires tenant-specific SAP configuration")


def build_mock_data() -> dict[Entity, list[dict[str, Any]]]:
    employees = [
        ("E1001", "Avery", "Stone", "P100", "E1005", "D100", "active"),
        ("E1002", "Jordan", "Vale", "P101", "E1005", "D100", "active"),
        ("E1003", "Morgan", "Reed", "P102", "E1006", "D200", "active"),
        ("E1004", "Casey", "North", "P999", "E1006", "D200", "active"),
        ("E1005", "Riley", "Quinn", "P105", "E1009", "D100", "active"),
        ("E1006", "Taylor", "Lake", "P106", "E9998", "D300", "active"),
        ("E1007", "Cameron", "Pike", "P107", "E1009", "D999", "active"),
        ("E1008", "Drew", "Sage", "P108", "E1009", "D400", "terminated"),
        ("E1009", "Robin", "Frost", "P109", "", "D500", "active"),
        ("E1010", "Skyler", "Brook", "", "E1009", "D600", "active"),
    ]
    first_names = ("Alex", "Bailey", "Charlie", "Dakota", "Emerson", "Finley", "Gray", "Harper")
    last_names = ("Ash", "Blake", "Cove", "Dale", "Ellis", "Flynn", "Grove", "Hart")
    for i in range(10, 50):
        employee_id = f"E{1001 + i}"
        position = f"P{100 + i}"
        manager = "E1005" if i % 2 == 0 else "E1009"
        department = f"D{100 + (i % 10) * 100}"
        employees.append(
            (
                employee_id,
                first_names[i % len(first_names)],
                last_names[i % len(last_names)],
                position,
                manager,
                department,
                "active",
            )
        )
    per_person = [{"personIdExternal": e[0]} for e in employees]
    national_ids = [
        {
            "personIdExternal": e[0],
            "country": "CAN" if i % 2 == 0 else "USA",
            "cardType": "SIN" if i % 2 == 0 else "SSN",
            "nationalId": f"SYNTHETIC-DO-NOT-USE-{100000000 + i}",
            "isPrimary": True,
            "effectiveStartDate": "2020-01-01",
        }
        for i, e in enumerate(employees)
    ]
    personal = [
        {
            "personIdExternal": e[0],
            "firstName": e[1],
            "lastName": e[2],
            "effectiveStartDate": "2020-01-01",
            "dateOfBirth": "1980-01-01",
        }
        for e in employees
    ]
    employment = [
        {
            "personIdExternal": e[0],
            "userId": e[0],
            "startDate": "2020-01-01",
            "endDate": "2024-12-31" if e[6] == "terminated" else "9999-12-31",
        }
        for e in employees
    ]
    jobs = [
        {
            "userId": e[0],
            "startDate": "2024-01-01",
            "endDate": "9999-12-31",
            "company": "C100",
            "businessUnit": "BU100",
            "division": "DV100",
            "department": e[5],
            "jobCode": "J100",
            "position": e[3],
            "managerId": e[4],
            "employmentStatus": e[6],
            "salary": 999999,
        }
        for e in employees
    ]
    jobs += [
        {
            **jobs[0],
            "startDate": "2022-01-01",
            "endDate": "2023-12-31",
            "position": "P110",
            "department": "D200",
        },
        {**jobs[1], "startDate": "2023-01-01", "endDate": "2024-06-30"},
        {**jobs[1], "startDate": "2024-06-01", "endDate": "2024-12-31"},
        {**jobs[2], "startDate": "2027-01-01", "endDate": "9999-12-31", "position": "P111"},
    ]
    positions = []
    for i in range(50):
        code = f"P{100 + i}"
        incumbent = employees[i][0] if i < len(employees) and employees[i][3] == code else None
        positions.append(
            {
                "code": code,
                "externalName": f"Fictional Position {i + 1}",
                "effectiveStartDate": "2020-01-01",
                "effectiveStatus": "A",
                "company": f"C{100 + (i % 50) * 100}",
                "businessUnit": f"BU{100 + (i % 50) * 100}",
                "division": f"DV{100 + (i % 50) * 100}",
                "department": f"D{100 + (i % 50) * 100}",
                "jobCode": f"J{100 + i}",
                "parentPosition": "P109" if code != "P109" else None,
                "incumbent": incumbent,
            }
        )
    foundations: dict[Entity, list[dict[str, Any]]] = {}
    specs = {
        Entity.FO_COMPANY: [f"C{i}00" for i in range(1, 51)],
        Entity.FO_BUSINESS_UNIT: [f"BU{i}00" for i in range(1, 51)],
        Entity.FO_DIVISION: [f"DV{i}00" for i in range(1, 51)],
        Entity.FO_DEPARTMENT: [f"D{i}00" for i in range(1, 51)],
    }
    for entity, codes in specs.items():
        foundations[entity] = [
            {
                "code": code,
                "name": f"Fictional {entity.value} {code}",
                "status": "A",
                "effectiveStartDate": "2020-01-01",
                "effectiveEndDate": "9999-12-31",
            }
            for code in codes
        ]
    return {
        Entity.PER_PERSON: per_person,
        Entity.PER_PERSONAL: personal,
        Entity.PER_NATIONAL_ID: national_ids,
        Entity.EMP_EMPLOYMENT: employment,
        Entity.EMP_JOB: jobs,
        Entity.POSITION: positions,
        **foundations,
    }
