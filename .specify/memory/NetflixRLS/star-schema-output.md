# Star Schema Design — NetflixRLS

- **Workbook**: `Data/Netflix RLS/Netfix Workbook rls.twb`
- **Source analysis**: `.specify/memory/NetflixRLS/tableau-analysis-output.md`
- **Authoritative naming**: `specs/001-netflixrls-pbi/spec.md` — Clarifications C-001…C-015, FR-007, FR-045–FR-052
- **DAX contract**: `.specify/memory/NetflixRLS/dax-measures-output.md`
- **Rulebook**: `.specify/memory/constitution.md` §1, §2, §4, §5
- **Generated**: 2026-08-03

## Design Summary

Eight tables: one fact (`Titles`), four dimensions (`DimCountry`, `DimDate`, `DimGenre`, `DimRating`), two bridges (`BridgeTitleCountry`, `BridgeTitleGenre`), one hidden security table (`Users`). Seven relationships. **Natural keys only** (C-002) — no surrogate keys, so no cross-table M joins and no circular load dependencies.

```
                      Users (hidden)
                        │  Entitled Country  (*→1, BOTH, security BOTH)
                        ▼
DimRating ──1→*── Titles ──1→*── BridgeTitleCountry ──*←1── DimCountry
                    │  (BOTH, security BOTH)      (single, 1→*)
                    │
DimDate ──1→*───────┤
                    │
                    └──1→*── BridgeTitleGenre ──*←1── DimGenre
                       (BOTH)                    (single, 1→*)
```

8 nodes / 7 edges, connected and acyclic → **single tree, no alternate path between any two tables, no ambiguity**. See §Ambiguity & Circularity Analysis.

---

## Source Files

| File | Rows | Role |
|---|---|---|
| `Data/Netflix RLS/netflix_titles.csv` | 6,234 | Title catalogue. Header: `show_id,type,title,director,cast,country,date_added,release_year,rating,duration,listed_in,description`. `show_id` unique → natural PK. |
| `Data/Netflix RLS/User_Access.csv` | 3 | Entitlement mapping. Header: `Username,Country`. |

**Load-safety rule (§5, star-schema skill "Key Strategy")**: every table query reads its CSV **directly** via `Csv.Document(File.Contents(...))`. No query references another model table's query. Only two shared M expressions are permitted — `TitlesSourcePath` and `UserAccessSourcePath` (scalar text, absolute paths resolved from the workspace root, per FR-001/FR-002/§5). Scalar expressions are not tables and cannot create a load cycle.

---

## Fact Table

### `Titles`
- **Source**: `netflix_titles.csv` (direct read)
- **Grain**: one row per title — 6,234 rows, keyed by `Show ID` (C-001, FR-007)
- **Keys**: `Show ID` (natural PK, `isKey`); `Rating` (natural FK → `DimRating[Rating]`); `Date Added` (natural FK → `DimDate[Date]`)
- **Measures live here**: all 19 measures use `Titles` as home table (per DAX contract)

| Column | Type | Source | Hidden | Data category | Notes |
|---|---|---|---|---|---|
| `Show ID` | Int64 | `show_id` | **Yes** | — | Natural PK, `isKey = true`, `summarizeBy: none`. Hidden per FR-013; still referenced by `Distinct Titles`. |
| `Type` | String | `type` | No | — | Domain: `Movie`, `TV Show`. Slicer + `% of Titles` / `Movie Titles` / `TV Show Titles`. |
| `Title` | String | `title` | No | — | Slicer field; drives the four detail cards. |
| `Director` | String | `director` | No | — | ⚠ Un-split comma-separated list (see Open Risks R-1). |
| `Cast` | String | `cast` | No | — | ⚠ Un-split comma-separated list. Not used by any visual or measure; retained as a Key-Entity attribute. |
| `Country List` | String | `country` | **Yes** | — | Raw multi-value string. **Hidden by FR-048/C-006** so it can never be sliced. Name deliberately differs from `DimCountry[Country]` and `Users[Entitled Country]` (FR-011 — resolves the `country` / `Country` case-only collision). |
| `Date Added` | Date | `date_added` (parsed) | No | — | FK to `DimDate[Date]`. 11 nulls preserved (FR-005). Referenced by `Titles Added`. |
| `Release Year` | Int64 | `release_year` | No | — | `summarizeBy: none` (it is a year label, not an additive value). Range 1925–2020. |
| `Rating` | String | `rating` | **Yes** | — | FK to `DimRating[Rating]`. Hidden per FR-013 — **but still referenced by the `Selected Title Rating` measure**, which is legal (hidden ≠ unavailable to DAX). |
| `Duration` | String | `duration` | No | — | Mixed units (`90 min` / `2 Seasons`); kept as text, rendered verbatim by the detail card. |
| `Genres` | String | `listed_in` | No | — | Raw multi-value string kept **visible** by FR-048/C-006 because the genre detail card renders it verbatim. Analysis/grouping must use `DimGenre`. |
| `Description` | String | `description` | No | — | Detail card. |

