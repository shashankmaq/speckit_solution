# Quickstart — Open and Verify the NetflixRLS Project

**Feature**: `001-netflixrls-pbi` | **Plan**: [plan.md](./plan.md)

## Prerequisites

- Power BI Desktop with **PBIP** and the **enhanced report format (PBIR)** preview options enabled.
- Python 3.x on `PATH` (for `validate_pbip.py`).
- The source CSVs still present at `Data/Netflix RLS/` — the model reads them by absolute path and will not refresh if they move (A-012).

## 1. Validate before opening

Run from the workspace root, in order. Stop and fix on any failure.

```powershell
& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\NetflixRLS\NetflixRLS.SemanticModel\definition"
python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\NetflixRLS"
```

`validate_pbip.py` exit codes: `0` clean · `1` warnings · `2` errors (**must fix**) · `3` usage error.

## 2. Open

Open `Output\NetflixRLS\NetflixRLS.pbip` in Power BI Desktop and refresh.

Expected: both tables load with no errors and no failed transformation step (SC-001, SC-002).

## 3. Verify the model

| Check | Expected | Requirement |
|---|---|---|
| Table count | 8 | FR-007 |
| Relationship count | 7, all active, none ambiguous | FR-015, SC-003 |
| Measure count | 18 | — |
| Calculated columns | exactly 1 — `DimRating[Rating Category]` | FR-051 |
| Roles | exactly 1 — `Country Access` | FR-022 |
| `Distinct Titles`, no filters | **6,234** | SC-005 |
| Split by `Titles[Type]` | 2 categories summing to 6,234 | US1 AS-3 |
| Split by `DimRating[Rating]` | 15 categories | US1 AS-4 |
| `DimDate` | marked as date table, years sort chronologically | FR-010, US4 |
| Blank added-dates | 11 rows blank, not dropped, not defaulted | FR-005 |

## 4. Verify row-level security — **the critical check**

**Modeling → View as → Other user**, entering each identity from `Data/Netflix RLS/User_Access.csv`.

| Identity | Expected |
|---|---|
| The India-mapped identity | Only India titles; count well below 6,234 |
| The United States-mapped identity | Only US titles |
| The United Kingdom-mapped identity | Only UK titles |
| Any identity **not** in the file | All visuals empty, no error |
| No role applied | 6,234 |

> ### If a secured identity returns 6,234, RLS has failed open.
> The cause is a missing `securityFilteringBehavior: bothDirections` on relationship **R1** (`Users[Entitled Country]` → `DimCountry[Country]`) or **R3** (`BridgeTitleCountry[Show ID]` → `Titles[Show ID]`).
>
> Bi-directional *cross*-filtering alone does **not** carry an RLS filter across a relationship. The model loads cleanly, every measure evaluates, and both validators pass — this check is the only thing that catches it.

Also confirm:
- A title listing four countries (e.g. `"United States, India, South Korea, China"`) is visible to each of those four entitled viewers and counts as **1** for each (SC-007).
- Titles with no recorded country are invisible to **every** secured viewer (FR-026). Per-user totals will not sum to 6,234 — that is expected (A-002).

## 5. Verify the report page

| Check | Expected | Requirement |
|---|---|---|
| Visual count | 12 (9 worksheet equivalents + 2 slicers + header) | SC-009 |
| Type slicer | filters the four detail cards; **not** pre-set to "TV Show" | FR-032, A-006 |
| Title slicer | filters the four detail cards | FR-032 |
| Map selection | cross-filters every other visual | FR-035 |
| Top 10 Genre | exactly 10 bars, descending by distinct title count | FR-033 |
| Titles by year | no blank category on the axis | FR-034 |
| Theme | black background, red accent, light text, 10pt base | FR-036 |
| Header region | styled text substitute where `netflix.png` was | FR-037 |

## 6. Final checks

```powershell
# Must return nothing — zero literal identities anywhere (SC-008)
Select-String -Path "Output\NetflixRLS" -Pattern "@maq.com" -Recurse

# Every JSON-family file must parse
Get-ChildItem "Output\NetflixRLS" -Recurse -Include "*.json","*.pbir","*.pbip","*.pbism" | ForEach-Object { try { Get-Content $_.FullName -Raw | ConvertFrom-Json | Out-Null } catch { Write-Error "Invalid JSON: $($_.FullName)" } }
```

Also confirm `definition.pbism` version `4.2`, `definition.pbir` version `4.0`, `.pbip` carries `$schema` and declares **no** `dataset` artifact, and all files are UTF-8 without BOM.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `DataModelLoadFailed` on open | `crossFilteringBehavior: single` in `relationships.tmdl` | Only `oneDirection` / `bothDirections` / `automatic` are valid TMDL |
| Every viewer sees 6,234 under a role | Missing `securityFilteringBehavior: bothDirections` on R1 or R3 | Add it to both |
| Refresh fails on `date_added` | Bare type change instead of the explicit en-US parse | Use `try Date.FromText(…, [Format="MMMM d, yyyy", Culture="en-US"]) otherwise null` |
| Columns shifted on multi-country rows | `QuoteStyle` not set to `QuoteStyle.Csv` | Embedded commas inside quotes need `QuoteStyle.Csv` |
| `duplicate member <name>` | An M expression name collides with a table name | Rename the expression (they share one namespace) |
| A visual renders blank | Binding does not match the emitted TMDL name | Reconcile against `contracts/model-contract.md` |
| `Property has not been defined…` on a visual | A `filters` (or other) property at the `visual.json` root | Only `$schema`, `name`, `position`, `visual`/`visualGroup` are allowed |
| "Load was cancelled" during refresh | A query references another model query | Every table must read its CSV directly |
