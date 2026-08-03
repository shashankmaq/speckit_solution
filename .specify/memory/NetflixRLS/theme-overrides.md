# Theme Overrides — NetflixRLS

Workbook-scoped overrides layered **on top of** the universal `.specify/memory/report-constitution.md`.
The universal constitution is not modified by this migration.

Source: `<style>` element of `Data/Netflix RLS/Netfix Workbook rls.twb`.

## Palette

| Role | Hex | Origin |
|---|---|---|
| Page background / outspace | `#000000` | dashboard `table` `background-color` |
| Visual background | `#000000` | inherits dashboard |
| Visual border | `#aa0000` | Tableau `mark` colour / quick-filter border |
| Accent (header text) | `#ff0000` | quick-filter-title colour |
| Primary text (titles, axis, legend, labels) | `#ffffff` | `worksheet` colour |
| Secondary text (slicer items) | `#c0c0c0` | quick-filter text colour |
| Single-series data point fill | `#aa0000` | Tableau `mark` colour |
| Series — Movie | `#d3293d` | Netflix standard |
| Series — TV Show | `#ffbeb2` | Netflix standard |

## Typography

| Element | Family | Size | Weight |
|---|---|---|---|
| Visual title | Aptos | 12pt | bold |
| Header textbox | Aptos | 40pt | bold |
| Axis / legend labels | Aptos | 10pt | normal |
| Data labels | Aptos | 10pt | bold (Tableau `font-weight: bold`) |
| Card callout — Rating / Duration | Aptos | 20pt | bold |
| Card callout — Genre | Aptos | 14pt | normal |
| Card callout — Description | Aptos | 11pt | normal |

## Chrome rules (override the constitution defaults)

| Constitution default | Override | Reason |
|---|---|---|
| 25 px edge padding | **12 px** | Tableau dashboard uses an 8 px root margin; 12 px is the 8 px zone origin + 4 px zone margin |
| 20 px inter-visual gap | **8 px** | Mandatory Fidelity Rule 4 — exact Tableau zone positions, minimum 8 px gap |
| Light professional theme | **Dark** (`#000000` canvas, `#aa0000` borders) | Tableau dashboard is a black Netflix theme |
| Card minimum height 80 px | **70 px** on `crd_rating` | Tableau zone 21 is 78.5 px tall; enlarging it would break the 8 px gutter to `crd_duration` |

## Element settings derived from the TWB

- Grid lines: **off** (`gridline stroke-size = 0`, `line-visibility = off` on Ratings / Top 10 Genre / Years)
- Value axis: **hidden** on Ratings, Top 10 Genre and Years; data labels carry the numbers instead
- Axis titles: **hidden** (`display-field-labels = false`)
- Category axis labels: `#ffffff`, Aptos 10pt
- Legend: shown on the donut and area charts only (Tableau `color` encoding present), labels `#ffffff`
- Filled map: dark base (`map-style = dark`); the `tableau-map-blue-green-light` ramp is replaced by a
  `#3d0000` → `#e50914` red gradient to stay on-theme
- Slicers: container title **off** (built-in header already shows the field name), header `#ffffff`,
  items `#c0c0c0`, dropdown mode
