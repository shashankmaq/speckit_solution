# Tableau Visual Extraction — Netfix Workbook rls

**Source**: `Data/Netflix RLS/Netfix Workbook rls.twb`
**Method**: direct `[xml]` parse of the TWB (PowerShell), not derived from the analysis summary.
**Workbook version**: 18.1 · 1 dashboard (`Netflix`) · 9 worksheets

---

## 1. Dashboard geometry

| Property | Value |
|---|---|
| Dashboard name | `Netflix` |
| `<size maxwidth>` | **1700** |
| `<size maxheight>` | **800** |
| `sizing-mode` | `fixed` |
| Root `table` background-color | `#000000` |
| Zone `margin` | `4` (8 on root containers) |

Because the target page is authored at the same 1700 × 800, **coordinates are applied 1:1** (no rescale).
Conversion used for every zone: `px_x = x / 100000 * 1700`, `px_y = y / 100000 * 800`.

---

## 2. Worksheet visual inventory (mark class → shelves → encodings)

| # | Worksheet | `mark.class` | `<rows>` | `<cols>` | Encodings | Inferred Power BI visual |
|---|---|---|---|---|---|---|
| 1 | Country wise distribution | `Multipolygon` | Latitude (generated) | Longitude (generated) | `color=ctd:show_id`, `lod=none:country`, geometry generated | `filledMap` |
| 2 | Description | `Automatic` | — | — | `text=none:description` | `card` |
| 3 | Duration | `Automatic` | — | — | `text=none:duration` | `card` |
| 4 | Genre | `Automatic` | — | — | `text=none:listed_in` | `card` |
| 5 | Movies and TV Shows distribution | `Circle` | — | — | `size=ctd:show_id`, `color=none:type`, `text=none:type`, `text=ctd:show_id`, `text=pcto:ctd:show_id` (% of total) | `donutChart` |
| 6 | Rating | `Automatic` | — | — | `text=none:rating` | `card` |
| 7 | Ratings | `Automatic` | `ctd:show_id` | `none:rating` | `text=ctd:show_id` | `clusteredColumnChart` (vertical — measure on rows) |
| 8 | Top 10 Genre | `Automatic` | `none:listed_in` | `ctd:show_id` | `text=ctd:show_id` | `clusteredBarChart` (horizontal — dimension on rows) |
| 9 | Total Movies and TV Shows by Years | `Area` | `ctd:show_id` | `yr:Calculation_1138566281481768960` (YEAR of the `Year` calc) | `color=none:type`, `text=none:type` | `stackedAreaChart` |

**Mark → orientation rule applied**: dimension on `<rows>` + measure on `<cols>` ⇒ horizontal bars; measure on `<rows>` + dimension on `<cols>` ⇒ vertical columns.

**Not present anywhere in this workbook** (verified by search, not assumption):

- Dual-axis / `<dual-axis>` markers — **NONE**
- `<reference-line>` / `<reference-line-aggregation>` — **NONE**
- `<trend-lines>` — **NONE**
- `<zone type-v2='dashboard-object'>` / `<button>` / `goto-sheet` / `<toggle-action>` — **NONE** (single-page dashboard, no navigation or toggle buttons required)

---

## 3. Filter inventory

| Worksheet | Filter | Interpretation |
|---|---|---|
| Top 10 Genre | `<groupfilter function='end' end='top' count='10'>` ordered `DESC` by `COUNTD([show_id])` | Real Top-N business rule → must be preserved |
| Total Movies and TV Shows by Years | `date_added` **except** `%null%` | Exclude the 11 rows with no added date |
| Description, Duration, Genre, Rating | `type` member `"TV Show"` + `title` level-members | Saved *slicer state*, not a business rule → do **not** hard-code |
| All 9 worksheets | `[usr:Calculation_…]` user filter | RLS — already implemented as a semantic-model role |
| All 9 worksheets | `[Action (Country)]` dashboard action | Native Power BI cross-highlighting → no artifact needed |

