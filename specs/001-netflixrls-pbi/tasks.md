# Tasks: Netflix RLS Workbook → Power BI Semantic Model

**Input**: Design documents from `specs/001-netflixrls-pbi/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md) (incl. C-001…C-015), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/model-contract.md](./contracts/model-contract.md), [quickstart.md](./quickstart.md)
**Governing rulebook**: `.specify/memory/constitution.md` §1–§7 — **read-only, never modified by any task below**

**Tests**: No automated test suite exists for this feature (it is a BI artefact, not application code). "Tests" here are the five validation gates defined in `plan.md` Phase 3 — they appear as explicit validation tasks inside each phase.

**Organization**: Tasks are grouped by user story so each story can be implemented and verified independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: `[US1]`…`[US4]` — maps to the user stories in `spec.md`
- Every task names the exact file it creates/edits and its acceptance check

## Path Conventions

- **Workspace root**: `C:\Users\AmanRajMAQSoftware\Downloads\Agentic Solution\speckit_solution`
- **Input (read-only)**: `Data\Netflix RLS\`
- **Output (deliverable)**: `Output\NetflixRLS\`
- **Validators**: `plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe`, `plugins\pbip\skills\pbip\scripts\validate_pbip.py`
- All commands are PowerShell, run from the workspace root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the rulebook, the design artefacts, the source data, and the validator tooling are all present and correct **before** a single output file is written.

- [ ] T001 [P] Verify the universal rulebook `.specify\memory\constitution.md` exists and is readable, and record its §1–§7 headings in the implementation log. **Acceptance**: file exists; §1–§7 present; **the file is NOT modified by this or any later task** (any rule that cannot be applied is recorded as an exception in `spec.md`, per FR-042).
- [ ] T002 [P] Verify every design artefact exists and is non-empty: `specs\001-netflixrls-pbi\spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts\model-contract.md`, plus `.specify\memory\NetflixRLS\star-schema-output.md`, `.specify\memory\NetflixRLS\dax-measures-output.md`, `.specify\memory\NetflixRLS\tableau-analysis-output.md`. **Acceptance**: 9 of 9 files present; `spec.md` contains clarifications C-001…C-015.
- [ ] T003 [P] Resolve and record the two absolute source paths: `C:\Users\AmanRajMAQSoftware\Downloads\Agentic Solution\speckit_solution\Data\Netflix RLS\netflix_titles.csv` and `C:\Users\AmanRajMAQSoftware\Downloads\Agentic Solution\speckit_solution\Data\Netflix RLS\User_Access.csv`. **Acceptance**: both `Test-Path` true; `netflix_titles.csv` has 6,234 data rows + 1 header; `User_Access.csv` has 3 data rows + 1 header. The authoring path recorded in the TWB is **not** used (FR-001, FR-002, §5).
- [ ] T004 [P] Verify validator tooling: `plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe` exists and is executable, and `python --version` resolves. **Acceptance**: the exe runs with no arguments and prints usage; Python 3.x reported.
- [ ] T005 [P] Reconcile the measure count before generation begins: `contracts\model-contract.md` and `.specify\memory\NetflixRLS\dax-measures-output.md` both enumerate **19** measures, while `plan.md` and `data-model.md` prose say "18". **Acceptance**: the authoritative count is fixed at **19** (the contract's name list is the interface); record the prose discrepancy in the implementation log as a documentation-only defect — do **not** drop a measure to reach 18.
- [ ] T006 Create the output folder tree `Output\NetflixRLS\NetflixRLS.SemanticModel\definition\tables`, `...\definition\roles`, and `Output\NetflixRLS\NetflixRLS.Report\definition\pages`, `...\StaticResources\SharedResources\BaseThemes`. **Acceptance**: all six directories exist and are empty; the deepest planned path `Output\NetflixRLS\NetflixRLS.Report\definition\pages\Netflix\visuals\<id>\visual.json` measures under 260 characters with a 20-character visual id.

**Checkpoint**: Rulebook, design, data and tooling verified. Generation may begin.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The PBIP scaffold and the shared M expressions. Every table partition in every user story reads a path from `expressions.tmdl`, so nothing below can start until this phase completes.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T007 Create `Output\NetflixRLS\NetflixRLS.pbip` with `$schema`, `version`, and `artifacts[0].report.path = "NetflixRLS.Report"`. **Acceptance**: parses as JSON; `$schema` present; **no `dataset` artifact declared** (§6, plan §2.1).
- [ ] T008 [P] Create `Output\NetflixRLS\NetflixRLS.SemanticModel\.platform` with `metadata.type = "SemanticModel"`, `metadata.displayName = "NetflixRLS"`, and a freshly generated GUID in `config.logicalId`. **Acceptance**: parses as JSON; `logicalId` is a valid GUID and differs from T009's.
- [ ] T009 [P] Create `Output\NetflixRLS\NetflixRLS.Report\.platform` with `metadata.type = "Report"`, `metadata.displayName = "NetflixRLS"`, and its own fresh GUID `config.logicalId`. **Acceptance**: parses as JSON; GUID distinct from T008's.
- [ ] T010 [P] Create `Output\NetflixRLS\NetflixRLS.SemanticModel\definition.pbism` with version **`"4.2"`**. **Acceptance**: parses as JSON; `version` is exactly the string `4.2` (§6, plan Constraints).
- [ ] T011 [P] Create `Output\NetflixRLS\NetflixRLS.SemanticModel\definition\database.tmdl` declaring `compatibilityLevel: 1567`. **Acceptance**: single `database` object; tab-indented; parses under `tmdl-validate`.
- [ ] T012 Create `Output\NetflixRLS\NetflixRLS.SemanticModel\definition\expressions.tmdl` with two scalar text expressions `TitlesSourcePath` and `UserAccessSourcePath` holding the absolute paths resolved in T003 (R-01). **Acceptance**: both expressions are scalar `type text`, not tables; **neither name matches any of the 8 table names** (`Titles`, `DimCountry`, `DimDate`, `DimGenre`, `DimRating`, `BridgeTitleCountry`, `BridgeTitleGenre`, `Users`) — a collision fails the load with `duplicate member`.

**Checkpoint**: Scaffold ready — user story implementation can begin.

---

## Phase 3: User Story 1 - Analyst opens the migrated model and sees the same numbers (Priority: P1) 🎯 MVP

**Goal**: An 8-table star schema that loads both CSVs without error and returns the same unfiltered numbers the Tableau workbook produced with its user filter removed — 6,234 distinct titles, 2 types, 15 ratings.

**Independent Test**: Open `Output\NetflixRLS\NetflixRLS.pbip` in Power BI Desktop, refresh, and confirm `Distinct Titles` = 6,234, the type breakdown sums to 6,234 across exactly two categories, and the rating breakdown shows 15 categories.

### Implementation for User Story 1

- [ ] T013 [US1] Create `Output\NetflixRLS\NetflixRLS.SemanticModel\definition\tables\Titles.tmdl` — the M partition only: `Csv.Document(File.Contents(TitlesSourcePath), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv])` → `Table.PromoteHeaders(..., [PromoteAllScalars=true])` → `date_added` parsed with `try Date.FromText(_, [Format="MMMM d, yyyy", Culture="en-US"]) otherwise null` → explicit `Table.TransformColumnTypes` on **every** column (R-01, R-03, FR-003, FR-004). **Acceptance**: `QuoteStyle.Csv` present (without it the quoted multi-country rows shred silently); no column left to implicit typing; the partition references `TitlesSourcePath` and **no other model query** (no load cycle).
- [ ] T014 [US1] In `...\definition\tables\Titles.tmdl`, declare the 12 columns exactly as `data-model.md` specifies: `Show ID` (Int64, hidden, `isKey`, `summarizeBy: none`), `Type`, `Title`, `Director`, `Cast`, `Country List` (**hidden**, FR-048), `Date Added` (nullable date), `Release Year` (Int64, `summarizeBy: none`), `Rating` (**hidden but RETAINED** — `Selected Title Rating` references it), `Duration`, `Genres` (**visible**, FR-048), `Description`. **Acceptance**: 12 columns; each has `dataType`, `summarizeBy`, `lineageTag`; `Titles[Rating]` present; names match `contracts\model-contract.md` character for character.
- [ ] T015 [US1] Add the `Title Counts` and `Time` measures to `...\definition\tables\Titles.tmdl`, transcribed **verbatim** from `.specify\memory\NetflixRLS\dax-measures-output.md`: `Distinct Titles`, `Movie Titles`, `TV Show Titles`, `Titles Added`. **Acceptance**: 4 measures; each has a `///` description immediately above its declaration with no blank line, a `formatString` of `#,##0`, and `displayFolder`; DAX bodies indented two levels deeper than the declaration; `Titles Added` excludes blank added-dates via `KEEPFILTERS(NOT ISBLANK(Titles[Date Added]))` (FR-034).
- [ ] T016 [US1] Add the `Catalogue Coverage` and `Release Year` measures to `...\definition\tables\Titles.tmdl`: `Distinct Countries`, `Distinct Genres`, `Distinct Directors` (keep the `-- REVIEW:` comment on the un-split director list), `Average Release Year`, `Earliest Release Year`, `Latest Release Year`. **Acceptance**: 6 measures with correct `formatString` (`#,##0`, `#,##0`, `#,##0`, `0.0`, `0`, `0`); `Distinct Countries` counts `BridgeTitleCountry[Country]`, `Distinct Genres` counts `BridgeTitleGenre[Genre]`.
- [ ] T017 [US1] Add the `Distribution` measures to `...\definition\tables\Titles.tmdl`: `% of Titles`, `% of Titles by Rating`, `% of Titles by Genre`. **Acceptance**: 3 measures, `formatString` `0.0%`; all use `DIVIDE` (never `/`) with a `VAR`-captured numerator and denominator (FR-018, FR-020); `ALLSELECTED` is **column-scoped** to `Titles[Type]` / `DimRating[Rating]` / `DimGenre[Genre]` only; **no `% of Titles by Country` measure is created** (it would sit on the security chain).
- [ ] T018 [US1] Add the `Ranking` measures to `...\definition\tables\Titles.tmdl`: `Genre Rank` (`RANKX` over `ALLSELECTED(DimGenre[Genre])` by `Distinct Titles` descending) and `Distinct Titles (Top 10 Genres)`. **Acceptance**: 2 measures; `Genre Rank` is captured in a `VAR` before any comparison (no measure reference inside a `CALCULATE` boolean filter, §3/FR-020); `Distinct Titles (Top 10 Genres)` returns a value only for ranks 1–10 (FR-050) — the Top-10 restriction lives here, never in report JSON.
- [ ] T019 [US1] Add the `Selected Title` measures to `...\definition\tables\Titles.tmdl`: `Selected Title Description`, `Selected Title Duration`, `Selected Title Genres`, `Selected Title Rating`. **Acceptance**: 4 measures using `SELECTEDVALUE`, **no `formatString`** (they return text); `Selected Title Rating` references the hidden `Titles[Rating]` column and resolves.
- [ ] T020 [P] [US1] Create `...\definition\tables\DimCountry.tmdl` — one column `Country` (String, `isKey`, `dataCategory: Country/Region` per FR-047), partition reading **both** CSVs directly and `Table.Combine`-ing the split catalogue countries with the trimmed entitlement countries before `Table.Distinct` (FR-049, R-02). **Acceptance**: split order is drop-blanks → `Text.Split(_, ",")` → `Table.ExpandListColumn` → `Text.Trim` → drop empties → `Table.Distinct`; trimming happens **after** the expand; ~100–130 rows; no query references another model query; no sub-national geographic role carried over (C-007).
- [ ] T021 [P] [US1] Create `...\definition\tables\DimGenre.tmdl` — one column `Genre` (String, `isKey`), same split/trim/dedupe order over `listed_in` (FR-045, R-02). **Acceptance**: ~42 distinct rows; partition reads `netflix_titles.csv` directly via `TitlesSourcePath`.
- [ ] T022 [P] [US1] Create `...\definition\tables\DimRating.tmdl` — `Rating` (String, `isKey`) plus the calculated column `Rating Category` transcribed verbatim from the DAX document's `SWITCH(TRUE(), …)` grouping into Kids / Teens / Adults / Unrated. **Acceptance**: 15 rating rows; `Rating Category` is the model's **only** calculated column (FR-046, FR-051, exception A-014); name quoted as `'Rating Category'`.
- [ ] T023 [P] [US1] Create `...\definition\tables\DimDate.tmdl` — the generated calendar and its 12 columns, with bounds **computed** via `Date.StartOfYear(List.Min(...))` / `Date.EndOfYear(List.Max(...))` over the parsed non-null added-dates, and `Date.MonthName` / `Date.DayOfWeekName` pinned to `"en-US"` (R-06, FR-006, FR-010). **Acceptance**: no hardcoded date bounds anywhere; 12 columns declared with explicit types; `Date` carries `isKey`; sort-helper columns (`Quarter Number`, `Month Number`, `Year Month Number`, `Day of Week Number`) hidden. *(Sort wiring, hierarchy and date-table marking are US4.)*
- [ ] T024 [P] [US1] Create `...\definition\tables\BridgeTitleCountry.tmdl` — `Show ID` (**Int64**) and `Country` (String), **both columns hidden and the table hidden** (FR-013), built with the R-02 step order and `Table.Distinct` on both columns (FR-009). **Acceptance**: `Show ID` is Int64 — identical to `Titles[Show ID]`, or R3 fails to bind; rows with a blank source `country` produce **zero** bridge rows (this is the load-bearing mechanism behind C-014/FR-026, not an optimisation).
- [ ] T025 [P] [US1] Create `...\definition\tables\BridgeTitleGenre.tmdl` — `Show ID` (**Int64**) and `Genre` (String), table and both columns hidden, same split/dedupe logic (FR-045). **Acceptance**: `Show ID` Int64 matching `Titles[Show ID]`; `Table.Distinct` on both columns.
- [ ] T026 [P] [US1] Create `...\definition\tables\Users.tmdl` — `Username` and `Entitled Country` (renamed from the source `Country` to kill the case-only collision, FR-011), **table hidden AND every column hidden** (FR-052), partition reading `UserAccessSourcePath` directly. **Acceptance**: 3 rows; `isHidden` on the table and on both columns; **no literal identity value appears anywhere in the file** — only the file path and column definitions (FR-023, SC-008).
- [ ] T027 [US1] Create `...\definition\relationships.tmdl` with all seven relationships R1–R7 exactly as tabulated in `data-model.md`, setting `fromCardinality`/`toCardinality`/`crossFilteringBehavior` and `isActive: true` on each. **Acceptance**: 7 relationships; every endpoint column exists with matching data type (FR-015); `crossFilteringBehavior` is `bothDirections` on R1/R3/R5 and `oneDirection` on R2/R4/R6/R7; **the token `single` appears nowhere** — it is the Power BI *UI* word and is invalid TMDL that causes `DataModelLoadFailed`. *(`securityFilteringBehavior` is set in US2 — T036.)*
- [ ] T028 [US1] Create `...\definition\model.tmdl` with `culture: en-US`, `sourceQueryCulture: en-US`, `ref table` entries for all **8** tables, and the discourage-implicit-measures annotation. **Acceptance**: exactly 8 `ref table` lines matching the 8 filenames under `definition\tables\`; no table referenced that does not exist and no table file left unreferenced.
- [ ] T029 [P] [US1] Create `Output\NetflixRLS\NetflixRLS.SemanticModel\diagramLayout.json` placing `Titles` centrally with the dimensions around it and `Users` visually separated. **Acceptance**: parses as JSON; every node name matches a table in T028.

### Model validation for User Story 1 (Gates A, B and the model half of Gate D)

- [ ] T030 [US1] Run Gate A — `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\NetflixRLS\NetflixRLS.SemanticModel\definition"`. **Acceptance**: **zero errors**. Watch specifically for `crossFilteringBehavior` enum values, a `///` followed by a blank line, DAX body indentation, and an `expression` name colliding with a `table` name. Fix and re-run until clean — a failure blocks every later task.
- [ ] T031 [US1] Run Gate B — `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\NetflixRLS"`. **Acceptance**: exit code `0` or `1`; **exit code `2` (errors) must be resolved before proceeding**. At this stage report-layer warnings about the missing `.Report\definition` are expected and acceptable.
- [ ] T032 [P] [US1] Verify the entry-point files: `NetflixRLS.pbip` carries `$schema` and declares **no `dataset` artifact`**; `definition.pbism` version is exactly `4.2`. **Acceptance**: `Get-Content <file> -Raw | ConvertFrom-Json` succeeds on both; the two assertions hold (§6).
- [ ] T033 [P] [US1] Verify **UTF-8 without BOM** on every file written so far under `Output\NetflixRLS\` (FR-041, §6). **Acceptance**: no file begins with the bytes `EF BB BF`; re-write any offender with a no-BOM encoder.
- [ ] T034 [P] [US1] Assert the invalid enum token is absent — `Select-String -Path "Output\NetflixRLS\NetflixRLS.SemanticModel\definition\relationships.tmdl" -Pattern "single"`. **Acceptance**: **zero matches**. `crossFilteringBehavior: single` loads-fails the whole model with `InvalidValueFormat`; `oneDirection` is the only correct token for single-direction filtering.
- [ ] T035 [US1] Object-count check against the design, then open the project in Power BI Desktop and refresh. **Acceptance**: 8 tables, 7 relationships, **19 measures** (per T005), 1 calculated column; both CSVs load with no error and no failed step (SC-001, SC-002); `Distinct Titles` with no filters = **6,234** (SC-005); the type breakdown shows exactly 2 categories summing to 6,234; the rating breakdown shows 15 categories; filtering to one genre returns that genre's title count.

**Checkpoint**: A correct, loading, unsecured star schema. This is the MVP — User Story 1 is fully testable here.

---

## Phase 4: User Story 2 - Each user sees only the countries they are entitled to (Priority: P1)

**Goal**: Exactly one dynamic role, `Country Access`, filtering only `Users`, propagating `Users → DimCountry → BridgeTitleCountry → Titles`, with **zero** literal identities anywhere in the output.

**Independent Test**: In Power BI Desktop use **Modeling → View as → Other user** with each of the three entitled identities and one unmapped identity, and confirm the visible title set changes accordingly.

**Depends on**: Phase 3 complete and Gates A + B green (T030, T031).

### Implementation for User Story 2

- [ ] T036 [US2] Edit `Output\NetflixRLS\NetflixRLS.SemanticModel\definition\relationships.tmdl` to add `securityFilteringBehavior: bothDirections` to **R1** (`Users[Entitled Country]` → `DimCountry[Country]`) and **R3** (`BridgeTitleCountry[Show ID]` → `Titles[Show ID]`), and `securityFilteringBehavior: oneDirection` explicitly on R2, R4, R5, R6, R7. **Acceptance**: `securityFilteringBehavior` appears on all 7 relationships with `bothDirections` on exactly R1 and R3. ⚠ **This is the single highest-risk line in the migration**: `crossFilteringBehavior: bothDirections` alone does **not** carry an RLS filter across a relationship. Omit `securityFilteringBehavior` and the model loads, every measure evaluates, every validator stays green — and **RLS fails open**, showing all 6,234 titles to every viewer with no error anywhere.
- [ ] T037 [US2] Create `Output\NetflixRLS\NetflixRLS.SemanticModel\definition\roles\CountryAccess.tmdl` containing exactly one `role 'Country Access'`, `modelPermission: read`, and one `tablePermission Users = [Username] = USERPRINCIPALNAME()` (R-05, C-012, FR-022). **Acceptance**: exactly one role and exactly one `tablePermission`; **no `member` entries** (membership is assigned in the Service, and a member would leak a literal identity); `USERPRINCIPALNAME()` — not `USERNAME()`; no `LOWER()` wrapper (DAX `=` is already case-insensitive, FR-029); the role name is quoted, the filename is not.
- [ ] T038 [US2] Edit `...\definition\model.tmdl` to add `ref role 'Country Access'`. **Acceptance**: exactly one `ref role` line; it resolves to `definition\roles\CountryAccess.tmdl`; no second role exists anywhere in the model (FR-022).

### Validation for User Story 2

- [ ] T039 [US2] **Explicitly verify the fail-open guard** — `Select-String -Path "Output\NetflixRLS\NetflixRLS.SemanticModel\definition\relationships.tmdl" -Pattern "securityFilteringBehavior: bothDirections"`. **Acceptance**: exactly **2** matches, and manual inspection confirms they sit on R1 and R3 — not on any other relationship. No validator in any gate detects this omission; this text assertion plus Gate C (T043) are the only defences.
- [ ] T040 [P] [US2] Assert zero identity leakage — `Select-String -Path "Output\NetflixRLS" -Pattern "@maq.com" -Recurse`. **Acceptance**: **zero matches** across the entire output tree (SC-008, FR-023, C-015). Also confirm the Tableau `RLS` calculated field and the identifier `Calculation_0182254345785358` appear nowhere (FR-028, FR-012).
- [ ] T041 [P] [US2] Confirm `Users` is unusable as an analytical dimension — inspect `...\definition\tables\Users.tmdl`. **Acceptance**: `isHidden` on the table and on both `Username` and `Entitled Country` (FR-052); no measure in `Titles.tmdl` references either column.
- [ ] T042 [US2] Re-run Gate A and Gate B after the role and relationship edits (same commands as T030, T031). **Acceptance**: zero TMDL errors; `validate_pbip.py` exit code ≤ 1.
- [ ] T043 [US2] Run **Gate C — "View as role"** in Power BI Desktop (Modeling → View as → Other user), which cannot be automated. **Acceptance**: the India-mapped identity sees only India titles; the United-States-mapped identity sees only US titles; the United-Kingdom-mapped identity sees only UK titles; each `Distinct Titles` is non-zero and far below 6,234. ⚠ **If any secured identity returns 6,234, `securityFilteringBehavior: bothDirections` is missing from R1 or R3** — that is the exact failure signature, with every other gate still passing.
- [ ] T044 [US2] Gate C, negative case — apply the role for an identity absent from `User_Access.csv`. **Acceptance**: every visual renders empty, measures return `BLANK()`, and **no error** is raised (FR-027); `DIVIDE` returns blank rather than infinity (FR-018).
- [ ] T045 [US2] Gate C, many-to-many case — pick a title listing four countries (e.g. "United States, India, South Korea, China") and view as an identity entitled to each. **Acceptance**: the title is visible to every one of those viewers and contributes exactly **1** to each viewer's `Distinct Titles` (SC-007, FR-025); separately confirm that titles with no recorded country are invisible to every secured viewer while the unsecured total stays 6,234 (FR-026, C-014, A-002).

**Checkpoint**: The model is correct **and** correctly secured. The report layer may now be generated.

---

## Phase 5: User Story 3 - The dashboard experience is reproduced on one report page (Priority: P2)

**Goal**: One PBIR page named `Netflix` carrying 12 visuals that cover all 9 Tableau worksheets plus 2 slicers and the image substitute, on the source dark theme.

**Independent Test**: Open the report page and confirm every Tableau worksheet has a counterpart visual, both slicers filter the four detail cards, and selecting a country on the map cross-filters the page.

**⚠️ ORDERING CONSTRAINT (plan §2.4, MANDATORY)**: no `visual.json` may be written until Gates A and B pass and `contracts\model-contract.md` has been reconciled against the **emitted TMDL files** (T046). A PBIR binding is a plain string that nothing validates against the model — a typo or a case difference produces a blank or erroring visual that surfaces only when the project is opened in Power BI Desktop.

### Implementation for User Story 3

- [ ] T046 [US3] Reconcile `specs\001-netflixrls-pbi\contracts\model-contract.md` against the **actual** table, column and measure names emitted in `Output\NetflixRLS\NetflixRLS.SemanticModel\definition\`, not against the design documents. **Acceptance**: every one of the 8 table names, every bindable column, and all 19 measure names match character for character; any mismatch is fixed in the TMDL **before** any visual is written. Names are frozen from this point — a later model rename requires regenerating every affected `visual.json`.
- [ ] T047 [US3] Create `Output\NetflixRLS\NetflixRLS.Report\definition.pbir` with version **`"4.0"`** and `datasetReference.byPath.path = "../NetflixRLS.SemanticModel"`. **Acceptance**: parses as JSON; `$schema` and `version` present; the `byPath` target directory exists (Gate B checks this).
- [ ] T048 [P] [US3] Create the dark base theme under `Output\NetflixRLS\NetflixRLS.Report\StaticResources\SharedResources\BaseThemes\` — black `#000000` background, `#ff0000` accent, `#aa0000` marks, light text, 10pt base font (FR-036). **Acceptance**: parses as JSON; theme name matches the `themeCollection` reference in T049.
- [ ] T049 [US3] Create `Output\NetflixRLS\NetflixRLS.Report\definition\report.json` with `$schema` and `themeCollection` pointing at the T048 theme. **Acceptance**: parses as JSON; both required fields present; Gate B resolves the theme resource with no warning.
- [ ] T050 [US3] Create `...\definition\pages\pages.json` with `pageOrder` and `activePageName` set to `Netflix`. **Acceptance**: parses as JSON; the single referenced page folder exists (no orphan pages).
- [ ] T051 [US3] Create `...\definition\pages\Netflix\page.json` with `$schema`, `name: "Netflix"`, `displayName`, `displayOption`, and a canvas reflecting the source 1700 × 800 dashboard arrangement (FR-030). **Acceptance**: `name` matches `^[\w-]+$` — no spaces, no dots; canvas dimensions recorded.
- [ ] T052 [P] [US3] Create the country map visual at `...\pages\Netflix\visuals\<id>\visual.json` — filled map, category `DimCountry[Country]`, value `Distinct Titles`, configured for country-level geography (FR-038). **Acceptance**: bound to `DimCountry[Country]` — **never** the hidden `Titles[Country List]`; visual folder id ≤20 characters; root contains only `$schema`, `name`, `position`, `visual`.
- [ ] T053 [P] [US3] Create the Ratings column chart at `...\pages\Netflix\visuals\<id>\visual.json` — axis `DimRating[Rating]`, value `Distinct Titles`. **Acceptance**: bound to `DimRating[Rating]`, **not** the hidden `Titles[Rating]` FK.
- [ ] T054 [P] [US3] Create the Top 10 Genre horizontal bar chart at `...\pages\Netflix\visuals\<id>\visual.json` — axis `DimGenre[Genre]`, value **`Distinct Titles (Top 10 Genres)`**. **Acceptance**: the ranking measure is used (not `Distinct Titles`); **no `filters` and no `filterConfig` property at the visual root** — the `visualContainer/2.4.0` schema rejects them outright, which is exactly why the Top-10 restriction lives in DAX (FR-033, C-011).
- [ ] T055 [P] [US3] Create the type-distribution donut at `...\pages\Netflix\visuals\<id>\visual.json` — legend `Titles[Type]`, values `Distinct Titles` and `% of Titles`. **Acceptance**: both measure references carry the `Titles` entity, `queryRef` `Titles.<name>` and `nativeQueryRef` `<name>`.
- [ ] T056 [P] [US3] Create the titles-added stacked area chart at `...\pages\Netflix\visuals\<id>\visual.json` — axis `DimDate[Year]`, legend `Titles[Type]`, value `Titles Added`. **Acceptance**: axis is `DimDate[Year]`, **not** `Titles[Release Year]`; no blank category appears because `Titles Added` already excludes blank added-dates (FR-034).
- [ ] T057 [P] [US3] Create the four detail cards, one folder each under `...\pages\Netflix\visuals\`, bound to `Selected Title Description`, `Selected Title Duration`, `Selected Title Genres`, `Selected Title Rating`. **Acceptance**: 4 card visuals; each binds the **measure**, never the underlying column.
- [ ] T058 [P] [US3] Create the type slicer at `...\pages\Netflix\visuals\<id>\visual.json` bound to `Titles[Type]`. **Acceptance**: **no saved `"TV Show"` selection** is written — the workbook's stored state is user state, not a business rule (FR-032, A-006).
- [ ] T059 [P] [US3] Create the title slicer at `...\pages\Netflix\visuals\<id>\visual.json` bound to `Titles[Title]`, unfiltered. **Acceptance**: no default selection; positioned as in the source dashboard zone 19.
- [ ] T060 [P] [US3] Create the styled text-box header at `...\pages\Netflix\visuals\<id>\visual.json` occupying the layout region of the unavailable `netflix.png` (FR-037, A-007). **Acceptance**: no reference to `netflix.png` anywhere in the report; the region is filled, not left as a gap.

### Validation for User Story 3

- [ ] T061 [US3] Audit every `visual.json` under `...\pages\Netflix\visuals\` for PBIR root-schema compliance. **Acceptance**: each root contains **only** `$schema`, `name`, `position`, and one of `visual`/`visualGroup`; `visualContainerObjects.title` uses only `show` and `text`; colours use `{"solid":{"color":{"expr":{"Literal":{"Value":"'#RRGGBB'"}}}}}` and booleans `{"expr":{"Literal":{"Value":"true"}}}`.
- [ ] T062 [US3] Cross-check every binding string in every `visual.json` against `contracts\model-contract.md`. **Acceptance**: zero references to `Titles[Listed In]`, `Titles[Country List]`, `Titles[Rating]` on an axis, `Titles[Release Year]` on the time axis, `Distinct Titles` on the genre bar, or any `Users` column (FR-052).
- [ ] T063 [US3] Parse-check all report JSON — `Get-ChildItem "Output\NetflixRLS\NetflixRLS.Report" -Recurse -Include "*.json","*.pbir" | ForEach-Object { Get-Content $_.FullName -Raw | ConvertFrom-Json | Out-Null }`. **Acceptance**: every file parses with no exception.
- [ ] T064 [US3] Re-run Gate B — `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\NetflixRLS"`. **Acceptance**: exit code ≤ 1; `definition.pbir` `byPath` target resolves; page name regex passes; no orphan pages; theme resource resolves.
- [ ] T065 [US3] Open the report in Power BI Desktop and verify behaviour. **Acceptance**: all 12 visuals render; all 9 Tableau worksheets have a counterpart (SC-009); both slicers update the four detail cards; selecting a country on the map cross-filters the page (FR-035, native behaviour — no explicit configuration); the genre chart shows exactly 10 bars descending; the year chart shows no blank category.

