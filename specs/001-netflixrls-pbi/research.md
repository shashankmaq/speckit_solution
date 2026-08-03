# Phase 0 Research — NetflixRLS Migration

**Feature**: `001-netflixrls-pbi` | **Date**: 2026-08-03 | **Plan**: [plan.md](./plan.md)

Every NEEDS CLARIFICATION from the plan's Technical Context is resolved below. No open questions remain.

---

## R-01 — CSV reading pattern (`Csv.Document`)

**Decision**: Every table partition reads its source file directly with:

```m
Csv.Document(
    File.Contents( TitlesSourcePath ),
    [ Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv ]
)
```

followed by `Table.PromoteHeaders( Source, [PromoteAllScalars = true] )`.

**Rationale**:
- `QuoteStyle = QuoteStyle.Csv` is **mandatory**. `country`, `cast` and `listed_in` all contain commas *inside* quoted fields (`"United States, India, South Korea, China"`). The default `QuoteStyle.None` splits inside the quotes and shifts every subsequent column on those rows — a silent corruption that produces the right row count with the wrong data.
- `Encoding = 65001` (UTF-8) — title and cast values contain non-ASCII characters.
- Absolute paths live in two **scalar** M expressions in `expressions.tmdl`: `TitlesSourcePath` and `UserAccessSourcePath`, both pointing under `Data/Netflix RLS/` (§5, FR-001, FR-002). The authoring path recorded in the TWB (`.../semantic model generation v4/Data/Netflix RLS`) is **not** used.
- Neither expression name collides with a table name, avoiding the `duplicate member` load failure that the TMDL skill warns about (M expressions and tables share one namespace).
- Scalar expressions are not tables, so they cannot create a load cycle. **No query references another model query** — `DimCountry` reads both CSVs itself rather than referencing `Titles` or `Users` (star-schema R-5).

**Alternatives considered**:
- *Relative paths / a folder parameter* — rejected; §5 requires absolute paths detected from the workspace root.
- *One shared `Titles` query that other tables reference* — rejected; cross-query references are the documented cause of "Load was cancelled" failures in this pipeline.
- *`Csv.Document` with `Columns = 12`* — unnecessary once headers are promoted, and it would mask a source schema change rather than surface it.

---

## R-02 — Comma-split → expand → trim → dedupe

**Decision**: A single fixed step order, reused verbatim for `BridgeTitleCountry`, `BridgeTitleGenre`, `DimCountry` and `DimGenre`:

1. Read the CSV directly; keep only the key column(s) needed.
2. **Drop null/empty first** — `Table.SelectRows( t, each [country] <> null and Text.Trim([country]) <> "" )`.
3. `Table.TransformColumns( t, {{ "country", each Text.Split( _, "," ) }} )`.
4. `Table.ExpandListColumn( t, "country" )`.
5. `Table.TransformColumns( t, {{ "country", Text.Trim }} )` — **after** expansion.
6. Drop any value that trimmed to empty (guards against `"US,,India"` and trailing commas).
7. `Table.Distinct` — on both columns for a bridge, on the single column for a dimension.
8. `Table.TransformColumnTypes` with explicit types.

**Rationale**:
- Trimming **after** the expand is what turns `"United States, India"` into `India`, not `" India"`. Trimming the whole string before splitting would leave the interior leading spaces intact, producing two dimension members that differ only by a leading space — and silently breaking the RLS join for every country after the first in a list.
- Dropping blanks **before** splitting means the 476 blank-country rows produce zero bridge rows, which is exactly the mechanism that makes them invisible under RLS (C-014, FR-026, A-002). This is load-bearing behaviour, not an optimisation.
- `Table.Distinct` on `(Show ID, Country)` satisfies FR-009 — a title never appears twice for the same country, so a duplicated country in a source list cannot inflate a count.
- `DimCountry` additionally `Table.Combine`s the split catalogue countries with the trimmed `User_Access` countries before the `Table.Distinct`, satisfying FR-049 — every entitlement value resolves to a dimension row, now and for any future entitlement value.

**Expected cardinalities**: ~100–130 distinct countries; ~42 distinct genres; 15 distinct ratings.

**Alternatives considered**:
- *`Text.Split(_, ", ")` on the two-character separator* — rejected as brittle; the source is not guaranteed to use a space after every comma.
- *Splitting in DAX with `PATHITEM`* — rejected; it bloats the model and cannot produce a bridge table.
- *Keeping duplicates and relying on `DISTINCTCOUNT`* — rejected; FR-009 requires the bridge itself to be clean, and duplicates would distort `Distinct Countries`.

---

## R-03 — `date_added` en-US parsing

**Decision**:

