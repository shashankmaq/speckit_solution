# Model Contract — Names the Report Layer MUST Bind To

**Feature**: `001-netflixrls-pbi` | **Date**: 2026-08-03 | **Plan**: [../plan.md](../plan.md)

This is the **frozen name list** for the NetflixRLS semantic model. It is the interface between the semantic-model layer (TMDL) and the report layer (PBIR).

> **Ordering constraint**: no `visual.json` may be written until the semantic model passes Validation Gates A and B, and this contract has been reconciled against the emitted TMDL files. A PBIR binding is a plain string that nothing validates against the model — a typo, a case difference, or a post-hoc rename produces a blank or erroring visual that only surfaces when the project is opened in Power BI Desktop.

---

## Table names (8) — exact, case-sensitive

`Titles` · `DimCountry` · `DimDate` · `DimGenre` · `DimRating` · `BridgeTitleCountry` · `BridgeTitleGenre` · `Users`

---

## Column names bindable from the report

| Table | Column | Bindable from report? | Note |
|---|---|---|---|
| `Titles` | `Type` | ✅ | Slicer, donut legend, area-chart legend |
| `Titles` | `Title` | ✅ | Slicer |
| `Titles` | `Director` | ✅ | Not used by any visual |
| `Titles` | `Cast` | ✅ | Not used by any visual |
| `Titles` | `Date Added` | ✅ | Prefer `DimDate` for grouping |
| `Titles` | `Release Year` | ✅ | Not used by the migrated page |
| `Titles` | `Duration` | ✅ | Card renders the measure, not the column |
| `Titles` | `Genres` | ✅ | Raw multi-value string — display only, never group by it |
| `Titles` | `Description` | ✅ | Card renders the measure, not the column |
| `Titles` | `Show ID` | ❌ hidden | DAX only |
| `Titles` | `Country List` | ❌ hidden | **Never bind.** Use `DimCountry[Country]` |
| `Titles` | `Rating` | ❌ hidden | DAX only. Use `DimRating[Rating]` on the axis |
| `DimCountry` | `Country` | ✅ | **Map binding** (Country/Region) |
| `DimGenre` | `Genre` | ✅ | Top-10 bar chart axis |
| `DimRating` | `Rating` | ✅ | Ratings column chart axis |
| `DimRating` | `Rating Category` | ✅ | Calculated column |
| `DimDate` | `Date`, `Year`, `Quarter`, `Month`, `Year Month`, `Day`, `Day of Week`, `Week Number` | ✅ | `Year` is the area-chart axis |
| `DimDate` | `Quarter Number`, `Month Number`, `Year Month Number`, `Day of Week Number` | ❌ hidden | Sort helpers |
| `BridgeTitleCountry` | `Show ID`, `Country` | ❌ hidden | DAX only |
| `BridgeTitleGenre` | `Show ID`, `Genre` | ❌ hidden | DAX only |
| `Users` | `Username`, `Entitled Country` | ❌ hidden | **Never bind, never slice** (FR-052) |

---

## Measure names (19) — all on entity `Titles`

`Distinct Titles` · `Movie Titles` · `TV Show Titles` · `Titles Added` · `Distinct Countries` · `Distinct Genres` · `Distinct Directors` · `Average Release Year` · `Earliest Release Year` · `Latest Release Year` · `% of Titles` · `% of Titles by Rating` · `% of Titles by Genre` · `Genre Rank` · `Distinct Titles (Top 10 Genres)` · `Selected Title Description` · `Selected Title Duration` · `Selected Title Genres` · `Selected Title Rating`

PBIR measure reference shape:

```json
{
  "Measure": {
    "Expression": { "SourceRef": { "Entity": "Titles" } },
    "Property": "Distinct Titles"
  }
}
```

with sibling `"queryRef": "Titles.Distinct Titles"` and `"nativeQueryRef": "Distinct Titles"`.

---

## Visual binding map (12 visuals, 1 page named `Netflix`)

| Visual | Type | Category / axis | Values |
|---|---|---|---|
| Country map | filled map | `DimCountry[Country]` | `Distinct Titles` |
| Ratings chart | column chart | `DimRating[Rating]` | `Distinct Titles` |
| Top 10 Genre | horizontal bar | `DimGenre[Genre]` | **`Distinct Titles (Top 10 Genres)`** |
| Type distribution | donut | `Titles[Type]` | `Distinct Titles`, `% of Titles` |
| Titles by year | stacked area | `DimDate[Year]`, legend `Titles[Type]` | `Titles Added` |
| Description card | card | — | `Selected Title Description` |
| Duration card | card | — | `Selected Title Duration` |
| Genre card | card | — | `Selected Title Genres` |
| Rating card | card | — | `Selected Title Rating` |
| Type slicer | slicer | `Titles[Type]` | — (unfiltered) |
| Title slicer | slicer | `Titles[Title]` | — (unfiltered) |
| Header | text box | — | Substitute for the unavailable `netflix.png` |

---

## Bindings that are easy to get wrong

| Tempting (wrong) | Correct | Why |
|---|---|---|
| `Titles[Listed In]` | `Titles[Genres]` | Renamed from the source `listed_in` |
| `Titles[Country List]` on the map | `DimCountry[Country]` | The raw column is hidden and multi-value; binding it would put comma-joined strings on the map |
| `Titles[Rating]` on the Ratings axis | `DimRating[Rating]` | `Titles[Rating]` is a hidden FK |
| `Titles[Release Year]` on the time axis | `DimDate[Year]` | The chart is titles *added* per year, not release year |
| `Distinct Titles` on the genre bar | `Distinct Titles (Top 10 Genres)` | The Top-10 restriction lives in DAX because PBIR forbids a `filters` property at the visual root |
| `Users[Entitled Country]` in a slicer | — | `Users` is hidden and must never be bindable (FR-052) |

---

## PBIR structural constraints

- `visual.json` root accepts **only** `$schema`, `name`, `position`, and one of `visual` / `visualGroup`. **No `filters`, no `filterConfig`, no other root property** — Power BI Desktop rejects them with "Property has not been defined and the schema does not allow additional properties".
- `visualContainerObjects.title` accepts only `show` and `text`.
- Colour: `{"solid":{"color":{"expr":{"Literal":{"Value":"'#RRGGBB'"}}}}}`.
- Boolean: `{"expr":{"Literal":{"Value":"true"}}}`.
- Page name must match `^[\w-]+$` — the page is named `Netflix` (no spaces, no dots).
- Visual folder IDs ≤20 characters, to keep the deepest path well under the 260-character MAX_PATH limit Power BI Desktop enforces on PBIP projects.

---

## DAX column-reference audit (Phase 1.2 result)

| Reference | Provided | Note |
|---|---|---|
| `Titles[Show ID]` | ✅ | Hidden — legal for DAX |
| `Titles[Type]`, `[Title]`, `[Director]`, `[Date Added]`, `[Release Year]`, `[Duration]`, `[Genres]`, `[Description]` | ✅ | |
| `Titles[Rating]` | ✅ | ⚠ The DAX document's own model-context table omits it, yet `Selected Title Rating` references it. **Must not be dropped.** |
| `DimCountry[Country]`, `DimGenre[Genre]`, `DimRating[Rating]`, `DimRating[Rating Category]` | ✅ | |
| `DimDate[Date]`, `DimDate[Year]` | ✅ | |
| `BridgeTitleCountry[Country]`, `BridgeTitleGenre[Genre]` | ✅ | Hidden — legal for DAX |
| `Users[Username]`, `Users[Entitled Country]` | ✅ | Role only; referenced by no measure |

**Missing columns: none.**