**Checkpoint**: Model + report both complete and consistent.

---

## Phase 6: User Story 4 - Time-based analysis works off a proper calendar (Priority: P3)

**Goal**: `DimDate` behaves as a real date dimension — chronological sorting, a drillable hierarchy, and marked as the model's date table.

**Independent Test**: Place `DimDate[Year]` on an axis and confirm chronological (not alphabetical) ordering, then drill Year → Quarter → Month → Date.

**Depends on**: T023 (the `DimDate` table exists).

### Implementation for User Story 4

- [ ] T066 [US4] Edit `Output\NetflixRLS\NetflixRLS.SemanticModel\definition\tables\DimDate.tmdl` to wire the four `sortByColumn` pairs: `Quarter`→`Quarter Number`, `Month`→`Month Number`, `Year Month`→`Year Month Number`, `Day of Week`→`Day of Week Number`. **Acceptance**: 4 `sortByColumn` properties; each target column exists and is hidden; text labels no longer sort alphabetically.
- [ ] T067 [US4] Add the `Calendar` hierarchy (`Year` → `Quarter` → `Month` → `Date`) to `...\tables\DimDate.tmdl`. **Acceptance**: one hierarchy with 4 levels in that order; every level references an existing column.
- [ ] T068 [US4] Mark `DimDate` as the model's date table — `dataCategory: Time` on the table with `isKey` on `Date` (FR-010, §1). **Acceptance**: `dataCategory: Time` present; `Date` is the key column; R6 (`Titles[Date Added]` → `DimDate[Date]`) still resolves.
- [ ] T069 [US4] Re-run Gate A on the semantic model definition folder (same command as T030). **Acceptance**: zero errors after the hierarchy and sort-by edits.
- [ ] T070 [US4] Verify date behaviour in Power BI Desktop. **Acceptance**: years sort chronologically; `"September 9, 2019"` resolves to 9 September 2019 with no day/month transposition; the 11 source rows with no added-date persist as **blank** — not dropped, not defaulted (FR-005), and are excluded from the year chart.

