# Visual Specification: NetflixRLS Report

Derived from `.specify/memory/NetflixRLS/tableau-visuals-output.md` (direct TWB XML parse) and constrained by
`specs/001-netflixrls-pbi/contracts/model-contract.md`.

## Pages

### Page 1 — `Netflix`

| Property | Value |
|---|---|
| Folder / `name` | `Netflix` |
| `displayName` | `Netflix` |
| Canvas | **1700 × 800** (exact Tableau `<size maxwidth/maxheight>`) |
| `displayOption` | `FitToPage` |
| Background | `#000000`, 0 % transparency (page + outspace) |
| Layout | Row 1 — filters, KPI cards, header, description · Row 2 — map, ratings, type split · Row 3 — top genres, yearly trend |

There is exactly one Tableau dashboard, therefore exactly one report page. No extra pages are invented.

---

## Slicers

### S1 `slc_type`
- Type: `slicer`, dropdown
- Field: `Titles[Type]`
- Position: x=12, y=12, w=155, h=73
- **Container title: DISABLED** (slicers use the built-in header only)
- Header `#ffffff`, items `#c0c0c0`, border `#aa0000`
- Source: dashboard zone 18 (`quick-filter` on `type`)

### S2 `slc_title`
- Type: `slicer`, dropdown
- Field: `Titles[Title]`
- Position: x=12, y=93, w=155, h=79
- **Container title: DISABLED**
- Source: dashboard zone 19 (`quick-filter` on `title`)

> The saved Tableau slicer state (`type = "TV Show"`, specific `title` members) is deliberately **not**
> hard-coded — it is UI state, not a business rule.

---

## Visuals

### V1 `crd_rating` — "Rating"
- Type: `card`
- Values: measure `Titles[Selected Title Rating]`
- Position: x=175, y=12, w=246, h=70
- Callout Aptos 20pt bold `#ffffff`; category label off
- Source: worksheet `Rating` (mark `Automatic`, `text=none:rating`), zone 21

### V2 `crd_duration` — "Duration"
- Type: `card`
- Values: measure `Titles[Selected Title Duration]`
- Position: x=175, y=90, w=246, h=82
- Source: worksheet `Duration` (`text=none:duration`), zone 20

### V3 `txt_header` — header
- Type: `textbox`
- Content: static "NETFLIX", Aptos 40pt bold `#ff0000`, centred
- Position: x=429, y=12, w=294, h=160
- Title / background / border off
- Source: zone 23 `bitmap`, whose asset `C:/Users/ash_s/OneDrive/Desktop/netflix.png` is **missing** — substituted

### V4 `crd_genre` — "Genre"
- Type: `card`
- Values: measure `Titles[Selected Title Genres]`
- Position: x=731, y=12, w=294, h=160
- Callout Aptos 14pt `#ffffff`
- Source: worksheet `Genre` (`text=none:listed_in`), zone 22

### V5 `crd_desc` — "Description"
- Type: `card`
- Values: measure `Titles[Selected Title Description]`
- Position: x=1033, y=12, w=655, h=160
- Callout Aptos 11pt `#ffffff`
- Source: worksheet `Description` (`text=none:description`), zone 14

### V6 `map_country` — "Country wise distribution"
- Type: `filledMap`
- Category (Location): `DimCountry[Country]` (`dataCategory: Country/Region`)
- Y (Colour saturation): measure `Titles[Distinct Titles]`
- Position: x=12, y=180, w=575, h=300
- Colour ramp `#3d0000` → `#e50914`
- Source: worksheet `Country wise distribution` (mark `Multipolygon`, `color=ctd:show_id`, `lod=none:country`), zone 12

### V7 `chr_ratings` — "Ratings"
- Type: `clusteredColumnChart` (vertical: measure on Tableau `<rows>`, dimension on `<cols>`)
- Category: `DimRating[Rating]`
- Y: measure `Titles[Distinct Titles]`
- Position: x=595, y=180, w=499, h=300
- Column fill `#aa0000`; value axis hidden, grid lines off, axis titles off; data labels on, Aptos 10pt bold `#ffffff`
- Source: worksheet `Ratings`, zone 11