```m
try Date.FromText( [date_added], [ Format = "MMMM d, yyyy", Culture = "en-US" ] ) otherwise null
```

applied via `Table.AddColumn` / `Table.TransformColumns`, then typed `type nullable date`.

**Rationale**:
- The source value is a **string** formatted `"September 9, 2019"`. A bare `Table.TransformColumnTypes( t, {{"date_added", type date}} )` uses the machine locale, so it fails outright on a non-US machine or, worse, transposes day and month where both are ≤12. FR-006 requires machine-independent determinism.
- `Format = "MMMM d, yyyy"` matches the source exactly — full month name, non-padded day, four-digit year.
- The `try … otherwise null` wrapper is what lets the **11 blank rows survive as null** instead of erroring the refresh (FR-005). Without it, `Date.FromText(null, …)` raises and the whole partition fails.
- Nulls land in `DimDate`'s auto-created blank member via R6; the `Titles Added` measure excludes them explicitly with `KEEPFILTERS( NOT ISBLANK( Titles[Date Added] ) )`, satisfying FR-034 without a report-layer filter.

**Alternatives considered**:
- *`Date.FromText(x, "en-US")` (culture-only overload)* — works for this format but is looser; pinning `Format` as well makes the intent explicit and rejects an unexpected format instead of guessing at it.
- *Replacing blanks with a sentinel date* — rejected outright by FR-005; a fabricated date would corrupt the by-year chart.
- *Parsing in DAX* — rejected; §5 puts type conversion in Power Query.

---

## R-04 — TMDL syntax and enum constraints

**Decision** — the authoring rules applied to every `.tmdl` file, from `plugins/pbip/skills/tmdl/SKILL.md`:

| Rule | Applied as |
|---|---|
| Indentation is semantic | One **tab** per nesting level (the TOM `TmdlSerializer` default). Table-level objects at depth 1, their properties at depth 2, multi-line DAX bodies **two levels deeper than their declaration** (depth 3 inside a table). |
| Descriptions | `///` immediately above the declaration, **no blank line between**, never used as a separator. `//` for ordinary comments. |
| Name quoting | Quote only names with spaces, special characters, or a leading digit: `'Show ID'`, `'Rating Category'`, `'% of Titles'`, `'Distinct Titles (Top 10 Genres)'`, `'Country Access'`. Leave `Titles`, `DimCountry`, `BridgeTitleGenre`, `Users` unquoted. |
| Property order | Columns: `dataType`, `isHidden`, `isKey`, `displayFolder`, `lineageTag`, `summarizeBy`, `sourceColumn`, `sortByColumn`, then annotations. Measures: expression, `formatString`, `displayFolder`, `lineageTag`, then annotations. |
| Namespace collision | `expression` names and `table` names share one namespace — `TitlesSourcePath` / `UserAccessSourcePath` verified distinct from all 8 table names. |

**Enum constraints (the load-breaking ones)**:

| Property | Valid tokens | Invalid |
|---|---|---|
| `crossFilteringBehavior` | `oneDirection`, `bothDirections`, `automatic` | ⚠ **`single`** — the Power BI **UI** word. Emitting it produces `InvalidValueFormat: Failed to convert the value 'single' to the expected type CrossFilteringBehavior` and the model fails to open with `DataModelLoadFailed`. |
| `securityFilteringBehavior` | `oneDirection`, `bothDirections`, `none` | anything else |
| `fromCardinality` / `toCardinality` | `many`, `one`, `none` | — |

**Rationale**: `single` is the single most likely enum mistake because it is the word the Power BI Desktop relationship dialog displays. The generator must normalise at the TMDL writer choke point so no code path can emit it.

**Alternatives considered**: *Space indentation* — valid TMDL (`IndentationMode.Spaces`, 4 per level) but inconsistent with the rest of the workspace and with what Power BI Desktop rewrites on save; rejected for consistency.

---

## R-05 — Roles TMDL shape

**Decision**: `definition/roles/CountryAccess.tmdl` containing exactly one role, one `modelPermission`, one `tablePermission`:

```tmdl
/// Dynamic row-level security: each viewer sees only the countries mapped to their principal name.
role 'Country Access'
	modelPermission: read

	tablePermission Users = [Username] = USERPRINCIPALNAME()
```