**Power Query derivation**
1. `Csv.Document(File.Contents(TitlesSourcePath), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv])` — quoting matters: `country`, `cast`, `listed_in` contain embedded commas inside quotes.
2. `Table.PromoteHeaders`.
3. Rename to the Title-Case names above (`show_id`→`Show ID`, `country`→`Country List`, `listed_in`→`Genres`, …) (§2).
4. Parse the date **explicitly**: `Date.FromText([Date Added], [Format = "MMMM d, yyyy", Culture = "en-US"])` wrapped in `try … otherwise null` so the 11 blanks survive as null (FR-004, FR-005, C-008). Do **not** use `Table.TransformColumnTypes(..., "en-US")` alone — a bare type change is locale-dependent.
5. `Table.TransformColumnTypes` for every remaining column — explicit types, no inference (FR-003).
6. No trimming beyond `Text.Trim` on `Type` and `Rating` (join keys).

---

## Dimension Tables

### `DimCountry`
- **Source**: derived — union of **both** CSVs (FR-049, C-003)
- **Grain**: one row per distinct country name
- **Key**: `Country`

| Column | Type | Hidden | Data category | Notes |
|---|---|---|---|---|
| `Country` | String | No | **Country/Region** (FR-047, C-007) | `isKey = true`. Bound to the map visual (FR-038). No sub-national/state role carried over from Tableau. |

**Power Query derivation**
1. Read `netflix_titles.csv` directly → keep `country` only.
2. `Table.SelectRows` to drop null/empty → `Text.Split([country], ",")` → `Table.ExpandListColumn` → `Text.Trim`.
3. Read `User_Access.csv` directly → keep `Country` → `Text.Trim`, drop blanks.
4. `Table.Combine` the two single-column tables → `Table.Distinct` → sort ascending.
- Expected: 100–130 distinct country names. All three entitlement values (India, United States, United Kingdom) already occur in the catalogue, but the union is mandatory so a future entitlement value can never dangle (FR-049).

### `DimGenre`
- **Source**: derived from `netflix_titles.csv` `listed_in` (FR-045, C-004)
- **Grain**: one row per distinct genre
- **Key**: `Genre`

| Column | Type | Hidden | Notes |
|---|---|---|---|
| `Genre` | String | No | `isKey = true`. Axis of the Top-10 genre bar chart; scope column for `Genre Rank` / `% of Titles by Genre`. |

**Power Query derivation**: read the CSV → keep `listed_in` → drop blanks → `Text.Split` on `,` → expand → `Text.Trim` → `Table.Distinct` → sort. (~42 distinct genres.)

### `DimRating`
- **Source**: derived from `netflix_titles.csv` `rating`
- **Grain**: one row per distinct rating — 15 rows (analysis)
- **Key**: `Rating`

| Column | Type | Hidden | Notes |
|---|---|---|---|
| `Rating` | String | No | `isKey = true`. Axis of the *Ratings* column chart; scope column for `% of Titles by Rating`. |
| `Rating Category` | String | No | **Calculated column** (DAX, not M) — the model's only calculated column (FR-046, C-005, exception A-014). Expression is owned by `dax-measures-output.md`. |