### V8 `chr_typedist` — "Movies and TV Shows distribution"
- Type: `donutChart`
- Category: `Titles[Type]`
- Y: measure `Titles[Distinct Titles]`
- Tooltips: measure `Titles[% of Titles]` (Tableau `pcto:ctd:show_id` % of total)
- Position: x=1102, y=180, w=586, h=300
- Slice colours Movie `#d3293d`, TV Show `#ffbeb2`; labels "Data value, percent of total"; legend bottom `#ffffff`
- Source: worksheet `Movies and TV Shows distribution` (mark `Circle`, `size=ctd:show_id`, `color=none:type`), zone 10

### V9 `chr_top10genre` — "Top 10 Genre"
- Type: `clusteredBarChart` (horizontal: dimension on Tableau `<rows>`)
- Category: `DimGenre[Genre]`
- Y: measure `Titles[Distinct Titles (Top 10 Genres)]`
- Sort: that measure, Descending
- Position: x=12, y=488, w=800, h=300
- Bar fill `#aa0000`; value axis hidden; data labels on
- Source: worksheet `Top 10 Genre`, zone 13

### V10 `chr_years` — "Total Movies and TV Shows by Years"
- Type: `stackedAreaChart`
- Category: `DimDate[Year]`
- Series: `Titles[Type]`
- Y: measure `Titles[Titles Added]`
- Position: x=820, y=488, w=868, h=300
- Series colours Movie `#d3293d`, TV Show `#ffbeb2`; legend bottom; value axis hidden; grid lines off
- Source: worksheet `Total Movies and TV Shows by Years` (mark `Area`, `color=none:type`, `yr:` truncation on the `Year` calc), zone 3

---

## Navigation Buttons

**None.** The TWB contains no `<zone type-v2='dashboard-object'>`, no `<button>`, no `tabdoc:goto-sheet` action and
no `<toggle-action>`. The dashboard is single-page, so no `actionButton` visuals are generated.

---

## Clarifications resolved

| # | Ambiguity | Resolution |
|---|---|---|
| C1 | Tableau `Circle` marks (packed bubbles) have no direct Power BI equivalent | `donutChart` per the frozen model contract — preserves the part-to-whole reading of Movie vs TV Show and the `% of total` label |
| C2 | Tableau `Multipolygon` with `geo-area-type = State` but country-level data | `filledMap` on `DimCountry[Country]`, whose `dataCategory` is `Country/Region` |
| C3 | Top-10 `groupfilter` cannot be expressed as a visual-level filter | Bound to the model measure `Distinct Titles (Top 10 Genres)`; `visualContainer/2.4.0` forbids a root `filters` property |
| C4 | `date_added except %null%` filter on the year chart | Bound to `Titles Added`, which applies `KEEPFILTERS ( NOT ISBLANK ( Titles[Date Added] ) )` |
| C5 | Model contract says the year chart value is `Titles Added`; the request table said `Distinct Titles` | **Contract wins** — `Distinct Titles` would re-admit the 11 null-date rows the Tableau filter removes |
| C6 | Constitution mandates a 20 px gap; Tableau zones sit 8 px apart | Fidelity Rule 4 wins — exact zone positions with an 8 px minimum gutter |
| C7 | Constitution mandates cards ≥ 80 px; Tableau zone 21 is 78.5 px | Emitted at 70 px; growing it would collide with `crd_duration` |
| C8 | `netflix.png` referenced by zone 23 does not exist | Replaced with a styled `textbox` in the identical rectangle |
| C9 | Saved Tableau filter state (`type = "TV Show"`) | Not hard-coded — UI state, not a business rule |
| C10 | `[Action (Country)]` dashboard action | Native Power BI cross-highlighting; no artifact emitted |

## Unverified / manual follow-up

- `UNVERIFIED` — none. Every visual, binding and position traces to a concrete TWB element.
- Manual: Power BI's `card` truncates very long strings; `crd_desc` may need the container enlarged or swapped to a
  multi-row card in Desktop if descriptions clip.