**Rationale**:
- `tablePermission` nests inside `role`; `columnPermission` would nest inside `tablePermission` and is not used (no object-level security required).
- The filter is placed on the **mapping table only** (C-012, FR-022). Every other table is secured by relationship propagation, which is why every measure is secured automatically without any per-measure work (FR-024).
- The expression uses the *unqualified* `[Username]` form, which is the conventional shape for a table permission and is unambiguous inside `tablePermission Users`.
- **No `member` entries.** Role membership is assigned in the Power BI Service, not in the project file — and emitting a member would put a literal identity into the artefacts, violating FR-023 / SC-008.
- DAX `=` is case-insensitive, so FR-029 is satisfied without wrapping either side in `LOWER()`. Adding `LOWER()` would also defeat any query folding and add no correctness.
- The file name (`CountryAccess.tmdl`) has no space; the role **name** (`'Country Access'`) does and is therefore quoted.

**Alternatives considered**:
- *`USERNAME()` instead of `USERPRINCIPALNAME()`* — rejected; `USERNAME()` returns a domain-qualified name in Desktop and a UPN in the Service, so it is inconsistent across environments. The entitlement values are e-mail-style, which matches `USERPRINCIPALNAME()` (A-004).
- *Filtering `DimCountry` or `Titles` directly* — rejected; it would require the role to know the country list, breaking the dynamic design and duplicating the entitlement logic.
- *Multiple roles, one per country* — rejected; static roles do not scale and would hardcode country names, defeating the whole purpose of the entitlement table.

---

## R-06 — `DimDate` generation

**Decision**: `DimDate` is generated in M from the parsed `date_added` values, with bounds **computed, never hardcoded**:

```m
Parsed   = the same try/Date.FromText step as R-03, over netflix_titles.csv
NonNull  = List.RemoveNulls( Parsed )
Start    = Date.StartOfYear( List.Min( NonNull ) )
End      = Date.EndOfYear(   List.Max( NonNull ) )
Dates    = List.Dates( Start, Duration.Days( End - Start ) + 1, #duration(1,0,0,0) )
```

then `Table.FromList` and added columns: `Year`, `Quarter` / `Quarter Number`, `Month` / `Month Number`, `Year Month` / `Year Month Number`, `Day`, `Day of Week` / `Day of Week Number`, `Week Number`.

**Rationale**:
- Bounds are computed from the data (FR-006 determinism). The observed range is 2008–2020, but hardcoding it would silently truncate the calendar if the CSV is ever refreshed with newer titles.
- `Date.StartOfYear` / `Date.EndOfYear` expand to whole calendar years (C-008), so a year axis never shows a partial first or last year.
- **Locale is pinned**: `Date.MonthName( d, "en-US" )` and `Date.DayOfWeekName( d, "en-US" )`. Without the culture argument these return localised names on a non-US machine — the same class of bug as R-03, but in labels rather than values.
- Every text label has a numeric sort companion (`Month` → `Month Number`, etc.) wired via `sortByColumn`, which is what makes years and months sort chronologically rather than alphabetically (User Story 4).
- The table is marked as the model's date table (`dataCategory: Time` with `isKey` on `Date`), satisfying §1 and FR-010.
- The sort-helper columns are hidden; only the display columns are visible.

**Alternatives considered**:
- *`CALENDARAUTO()` in DAX* — rejected; it would scan `Titles[Release Year]` too (1925–2020) and generate ~35,000 rows covering a century of irrelevant dates.
- *A hardcoded 2008-01-01 → 2020-12-31 range* — rejected by FR-006.
- *Day-level only, deriving Year/Quarter/Month in DAX* — rejected; §1 wants a full date dimension, and DAX-derived columns would still need sort-by companions.

---

## Cross-cutting decisions

| Question | Decision | Rationale |
|---|---|---|
| `Show ID` data type | **Int64** on `Titles`, `BridgeTitleCountry` and `BridgeTitleGenre` — all three identical | Source values (e.g. `81145628`) fit Int64. A type mismatch on any one table makes R3 or R5 fail to bind (star-schema R-4). |
| Case-only `country` / `Country` collision | Three distinct names: `Titles[Country List]` (hidden), `DimCountry[Country]`, `Users[Entitled Country]` | FR-011. A case-only difference produces ambiguous references and silent mis-binding. |
| `Titles[Rating]` retention | **Kept** as a hidden FK column | `Selected Title Rating` evaluates `SELECTEDVALUE( Titles[Rating] )`. Hidden ≠ unavailable to DAX. The DAX document's own model-context table omits it — that omission is the error, not the schema. |
| `Director` / `Cast` remain un-split | Accepted, with the existing `-- REVIEW:` note on `Distinct Directors` | No Tableau worksheet uses `director`, and FR-007 enumerates the model's tables exhaustively — adding `DimDirector` would violate it (star-schema R-1). |
| Report format | PBIR enhanced (folder-per-visual) | Matches the workspace validators and skills; MAX_PATH margin verified safe with the short `NetflixRLS` / `Netflix` names. |