**Power Query derivation**: read the CSV → keep `rating` → `Text.Trim` → drop null/empty → `Table.Distinct` → sort. Any title whose rating is blank or absent from the dimension lands in the auto-created blank member of `DimRating`; it is not dropped from `Titles`.

### `DimDate`
- **Source**: derived / generated (FR-010, C-008)
- **Grain**: one row per calendar day, contiguous, no gaps
- **Key**: `Date` — **mark as the model's date table** (`dataCategory: Time`, `isKey` on `Date`)

| Column | Type | Hidden | Sort by | Notes |
|---|---|---|---|---|
| `Date` | Date | No | — | PK; FK target for `Titles[Date Added]`. |
| `Year` | Int64 | No | — | Referenced by the DAX contract. `summarizeBy: none`. |
| `Quarter` | String | No | `Quarter Number` | `Q1`…`Q4`. |
| `Quarter Number` | Int64 | **Yes** | — | Sort helper. |
| `Month` | String | No | `Month Number` | Full month name, en-US invariant. |
| `Month Number` | Int64 | **Yes** | — | Sort helper. |
| `Year Month` | String | No | `Year Month Number` | `2019-09`. |
| `Year Month Number` | Int64 | **Yes** | — | `201909`. |
| `Day` | Int64 | No | — | Day of month. |
| `Day of Week` | String | No | `Day of Week Number` | Full weekday name. |
| `Day of Week Number` | Int64 | **Yes** | — | 1 = Monday. |
| `Week Number` | Int64 | No | — | ISO week. |

- **Hierarchy** `Calendar`: `Year` → `Quarter` → `Month` → `Date`.
- **Range**: from `Date.StartOfYear(min non-null Date Added)` to `Date.EndOfYear(max non-null Date Added)` — computed from the parsed dates, expanded to whole calendar years (C-008). Observed source range is 2008–2020, but the bounds MUST be computed, not hardcoded (FR-006 determinism).
- **Power Query derivation**: read `netflix_titles.csv` directly → parse `date_added` with the same explicit `en-US` format → `List.Min` / `List.Max` over non-nulls → `List.Dates(start, Duration.Days(end-start)+1, #duration(1,0,0,0))` → `Table.FromList` → add the parts above with `Date.Year`, `Date.QuarterOfYear`, `Date.MonthName(..., "en-US")`, `Date.DayOfWeekName(..., "en-US")`, `Date.WeekOfYear`. Culture is pinned so month/weekday names are machine-independent (§5, FR-006).

---

## Bridge Tables

### `BridgeTitleCountry`
- **Source**: derived from `netflix_titles.csv` (`show_id` × split `country`) — FR-008, C-003
- **Grain**: one row per title × country. **Titles with a blank `country` produce ZERO rows** (476 rows → no bridge rows) — this is what makes them invisible under RLS (C-014, FR-026, A-002).
- **Key**: composite (`Show ID`, `Country`) — not declared as a TMDL key; uniqueness is guaranteed by the de-duplicate step.
- **Entire table hidden** (FR-013).

| Column | Type | Hidden | Notes |
|---|---|---|---|
| `Show ID` | Int64 | Yes | FK → `Titles[Show ID]`. |
| `Country` | String | Yes | FK → `DimCountry[Country]`. Referenced by `Distinct Countries`. |

**Power Query derivation**: read the CSV → keep `show_id`, `country` → drop rows where `country` is null/empty → `Text.Split([country], ",")` → `Table.ExpandListColumn` → `Text.Trim` → drop rows that trimmed to empty → `Table.Distinct` on both columns (FR-009: a title never appears twice for the same country) → set types.

### `BridgeTitleGenre`
- **Source**: derived from `netflix_titles.csv` (`show_id` × split `listed_in`) — FR-045, C-004
- **Grain**: one row per title × genre. Blank `listed_in` produces no rows.
- **Key**: composite (`Show ID`, `Genre`).
- **Entire table hidden** (FR-013).