### Top-N migration decision

PBIR's `visualContainer/2.4.0` root allows only `$schema`, `name`, `position`, `visual`/`visualGroup`.
A visual-level `filters` / `filterConfig` property is therefore **not emitted**. The Top-10 restriction is
carried by the model measure **`Distinct Titles (Top 10 Genres)`**
(`VAR CurrentRank = [Genre Rank] RETURN IF ( CurrentRank <= 10, [Distinct Titles] )`), which reproduces the
Tableau `groupfilter` semantics (rank by `COUNTD(show_id)` DESC, keep top 10).

### `date_added` null-exclusion decision

Carried by the model measure **`Titles Added`**
(`CALCULATE ( [Distinct Titles], KEEPFILTERS ( NOT ISBLANK ( Titles[Date Added] ) ) )`), which is exactly the
Tableau `except %null%` filter. This is why the year area chart binds `Titles Added` rather than `Distinct Titles`.

---

## 4. Dashboard zone geometry (deduped)

Tableau units are 0–100000. `x px = x/100000×1700`, `y px = y/100000×800`.
Emitted position applies the Tableau zone `margin` of 4 (`x+4`, `y+4`, `w-8`, `h-8`) which yields an
8 px gutter between every adjacent visual and reproduces the original spacing.

| Zone | Type | Source | x | y | w | h | px x | px y | px w | px h | Emitted x/y/w/h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 18 | filter | `type` | 471 | 1000 | 9588 | 10125 | 8 | 8 | 163 | 81 | 12 / 12 / 155 / 73 |
| 19 | filter | `title` | 471 | 11125 | 9588 | 10875 | 8 | 89 | 163 | 87 | 12 / 93 / 155 / 79 |
| 21 | viz | Rating | 10059 | 1000 | 14941 | 9812 | 171 | 8 | 254 | 78.5 | 175 / 12 / 246 / 70 |
| 20 | viz | Duration | 10059 | 10812 | 14941 | 11188 | 171 | 86.5 | 254 | 89.5 | 175 / 90 / 246 / 82 |
| 23 | bitmap | `netflix.png` | 25000 | 1000 | 17764 | 21000 | 425 | 8 | 302 | 168 | 429 / 12 / 294 / 160 |
| 22 | viz | Genre | 42764 | 1000 | 17765 | 21000 | 727 | 8 | 302 | 168 | 731 / 12 / 294 / 160 |
| 14 | viz | Description | 60529 | 1000 | 39000 | 21000 | 1029 | 8 | 663 | 168 | 1033 / 12 / 655 / 160 |
| 12 | viz | Country wise distribution | 471 | 22000 | 34294 | 38499 | 8 | 176 | 583 | 308 | 12 / 180 / 575 / 300 |
| 11 | viz | Ratings | 34765 | 22000 | 29823 | 38499 | 591 | 176 | 507 | 308 | 595 / 180 / 499 / 300 |
| 10 | viz | Movies and TV Shows distribution | 64588 | 22000 | 34941 | 38499 | 1098 | 176 | 594 | 308 | 1102 / 180 / 586 / 300 |
| 13 | viz | Top 10 Genre | 471 | 60499 | 47529 | 38501 | 8 | 484 | 808 | 308 | 12 / 488 / 800 / 300 |
| 3 | viz | Total Movies and TV Shows by Years | 48000 | 60499 | 51529 | 38501 | 816 | 484 | 876 | 308 | 820 / 488 / 868 / 300 |

**Missing asset**: zone 23 references `C:/Users/ash_s/OneDrive/Desktop/netflix.png`, which does not exist in this
workspace. Substituted with a styled `textbox` header ("NETFLIX") occupying the identical rectangle.

### Layout verification

