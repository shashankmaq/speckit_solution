# DAX Measures & Calculations — NetflixRLS

- **Workbook**: `Data/Netflix RLS/Netfix Workbook rls.twb`
- **Source analysis**: `.specify/memory/NetflixRLS/tableau-analysis-output.md`
- **Spec (authoritative names)**: `specs/001-netflixrls-pbi/spec.md` (Clarifications C-001…C-015)
- **Rulebook**: `.specify/memory/constitution.md` §3
- **Generated**: 2026-08-03

## Model context used (confirmed against spec Clarifications)

| Table | Role | Key columns referenced by DAX |
|---|---|---|
| `Titles` | Fact/detail, grain = 1 row per title (C-001) | `Show ID`, `Type`, `Title`, `Director`, `Date Added`, `Release Year`, `Duration`, `Genres`, `Description` |
| `DimCountry` | Country dimension (C-003, C-007) | `Country` |
| `DimGenre` | Genre dimension (C-004) | `Genre` |
| `DimRating` | Rating dimension (C-005) | `Rating`, `Rating Category` (calculated column) |
| `DimDate` | Marked date table (C-008) | `Date`, `Year` |
| `BridgeTitleCountry` | Title × Country bridge (C-003) | `Show ID`, `Country` |
| `BridgeTitleGenre` | Title × Genre bridge (C-004) | `Show ID`, `Genre` |
| `Users` | Hidden entitlement table (C-001, C-012, FR-052) | `Username`, `Entitled Country` — **never referenced by any measure** |

**Home table for every measure**: `Titles`. FR-007 enumerates the model's tables exhaustively, so no extra `_Measures` table is introduced.

---

## Measures