| Column | Type | Hidden | Notes |
|---|---|---|---|
| `Show ID` | Int64 | Yes | FK → `Titles[Show ID]`. |
| `Genre` | String | Yes | FK → `DimGenre[Genre]`. Referenced by `Distinct Genres`. |

**Power Query derivation**: identical split/trim/de-duplicate logic to `BridgeTitleCountry`, on `listed_in`.

---

## Security Table

### `Users`
- **Source**: `User_Access.csv` (direct read) — FR-002
- **Grain**: one row per entitled identity — 3 rows
- **Key**: `Username`
- **TABLE HIDDEN, and every column hidden** (FR-052). Not an analytical dimension; never placed in a slicer.

| Column | Type | Source | Hidden | Notes |
|---|---|---|---|---|
| `Username` | String | `Username` | Yes | Compared to `USERPRINCIPALNAME()` by the role. DAX `=` is case-insensitive → FR-029 satisfied without `LOWER()`. |
| `Entitled Country` | String | `Country` | Yes | Renamed from `Country` to remove the case-only collision with `DimCountry[Country]` and `Titles[Country List]` (FR-011, C-003). FK → `DimCountry[Country]`. No data category (hidden — FR-047 note). |

**Power Query derivation**: read `User_Access.csv` → promote headers → rename `Country` → `Entitled Country` → `Text.Trim` both columns → explicit text types.

> **Never emit the literal `user2@maq.com`** (or any identity) into TMDL, DAX, roles, or report JSON (FR-023, C-015, SC-008). The defective Tableau `RLS` calculated field is **not migrated in any form** (FR-028).

---

## Relationships

TMDL enum reminder for `pbip-generator`: `crossFilteringBehavior` accepts only `oneDirection` | `bothDirections` | `automatic` — the UI word **`single` is invalid TMDL** and causes `DataModelLoadFailed`. `securityFilteringBehavior` accepts `oneDirection` | `bothDirections` | `none`.

| # | From (many side) | To (one side) | Cardinality | Cross-filter | **Security filter** | Active | Rationale |
|---|---|---|---|---|---|---|---|
| R1 | `Users[Entitled Country]` | `DimCountry[Country]` | many → one | **bothDirections** | **bothDirections** | Yes | C-013 step 1 / FR-014. The role filters `Users` (many side); the filter must climb to `DimCountry` (one side), which only happens with bi-directional cross-filtering **and** bi-directional *security* filtering. Without `securityFilteringBehavior: bothDirections` the RLS filter stops at `Users` and every viewer sees the whole catalogue. |
| R2 | `BridgeTitleCountry[Country]` | `DimCountry[Country]` | many → one | `oneDirection` (`DimCountry` → bridge) | `oneDirection` | Yes | C-013 step 2. Natural one-to-many propagation; deliberately **not** bi-directional — see Ambiguity Analysis A-2. |
| R3 | `BridgeTitleCountry[Show ID]` | `Titles[Show ID]` | many → one | **bothDirections** | **bothDirections** | Yes | C-013 step 3 / FR-014. Bridge must filter the fact (many → one), for both ordinary cross-filtering and the RLS chain. |
| R4 | `BridgeTitleGenre[Genre]` | `DimGenre[Genre]` | many → one | `oneDirection` (`DimGenre` → bridge) | `oneDirection` | Yes | Mirrors R2 for genre. |
| R5 | `BridgeTitleGenre[Show ID]` | `Titles[Show ID]` | many → one | **bothDirections** | `oneDirection` | Yes | FR-014 permits this third bi-directional relationship so `DimGenre` reaches the fact. Security direction stays one-way: the genre chain carries **no** entitlement, and widening it would add a needless RLS traversal path. |
| R6 | `Titles[Date Added]` | `DimDate[Date]` | many → one | `oneDirection` | `oneDirection` | Yes | Standard date dimension (FR-010). The 11 null `Date Added` rows fall into `DimDate`'s blank member; `Titles Added` excludes them explicitly (FR-034). |
| R7 | `Titles[Rating]` | `DimRating[Rating]` | many → one | `oneDirection` | `oneDirection` | Yes | Standard conformed dimension. |