| Row | y | bottom | Members (left → right, x…x+w) | Min gutter |
|---|---|---|---|---|
| 1 | 12 / 90 / 93 | 172 | slicers 12–167 · cards 175–421 · header 429–723 · genre 731–1025 · description 1033–1688 | 8 px |
| 2 | 180 | 480 | map 12–587 · ratings 595–1094 · donut 1102–1688 | 8 px |
| 3 | 488 | 788 | top-10 genre 12–812 · years 820–1688 | 8 px |

No overlaps. Max extent 1688 × 788 inside the 1700 × 800 canvas.

---

## 5. Theme extracted from the TWB `<style>` element

| Token | Hex | Applied to |
|---|---|---|
| `table` background-color | `#000000` | page background + page outspace |
| `mark` color | `#aa0000` | data point fill (single-series charts), visual borders |
| quick-filter title color | `#ff0000` | header accent text |
| `worksheet` color | `#ffffff` | titles, axis labels, legend labels, data labels |
| quick-filter text | `#c0c0c0` | slicer item text |
| bubble label color | `#000000` | (Tableau-only, not portable) |
| Description sheet header/cell | `#ffffff` | card callout text |
| `worksheet` font-size | `10` | base font size |
| labels `font-weight` | `bold` | chart data labels |
| gridline `stroke-size` | `0` / `line-visibility: off` | grid + value axis hidden on Ratings, Top 10 Genre, Years |
| `display-field-labels` | `false` | axis titles hidden |
| map `map-style` | `dark` | filled map dark base |
| map palette | `tableau-map-blue-green-light` | replaced with the Netflix red ramp |
| map `geo-area-type` | `State` (data is country-level) | mapped to `DimCountry[Country]` (`dataCategory: Country/Region`) |

Saved as overrides in `.specify/memory/NetflixRLS/theme-overrides.md`.
The universal `.specify/memory/report-constitution.md` was **not** modified.

---

## 6. Target visual manifest (12 visuals, 1 page)

| # | Folder | Power BI `visualType` | Source | Binding |
|---|---|---|---|---|
| 1 | `slc_type` | `slicer` | zone 18 filter | `Titles[Type]` — container title **off** |
| 2 | `slc_title` | `slicer` | zone 19 filter | `Titles[Title]` — container title **off** |
| 3 | `crd_rating` | `card` | Rating | `[Selected Title Rating]` |
| 4 | `crd_duration` | `card` | Duration | `[Selected Title Duration]` |
| 5 | `crd_genre` | `card` | Genre | `[Selected Title Genres]` |
| 6 | `crd_desc` | `card` | Description | `[Selected Title Description]` |
| 7 | `map_country` | `filledMap` | Country wise distribution | Category `DimCountry[Country]` · Y `[Distinct Titles]` |
| 8 | `chr_ratings` | `clusteredColumnChart` | Ratings | Category `DimRating[Rating]` · Y `[Distinct Titles]` |
| 9 | `chr_typedist` | `donutChart` | Movies and TV Shows distribution | Category `Titles[Type]` · Y `[Distinct Titles]` · Tooltips `[% of Titles]` |
| 10 | `chr_top10genre` | `clusteredBarChart` | Top 10 Genre | Category `DimGenre[Genre]` · Y `[Distinct Titles (Top 10 Genres)]` |
| 11 | `chr_years` | `stackedAreaChart` | Total Movies and TV Shows by Years | Category `DimDate[Year]` · Series `Titles[Type]` · Y `[Titles Added]` |
| 12 | `txt_header` | `textbox` | zone 23 bitmap (missing) | static "NETFLIX" |

All bindings resolve against the emitted TMDL: 19 `Titles` measures, `DimCountry[Country]`,
`DimGenre[Genre]`, `DimRating[Rating]`, `DimDate[Year]`, `Titles[Type]`, `Titles[Title]`.
No binding targets `Titles[Show ID]`, `Titles[Country List]`, `Titles[Rating]` (hidden FK), `Users[*]`, or any `Bridge*[*]`.
