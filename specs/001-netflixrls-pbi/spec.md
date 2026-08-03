# Feature Specification: Netflix RLS Workbook → Power BI Semantic Model

**Feature Branch**: `001-netflixrls-pbi`  
**Created**: 2026-08-03  
**Status**: Draft  
**Input**: User description: "Migrate the 'Netfix Workbook rls' Tableau workbook to a Power BI semantic model (.pbip), preserving all analytical content and replacing the workbook's defective Tableau user filter with correct dynamic row-level security."

**Source workbook**: `Data/Netflix RLS/Netfix Workbook rls.twb`  
**Source analysis**: `.specify/memory/NetflixRLS/tableau-analysis-output.md`  
**Governing rulebook**: `.specify/memory/constitution.md` (§1–§7)  
**Output location**: `Output/NetflixRLS/`

## Clarifications

### Session 2026-08-03

This clarification pass ran unattended as part of the migration pipeline. Every ambiguity below was auto-resolved against the universal rulebook `.specify/memory/constitution.md` (§1–§7) and the source analysis `.specify/memory/NetflixRLS/tableau-analysis-output.md`. The constitution was not modified; workbook-specific exceptions are recorded under **Assumptions**.

#### Model structure

- **C-001** — Q: Which tables form the star schema, and what is the fact grain? → A: Fact `Titles` at a grain of one row per title (`Show ID`); dimensions `DimCountry`, `DimDate`, `DimGenre`, `DimRating`; bridges `BridgeTitleCountry`, `BridgeTitleGenre`; hidden security table `Users` (from `User_Access.csv`).
  - Rationale: §1 requires an explicit fact grain plus bridge tables for comma-separated fields. `show_id` is unique across all 6,234 rows, so the grain is unambiguous. `Users` is a security artefact, never an analytical dimension.
- **C-002** — Q: Natural keys or surrogate keys? → A: **Natural keys** throughout — `Show ID`, `Country`, `Genre`, `Rating`, `Date`. No surrogate keys are introduced.
  - Rationale: §4 prescribes natural keys for single-source models. Both CSVs belong to one Tableau federated datasource, so this is a single-source model.
- **C-003** — Q: How is the comma-separated `country` list resolved, and how do the two country sources reconcile? → A: Power Query splits `country` on commas into `BridgeTitleCountry` (`Show ID`, `Country`), trimming each value and de-duplicating per title. `DimCountry` is the distinct union of those split values and the entitlement countries, so every entitlement value has a matching dimension row.
  - Rationale: §1 (bridge tables with natural keys) and A-003. The union guarantees referential integrity in both directions of the security chain.
- **C-004** — Q: Is the multi-value `listed_in` genre list handled the same way? → A: Yes — `BridgeTitleGenre` (`Show ID`, `Genre`) plus `DimGenre`, built with the same split/trim/de-duplicate logic.
  - Rationale: §1 treats all comma-separated fields identically; this makes the top-10 genre ranking correct without double-counting titles (A-009).
- **C-005** — Q: How is rating grouping modelled? → A: A **calculated column** `Rating Category` on `DimRating`, grouping the 15 source ratings into Kids / Teens / Adults / Unrated.
  - Rationale: §3 prefers measures, but a grouping attribute must be a column to be sliced, grouped and placed on an axis. Recorded as an exception under A-014.
- **C-006** — Q: Which raw multi-value strings remain user-visible? → A: `Genres` (the raw `listed_in` text) stays visible on `Titles` because the genre detail card renders it verbatim. The raw `country` string is hidden; country analysis goes through `DimCountry`.
  - Rationale: FR-013 — expose only columns with analytical meaning, and prevent slicing on a multi-value string.
- **C-007** — Q: What data categories are assigned? → A: `DimCountry[Country]` is set to **Country/Region**. No sub-national (state) geographic role is carried forward, and the entitlement country is hidden so it needs none.
  - Rationale: The Tableau semantic role is `[Country].[ISO3166_2]` with `geo-area-type='State'` while the data is country-level (A-008).
- **C-008** — Q: How is the date dimension built and how does the text date parse? → A: `date_added` is parsed in Power Query with an explicit `en-US` locale (`"MMMM d, yyyy"`); `DimDate` is generated over the observed minimum-to-maximum added-date, expanded to whole calendar years, and marked as the model's date table. The 11 blank added-dates remain blank and fall into the relationship's blank member.
  - Rationale: §1 (always create a date dimension), §5 (deterministic, machine-independent transforms), edge case 4 in the analysis.