**Checkpoint**: All four user stories independently functional.

---

## Phase 7: Polish & Final Validation (Gates A, B, D, E)

**Purpose**: End-to-end re-validation across the whole project after every layer exists.

- [ ] T071 Re-run Gate A across the full semantic model — `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\NetflixRLS\NetflixRLS.SemanticModel\definition"`. **Acceptance**: zero errors (SC-011).
- [ ] T072 Re-run Gate B across the whole project — `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\NetflixRLS"`. **Acceptance**: exit code `0`; any remaining warnings triaged and recorded.
- [ ] T073 [P] Parse-check **every** JSON-family file in the output — `Get-ChildItem "Output\NetflixRLS" -Recurse -Include "*.json","*.pbir","*.pbip","*.pbism" | ForEach-Object { Get-Content $_.FullName -Raw | ConvertFrom-Json | Out-Null }`. **Acceptance**: zero parse failures; `definition.pbism` = `4.2`, `definition.pbir` = `4.0`, `.pbip` has `$schema` and no `dataset` artifact.
- [ ] T074 [P] Re-verify **UTF-8 without BOM** across the entire `Output\NetflixRLS\` tree (FR-041). **Acceptance**: no file starts with `EF BB BF`.
- [ ] T075 [P] Final identity-leakage scan — `Select-String -Path "Output\NetflixRLS" -Pattern "@maq.com" -Recurse`. **Acceptance**: **zero matches** anywhere in the project, model and report alike (SC-008).
- [ ] T076 [P] Final enum scan — `Select-String -Path "Output\NetflixRLS\NetflixRLS.SemanticModel\definition" -Pattern "single" -Recurse`. **Acceptance**: **zero matches** for `crossFilteringBehavior: single`; every single-direction relationship uses `oneDirection`.
- [ ] T077 Final object-count reconciliation against `data-model.md`. **Acceptance**: 8 tables, 7 relationships, **19 measures**, 1 calculated column, 1 role, 1 page, 12 visuals.
- [ ] T078 **Gate E** — re-run the "View as role" checks from T043–T045 now that the report page exists, so RLS is verified through real visuals rather than an ad-hoc table. **Acceptance**: each entitled identity sees only its country across **all** 12 visuals; the unmapped identity sees empty visuals with no error; with no role applied `Distinct Titles` = 6,234 (SC-005, SC-006).
- [ ] T079 Walk `specs\001-netflixrls-pbi\quickstart.md` end to end as a first-time user. **Acceptance**: every step is accurate against the delivered project; a reviewer can identify each migrated visual's Tableau counterpart unassisted (SC-012); any step that no longer matches reality is corrected in `quickstart.md`.
- [ ] T080 Record the final compliance summary in the implementation log: constitution §1–§7 status, the two documented exceptions (A-014 calculated column, A-015 bi-directional relationships), and the T005 measure-count discrepancy. **Acceptance**: `.specify\memory\constitution.md` is **byte-identical to its state at T001** — exceptions are recorded in `spec.md`, never by amending the rulebook (FR-042).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Phase 1 — **blocks every user story** (all partitions read `expressions.tmdl`).
- **User Story 1 (Phase 3, P1)**: depends on Phase 2. Delivers the MVP.
- **User Story 2 (Phase 4, P1)**: depends on US1 Gates A + B (T030, T031) — the role and `securityFilteringBehavior` are edits to files US1 creates.
- **User Story 3 (Phase 5, P2)**: depends on US1 **and** US2 — plan §2.4 forbids writing any `visual.json` before the model validates and the name contract is reconciled (T046).
- **User Story 4 (Phase 6, P3)**: depends only on T023. Can run in parallel with US2 and US3 if `DimDate.tmdl` is not edited concurrently.
- **Polish (Phase 7)**: depends on all desired stories being complete.

### Critical Path

`T001…T006 → T007…T012 → T013…T029 → T030/T031 → T036…T038 → T043 → T046 → T047…T060 → T071…T080`

### Within User Story 1

- `Titles.tmdl` partition (T013) → its columns (T014) → its measures (T015–T019). **All five measure tasks touch the same file — none is [P].**
- The six independent table files (T020–T026) are all [P] with each other.
- Relationships (T027) require every table file to exist. `model.tmdl` (T028) requires all 8 tables.
- Gate A (T030) requires every `.tmdl` file to exist.

### Parallel Opportunities

- **Phase 1**: T001–T005 all [P].
- **Phase 2**: T008, T009, T010, T011 all [P] (T007 first, T012 last).
- **US1 tables**: T020, T021, T022, T023, T024, T025, T026 — seven independent files, fully parallel.
- **US1 validation**: T032, T033, T034 all [P] after T031.
- **US3 visuals**: T052–T060 — nine independent visual folders, fully parallel once T051 exists.
- **Phase 7**: T073, T074, T075, T076 all [P].

---

## Parallel Example: User Story 1 table generation

```text
# After T012 (expressions.tmdl) and T014 (Titles columns), launch all seven together:
Task: "Create DimCountry.tmdl — union of split catalogue + entitlement countries"     (T020)
Task: "Create DimGenre.tmdl — split/trim/dedupe of listed_in"                          (T021)
Task: "Create DimRating.tmdl — 15 ratings + Rating Category calculated column"         (T022)
Task: "Create DimDate.tmdl — computed-bounds calendar, 12 columns"                     (T023)
Task: "Create BridgeTitleCountry.tmdl — Show ID Int64 + Country, both hidden"          (T024)
Task: "Create BridgeTitleGenre.tmdl — Show ID Int64 + Genre, both hidden"              (T025)
Task: "Create Users.tmdl — hidden table, hidden columns, zero literal identities"      (T026)
```

## Parallel Example: User Story 3 visuals

```text
# After T051 (page.json), launch all nine visual folders together:
Task: "Country filled map → DimCountry[Country] + Distinct Titles"                     (T052)
Task: "Ratings column chart → DimRating[Rating] + Distinct Titles"                     (T053)
Task: "Top 10 Genre bar → DimGenre[Genre] + Distinct Titles (Top 10 Genres)"           (T054)
Task: "Type donut → Titles[Type] + Distinct Titles, % of Titles"                       (T055)
Task: "Titles-by-year area → DimDate[Year], legend Titles[Type], Titles Added"         (T056)
Task: "Four detail cards → Selected Title Description/Duration/Genres/Rating"          (T057)
Task: "Type slicer → Titles[Type], unfiltered"                                         (T058)
Task: "Title slicer → Titles[Title], unfiltered"                                       (T059)
Task: "Header text box → netflix.png substitute"                                       (T060)
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational.
2. Phase 3 User Story 1, ending at T035.
3. **STOP and VALIDATE**: Gates A and B green, project opens, `Distinct Titles` = 6,234.
4. This is a demonstrable, correct — but **unsecured** — model. Do not ship it to a shared workspace in this state.

