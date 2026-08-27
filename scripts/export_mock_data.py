"""Export the exact synthetic records used by MockProvider to readable JSON files."""

import json
from pathlib import Path

from sf_mcp_poc.domain import Entity
from sf_mcp_poc.provider import build_mock_data

OUTPUTS = {
    "employees.json": (
        Entity.PER_PERSON,
        Entity.PER_PERSONAL,
        Entity.EMP_EMPLOYMENT,
    ),
    "national_ids.json": (Entity.PER_NATIONAL_ID,),
    "jobs.json": (Entity.EMP_JOB,),
    "positions.json": (Entity.POSITION,),
    "foundation_objects.json": (
        Entity.FO_COMPANY,
        Entity.FO_BUSINESS_UNIT,
        Entity.FO_DIVISION,
        Entity.FO_DEPARTMENT,
    ),
}


def main() -> None:
    output_dir = Path(__file__).resolve().parents[1] / "test_data"
    output_dir.mkdir(exist_ok=True)
    data = build_mock_data()
    for filename, entities in OUTPUTS.items():
        payload = {entity.value: data[entity] for entity in entities}
        (output_dir / filename).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(f"Exported exact mock-provider data to {output_dir}")


if __name__ == "__main__":
    main()