#### Metrics

- **C-009** — Q: Measures or calculated columns for the analytics? → A: **Measures** for everything quantitative — `Distinct Titles`, `% of Titles`, `Genre Rank`, `Distinct Titles (Top 10 Genres)` — in display folders by subject area. The only calculated column is `Rating Category` (C-005).
  - Rationale: §3 — prefer measures, calculate at query time, keep the model small.
- **C-010** — Q: How is the Tableau percent-of-total table calculation mapped? → A: `% of Titles` uses the VAR pattern with `DIVIDE` over a `CALCULATE(..., ALLSELECTED(...))` denominator, so the total follows the visual's own selection rather than a hardcoded value.
  - Rationale: §3 — table calculations map to `CALCULATE` + filter removal; `DIVIDE` for safe division; no measure referenced inside a `CALCULATE` boolean filter.
- **C-011** — Q: How is the Tableau Top-10 filter mapped? → A: A `Genre Rank` measure using `RANKX` over `ALLSELECTED(DimGenre[Genre])` ordered by `Distinct Titles` descending, and a `Distinct Titles (Top 10 Genres)` measure that returns a value only for ranks 1–10. No visual-level filter is written into the report JSON.
  - Rationale: §3 maps `RANK` table calculations to `RANKX`. The PBIR `visualContainer/2.4.0` schema rejects a `filters` property at the visual root, so ranking must live in DAX.

#### Security

- **C-012** — Q: What exactly is the security role? → A: Exactly one role, `Country Access`, **dynamic**, with the table filter `Users[Username] = USERPRINCIPALNAME()` applied to the `Users` entitlement table. No other table carries a role filter.
  - Rationale: Matches the reconstructed intent in the analysis (A-001) and keeps the filter on the mapping table so it propagates once for the whole model. DAX `=` comparison is case-insensitive, satisfying FR-029 without extra `LOWER()` wrapping.