| Tableau Field / Usage | DAX Measure Name | DAX Expression | Home Table | Display Folder | Format String | Description |
|---|---|---|---|---|---|---|
| `COUNTD([show_id])` — all 9 worksheets (FR-016) | `Distinct Titles` | `DISTINCTCOUNT ( Titles[Show ID] )` | `Titles` | `Title Counts` | `#,##0` | Distinct count of Netflix titles. Distinct-counting the title key keeps a multi-country / multi-genre title at 1 across the bridge tables (FR-021). |
| `COUNTD([show_id])` filtered to `type = "Movie"` (worksheet *Movies and TV Shows distribution*) | `Movie Titles` | `VAR Result =`<br>`CALCULATE ( [Distinct Titles], KEEPFILTERS ( Titles[Type] = "Movie" ) )`<br>`RETURN`<br>`    Result` | `Titles` | `Title Counts` | `#,##0` | Distinct titles of type Movie. `KEEPFILTERS` preserves any existing Type slicer selection. |
| `COUNTD([show_id])` filtered to `type = "TV Show"` (same worksheet) | `TV Show Titles` | `VAR Result =`<br>`CALCULATE ( [Distinct Titles], KEEPFILTERS ( Titles[Type] = "TV Show" ) )`<br>`RETURN`<br>`    Result` | `Titles` | `Title Counts` | `#,##0` | Distinct titles of type TV Show. |
| `COUNTD([show_id])` with `date_added` ≠ null (worksheet *Total Movies and TV Shows by Years*, FR-034) | `Titles Added` | `VAR Result =`<br>`CALCULATE (`<br>`    [Distinct Titles],`<br>`    KEEPFILTERS ( NOT ISBLANK ( Titles[Date Added] ) )`<br>`)`<br>`RETURN`<br>`    Result` | `Titles` | `Time` | `#,##0` | Distinct titles added to the catalogue in the current date context, excluding the 11 rows with no added date. Used on the titles-by-year area chart. |
| `COUNTD([show_id])` on *Country wise distribution* (supporting) | `Distinct Countries` | `DISTINCTCOUNT ( BridgeTitleCountry[Country] )` | `Titles` | `Catalogue Coverage` | `#,##0` | Number of distinct production countries represented by the visible titles. Counted on the bridge so it reflects the current title selection. |
| `COUNTD([show_id])` on *Top 10 Genre* / *Genre* card (supporting) | `Distinct Genres` | `DISTINCTCOUNT ( BridgeTitleGenre[Genre] )` | `Titles` | `Catalogue Coverage` | `#,##0` | Number of distinct genres represented by the visible titles. |
| `director` column (supporting) | `Distinct Directors` | `DISTINCTCOUNT ( Titles[Director] )`<br>`-- REVIEW: [director] is an un-split comma-separated string in the source; this counts distinct director *lists*, not individuals. Split into a bridge if per-person accuracy is required.` | `Titles` | `Catalogue Coverage` | `#,##0` | Distinct director values in the current context. See the REVIEW note — the source column is multi-value. |
| `release_year` (supporting) | `Average Release Year` | `AVERAGE ( Titles[Release Year] )` | `Titles` | `Release Year` | `0.0` | Mean release year of the titles in context. |
| `release_year` (supporting) | `Earliest Release Year` | `MIN ( Titles[Release Year] )` | `Titles` | `Release Year` | `0` | Oldest release year in context (source range starts at 1925). |
| `release_year` (supporting) | `Latest Release Year` | `MAX ( Titles[Release Year] )` | `Titles` | `Release Year` | `0` | Newest release year in context (source range ends at 2020). |
| `[pcto:ctd:show_id:qk]` — Percent of Total of `COUNTD(show_id)` on *Movies and TV Shows distribution* (FR-017, C-010) | `% of Titles` | `VAR CurrentTitles = [Distinct Titles]`<br>`VAR AllTypeTitles =`<br>`    CALCULATE ( [Distinct Titles], ALLSELECTED ( Titles[Type] ) )`<br>`RETURN`<br>`    DIVIDE ( CurrentTitles, AllTypeTitles )` | `Titles` | `Distribution` | `0.0%` | Share of visible titles held by the current title type. Denominator removes only the Type grouping, so the total follows the visual's own selection (never a hardcoded value). |
| Variant of the above for the *Ratings* column chart | `% of Titles by Rating` | `VAR CurrentTitles = [Distinct Titles]`<br>`VAR AllRatingTitles =`<br>`    CALCULATE ( [Distinct Titles], ALLSELECTED ( DimRating[Rating] ) )`<br>`RETURN`<br>`    DIVIDE ( CurrentTitles, AllRatingTitles )` | `Titles` | `Distribution` | `0.0%` | Share of visible titles held by the current rating. |
| Variant of the above for the *Top 10 Genre* bar chart | `% of Titles by Genre` | `VAR CurrentTitles = [Distinct Titles]`<br>`VAR AllGenreTitles =`<br>`    CALCULATE ( [Distinct Titles], ALLSELECTED ( DimGenre[Genre] ) )`<br>`RETURN`<br>`    DIVIDE ( CurrentTitles, AllGenreTitles )` | `Titles` | `Distribution` | `0.0%` | Share of visible titles held by the current genre. A title in three genres contributes to all three, so genre shares sum above 100% (A-009). |
| Top 10 `listed_in` by `COUNTD(show_id)` desc (FR-050, C-011) | `Genre Rank` | `VAR CurrentTitles = [Distinct Titles]`<br>`VAR Result =`<br>`    IF (`<br>`        NOT ISBLANK ( CurrentTitles ),`<br>`        RANKX ( ALLSELECTED ( DimGenre[Genre] ), [Distinct Titles],, DESC, DENSE )`<br>`    )`<br>`RETURN`<br>`    Result` | `Titles` | `Ranking` | `0` | Rank of the current genre by distinct title count, descending, within the current selection. Blank for genres with no visible titles. |
| Top 10 filter materialised in DAX (FR-050, FR-033) | `Distinct Titles (Top 10 Genres)` | `VAR CurrentRank = [Genre Rank]`<br>`VAR Result =`<br>`    IF ( CurrentRank <= 10, [Distinct Titles] )`<br>`RETURN`<br>`    Result` | `Titles` | `Ranking` | `#,##0` | Distinct titles for genres ranked 1–10 only; blank otherwise. Reproduces the Tableau Top-10 worksheet filter without a `filters` property in the visual JSON. |
| Worksheet *Description* (detail card, `type` + `title` slicers) | `Selected Title Description` | `SELECTEDVALUE ( Titles[Description], "Select a single title" )` | `Titles` | `Selected Title` | _(text — none)_ | Description of the single selected title; prompt text when zero or multiple titles are selected. |
| Worksheet *Duration* (detail card) | `Selected Title Duration` | `SELECTEDVALUE ( Titles[Duration], "Select a single title" )` | `Titles` | `Selected Title` | _(text — none)_ | Duration of the single selected title. |
| Worksheet *Genre* (detail card, renders raw `listed_in`) | `Selected Title Genres` | `SELECTEDVALUE ( Titles[Genres], "Select a single title" )` | `Titles` | `Selected Title` | _(text — none)_ | Raw genre list of the single selected title, rendered verbatim as in Tableau (C-006). |
| Worksheet *Rating* (detail card) | `Selected Title Rating` | `SELECTEDVALUE ( Titles[Rating], "Select a single title" )` | `Titles` | `Selected Title` | _(text — none)_ | Rating of the single selected title. |