### Incremental Delivery

1. Setup + Foundational → scaffold ready.
2. + User Story 1 → correct numbers (MVP).
3. + User Story 2 → correct **and secured**. This is the migration's primary value-add and the minimum shippable state.
4. + User Story 3 → the familiar dashboard experience.
5. + User Story 4 → proper calendar behaviour.
6. Phase 7 → end-to-end re-validation.

### Parallel Team Strategy

After Phase 2, one developer can take US1's `Titles.tmdl` chain (T013–T019) while another takes the seven independent table files (T020–T026). US4 (T066–T068) can proceed alongside US2 provided `DimDate.tmdl` is not edited by two people at once. US3 must wait for US2's Gate C.

---

## Notes

- **The single most likely way this ships broken**: omitting `securityFilteringBehavior: bothDirections` on R1 and R3 (T036). The model loads, every measure evaluates, Gates A, B, D and E all pass — and every viewer sees all 6,234 titles. T039 (text assertion) and T043 (View as role) are the only checks that catch it.
- **The second most likely**: emitting `crossFilteringBehavior: single`. That word is the Power BI *UI* label, not a TMDL token; it fails the model open with `DataModelLoadFailed`. Guarded by T034 and T076.
- **The third**: a report binding that does not match the emitted model name. Nothing in the report layer validates bindings — hence the T046 reconciliation gate and the T062 cross-check.
- `[P]` tasks touch different files and have no incomplete dependencies.
- Measure count is **19**, not the "18" written in `plan.md` and `data-model.md` prose — see T005.
- `.specify\memory\constitution.md` is read-only for the entire duration of this feature (T001, T080).
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