- **C-013** — Q: What is the filter propagation path, with explicit direction and cardinality? → A:
  1. `Users[Entitled Country]` **many → one** `DimCountry[Country]`, cross-filter **both directions** (required so the role's filter on `Users` reaches `DimCountry`).
  2. `DimCountry[Country]` **one → many** `BridgeTitleCountry[Country]`, cross-filter **single**.
  3. `Titles[Show ID]` **one → many** `BridgeTitleCountry[Show ID]`, cross-filter **both directions** (required so the bridge filters the fact).
  This is a single, unambiguous chain: `Users → DimCountry → BridgeTitleCountry → Titles`. `BridgeTitleGenre` uses the same bridge pattern (`DimGenre` one → many bridge, single; `Titles` one → many bridge, both) for genre analysis. `DimDate → Titles` and `DimRating → Titles` remain one-to-many, single-direction.
  - Rationale: §4 defaults to single-direction and permits bi-directional filtering specifically for bridge tables and dynamic RLS, provided it is documented — which A-015 does.
- **C-014** — Q: Are the 476 blank-country titles visible to secured viewers? → A: **No.** A blank country produces no `BridgeTitleCountry` row, so those titles are unreachable through the security chain and are invisible to every viewer under `Country Access`. The unfiltered `Distinct Titles` total is unaffected and still returns 6,234.
  - Rationale: Confirms A-002. Showing them to everyone would leak unattributed content across all regions.
- **C-015** — Q: How is the defective source identity handled? → A: The literal `user2@maq.com` — and any other literal identity — is never emitted into any TMDL expression, role filter, measure, calculated column, or report artefact. The Tableau `RLS` calculated field is not migrated in any form.
  - Rationale: A-001 and the analysis's explicit warning that the formula self-compares and pins the workbook to one test account. SC-008 verifies this by text search.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Analyst opens the migrated model and sees the same numbers (Priority: P1)

A content analyst who previously used the Tableau "Netflix" dashboard opens the migrated Power BI project. Every table loads, the catalogue of 6,234 titles is present, and the headline metrics — distinct title counts by rating, by genre, by country, by type, and by year added — return the same values the Tableau workbook produced when no user filter was applied.

**Why this priority**: Without a model that loads and returns correct counts, nothing else in the migration has value. This is the minimum viable outcome.

**Independent Test**: Open the generated project in Power BI Desktop, refresh, and compare the distinct title count and the per-rating / per-type breakdowns against the Tableau workbook with its user filter removed.

**Acceptance Scenarios**:

1. **Given** the generated project, **When** the analyst opens it in Power BI Desktop and refreshes, **Then** both source files load with no errors and no transformation step fails.
2. **Given** a loaded model, **When** the analyst evaluates the distinct title count with no filters applied, **Then** the result is 6,234.
3. **Given** a loaded model, **When** the analyst breaks the distinct title count down by title type, **Then** exactly two categories appear (Movie, TV Show) and their counts sum to 6,234.
4. **Given** a loaded model, **When** the analyst breaks the distinct title count down by rating, **Then** 15 rating categories appear.
5. **Given** a loaded model, **When** the analyst filters to a single genre, **Then** the distinct title count equals the number of titles whose genre list includes that genre.

---

### User Story 2 - Each user sees only the countries they are entitled to (Priority: P1)

A regional user opens the report and sees only the titles produced in the country assigned to their account. A user mapped to India sees India titles; a user mapped to the United Kingdom sees UK titles. No user sees another region's data, and no identity is hardcoded anywhere in the model.

**Why this priority**: Row-level security is the reason this workbook exists in its "rls" variant. The Tableau original is defective — it pins every viewer to one hardcoded test account — so correcting it is the primary migration value-add, not an optional extra.

**Independent Test**: Use "View as role" in Power BI Desktop with each of the three mapped identities and confirm the visible title set changes accordingly, and that an unmapped identity sees nothing.

**Acceptance Scenarios**:

1. **Given** the security role is applied for the identity mapped to India, **When** the analyst views the country breakdown, **Then** only titles whose country list includes India are visible.
2. **Given** the security role is applied for the identity mapped to the United States, **When** the analyst views any visual, **Then** every metric reflects only United States titles.
3. **Given** a title listing multiple countries (for example "United States, India, South Korea, China"), **When** the role is applied for either the India-mapped or the United-States-mapped identity, **Then** that title is visible to both.
4. **Given** an identity absent from the entitlement list, **When** the role is applied, **Then** no titles are visible and visuals render empty rather than erroring.
5. **Given** the model definition, **When** it is inspected for literal e-mail addresses, **Then** no user identity is hardcoded in any expression or role filter.
6. **Given** the security role is applied for any identity, **When** the analyst views the title list, **Then** titles with no recorded country are not visible.

---

### User Story 3 - The dashboard experience is reproduced on one report page (Priority: P2)

A business consumer opens the report and finds a single page mirroring the Tableau "Netflix" dashboard: a country map, a rating column chart, a top-10 genre bar chart, a type distribution, a titles-added-over-time area chart, four detail cards, and the type/title slicers — all on the source dark theme.

**Why this priority**: The report layer delivers the familiar experience, but it depends on a correct, secured model being in place first.

**Independent Test**: Open the report page and confirm every Tableau worksheet has a corresponding visual, that both slicers filter the detail cards, and that selecting a country on the map cross-filters the other visuals.

**Acceptance Scenarios**:

1. **Given** the report page, **When** the consumer counts the visuals, **Then** each of the nine Tableau worksheets is represented by at least one Power BI visual.
2. **Given** the report page, **When** the consumer selects a value in the type slicer, **Then** the four detail cards update accordingly.
3. **Given** the report page, **When** the consumer selects a country on the map, **Then** all other visuals on the page cross-filter to that country.
4. **Given** the top-10 genre visual, **When** it renders, **Then** exactly ten genres are shown, ordered by distinct title count descending.
5. **Given** the titles-over-time visual, **When** it renders, **Then** titles with no recorded added-date are excluded and no blank category appears on the axis.

---

### User Story 4 - Time-based analysis works off a proper calendar (Priority: P3)

An analyst groups titles by the year they were added to the catalogue and drills between year, quarter and month without the ordering breaking or the axis sorting alphabetically.

**Why this priority**: The Tableau workbook only ever uses year granularity, so this is an enhancement over strict parity — valuable but not required for sign-off.

**Independent Test**: Place the added-date year on an axis and confirm chronological ordering and correct drill behaviour.

**Acceptance Scenarios**:

1. **Given** the model, **When** the analyst groups titles by added year, **Then** years sort chronologically, not alphabetically.
2. **Given** a source date value such as "September 9, 2019", **When** it is loaded, **Then** it resolves to 9 September 2019 and is neither transposed nor rejected.
3. **Given** the 11 source rows with no added-date, **When** they are loaded, **Then** they persist as blank rather than causing a load failure or defaulting to a fabricated date.

---

### Edge Cases

- **Multi-value country strings**: `country` holds comma-separated lists across 555 distinct raw strings. A direct equality match between the entitlement value and this column would make every multi-country title invisible to everyone. The model must resolve the many-to-many so a title is counted once but reachable from each of its countries.
- **Double counting**: Once countries are split out, a title associated with four countries must still contribute exactly 1 to an unfiltered distinct title count — never 4.
- **Blank country (476 rows)**: These rows cannot match any entitlement. They are hidden from all secured viewers by decision (A-002) and this must be documented, because the unsecured total (6,234) will not equal the sum of all per-user totals.
- **Case-only name collision**: `country` (title catalogue) and `Country` (entitlement list) differ only by letter case. Left unresolved this produces ambiguous references and silent mis-binding. Both must be given explicit, distinct, human-readable names.
- **Text dates**: `date_added` arrives as US-formatted text. An implicit or machine-locale-dependent conversion will fail or mis-parse on non-US machines.
- **Defective source formula**: The Tableau `RLS` calculation compares the country column to itself and then hardcodes `user2@maq.com`. Its literal behaviour is "show only United States to everyone". It must not be ported.
- **Unused parameter**: The Tableau `Year` date parameter is referenced by nothing; carrying it forward would create a control with no effect.
- **Missing image asset**: The dashboard references `netflix.png` by an absolute path on an unavailable machine. The layout must not break because of it.
- **Relocated data files**: The workbook records an authoring path from a different folder than where the files now live.
- **Geography mismatch**: The Tableau map uses a sub-national (state) geographic role while the data is country-level.
- **Saved slicer state**: The `"TV Show"` type selection stored in the workbook is saved user state, not a business rule; it must not become a permanent filter.
- **Duplicate rating worksheets**: "Rating" (card) and "Ratings" (chart) present the same field at different granularities; both are retained as distinct visuals.

## Requirements *(mandatory)*

### Functional Requirements

#### Data loading

- **FR-001**: The model MUST load the title catalogue from `Data/Netflix RLS/netflix_titles.csv` (6,234 rows, 12 source columns) using an absolute path resolved from the workspace root, not the authoring path recorded in the workbook.
- **FR-002**: The model MUST load the entitlement list from `Data/Netflix RLS/User_Access.csv` (3 rows: user identity and country).
- **FR-003**: Every loaded column MUST have an explicitly assigned data type; no column may be left to implicit type inference.
- **FR-004**: The added-date text MUST be converted to a true date in Power Query using an explicit United States English locale and the source format `MMMM d, yyyy` (for example "September 9, 2019"), so the result is machine-independent (C-008).
- **FR-005**: The 11 rows with no added-date MUST load successfully and retain a blank date; they MUST NOT be dropped, defaulted, or cause an error.
- **FR-006**: All data transformations MUST be deterministic — refreshing twice against unchanged source files MUST produce identical results.

#### Model structure

- **FR-007**: The model MUST follow a star schema comprising the fact table `Titles` (grain: one row per title, `Show ID`), the dimensions `DimCountry`, `DimDate`, `DimGenre` and `DimRating`, the bridges `BridgeTitleCountry` and `BridgeTitleGenre`, and the hidden security table `Users`. `Show ID` is unique across all 6,234 rows and serves as the fact's natural key (C-001).
- **FR-008**: The model MUST resolve the comma-separated country list into the many-to-many bridge `BridgeTitleCountry` (one row per title × country, keyed on `Show ID` and `Country`) so a title can be reached from each of its countries (C-003).
- **FR-009**: Country values derived from the split MUST be trimmed of surrounding whitespace and deduplicated per title so a title never appears twice for the same country.
- **FR-010**: The model MUST include the date dimension `DimDate`, generated over the observed minimum-to-maximum added-date and expanded to whole calendar years, marked as the model's date table, with all date-based grouping routed through it (C-008).
- **FR-011**: The catalogue's country column and the entitlement list's country column MUST be given distinct, unambiguous, human-readable names — `DimCountry[Country]` for the catalogue and `Users[Entitled Country]` for the entitlement list; a case-only difference between them is not acceptable (C-003).
- **FR-012**: All tables, columns and measures MUST follow the constitution's naming conventions (§2); no Tableau-generated identifier such as `Calculation_0182254345785358` may be surfaced to users.
- **FR-013**: Technical key and bridge columns that carry no analytical meaning MUST be hidden from report authors.
- **FR-014**: Relationships MUST default to single-direction filtering. Exactly three relationships MAY be bi-directional, each documented under A-015: `Users[Entitled Country]` ↔ `DimCountry[Country]`, `Titles[Show ID]` ↔ `BridgeTitleCountry[Show ID]`, and `Titles[Show ID]` ↔ `BridgeTitleGenre[Show ID]` (C-013).
- **FR-015**: Every relationship endpoint MUST resolve — no relationship may reference a column that does not exist or has been renamed elsewhere.
- **FR-045**: The model MUST resolve the comma-separated genre list into the bridge `BridgeTitleGenre` (`Show ID`, `Genre`) with a companion `DimGenre` dimension, built with the same split, trim and de-duplicate logic as the country bridge (C-004).
- **FR-046**: `DimRating` MUST expose a `Rating Category` calculated column grouping the 15 source ratings into Kids, Teens, Adults and Unrated (C-005, exception A-014).
- **FR-047**: `DimCountry[Country]` MUST be assigned the Country/Region data category; no sub-national geographic role from the source may be carried forward (C-007).
- **FR-048**: The raw multi-value `country` string MUST be hidden on `Titles`; the raw genre list MUST remain visible as `Genres` because the genre detail card renders it verbatim (C-006).
- **FR-049**: `DimCountry` MUST contain the distinct union of the split catalogue countries and the entitlement countries, so every entitlement value resolves to a dimension row (C-003).

#### Metrics

- **FR-016**: The model MUST provide the measure `Distinct Titles`, a distinct count of `Titles[Show ID]`, equivalent to the Tableau `COUNTD([show_id])` used by every worksheet (C-009).
- **FR-017**: The model MUST provide the measure `% of Titles`, equivalent to the Tableau percent-of-total table calculation used in the type-distribution worksheet, computed with a safe division over a denominator that removes only the current visual's own grouping filter — never a hardcoded denominator (C-010).
- **FR-018**: Division in any measure MUST be performed safely so an empty or zero denominator yields blank rather than an error or infinity.
- **FR-019**: Measures MUST be organised into display folders by subject area.
- **FR-020**: No measure may be referenced directly inside a filter-condition argument; intermediate values MUST be captured in variables first.
- **FR-021**: The distinct title count MUST remain accurate after the country and genre splits — a title associated with N countries contributes 1, not N, to an unfiltered count.
- **FR-050**: The model MUST provide a `Genre Rank` measure that ranks genres by `Distinct Titles` descending within the current selection, and a `Distinct Titles (Top 10 Genres)` measure that returns a value only for ranks 1–10, so the Tableau Top-10 filter is reproduced entirely in DAX (C-011).
- **FR-051**: Measures MUST NOT be expressed as calculated columns; the only calculated column in the model is `DimRating[Rating Category]` (C-009).

#### Security

- **FR-022**: The model MUST define exactly one security role, named `Country Access`, of the dynamic kind, whose only filter is placed on the `Users` entitlement table and restricts it to the rows matching the current viewer's principal name (C-012). No other table may carry a role filter.
- **FR-023**: The role MUST determine the viewer's identity dynamically at query time; it MUST NOT contain any literal user identity, and specifically MUST NOT contain `user2@maq.com` (C-015).
- **FR-024**: The entitlement filter MUST propagate along exactly one unambiguous chain — `Users` → `DimCountry` → `BridgeTitleCountry` → `Titles` — with the directions and cardinalities fixed in C-013, so all measures and all visuals are secured, not just the country visual.
- **FR-025**: A title listing multiple countries MUST be visible to every user entitled to any one of those countries.
- **FR-026**: Titles with no recorded country MUST NOT be visible to any user under the security role; a blank country produces no bridge row, so those 476 titles are unreachable through the security chain (C-014).
- **FR-027**: A viewer whose identity is absent from the entitlement list MUST see an empty result set — not an error, and not the full catalogue.
- **FR-028**: The defective Tableau `RLS` calculated field MUST NOT be migrated in any form — neither as a column, a measure, nor a role expression.
- **FR-029**: Identity matching against the entitlement list MUST be case-insensitive (C-012).
- **FR-052**: The `Users` table and all of its columns MUST be hidden from report authors; it exists solely to drive the role and MUST NOT be usable as an analytical dimension.

#### Report

- **FR-030**: The report MUST contain a single page reproducing the Tableau "Netflix" dashboard, laid out to reflect the source 1700 × 800 arrangement.
- **FR-031**: Each of the nine Tableau worksheets MUST be represented by a corresponding Power BI visual: a country map, a rating column chart, a top-10 genre bar chart, a type distribution, a titles-added-by-year area chart, and four detail cards (description, duration, genre, rating).
- **FR-032**: The report MUST provide slicers for title type and title, positioned as in the source dashboard, with no permanent filter locked to the workbook's saved `"TV Show"` selection.
- **FR-033**: The top-10 genre visual MUST show exactly ten genres ranked by distinct title count descending, driven by the ranking measures in FR-050; no `filters` property may be written at the root of the visual definition (C-011).
- **FR-034**: The titles-added-by-year visual MUST exclude titles with no added-date.
- **FR-035**: Selecting a country on the map MUST cross-filter the other visuals on the page, reproducing the Tableau dashboard filter action.
- **FR-036**: The report MUST apply the source dark theme (black background, red accent, light text, 10pt base font).
- **FR-037**: The unavailable `netflix.png` asset MUST be replaced with an equivalent text or shape header occupying the same layout region; its absence MUST NOT leave a broken reference or an empty gap.
- **FR-038**: The map visual MUST be bound to `DimCountry[Country]` and configured for country-level geography, overriding the sub-national geographic role carried over from Tableau (C-007).

#### Output and validation

- **FR-039**: All generated artefacts MUST be written to `Output/NetflixRLS/` as a valid thick project comprising the project entry point, the semantic model folder, and the report folder.
- **FR-040**: The generated project MUST pass the workspace's structural and format validators with zero errors before it is presented as complete.
- **FR-041**: All generated files MUST be UTF-8 without a byte-order mark.
- **FR-042**: Any constitution rule that cannot be applied MUST be recorded as an exception with a rationale in this specification rather than by amending the constitution.

#### Explicit exclusions

- **FR-043**: The unused Tableau `Year` date parameter MUST NOT be migrated as a what-if parameter or any other control.
- **FR-044**: The auto-generated dashboard-action set `[Action (Country)]` MUST NOT be migrated as a user-defined set; native cross-filtering satisfies it.

### Key Entities

- **Title**: One entry in the Netflix catalogue, uniquely identified by its show identifier. Attributes: type (Movie / TV Show), title, director, cast, raw country list, added date, release year, rating, duration, genre list, description. 6,234 instances; the analytical grain of the model.
- **Country**: A production country. Sourced both from splitting the catalogue's multi-value country list and from the entitlement list; the two sources must reconcile to one shared set of country names so security can propagate.
- **Title-Country Bridge**: The many-to-many association between a title and each country it lists. Exists solely to make multi-country titles reachable from any of their countries without duplicating title counts, and carries the security chain.
- **Entitlement**: The mapping of a user identity to the country that identity may see. 3 instances. Drives the security role; hidden, and never exposed as an analytical dimension.
- **Date**: A calendar covering the range of added-dates, supporting year / quarter / month grouping and chronological ordering.
- **Genre**: A category drawn from the multi-value genre list, used by the top-10 genre visual and the genre detail card.
- **Title-Genre Bridge**: The many-to-many association between a title and each genre it lists, mirroring the country bridge so the top-10 ranking counts each title once per genre without inflating the overall total.
- **Rating**: The content rating (15 values), extended with a grouped `Rating Category` attribute for higher-level analysis.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The generated project opens in Power BI Desktop with zero load, model, or query errors on first attempt.
- **SC-002**: 100% of source tables load; the title catalogue reports exactly 6,234 rows and the entitlement list exactly 3 rows.
- **SC-003**: 100% of defined relationships resolve — no broken or ambiguous relationships remain.
- **SC-004**: 100% of defined measures evaluate without error and return non-error values across every visual on the report page.
- **SC-005**: The unfiltered distinct title count equals 6,234, matching the source workbook with its user filter removed.
- **SC-006**: For each of the three entitled identities, previewing the role returns a non-empty result set restricted to that identity's country, verified in under 2 minutes per identity.
- **SC-007**: A title listing four countries is visible to viewers entitled to each of those four countries, and is counted once per viewer.
- **SC-008**: Zero literal user identities appear anywhere in the model definition — a text search for `@maq.com` across the generated model artefacts returns no results.
- **SC-009**: All 9 Tableau worksheets have a corresponding visual on the migrated report page — 9-of-9 coverage.
- **SC-010**: Both slicers, the map cross-filter, and the top-10 genre ranking behave as described, confirmed by a reviewer in a single pass with no follow-up defects.
- **SC-011**: Structural and format validation of the output project returns zero errors.
- **SC-012**: A reviewer familiar with the Tableau dashboard can identify every migrated visual's Tableau counterpart without assistance.

## Assumptions

These defaults were chosen where the source workbook was silent, ambiguous, or defective. Each is recorded here per the constitution's edge-case policy rather than by amending the constitution.

- **A-001 — Corrected security intent**: The Tableau `RLS` formula is treated as a defective development artifact. The migration implements the reconstructed intent (each user sees the countries mapped to their identity) rather than the literal behaviour (everyone sees the United States). This is the single largest intentional behavioural difference from the source.
- **A-002 — Blank countries hidden**: The 476 titles with no recorded country are hidden from all secured viewers. Consequence: per-user totals will never sum to the unfiltered 6,234. The alternative — showing them to everyone — was rejected because it would leak unattributed content across all regions.
- **A-003 — Bridge over string matching**: The many-to-many country problem is solved with a bridge table rather than a substring-matching security expression, because substring matching performs poorly at scale, supports only one country per user, and can produce false positives on overlapping country names.
- **A-004 — Identity source**: The viewer's identity is taken from the signed-in principal name, matching the e-mail-style values in the entitlement list, compared case-insensitively.
- **A-005 — `Year` parameter out of scope**: Not referenced anywhere in the source workbook, so it is excluded.
- **A-006 — Saved slicer state is not a rule**: The stored `"TV Show"` selection is treated as user state; slicers ship unfiltered.
- **A-007 — Missing image**: `netflix.png` is unavailable, so a styled text header substitutes for it in the same layout region.
- **A-008 — Geography level**: The map is interpreted at country level despite the source's state-level geographic role, because the underlying data is country-level.
- **A-009 — Genre handling**: Genres are multi-value like countries; the top-10 genre ranking is computed over split genre values, so a title in three genres contributes to all three.
- **A-010 — Descriptive table naming permitted**: Business-recognisable table names may replace strict `Dim`/`Fact` prefixes where the constitution (§2) permits, provided naming is internally consistent across the whole model.
- **A-011 — Single report page**: The source has one dashboard and no navigation buttons, so no page navigation, bookmarks, or buttons are migrated.
- **A-012 — Data files remain in place**: `Data/Netflix RLS/` continues to hold the source CSVs; the model references them from there and is not expected to work if they are moved.
- **A-013 — Deployment out of scope**: Source credentials, scheduled refresh, and workspace publishing are outside this feature; the deliverable is the local project.
- **A-014 — Calculated column exception (§3)**: The constitution prefers measures over calculated columns. `DimRating[Rating Category]` is the single permitted exception, because a grouping attribute must be a column to be sliced, grouped, and placed on an axis. No other calculated column is created.
- **A-015 — Bi-directional relationship exception (§4)**: The constitution defaults to single-direction filtering. Three relationships are bi-directional, each for a reason §4 explicitly sanctions: `Users` ↔ `DimCountry` so the dynamic role's filter reaches the country dimension, and `Titles` ↔ each of the two bridge tables so bridge-side filters reach the fact. Together they form single, unambiguous paths — no alternative filter route exists between any pair of tables.
