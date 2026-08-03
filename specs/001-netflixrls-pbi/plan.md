# Implementation Plan: Netflix RLS Workbook → Power BI Semantic Model

**Branch**: `001-netflixrls-pbi` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-netflixrls-pbi/spec.md` (including `## Clarifications` C-001…C-015)

## Summary

Migrate `Data/Netflix RLS/Netfix Workbook rls.twb` into a Power BI Project (PBIP) at `Output/NetflixRLS/`, comprising a TMDL semantic model and a PBIR report.

The model is an 8-table star schema (1 fact `Titles`, 4 dimensions, 2 bridges, 1 hidden security table) with 7 relationships, 19 measures, exactly 1 calculated column (`DimRating[Rating Category]`), and exactly 1 dynamic RLS role (`Country Access`). All data arrives from two CSVs through `Csv.Document(File.Contents(...))` M queries that read their file **directly** — no query references another model query, so no load cycle is possible.

The migration's primary value-add is replacing the workbook's defective Tableau user filter (which self-compares `[country]` and hardcodes `user2@maq.com`) with a correct dynamic role filtered as `Users[Username] = USERPRINCIPALNAME()` and propagated `Users → DimCountry → BridgeTitleCountry → Titles`.

**The single highest-risk implementation detail** is `securityFilteringBehavior: bothDirections` on relationships **R1** (`Users[Entitled Country]` → `DimCountry[Country]`) and **R3** (`BridgeTitleCountry[Show ID]` → `Titles[Show ID]`). `crossFilteringBehavior: bothDirections` alone does **not** carry an RLS filter across a relationship. If `securityFilteringBehavior` is omitted, the model still loads, every measure still evaluates, and **RLS silently fails open** — all 6,234 titles become visible to every viewer, breaking FR-024 and SC-006 with no error message anywhere. This is verified only by "View as role", never by a validator.

## Technical Context

**Language/Version**: TMDL (Tabular Model Definition Language), compatibility level 1567; Power Query M; DAX; PBIR JSON (`visualContainer/2.4.0`)
**Primary Dependencies**: Power BI Desktop (PBIP preview / enhanced report format enabled); Python 3.x for `validate_pbip.py`; `tmdl-validate-windows-x64.exe`
**Storage**: Two flat CSVs read from disk — `Data/Netflix RLS/netflix_titles.csv` (6,234 rows, 12 columns) and `Data/Netflix RLS/User_Access.csv` (3 rows, 2 columns). Import storage mode; no gateway, no database.
**Testing**: `plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe` (TMDL structural lint) + `python plugins\pbip\skills\pbip\scripts\validate_pbip.py Output\NetflixRLS` (cross-cutting project validation) + manual "View as role" verification in Power BI Desktop for the three entitled identities and one unmapped identity.
**Target Platform**: Power BI Desktop on Windows, opening `Output/NetflixRLS/NetflixRLS.pbip` as a thick PBIP project.
**Project Type**: Data/BI artefact generation — no application source code. Deliverable is a PBIP folder tree, not a compiled program.
**Performance Goals**: Full refresh of both CSVs completes interactively (single-digit seconds); every measure evaluates without error on the report page (SC-004).
**Constraints**:

- `definition.pbism` version `4.2`; `definition.pbir` version `4.0`; `.pbip` MUST carry `$schema` and MUST NOT declare a `dataset` artifact (§6).
- All generated files UTF-8 **without BOM** (FR-041, §6).
- `crossFilteringBehavior` accepts only `oneDirection` | `bothDirections` | `automatic`. The Power BI UI word **`single` is INVALID TMDL** and causes `DataModelLoadFailed` on open.
- `securityFilteringBehavior` accepts only `oneDirection` | `bothDirections` | `none`.
- PBIR `visualContainer/2.4.0` permits **only** `$schema`, `name`, `position`, and one of `visual` / `visualGroup` at the root — no `filters` property (FR-033).
- Zero literal user identities anywhere in the output; `@maq.com` must return zero text-search hits (SC-008).
- M expression names and table names share one namespace — an `expression X` colliding with a `table X` fails the load with `duplicate member X`.

