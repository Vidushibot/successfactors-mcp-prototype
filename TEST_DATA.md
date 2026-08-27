# Synthetic test data

All records are fictional and generated for this demonstration. They are SuccessFactors-style records, not exports from an SAP system.

The exact records used by `MockProvider` are exported to `test_data/`:

- `employees.json`: PerPerson, PerPersonal, and EmpEmployment
- `jobs.json`: EmpJob, including effective-dated changes
- `positions.json`: Position records and vacancies
- `foundation_objects.json`: companies, business units, divisions, and departments
- `national_ids.json`: synthetic PerNationalId portlet records; identifiers remain prohibited from agent responses

## Coverage

- 50 employees: E1001–E1050
- 50 positions: P100–P149
- 50 companies, business units, divisions and departments in each collection
- 50 synthetic PerNationalId portlet records
- Multiple managers and two or more vacancies
- Historical, overlapping, terminated, and future-dated job records

## Intentional data-quality scenarios

| Identifier | Scenario |
|---|---|
| E1001 | Valid current employee plus historical job change |
| E1002 | Overlapping effective-dated job records |
| E1003 | Future-dated job change |
| E1004 | Assigned position P999 does not exist |
| E1006 | Manager E9998 does not exist |
| E1007 | Department D999 is outside the foundation-object data and mismatches its position |
| E1008 | Terminated employee scenario |
| E1010 | Missing position |
| P110, P111 | Vacant-position scenarios |

Some source records deliberately contain prohibited fields such as `salary`, `nationalId`, and `dateOfBirth`. National ID values use an obvious `SYNTHETIC-DO-NOT-USE-...` format and exist solely to test the PerNationalId portlet and prove that sanitization removes the identifier. They must never appear in MCP or chat responses. Only non-sensitive portlet metadata such as country, card type and primary status is allow-listed, and no National ID retrieval MCP tool is exposed.

## Regenerating the export

After activating the project environment:

```powershell
python .\scripts\export_mock_data.py
```

The provider implementation remains the source of truth, so this command ensures the exported files match the records used by the application.