> **Format-string provenance**: the source workbook records `Default` for every field — no Tableau `default-format` or `<format>` entry exists. The format strings above are Power BI model defaults chosen for integer counts, percentages and ranks per the requirement for explicit formats; none were inferred from a Tableau format that does not exist. Text measures carry no `formatString`.

---

## Calculated Columns

| Column Name | Table | DAX Expression | Description | Source (Tableau) |
|---|---|---|---|---|
| `Rating Category` | `DimRating` | `SWITCH (`<br>`    TRUE (),`<br>`    DimRating[Rating] IN { "G", "TV-G", "TV-Y", "TV-Y7", "TV-Y7-FV" }, "Kids",`<br>`    DimRating[Rating] IN { "PG", "PG-13", "TV-PG", "TV-14" }, "Teens",`<br>`    DimRating[Rating] IN { "R", "NC-17", "TV-MA" }, "Adults",`<br>`    "Unrated"`<br>`)` | Groups the 15 source ratings into Kids / Teens / Adults / Unrated. The only calculated column in the model (C-005, FR-046, exception A-014); everything else is a measure per FR-051. | Derived — no Tableau group existed (`Groups` section of the analysis is empty). Approved by C-005. |

> `-- REVIEW:` any source rating outside the listed members (including blank) falls into `Unrated`. Verify the 15 distinct values after the first refresh and extend the `IN` lists if a value lands in `Unrated` unintentionally.

---

## What-If Parameters

| Parameter Name | Min | Max | Step | Default | DAX Measure |
|---|---|---|---|---|---|
| _(none)_ | — | — | — | — | — |

The only Tableau parameter is `Year` (date, default `#2024-03-26#`), which is referenced by **no** worksheet, filter or calculation. FR-043 / A-005 explicitly exclude it. Per the constitution's parameter policy a date parameter would map to a slicer on `DimDate` anyway — not a What-If table.

---

## Not Migrated

| Tableau Object | Decision | Authority |
|---|---|---|
| `RLS` calculated field (`Calculation_0182254345785358`) | **Not migrated in any form** — no measure, no calculated column, no role expression, no report artefact. The formula self-compares `[country]` to itself and hardcodes `user2@maq.com`. | FR-028, C-015, A-001 |
| `user2@maq.com` (and any literal identity) | Never emitted. Verified by text search for `@maq.com` returning zero hits in the model definition. | FR-023, SC-008 |
| `Year` calculated field — `DATETIME([date_added])` | **Not a measure.** Handled as data loading + modelling: `date_added` is parsed to a real date in Power Query with an explicit `en-US` `"MMMM d, yyyy"` locale, exposed as `Titles[Date Added]`, and all year grouping is routed through `DimDate`. | C-008, FR-004, FR-010 |
| `[Action (Country)]` auto-generated set | Not a user-defined set; native cross-filtering satisfies it. No DAX. | FR-044 |
| Sets / Groups / Bins | The analysis records **None** for all three, so none were generated. | Analysis §Sets/Groups/Bins |
| Data blending | Single federated datasource — no blend, no DAX. | Analysis §Data Blending |
| `% of Titles by Country` | **Deliberately not created** — see RLS Safety note 3. | This document |

---

## RLS Safety

The role `Country Access` filters **only** `Users[Username] = USERPRINCIPALNAME()` (C-012). That filter reaches the fact by ordinary relationship propagation:

`Users` → `DimCountry` → `BridgeTitleCountry` → `Titles`

Because the chain is relationship propagation (not a filter applied directly to `Titles`), a measure that removes filters from **any table on that chain** would leak rows the role is meant to hide. The rules below were applied to every measure above.

### 1. Table-scoped filter removal is banned on the security chain