- **Exactly one active relationship per table pair.** No inactive relationships, therefore no `USERELATIONSHIP` anywhere.
- **Bi-directional count = 3** (R1, R3, R5) — exactly the three sanctioned by FR-014 / A-015, no more.
- **Referential integrity**: every FK resolves. `DimCountry` is the union of both country sources (FR-049) so no bridge or entitlement value dangles; `DimGenre` and `DimRating` are derived from the same column they key, so they are complete by construction; `DimDate` spans whole calendar years around the observed range.

### RLS role (for `pbip-generator`)

| Role | Kind | Table | Filter expression |
|---|---|---|---|
| `Country Access` | Dynamic | `Users` | `[Username] = USERPRINCIPALNAME()` |

Exactly one role, exactly one table filter (FR-022, C-012). Propagation path, in order:

`Users` —R1(both/security both)→ `DimCountry` —R2(1→*)→ `BridgeTitleCountry` —R3(both/security both)→ `Titles` → (R6, R7 outward to `DimDate`, `DimRating`; R5 outward to `BridgeTitleGenre` → `DimGenre`)

Because `Titles` is secured by propagation rather than a direct role filter, every measure is automatically secured (FR-024).

---

## Ambiguity & Circularity Analysis

**A-1 — Graph shape.** 8 tables, 7 relationships, connected ⇒ a spanning tree. There is exactly one path between any pair of tables, so Power BI's ambiguity detector has nothing to resolve. No relationship needs to be deactivated. ✅

**A-2 — Why R2 and R4 must stay one-directional.** If `BridgeTitleCountry → DimCountry` were made bi-directional, filters could travel `Titles → BridgeTitleCountry → DimCountry → Users`. That is still acyclic, but it is an RLS hazard: a report-side filter on `Titles` would reshape the `Users` table, and combined with R1's bi-directional security filtering it creates a filter loop through the secured chain that Power BI reports as *"ambiguity between … detected"* or silently over-filters the map. **Keep R2 and R4 `oneDirection`.** Same reasoning for R4 with `DimGenre`.

**A-3 — Known consequence, not a defect.** Because R2 is one-directional, a slicer on `Titles[Type]` (or any fact-side filter) does **not** shrink the country list rendered by `DimCountry`-bound slicers/maps; unmatched countries render with blank values instead of disappearing. This is the correct trade-off — the alternative (bi-directional R2) breaks A-2.

**A-4 — Bi-directional + RLS is not automatic.** `crossFilteringBehavior: bothDirections` alone does **not** make an RLS filter traverse the relationship. `securityFilteringBehavior: bothDirections` is required on R1 and R3. If `pbip-generator` omits it, the model still loads and every measure still evaluates — but **RLS silently fails open** (all 6,234 titles visible to every viewer), breaking FR-024/SC-006. This is the single highest-risk wiring detail in the model.

**A-5 — Blank-country titles.** 476 titles produce no `BridgeTitleCountry` row, so they are unreachable from `Users` and invisible under `Country Access` (C-014, FR-026). Unfiltered `Distinct Titles` still returns 6,234 (SC-005); per-user totals will not sum to 6,234 — documented, expected.

**A-6 — Unmapped identity.** `USERPRINCIPALNAME()` with no matching `Users` row leaves `Users` empty → `DimCountry` empty → bridge empty → `Titles` empty. Every measure returns `BLANK()`; visuals render empty rather than erroring (FR-027). ✅

**A-7 — No snowflaking.** `DimCountry` and `DimGenre` attach to the fact only through their bridges; no dimension attaches to another dimension. ✅

---

## DAX Column Coverage Audit

Every table/column referenced by `.specify/memory/NetflixRLS/dax-measures-output.md`:

