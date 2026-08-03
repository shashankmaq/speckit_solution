# Phase 1 Data Model — NetflixRLS

**Feature**: `001-netflixrls-pbi` | **Date**: 2026-08-03 | **Plan**: [plan.md](./plan.md)
**Derived from**: `.specify/memory/NetflixRLS/star-schema-output.md` and `.specify/memory/NetflixRLS/dax-measures-output.md`

8 tables · 7 relationships · 19 measures · 1 calculated column · 1 role. Natural keys only.

```
                      Users (hidden)
                        │  Entitled Country   R1: *→1  cross=BOTH  security=BOTH
                        ▼
DimRating ──R7 1→*── Titles ──R3 *→1── BridgeTitleCountry ──R2 *→1── DimCountry
                       │      (cross=BOTH, security=BOTH)   (oneDirection)
DimDate ──R6 1→*───────┤
                       └──R5 *→1── BridgeTitleGenre ──R4 *→1── DimGenre
                          (cross=BOTH, security=one)    (oneDirection)
```

8 nodes / 7 edges, connected and acyclic ⇒ **spanning tree**: exactly one path between any pair of tables, no ambiguity, no inactive relationships, no `USERELATIONSHIP`.

---

## Fact: `Titles`

- **Grain**: one row per title — 6,234 rows, keyed by `Show ID` (C-001, FR-007)
- **Source**: `netflix_titles.csv`, read directly
- **Home table for all 19 measures**

| Column | Type | Source | Hidden | Key | Notes |
|---|---|---|---|---|---|
| `Show ID` | Int64 | `show_id` | Yes | `isKey` | Natural PK. `summarizeBy: none`. Hidden per FR-013 but referenced by `Distinct Titles`. |
| `Type` | String | `type` | No | | `Movie` / `TV Show`. Slicer + `% of Titles`. |
| `Title` | String | `title` | No | | Slicer; drives the four detail cards. |
| `Director` | String | `director` | No | | ⚠ un-split multi-value list (R-1). |
| `Cast` | String | `cast` | No | | ⚠ un-split multi-value list. |
| `Country List` | String | `country` | **Yes** | | Raw multi-value string. Hidden by FR-048/C-006 so it can never be sliced. Name deliberately distinct from `DimCountry[Country]` and `Users[Entitled Country]` (FR-011). |
| `Date Added` | Date (nullable) | `date_added` parsed | No | FK → `DimDate[Date]` | 11 nulls preserved (FR-005). |
| `Release Year` | Int64 | `release_year` | No | | `summarizeBy: none` — a year label, not an additive value. Range 1925–2020. |
| `Rating` | String | `rating` | **Yes** | FK → `DimRating[Rating]` | **Must be retained** — `Selected Title Rating` references it. |
| `Duration` | String | `duration` | No | | Mixed units (`90 min` / `2 Seasons`); text, rendered verbatim. |
| `Genres` | String | `listed_in` | **No** | | Raw multi-value string kept **visible** (FR-048/C-006) — the genre detail card renders it verbatim. Grouping must use `DimGenre`. |
| `Description` | String | `description` | No | | Detail card. |

---

## Dimensions

### `DimCountry`

| Column | Type | Hidden | Key | Data category |
|---|---|---|---|---|
| `Country` | String | No | `isKey` | **Country/Region** (FR-047, C-007) |

Distinct **union** of the split catalogue countries and the entitlement countries (FR-049) — reads both CSVs directly inside its own query. ~100–130 rows. Bound to the map visual (FR-038). No sub-national/state role carried over.

### `DimGenre`

| Column | Type | Hidden | Key |
|---|---|---|---|
| `Genre` | String | No | `isKey` |

Distinct split of `listed_in`, ~42 rows. Axis of the Top-10 bar chart; scope column for `Genre Rank` and `% of Titles by Genre`.

### `DimRating`

| Column | Type | Hidden | Key | Notes |
|---|---|---|---|---|
| `Rating` | String | No | `isKey` | 15 distinct values. Axis of the *Ratings* column chart. |
| `Rating Category` | String | No | | **Calculated column** — the model's only one (FR-046, C-005, exception A-014). `SWITCH(TRUE(), …)` grouping into Kids / Teens / Adults / Unrated. |