No measure uses `ALL(...)`, `ALLEXCEPT(...)` or `REMOVEFILTERS(...)` against `Users`, `DimCountry`, `BridgeTitleCountry` or `Titles` — as a whole table or on any of their key columns (`DimCountry[Country]`, `BridgeTitleCountry[Country]`, `BridgeTitleCountry[Show ID]`, `Titles[Show ID]`). Doing so would drop the propagated entitlement filter and expose every country's titles.

### 2. Only column-scoped `ALLSELECTED` on non-security columns is used

| Measure | Filter-removal call | Column scope | Verdict |
|---|---|---|---|
| `% of Titles` | `ALLSELECTED ( Titles[Type] )` | Type only | **Safe** — `Type` is not on the security chain; the country filter survives. |
| `% of Titles by Rating` | `ALLSELECTED ( DimRating[Rating] )` | Rating only | **Safe** — `DimRating → Titles` is single-direction and carries no entitlement. |
| `% of Titles by Genre` | `ALLSELECTED ( DimGenre[Genre] )` | Genre only | **Safe** — the genre bridge is bi-directional but independent of the country chain. |
| `Genre Rank` | `ALLSELECTED ( DimGenre[Genre] )` | Genre only | **Safe** — same as above. |
| `Distinct Titles (Top 10 Genres)` | _(inherits `Genre Rank`)_ | — | **Safe**. |
| All other measures | _(none)_ | — | **Safe** — pure filter-context measures. |

No measure uses the no-argument form `ALLSELECTED()`; its interaction with a bridge-propagated entitlement chain is not worth the ambiguity when a column-scoped form expresses the same intent.

### 3. Intentional omission: no country-level percent-of-total

A `% of Titles by Country` measure would need `ALLSELECTED ( DimCountry[Country] )`, which sits directly on the security chain. Under the role, a viewer is entitled to exactly one country, so the measure would either return a constant 100% (harmless but useless) or, if written with `REMOVEFILTERS`, leak the unsecured total. The Tableau workbook never used percent-of-total on the country map, so it was not created. **If a later stage needs it, it must be reviewed against the role before being added.**

### 4. Measures that intentionally ignore filters

**None.** Every measure above is fully filter-context driven. There is no unfiltered-grand-total measure, no "All Titles" constant, and no `REMOVEFILTERS` anywhere in the model's DAX.

### 5. Consequences to expect (documented, not defects)

- Unfiltered `Distinct Titles` = **6,234** (SC-005). Under `Country Access`, per-user totals will **not** sum to 6,234 — the 476 blank-country titles produce no bridge row and are invisible to every secured viewer (C-014, A-002).
- A title listing four countries is visible to all four entitled viewers and counted as **1** by `Distinct Titles` for each (SC-007, FR-021, FR-025).
- An identity absent from `Users` sees an empty result set; every measure returns `BLANK()` rather than an error (FR-027) — `DIVIDE` guarantees the percentage measures return blank rather than a divide-by-zero (FR-018).

---

## Compliance Checklist (constitution §3)

| Rule | Status |
|---|---|
| `DIVIDE()` used for all division — no `/` operator | ✅ 3 of 3 percentage measures |
| `VAR` / `RETURN` for readability and single evaluation | ✅ every non-trivial measure |
| No measure referenced inside a `CALCULATE` boolean filter (FR-020) | ✅ `Movie Titles`, `TV Show Titles`, `Titles Added` filter on columns only; `Distinct Titles (Top 10 Genres)` captures `[Genre Rank]` in a `VAR` before comparing |
| `DISTINCTCOUNT` for `COUNTD` | ✅ |
| `SELECTEDVALUE()` rather than `VALUES()` for single-value retrieval | ✅ 4 detail-card measures |
| `ISBLANK()` rather than `= BLANK()` | ✅ `Titles Added`, `Genre Rank` |
| `KEEPFILTERS()` to preserve slicer context | ✅ `Movie Titles`, `TV Show Titles`, `Titles Added` |
| Fully qualified columns, unqualified measure references | ✅ |
| Description on every measure | ✅ 19 of 19 |
| Display folder on every measure | ✅ `Title Counts`, `Time`, `Catalogue Coverage`, `Release Year`, `Distribution`, `Ranking`, `Selected Title` |
| Explicit format string on every numeric measure | ✅ (text measures intentionally have none) |
| Measures preferred over calculated columns (FR-051) | ✅ 19 measures, 1 calculated column (the C-005 exception) |
| No reference to the removed `RLS` field or any literal identity | ✅ |