**Scale/Scope**: 8 tables, 7 relationships, 19 measures, 1 calculated column, 1 role, 1 report page, 12 visuals covering 9 Tableau worksheets + 2 slicers + 1 header substitute.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — see [Post-Design Constitution Re-check](#post-design-constitution-re-check).*

| § | Rule | Status | Evidence / Exception |
|---|---|---|---|
| §1 | Star schema, explicit fact grain, DimDate, bridges for comma-separated fields, no snowflaking | **PASS** | Fact `Titles` @ 1 row per `Show ID`; `DimCountry`/`DimGenre`/`DimRating`/`DimDate`; `BridgeTitleCountry`/`BridgeTitleGenre` for `country` and `listed_in`; no dimension attaches to another dimension (star-schema A-7). |
| §2 | Naming conventions, no Tableau auto-identifiers | **PASS** | `Dim`-prefixed dimensions, `Bridge`-prefixed bridges; descriptive fact name `Titles` permitted by §2's business-name clause and recorded as A-010. Title Case columns. `Calculation_0182254345785358` is not migrated at all. Case-only collision resolved: `Titles[Country List]` (hidden) / `DimCountry[Country]` / `Users[Entitled Country]` (FR-011). |
| §3 | Measures over calculated columns, `DIVIDE`, `VAR`/`RETURN`, display folders, no measure inside a `CALCULATE` boolean filter | **PASS with 1 documented exception** | 19 measures, 7 display folders, `DIVIDE` on all 3 percentage measures, `VAR` in every non-trivial measure, `[Genre Rank]` captured in a `VAR` before comparison. **Exception A-014**: `DimRating[Rating Category]` is a calculated column because a grouping attribute must be a column to be sliced/grouped/placed on an axis. |
| §4 | Natural keys for single-source, single-direction default, bi-directional only when justified, one active relationship per pair, referential integrity | **PASS with 1 documented exception** | Natural keys only (C-002) — both CSVs are one Tableau federated datasource. 4 of 7 relationships single-direction. **Exception A-015**: 3 bi-directional (R1, R3, R5), each sanctioned by §4's bridge/dynamic-RLS clause. 7 relationships over 8 tables = spanning tree ⇒ exactly one path per pair, no inactive relationships, no `USERELATIONSHIP`. `DimCountry` is the union of both country sources (FR-049) so no FK dangles. |
| §5 | Absolute paths from workspace root, correct connector, promote headers, explicit types, deterministic | **PASS** | `Csv.Document(File.Contents(...))` with `QuoteStyle.Csv`; absolute paths held in two scalar M expressions; explicit `Table.TransformColumnTypes` on every column (FR-003); `DimDate` bounds computed from the data, never hardcoded (FR-006); all locale-sensitive calls pinned to `en-US`. |
| §6 | Valid thick PBIP, `pbism` 4.2 / `pbir` 4.0, `.pbip` `$schema` and no `dataset` artifact, TMDL folder layout, UTF-8 no BOM, `.platform` files | **PASS** | Enforced by the Phase 2 file manifest and re-verified in Phase 3 Gate D. |
| §7 | Run `tmdl-validate`, run `validate_pbip.py`, verify counts and key resolution | **PASS** | Phase 3 defines five gates with explicit commands and exit-code handling. |

**Gate result**: PASS. Two exceptions (A-014, A-015), both already recorded in `spec.md` under Assumptions per the constitution's Edge-Case Policy — the constitution itself is **not** modified.

## Project Structure

### Documentation (this feature)

```text
specs/001-netflixrls-pbi/
├── plan.md              # This file
├── spec.md              # Feature specification (input)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output — how to open and verify the project
├── contracts/
│   └── model-contract.md   # Phase 1 output — names the report layer MUST bind to
├── checklists/
│   └── requirements.md  # Pre-existing
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Generated artefacts (repository root)

```text
Data/Netflix RLS/                      # INPUT — read-only, files stay in place (A-012)
├── Netfix Workbook rls.twb
├── netflix_titles.csv                 # 6,234 rows
└── User_Access.csv                    # 3 rows

Output/NetflixRLS/                     # OUTPUT — the deliverable
├── NetflixRLS.pbip                    # $schema, artifacts[].report.path — NO dataset artifact
├── NetflixRLS.SemanticModel/
│   ├── .platform                      # metadata.type=SemanticModel, displayName, config.logicalId GUID
│   ├── definition.pbism               # version "4.2"
│   ├── diagramLayout.json
│   └── definition/
│       ├── database.tmdl              # compatibilityLevel
│       ├── model.tmdl                 # culture en-US, ref table × 8, annotations
│       ├── relationships.tmdl         # 7 relationships (R1–R7)
│       ├── expressions.tmdl           # TitlesSourcePath, UserAccessSourcePath (scalar text)
│       ├── roles/
│       │   └── CountryAccess.tmdl     # role 'Country Access' — the ONLY role
│       └── tables/
│           ├── Titles.tmdl            # fact: 12 columns + 19 measures
│           ├── DimCountry.tmdl
│           ├── DimGenre.tmdl
│           ├── DimRating.tmdl         # + Rating Category calculated column
│           ├── DimDate.tmdl           # + Calendar hierarchy, dataCategory Time
│           ├── BridgeTitleCountry.tmdl
│           ├── BridgeTitleGenre.tmdl
│           └── Users.tmdl             # hidden table, all columns hidden
└── NetflixRLS.Report/
    ├── .platform                      # metadata.type=Report
    ├── definition.pbir                # version "4.0", datasetReference.byPath → ../NetflixRLS.SemanticModel
    ├── StaticResources/
    │   └── SharedResources/BaseThemes/  # dark theme (black bg, #ff0000 accent, 10pt)
    └── definition/
        ├── report.json                # $schema + themeCollection
        └── pages/
            ├── pages.json             # pageOrder, activePageName
            └── Netflix/
                ├── page.json          # name matches ^[\w-]+$ — "Netflix", no spaces
                └── visuals/<visualId>/visual.json   # one folder per visual
```

**Structure Decision**: PBIR **enhanced report format** (one folder per page, one folder per visual) rather than a single monolithic `report.json`. Rationale: it is the format the workspace validators and skills target (`plugins/pbip/skills/pbir-format/SKILL.md`), and it keeps each visual independently validatable. The known MAX_PATH hazard of this format does not apply here — `Output\NetflixRLS\NetflixRLS.Report\definition\pages\Netflix\visuals\<id>\visual.json` stays well under 260 characters with the short project and page names chosen above. Visual folder IDs MUST be kept to ≤20 characters to preserve that margin.

## Phase 0: Research

**Output**: [research.md](./research.md) — resolves every open technical question before any file is written. Six research areas:

1. **`Csv.Document` reading pattern.** `QuoteStyle.Csv` is mandatory — `country`, `cast` and `listed_in` contain commas inside quoted fields, and the default `QuoteStyle.None` shreds those rows. `Encoding = 65001`. Two scalar M expressions (`TitlesSourcePath`, `UserAccessSourcePath`) hold the absolute paths; neither name collides with a table name.
2. **Comma-split → expand → trim → dedupe** for `BridgeTitleCountry`, `BridgeTitleGenre`, `DimCountry`, `DimGenre`. Fixed step order: drop null/empty **before** splitting → `Text.Split(_, ",")` → `Table.ExpandListColumn` → `Text.Trim` → drop values that trimmed to empty → `Table.Distinct`. Trimming after expansion (not before) is what makes `"United States, India"` yield `India`, not `" India"`.
3. **`date_added` en-US parsing.** `try Date.FromText([date_added], [Format = "MMMM d, yyyy", Culture = "en-US"]) otherwise null`. A bare `Table.TransformColumnTypes(..., type date)` is machine-locale dependent and fails or transposes day/month on non-US machines. The `try … otherwise null` wrapper is what lets the 11 blanks survive as null instead of erroring the refresh (FR-005).
4. **TMDL syntax and enum constraints.** Tab indentation (one tab per level, DAX bodies two levels deeper than their declaration); `///` immediately precedes a declaration with no blank line; quote only names with spaces/special chars/leading digits. **`crossFilteringBehavior: single` is invalid** — emit `oneDirection`. `securityFilteringBehavior` is a separate property and defaults to `oneDirection`.
5. **Roles TMDL shape.** `role 'Country Access'` → `modelPermission: read` → `tablePermission Users = [Username] = USERPRINCIPALNAME()`. Exactly one `tablePermission`; no `member` entries (members are assigned in the Service, not the project file).
6. **`DimDate` generation.** Bounds computed via `List.Min`/`List.Max` over the parsed non-null dates, expanded with `Date.StartOfYear`/`Date.EndOfYear`; `Date.MonthName` and `Date.DayOfWeekName` pinned to `"en-US"` so month and weekday labels are machine-independent.

## Phase 1: Design & Contracts

**Prerequisite**: `research.md` complete.

**Outputs**: [data-model.md](./data-model.md), [contracts/model-contract.md](./contracts/model-contract.md), [quickstart.md](./quickstart.md).

### 1.1 Star schema validation

Confirmed from `.specify/memory/NetflixRLS/star-schema-output.md`:

- **8 nodes, 7 edges, connected, acyclic ⇒ spanning tree.** Exactly one path exists between any pair of tables, so Power BI's ambiguity detector has nothing to resolve. No relationship needs deactivating; no `USERELATIONSHIP` appears anywhere.
- **R2 and R4 stay `oneDirection`.** Making `BridgeTitleCountry → DimCountry` bi-directional would let a fact-side filter travel back into `Users` and, combined with R1's bi-directional security filtering, create a filter loop through the secured chain. Accepted consequence (A-3 in the star-schema doc): a `Titles[Type]` slicer does not shrink the country list on the map; unmatched countries render blank instead of disappearing. This is the correct trade-off.
- **Referential integrity**: `DimCountry` = distinct union of split catalogue countries **and** entitlement countries (FR-049), so no bridge or entitlement value dangles. `DimGenre` and `DimRating` are derived from the very columns they key. `DimDate` spans whole calendar years around the observed range.

### 1.2 DAX column-reference audit

Every column referenced by the 19 measures and 1 calculated column in `.specify/memory/NetflixRLS/dax-measures-output.md` must exist in `data-model.md`. The full audit is reproduced in `contracts/model-contract.md`. Two findings carried forward:

- **`Titles[Rating]` discrepancy** — the DAX document's own "Model context" table omits `Rating` from the `Titles` column list, yet `Selected Title Rating` evaluates `SELECTEDVALUE ( Titles[Rating] )`. The star schema **does** provide `Titles[Rating]` as a hidden FK. **`pbip-generator` must not drop it.** Hidden ≠ unavailable to DAX.
- **`Show ID` type consistency** — Int64 on `Titles`, `BridgeTitleCountry` **and** `BridgeTitleGenre`. A type mismatch on any one of the three makes R3 or R5 fail to bind.

Result: **missing columns — none.**

### 1.3 RLS chain design (the critical section)

| # | From (many) | To (one) | Cardinality | `crossFilteringBehavior` | `securityFilteringBehavior` |
|---|---|---|---|---|---|
| R1 | `Users[Entitled Country]` | `DimCountry[Country]` | many → one | **`bothDirections`** | **`bothDirections`** ⚠ |
| R2 | `BridgeTitleCountry[Country]` | `DimCountry[Country]` | many → one | `oneDirection` | `oneDirection` |
| R3 | `BridgeTitleCountry[Show ID]` | `Titles[Show ID]` | many → one | **`bothDirections`** | **`bothDirections`** ⚠ |
| R4 | `BridgeTitleGenre[Genre]` | `DimGenre[Genre]` | many → one | `oneDirection` | `oneDirection` |
| R5 | `BridgeTitleGenre[Show ID]` | `Titles[Show ID]` | many → one | `bothDirections` | `oneDirection` |
| R6 | `Titles[Date Added]` | `DimDate[Date]` | many → one | `oneDirection` | `oneDirection` |
| R7 | `Titles[Rating]` | `DimRating[Rating]` | many → one | `oneDirection` | `oneDirection` |

Propagation path: `Users` —R1→ `DimCountry` —R2→ `BridgeTitleCountry` —R3→ `Titles`, then outward via R5/R6/R7. Because `Titles` is secured by propagation rather than a direct role filter, **every measure is secured automatically** (FR-024).

> ⚠ **Fail-open warning.** `crossFilteringBehavior: bothDirections` does **not** make an RLS filter traverse a relationship. `securityFilteringBehavior: bothDirections` on **R1 and R3** is what carries the entitlement. Omit it and the model loads cleanly, every validator passes, every measure evaluates — and every viewer sees all 6,234 titles. No tool in Phase 3 detects this; only Gate C ("View as role") does.

Role definition (exactly one role, exactly one table filter):

| Role | Kind | Table | Filter |
|---|---|---|---|
| `Country Access` | Dynamic | `Users` | `[Username] = USERPRINCIPALNAME()` |

DAX `=` is case-insensitive, satisfying FR-029 without `LOWER()`. No literal identity is emitted anywhere (FR-023, C-015, SC-008).

**Design consequences to accept, not fix:**

- 476 blank-country titles produce no `BridgeTitleCountry` row ⇒ invisible to every secured viewer (C-014, A-002). Unfiltered `Distinct Titles` still returns 6,234 (SC-005); per-user totals will not sum to 6,234.
- An unmapped identity empties `Users` → `DimCountry` → bridge → `Titles`; every measure returns `BLANK()` and visuals render empty rather than erroring (FR-027).
- No `% of Titles by Country` measure is created — it would need `ALLSELECTED(DimCountry[Country])`, which sits directly on the security chain.

### 1.4 Agent context update

The `<!-- SPECKIT START -->` block in `.github/copilot-instructions.md` already points at `specs/001-netflixrls-pbi/plan.md`. No change required.

## Phase 2: Implementation

Semantic model first, complete and validated; report second. Files are generated in dependency order so each is validatable as soon as it exists.

### 2.1 Project scaffold

1. `Output/NetflixRLS/NetflixRLS.pbip` — `$schema` present, `artifacts[].report.path = "NetflixRLS.Report"`, **no `dataset` artifact** (§6).
2. `NetflixRLS.SemanticModel/.platform` and `NetflixRLS.Report/.platform` — correct `metadata.type`, `metadata.displayName`, fresh GUID `config.logicalId` each.
3. `NetflixRLS.SemanticModel/definition.pbism` — version **`"4.2"`**.

### 2.2 Semantic model TMDL

Generated in this order (each step depends only on prior steps):

| Order | File | Contents |
|---|---|---|
| 1 | `definition/database.tmdl` | `compatibilityLevel: 1567` |
| 2 | `definition/expressions.tmdl` | `TitlesSourcePath`, `UserAccessSourcePath` — scalar text, absolute paths under `Data/Netflix RLS/`. Names verified not to collide with any table name. |
| 3 | `definition/tables/Titles.tmdl` | 12 columns (`Show ID` Int64 hidden `isKey`; `Country List` hidden; `Rating` hidden **but retained**; `Genres` visible; `Date Added` parsed date) + **all 19 measures** with `///` description, `formatString` and `displayFolder` (text measures carry no `formatString`) + M partition. |
| 4 | `definition/tables/DimCountry.tmdl` | `Country` — `isKey`, Country/Region data category. Union partition reading **both** CSVs directly. |
| 5 | `definition/tables/DimGenre.tmdl` | `Genre` — `isKey`. Split/trim/dedupe partition. |
| 6 | `definition/tables/DimRating.tmdl` | `Rating` — `isKey`; `Rating Category` — **calculated column** (`SWITCH(TRUE(), …)`), the model's only one. |
| 7 | `definition/tables/DimDate.tmdl` | 12 columns, sort-by pairs (`Quarter`→`Quarter Number`, `Month`→`Month Number`, `Year Month`→`Year Month Number`, `Day of Week`→`Day of Week Number`), `Calendar` hierarchy (Year→Quarter→Month→Date), `dataCategory: Time`, `isKey` on `Date`. |
| 8 | `definition/tables/BridgeTitleCountry.tmdl` | `Show ID` Int64, `Country` string — both hidden, table hidden. |
| 9 | `definition/tables/BridgeTitleGenre.tmdl` | `Show ID` Int64, `Genre` string — both hidden, table hidden. |
| 10 | `definition/tables/Users.tmdl` | `Username`, `Entitled Country` — table hidden **and** every column hidden (FR-052). |
| 11 | `definition/relationships.tmdl` | R1–R7 exactly as in §1.3. **`oneDirection` never written as `single`.** `securityFilteringBehavior: bothDirections` explicitly present on R1 and R3. |
| 12 | `definition/roles/CountryAccess.tmdl` | `role 'Country Access'`, `modelPermission: read`, one `tablePermission Users = [Username] = USERPRINCIPALNAME()`. |
| 13 | `definition/model.tmdl` | `culture: en-US`, `ref table` × 8, `sourceQueryCulture`, discourage-implicit-measures annotation. |
| 14 | `diagramLayout.json` | Fact centre, dimensions around it, `Users` visually separated. |

TMDL authoring rules applied throughout (`plugins/pbip/skills/tmdl/SKILL.md`): one tab per nesting level; DAX bodies two levels deeper than their declaration; `///` immediately above the declaration with no intervening blank line; quote only names containing spaces or special characters (`'Show ID'`, `'Rating Category'`, `'% of Titles'`, `'Distinct Titles (Top 10 Genres)'`); every column gets an explicit `dataType`, `summarizeBy` and `lineageTag`.

### 2.3 Report layer (PBIR) — **only after §2.2 validates**

1. `NetflixRLS.Report/definition.pbir` — version **`"4.0"`**, `datasetReference.byPath.path = "../NetflixRLS.SemanticModel"`.
2. `definition/report.json` — `$schema` + `themeCollection` pointing at the dark base theme.
3. `StaticResources/SharedResources/BaseThemes/` — black `#000000` background, `#ff0000` accent, `#aa0000` marks, light text, 10pt base (FR-036).
4. `definition/pages/pages.json` + `pages/Netflix/page.json` — page name `Netflix` matches `^[\w-]+$`; canvas sized to reflect the source 1700 × 800 arrangement.
5. `pages/Netflix/visuals/<id>/visual.json` — 12 visuals mapping the 9 Tableau worksheets plus 2 slicers plus the image substitute:

| Tableau worksheet / zone | Power BI visual | Binding |
|---|---|---|
| Country wise distribution | Filled map | `DimCountry[Country]` (Country/Region) + `Distinct Titles` |
| Ratings | Column chart | `DimRating[Rating]` + `Distinct Titles` |
| Top 10 Genre | Horizontal bar chart | `DimGenre[Genre]` + `Distinct Titles (Top 10 Genres)` |
| Movies and TV Shows distribution | Donut | `Titles[Type]` + `Distinct Titles`, `% of Titles` |
| Total Movies and TV Shows by Years | Stacked area | `DimDate[Year]` + `Titles Added`, legend `Titles[Type]` |
| Description / Duration / Genre / Rating cards | 4 cards | `Selected Title Description` / `… Duration` / `… Genres` / `… Rating` |
| `type` filter zone 18 | Slicer | `Titles[Type]` — **unfiltered**, no saved `"TV Show"` state (A-006) |
| `title` filter zone 19 | Slicer | `Titles[Title]` — unfiltered |
| `netflix.png` zone 23 | Styled text box | Occupies the same layout region (A-007) |

**PBIR hard rules** (`plugins/pbip/skills/pbir-format/SKILL.md`): a `visual.json` root permits **only** `$schema`, `name`, `position`, and one of `visual` / `visualGroup`. **No `filters`, no `filterConfig`, no other root property** — Power BI Desktop rejects them outright. This is precisely why the Top-10 genre restriction lives in `Distinct Titles (Top 10 Genres)` rather than a visual filter (FR-033, C-011). `visualContainerObjects.title` allows only `show` and `text`. Colours use `{"solid":{"color":{"expr":{"Literal":{"Value":"'#RRGGBB'"}}}}}`; booleans use `{"expr":{"Literal":{"Value":"true"}}}`. Map cross-filtering to the rest of the page is Power BI's default behaviour — no explicit configuration is needed for FR-035.

### 2.4 Ordering constraint (MANDATORY)

> **Report visuals are generated only AFTER the semantic model passes Gates A and B in Phase 3, and every visual MUST bind to the exact TMDL table, column and measure names emitted in §2.2.**

Rationale and enforcement:

- A PBIR binding is a plain string (`"Entity": "DimCountry"`, `"Property": "Country"`, `nativeQueryRef`). Nothing in the report layer validates it against the model. A typo, a case difference, or a name that was renamed during model generation produces a visual that renders blank or errors **only when opened in Power BI Desktop** — no validator catches it.
- Therefore the model's names must be **frozen** before a single `visual.json` is written. `contracts/model-contract.md` is that frozen list; after Gate A passes it is reconciled against the actual TMDL files, not just the design documents.
- Bindings to watch, because their names differ from the obvious Tableau equivalent: `Titles[Genres]` (not `Listed In`), `Titles[Country List]` (hidden — the map must bind `DimCountry[Country]` instead), `DimDate[Year]` (not `Titles[Release Year]`), and `Distinct Titles (Top 10 Genres)` (not `Distinct Titles`) on the genre bar chart.
- If any model name changes after report generation, the affected `visual.json` files **must** be regenerated — a partial edit will silently desynchronise the report from the model.

## Phase 3: Validation

Five gates, run in order. **A gate failure blocks the next phase.**

### Gate A — TMDL structural syntax

```powershell
& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\NetflixRLS\NetflixRLS.SemanticModel\definition"
```

Checks indentation, property ordering, name quoting, object nesting, and referential integrity. **Zero errors required.** Watch specifically for: `crossFilteringBehavior` enum values, a `///` followed by a blank line, DAX body indentation, and an `expression` name colliding with a `table` name.

### Gate B — PBIP project structure

```powershell
python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\NetflixRLS"
```

Checks the `.pbip` root, `.platform` files, `definition.pbir` `byPath` target existence, page-name regex, orphan pages, theme resolution. Exit codes: `0` clean, `1` warnings, `2` errors, `3` usage. **Exit code 2 must be resolved before proceeding.**

### Gate C — Row-level security (manual, cannot be automated)

In Power BI Desktop → **Modeling → View as → Other user**:

| Identity under test | Expected result |
|---|---|
| Identity mapped to India | Only India titles; `Distinct Titles` non-zero and far below 6,234 |
| Identity mapped to United States | Only US titles |
| Identity mapped to United Kingdom | Only UK titles |
| An identity absent from `Users` | Empty visuals, `BLANK()` measures, **no error** (FR-027) |
| No role applied | `Distinct Titles` = 6,234 (SC-005) |

> **If any secured identity returns 6,234, `securityFilteringBehavior: bothDirections` is missing from R1 or R3.** That is the failure signature — the model loads fine and every other gate passes.

Also verify: a title listing four countries is visible to all four entitled viewers and counted as **1** each (SC-007); titles with no country are invisible to every secured viewer (FR-026).

### Gate D — Entry-point files, encoding, and identity leakage

1. Every `.json` / `.pbir` / `.pbip` / `.pbism` parses and carries `$schema`:

   ```powershell
   Get-ChildItem "Output\NetflixRLS" -Recurse -Include "*.json","*.pbir","*.pbip","*.pbism" | ForEach-Object { try { Get-Content $_.FullName -Raw | ConvertFrom-Json | Out-Null } catch { Write-Error "Invalid JSON: $($_.FullName)" } }
   ```

2. `definition.pbism` version `4.2`; `definition.pbir` version `4.0`; `.pbip` has `$schema` and no `dataset` artifact.
3. **No BOM** on any generated file (FR-041).
4. **Zero identity leakage** (SC-008) — must return nothing:

   ```powershell
   Select-String -Path "Output\NetflixRLS" -Pattern "@maq.com" -Recurse
   ```

5. Object counts match the design: 8 tables, 7 relationships, 19 measures, 1 calculated column, 1 role, 12 visuals on 1 page.

### Gate E — Report layer (after §2.3)

Re-run Gates A, B and D across the whole project, then confirm in Power BI Desktop: all 12 visuals render, both slicers filter the four detail cards, map selection cross-filters the page, the genre chart shows exactly 10 bars descending, and the year area chart shows no blank category.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| §3 — calculated column `DimRating[Rating Category]` (A-014) | A grouping attribute must be a column to be sliced, grouped, and placed on a chart axis. | A measure cannot be placed on an axis or used as a slicer field, so the Kids/Teens/Adults/Unrated grouping would be unusable. |
| §4 — 3 bi-directional relationships R1, R3, R5 (A-015) | R1 carries the dynamic role's filter from `Users` up to `DimCountry`; R3 and R5 let each bridge filter the fact. All three are the bridge/dynamic-RLS cases §4 explicitly sanctions. | Single-direction throughout leaves the RLS filter stranded on `Users` (every viewer sees everything) and leaves `DimCountry`/`DimGenre` unable to filter `Titles` at all. |
| Two bridge tables instead of a substring-matching security expression (A-003) | `country` is a comma-separated multi-value string across 555 distinct raw values; a bridge resolves the many-to-many exactly. | Substring matching performs poorly at scale, supports only one country per user, and produces false positives on overlapping country names. |
| `securityFilteringBehavior` set explicitly rather than left to default | The default is `oneDirection`, which silently fails RLS open. | Relying on the default is the single most likely way this migration ships broken with every validator green. |

## Post-Design Constitution Re-check

Re-evaluated after Phase 1: **PASS, unchanged.** The design introduces no new deviations. The two exceptions (A-014 calculated column, A-015 bi-directional relationships) were both anticipated by the pre-Phase-0 gate, remain documented in `spec.md`, and the constitution has not been modified.

## Progress Tracking

- [x] Phase 0 — Research complete (`research.md`)
- [x] Phase 1 — Design & contracts complete (`data-model.md`, `contracts/model-contract.md`, `quickstart.md`)
- [x] Constitution Check — initial: PASS
- [x] Constitution Check — post-design: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented
- [ ] Phase 2 — Task generation (`/speckit.tasks` — not this command)
- [ ] Phase 2 — Implementation
- [ ] Phase 3 — Validation Gates A–E