### `DimDate` — marked as the model's date table (`dataCategory: Time`)

| Column | Type | Hidden | Sort by |
|---|---|---|---|
| `Date` | Date | No | — (`isKey`) |
| `Year` | Int64 | No | — |
| `Quarter` | String | No | `Quarter Number` |
| `Quarter Number` | Int64 | **Yes** | — |
| `Month` | String | No | `Month Number` |
| `Month Number` | Int64 | **Yes** | — |
| `Year Month` | String | No | `Year Month Number` |
| `Year Month Number` | Int64 | **Yes** | — |
| `Day` | Int64 | No | — |
| `Day of Week` | String | No | `Day of Week Number` |
| `Day of Week Number` | Int64 | **Yes** | — |
| `Week Number` | Int64 | No | — |

Hierarchy `Calendar`: `Year` → `Quarter` → `Month` → `Date`. Range computed from the observed min/max added-date, expanded to whole calendar years (FR-006, FR-010).

---

## Bridges (both tables entirely hidden — FR-013)

### `BridgeTitleCountry`

| Column | Type | Hidden | Notes |
|---|---|---|---|
| `Show ID` | Int64 | Yes | FK → `Titles[Show ID]` |
| `Country` | String | Yes | FK → `DimCountry[Country]`. Referenced by `Distinct Countries`. |

One row per title × country; composite uniqueness guaranteed by `Table.Distinct` (FR-009). **Titles with a blank `country` produce ZERO rows** — this is the mechanism that makes those 476 titles invisible under RLS (C-014, FR-026, A-002).

### `BridgeTitleGenre`

| Column | Type | Hidden | Notes |
|---|---|---|---|
| `Show ID` | Int64 | Yes | FK → `Titles[Show ID]` |
| `Genre` | String | Yes | FK → `DimGenre[Genre]`. Referenced by `Distinct Genres`. |

---

## Security table: `Users` — **table hidden AND every column hidden** (FR-052)

| Column | Type | Source | Hidden | Notes |
|---|---|---|---|---|
| `Username` | String | `Username` | Yes | Compared to `USERPRINCIPALNAME()`. DAX `=` is case-insensitive ⇒ FR-029 without `LOWER()`. |
| `Entitled Country` | String | `Country` | Yes | Renamed to remove the case-only collision (FR-011, C-003). FK → `DimCountry[Country]`. |

3 rows. Never an analytical dimension; never in a slicer. **No literal identity is ever emitted into any artefact** (FR-023, C-015, SC-008).

---

## Relationships

| # | From (many) | To (one) | `fromCardinality` → `toCardinality` | `crossFilteringBehavior` | `securityFilteringBehavior` | Active |
|---|---|---|---|---|---|---|
| R1 | `Users[Entitled Country]` | `DimCountry[Country]` | many → one | **`bothDirections`** | **`bothDirections`** ⚠ | Yes |
| R2 | `BridgeTitleCountry[Country]` | `DimCountry[Country]` | many → one | `oneDirection` | `oneDirection` | Yes |
| R3 | `BridgeTitleCountry[Show ID]` | `Titles[Show ID]` | many → one | **`bothDirections`** | **`bothDirections`** ⚠ | Yes |
| R4 | `BridgeTitleGenre[Genre]` | `DimGenre[Genre]` | many → one | `oneDirection` | `oneDirection` | Yes |
| R5 | `BridgeTitleGenre[Show ID]` | `Titles[Show ID]` | many → one | `bothDirections` | `oneDirection` | Yes |
| R6 | `Titles[Date Added]` | `DimDate[Date]` | many → one | `oneDirection` | `oneDirection` | Yes |
| R7 | `Titles[Rating]` | `DimRating[Rating]` | many → one | `oneDirection` | `oneDirection` | Yes |

> **`oneDirection` — never `single`.** The UI word `single` is invalid TMDL and causes `DataModelLoadFailed`.

> ⚠ **R1 and R3 require `securityFilteringBehavior: bothDirections`.** Bi-directional *cross*-filtering alone does not carry an RLS filter. Omit it and RLS fails open — all 6,234 titles visible to everyone, with every validator still green.