| Reference | Provided by this schema | Note |
|---|---|---|
| `Titles[Show ID]` | ✅ | Hidden — legal for DAX. |
| `Titles[Type]` | ✅ | |
| `Titles[Title]` | ✅ | |
| `Titles[Director]` | ✅ | See R-1. |
| `Titles[Date Added]` | ✅ | |
| `Titles[Release Year]` | ✅ | |
| `Titles[Duration]` | ✅ | |
| `Titles[Genres]` | ✅ | Visible per FR-048. |
| `Titles[Description]` | ✅ | |
| **`Titles[Rating]`** | ✅ | ⚠ **Discrepancy flagged** — the DAX doc's own "Model context" table omits `Rating` from the `Titles` column list, yet `Selected Title Rating` evaluates `SELECTEDVALUE ( Titles[Rating] )`. This schema provides `Titles[Rating]` (hidden FK), so the measure resolves. `pbip-generator` must not drop it. |
| `DimCountry[Country]` | ✅ | |
| `DimGenre[Genre]` | ✅ | |
| `DimRating[Rating]` | ✅ | |
| `DimRating[Rating Category]` | ✅ | Calculated column. |
| `DimDate[Date]` | ✅ | |
| `DimDate[Year]` | ✅ | |
| `BridgeTitleCountry[Country]` | ✅ | Hidden — legal for DAX. |
| `BridgeTitleGenre[Genre]` | ✅ | Hidden — legal for DAX. |
| `Users[Username]`, `Users[Entitled Country]` | ✅ | Role only; referenced by no measure (FR-052). |

**Missing columns: none.** No measure references a column this schema does not provide.

---

## Open Risks / Notes for Downstream Stages

- **R-1 — `Director` (and `Cast`) are un-split multi-value strings.** `Distinct Directors` counts distinct *director lists*, not individuals. The DAX doc already carries a `-- REVIEW:` note. No `DimDirector` / `BridgeTitleDirector` is created because no Tableau worksheet uses `director` and the spec's FR-007 enumerates the model's tables exhaustively — adding one would violate FR-007. Revisit only if a later requirement demands per-person accuracy.
- **R-2 — `securityFilteringBehavior` on R1 and R3 is mandatory.** See A-4. Verify with "View as role" for all three identities (SC-006) — a role that returns the full 6,234 rows means this property is missing.
- **R-3 — Do not add `% of Titles by Country`.** It would need `ALLSELECTED(DimCountry[Country])`, which sits on the security chain. Already ruled out by the DAX doc's RLS Safety §3.
- **R-4 — `Show ID` type.** Source values (e.g. `81145628`) fit Int64. If `pbip-generator` prefers text keys, it must change the type identically on `Titles`, `BridgeTitleCountry` and `BridgeTitleGenre` or R3/R5 will fail to bind.
- **R-5 — No cross-table M references.** `DimCountry` unions data from *both CSVs* by reading both files directly inside its own query. It must **not** reference the `Titles` or `Users` queries, per the single-source key strategy — cross-table references are what produce "Load was cancelled" failures.

---

## Decomposition Notes

| Tableau source | Decomposed into |
|---|---|
| `netflix_titles.csv` (flat, 12 cols) | `Titles` (fact, 12 cols incl. parsed date) + `DimRating` + `DimGenre` + `DimCountry` (partial) + `DimDate` + `BridgeTitleCountry` + `BridgeTitleGenre` |
| `User_Access.csv` (2 cols) | `Users` (hidden security table) + `DimCountry` (union contribution) |
| Tableau logical relationship `netflix_titles.[country] = User_Access.[Country]` | Replaced by the four-hop chain R1 → R2 → R3. The literal equality was broken for multi-country titles (555 raw strings, most multi-valued); the bridge fixes it (A-003, FR-025). |
| Tableau `RLS` calculated field | **Not migrated** — replaced by the `Country Access` role (FR-028, C-015). |
| Tableau `Year` calculated field (`DATETIME([date_added])`) | Replaced by `Titles[Date Added]` (parsed in M) + `DimDate` (FR-004, FR-010). |
| Tableau `Year` parameter | **Not migrated** (FR-043, A-005). |
| `[Action (Country)]` auto-set | **Not migrated** — native cross-filtering (FR-044). |
