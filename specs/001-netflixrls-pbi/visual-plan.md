# Implementation Plan: NetflixRLS Visual Layer

## Approach

1. Extend the existing PBIR shell in `Output/NetflixRLS/NetflixRLS.Report/` — do **not** recreate it.
   `definition.pbir` (`definitionProperties/2.0.0`, `version: "4.0"`), `definition/report.json`
   (`report/2.0.0`), `definition/pages/pages.json` (`pagesMetadata/1.0.0`) and
   `definition/pages/Netflix/page.json` (`page/2.0.0`) keep their existing `$schema` values and versions.
2. Add `definition/version.json` (`versionMetadata/1.0.0`, `version: "2.0.0"`).
3. Add a black background to `page.json` via `objects.background` + `objects.outspace`.
4. Create `definition/pages/Netflix/visuals/<id>/visual.json` — one folder per visual, 12 total.
5. Bind every projection to a name verified against the emitted TMDL.
6. Apply the dark theme from `.specify/memory/NetflixRLS/theme-overrides.md`.
7. Validate, fix, re-validate.

## Technical decisions

| Decision | Choice | Rationale |
|---|---|---|
| Coordinate scaling | **1:1** | Page is authored at 1700 × 800, identical to the Tableau dashboard — no rescale error |
| Zone → position | `x+4, y+4, w−8, h−8` | Reproduces Tableau's zone `margin=4`, giving an exact 8 px gutter |
| `visual.json` `$schema` | `visualContainer/2.4.0` | Splits `objects` (visual-specific) from `visualContainerObjects` (container); mandated by the workspace rules |
| Visual title styling | `visualContainerObjects.title` = `show` + `text` only; colour/size in `objects.title` | Hard PBIR rule — extra properties on the container title are rejected |
| Visual-level filters | **Not emitted** | `visualContainer/2.4.0` root permits only `$schema`, `name`, `position`, `visual` |
| Top-10 restriction | Measure `Distinct Titles (Top 10 Genres)` | Only expressible route given the rule above |
| Null-date exclusion | Measure `Titles Added` | Mirrors the Tableau `except %null%` filter |
| Per-slice colours | `dataPoint` with a `scopeId` `Comparison` selector | Documented PBIR pattern; an unmatched selector degrades to the default palette rather than failing |
| Visual folder ids | ≤ 14 chars, `^[a-zA-Z0-9_][a-zA-Z0-9_-]*$` | Keeps the deepest path far below the 260-char PBI limit |
| Encoding | UTF-8 **without** BOM | `Set-Content -Encoding UTF8` on PS 5.1 writes a BOM that the validator flags and Power BI dislikes |
| Font | Aptos | Report constitution |

## Field-reference shapes

```jsonc
// column
{"Column": {"Expression": {"SourceRef": {"Entity": "DimCountry"}}, "Property": "Country"}}
// queryRef: "DimCountry.Country", nativeQueryRef: "Country"

// measure
{"Measure": {"Expression": {"SourceRef": {"Entity": "Titles"}}, "Property": "Distinct Titles"}}
// queryRef: "Titles.Distinct Titles", nativeQueryRef: "Distinct Titles"
```

Literal encodings: string `"'text'"`, colour `"'#RRGGBB'"`, boolean `"true"`, double `"10D"`, integer `"1L"`.

## Query roles per visual type

| Visual type | Roles used |
|---|---|
| `slicer` | `Values` |
| `card` | `Values` |
| `filledMap` | `Category`, `Y` |
| `clusteredColumnChart` | `Category`, `Y` |
| `clusteredBarChart` | `Category`, `Y` |
| `donutChart` | `Category`, `Y`, `Tooltips` |
| `stackedAreaChart` | `Category`, `Series`, `Y` |
| `textbox` | none — `objects.general.paragraphs` |

## Validation gates

1. `python plugins\pbip\skills\pbip\scripts\validate_pbip.py Output\NetflixRLS` — exit 0 or 1 required, 2 blocks.
2. Every `*.json` / `*.pbir` under `NetflixRLS.Report` parses as JSON.
3. Every `queryRef` resolves against the TMDL.
4. Pairwise overlap check across all 12 positions; all inside 1700 × 800.
5. Longest full path < 260 characters.