**Why R2 and R4 stay one-directional**: making `BridgeTitleCountry → DimCountry` bi-directional would let a fact-side filter travel back into `Users`, and combined with R1's bi-directional security filtering that creates a filter loop through the secured chain (ambiguity warnings or silent over-filtering). Accepted consequence: a `Titles[Type]` slicer does not shrink the country list on the map; unmatched countries render blank rather than disappearing.

---

## RLS role

| Role | Kind | Table | Filter |
|---|---|---|---|
| `Country Access` | Dynamic | `Users` | `[Username] = USERPRINCIPALNAME()` |

Propagation: `Users` —R1→ `DimCountry` —R2→ `BridgeTitleCountry` —R3→ `Titles` → (R5 → `BridgeTitleGenre` → `DimGenre`; R6 → `DimDate`; R7 → `DimRating`).

Because `Titles` is secured by propagation rather than a direct filter, **every measure is secured automatically** (FR-024).

---

## Measures (19) — all on `Titles`

| Display folder | Measure | Format |
|---|---|---|
| Title Counts | `Distinct Titles` | `#,##0` |
| Title Counts | `Movie Titles` | `#,##0` |
| Title Counts | `TV Show Titles` | `#,##0` |
| Time | `Titles Added` | `#,##0` |
| Catalogue Coverage | `Distinct Countries` | `#,##0` |
| Catalogue Coverage | `Distinct Genres` | `#,##0` |
| Catalogue Coverage | `Distinct Directors` | `#,##0` |
| Release Year | `Average Release Year` | `0.0` |
| Release Year | `Earliest Release Year` | `0` |
| Release Year | `Latest Release Year` | `0` |
| Distribution | `% of Titles` | `0.0%` |
| Distribution | `% of Titles by Rating` | `0.0%` |
| Distribution | `% of Titles by Genre` | `0.0%` |
| Ranking | `Genre Rank` | `0` |
| Ranking | `Distinct Titles (Top 10 Genres)` | `#,##0` |
| Selected Title | `Selected Title Description` | _(text — none)_ |
| Selected Title | `Selected Title Duration` | _(text — none)_ |
| Selected Title | `Selected Title Genres` | _(text — none)_ |
| Selected Title | `Selected Title Rating` | _(text — none)_ |

Full DAX is owned by `.specify/memory/NetflixRLS/dax-measures-output.md` and must be transcribed verbatim. Every measure carries a `///` description.

**RLS safety invariants** (already satisfied by the DAX contract, re-assert on any future edit):
- No `ALL` / `ALLEXCEPT` / `REMOVEFILTERS` against `Users`, `DimCountry`, `BridgeTitleCountry` or `Titles`, nor any of their key columns.
- Only **column-scoped** `ALLSELECTED` on non-security columns (`Titles[Type]`, `DimRating[Rating]`, `DimGenre[Genre]`).
- No bare `ALLSELECTED()`.
- No `% of Titles by Country` — it would need `ALLSELECTED(DimCountry[Country])`, which sits on the security chain.

---

## Validation rules encoded in this model

| Rule | Where enforced |
|---|---|
| Distinct title count = 6,234 unfiltered | `DISTINCTCOUNT(Titles[Show ID])` over a 1-row-per-title fact — a multi-country title still counts 1 (FR-021, SC-005) |
| 11 blank added-dates survive | `try … otherwise null` in M (FR-005); excluded from the year chart by `Titles Added` (FR-034) |
| 476 blank-country titles invisible under RLS | Zero bridge rows (C-014, FR-026) |
| Multi-country title visible to every entitled viewer | Bridge row per country (FR-025, SC-007) |
| Unmapped identity sees nothing, errors nothing | Empty `Users` cascades; `DIVIDE` returns blank not infinity (FR-027, FR-018) |
| No identity leakage | No `member` entries, no literal in any expression (FR-023, SC-008) |
| Every FK resolves | `DimCountry` is a union of both sources; `DimGenre`/`DimRating` derived from the columns they key; `DimDate` spans whole years (FR-015) |
