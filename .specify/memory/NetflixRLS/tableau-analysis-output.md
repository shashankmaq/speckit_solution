# Tableau Workbook Analysis: Netfix Workbook rls

- **Source File**: `Data/Netflix RLS/Netfix Workbook rls.twb`
- **WorkbookName (memory/output scope)**: `NetflixRLS`
- **Analyzed**: 2026-08-03

## Workbook Info
- **Version**: 18.1
- **Source Build**: 2026.1.1 (20261.26.0410.0924)
- **Platform**: win

## Data Source Summary
| Datasource | Connection Type | Source Details |
|-----------|----------------|----------------|
| `netflix_titles` (federated.1ti9kv81mb5xop1auz1ya0a06id2) | CSV (`class='textscan'`) | `netflix_titles.csv` + `User_Access.csv` |
| `Parameters` | (built-in) | Tableau parameter container |

> **Original authoring path** recorded in the TWB is `C:/Users/AmanRajMAQSoftware/Downloads/semantic model generation v4/Data/Netflix RLS`. Files now resolve from `Data/Netflix RLS/` — the M queries must be re-pointed to the workspace-relative path.

### Data Profile (measured from CSVs)
| File | Rows | Notes |
|------|------|-------|
| `netflix_titles.csv` | 6,234 | `show_id` is unique (6,234 distinct) — valid primary key |
| `User_Access.csv` | 3 | RLS entitlement mapping |

- `type` domain: `Movie`, `TV Show`
- `release_year` range: 1925–2020
- `rating`: 15 distinct values
- `country`: 555 distinct **raw strings**, 476 rows blank
- `date_added`: 11 rows blank

## Datasources

### netflix_titles (federated)
- **Connection Type**: CSV / `textscan` (two named connections to `netflix_titles.csv`, one to `User_Access.csv`)
- **Tables**: `[netflix_titles#csv]`, `[User_Access#csv]`
- **Model**: Tableau **logical relationship** (`type='collection'`), not a physical join

#### Dimensions
| Display Name | Field Name | Data Type | Semantic Role |
|--------------|------------|-----------|---------------|
| Show Id | `[show_id]` | integer | — (ordinal) |
| Type | `[type]` | string | — |
| Title | `[title]` | string | — |
| Director | `[director]` | string | — |
| Cast | `[cast]` | string | — |
| Country | `[country]` | string | `[Country].[ISO3166_2]` |
| Country1 | `[Country]` | string | `[Country].[ISO3166_2]` |
| Date Added | `[date_added]` | string | — |
| Release Year | `[release_year]` | integer | — (quantitative) |
| Rating | `[rating]` | string | — |
| Duration | `[duration]` | string | — |
| Listed In | `[listed_in]` | string | — |
| Description | `[description]` | string | — |
| Username | `[Username]` | string | — (from `User_Access.csv`) |

> `Country` (caption **Country1**) is `User_Access.Country`; `country` (caption **Country**) is `netflix_titles.country`. Case-only difference — a high-risk collision for the naming stage. Rename explicitly downstream.

#### Measures
| Display Name | Field Name | Data Type |
|--------------|------------|-----------|
| _(none — no native numeric measures)_ | | |

All quantitative output is derived via `COUNTD([show_id])`. `release_year` is modelled as a dimension.

## Parameters
| Name | Data Type | Domain Type | Default | Range/Values |
|------|-----------|-------------|---------|--------------|
| Year | date | `any` | `#2024-03-26#` | Unconstrained |

> **Unused**: the `Year` parameter is not referenced by any worksheet, filter, or calculation. Do not build a What-If parameter unless a later stage justifies it.

## Calculated Fields
| Name | Formula | Data Type | Type | Table Calc |
|------|---------|-----------|------|------------|
| RLS | see below | boolean | measure / nominal | None |
| Year | `DATETIME([date_added])` | datetime | dimension (ordinal) | None |

**`RLS`** — `[Calculation_0182254345785358]`
```
CONTAINS(
    LOWER(IFNULL(ATTR([country]), "")),
    LOWER(ATTR([country]))
)
AND LOWER(ATTR([Username])) = "user2@maq.com"
```

**`Year`** — `[Calculation_1138566281481768960]`
```
DATETIME([date_added])
```
> `date_added` is a **string** formatted `"September 9, 2019"`. Power Query must parse with an explicit `en-US` locale (`Date.FromText([date_added], [Format="MMMM d, yyyy", Culture="en-US"])`) — an implicit type change will fail. 11 blank values must survive as null.

## Aggregations In Use (column-instances)
| Instance | Base Column | Derivation |
|----------|-------------|------------|
| `[ctd:show_id:qk]` | `[show_id]` | **CountD** |
| `[pcto:ctd:show_id:qk]` | `[show_id]` | CountD → **Percent of Total** |
| `[yr:Calculation_1138566281481768960:ok]` | `Year` calc | **Year** truncation |
| `[usr:Calculation_0182254345785358:nk]` | `RLS` calc | **User** (Tableau user filter) |
| `[none:*]` | type, title, country, description, duration, listed_in, rating, date_added | None |

## Worksheets
1. Country wise distribution
2. Description
3. Duration
4. Genre
5. Movies and TV Shows distribution
6. Rating
7. Ratings
8. Top 10 Genre
9. Total Movies and TV Shows by Years

## Worksheet Visual Details
| Worksheet | Mark Type | Rows (Y-axis) | Cols (X-axis) | Color | Size | Text/Label | Inferred PBI Visual |
|-----------|-----------|---------------|---------------|-------|------|------------|---------------------|
| Country wise distribution | Multipolygon | Latitude (generated) | Longitude (generated) | CountD(show_id) | — | — (lod: country, geometry: generated) | **Filled Map (choropleth)** |
| Description | Automatic | — | — | — | — | description | **Card / multi-row card** |
| Duration | Automatic | — | — | — | — | duration | **Card** |
| Genre | Automatic | — | — | — | — | listed_in | **Card** |
| Rating | Automatic | — | — | — | — | rating | **Card** |
| Movies and TV Shows distribution | Circle | — | — | type | CountD(show_id) | type, CountD(show_id), %ofTotal CountD(show_id) | **Packed bubble / donut** |
| Ratings | Automatic | CountD(show_id) | rating | — | — | CountD(show_id) | **Column chart** |
| Top 10 Genre | Automatic | listed_in | CountD(show_id) | — | — | CountD(show_id) | **Horizontal bar chart** |
| Total Movies and TV Shows by Years | Area | CountD(show_id) | YEAR(Year) | type | — | type | **Stacked area chart** |

## Dashboards
1. Netflix

## Dashboard Layout: Netflix
- **Size**: 1700 × 800 px (`sizing-mode='fixed'`)

Tableau zone units are relative (0–100000). Pixel values below = `x/100000 × 1700`, `y/100000 × 800`.

| Zone | Type | Worksheet/Filter | x | y | w | h | x px | y px | w px | h px |
|------|------|-----------------|---|---|---|---|------|------|------|------|
| 18 | filter | `type` | 471 | 1000 | 9588 | 10125 | 8 | 8 | 163 | 81 |
| 19 | filter | `title` | 471 | 11125 | 9588 | 10875 | 8 | 89 | 163 | 87 |
| 21 | viz | Rating | 10059 | 1000 | 14941 | 9812 | 171 | 8 | 254 | 79 |
| 20 | viz | Duration | 10059 | 10812 | 14941 | 11188 | 171 | 87 | 254 | 90 |
| 23 | bitmap | `netflix.png` | 25000 | 1000 | 17764 | 21000 | 425 | 8 | 302 | 168 |
| 22 | viz | Genre | 42764 | 1000 | 17765 | 21000 | 727 | 8 | 302 | 168 |
| 14 | viz | Description | 60529 | 1000 | 39000 | 21000 | 1029 | 8 | 663 | 168 |
| 12 | viz | Country wise distribution | 471 | 22000 | 34294 | 38499 | 8 | 176 | 583 | 308 |
| 11 | viz | Ratings | 34765 | 22000 | 29823 | 38499 | 591 | 176 | 507 | 308 |
| 10 | viz | Movies and TV Shows distribution | 64588 | 22000 | 34941 | 38499 | 1098 | 176 | 594 | 308 |
| 13 | viz | Top 10 Genre | 471 | 60499 | 47529 | 38501 | 8 | 484 | 808 | 308 |
| 3 | viz | Total Movies and TV Shows by Years | 48000 | 60499 | 51529 | 38501 | 816 | 484 | 876 | 308 |

Container zones (no visual of their own): 4, 43 (`layout-basic`), 17, 42, 7 (`layout-flow`), 15, 5 (`layout-basic`).

### Navigation Buttons
| Button | Action | Tooltip | Target | x | y | w | h |
|--------|--------|---------|--------|---|---|---|---|
| _(none)_ | — | — | — | — | — | — | — |

No `dashboard-object` button zones and no `goto-sheet` / `toggle-action` commands exist. Single-page report — no page navigation or bookmark toggles required.

### Dashboard Image Asset
Zone 23 references `C:/Users/ash_s/OneDrive/Desktop/netflix.png` — an **absolute path on another machine**. The asset is not in the workspace. The report stage must substitute a Netflix logo/text header or omit the zone.

## Dashboard Actions
| Action | Type | Source | Target | Generated Field |
|--------|------|--------|--------|-----------------|
| Filter 1 (generated) | `tsc:tsl-filter`, `on-select`, `auto-clear=true` | worksheet `Country wise distribution` (dashboard `Netflix`) | dashboard `Netflix` (all fields) | `[Action (Country)]` |

Maps to Power BI **default cross-filtering** from the map visual to every other visual on the page. No calculated construct needed.

## Relationships
| Left Table | Right Table | Join Type | Condition |
|------------|-------------|-----------|-----------|
| `netflix_titles.csv` | `User_Access.csv` | Logical relationship (`type='collection'`) | `netflix_titles.[country] = User_Access.[Country]` |

Raw XML:
```xml
<relationship>
  <expression op="="><expression op="[country]" /><expression op="[Country]" /></expression>
  <first-end-point  object-id="netflix_titles.csv_51741C51ECB84DD2BFE7C92864987F33" />
  <second-end-point object-id="User_Access.csv_5D8FCF4F72E24AF5BA7453BC9D417154" />
</relationship>
```

> **Cardinality warning**: `netflix_titles.country` is a **comma-separated multi-value string** (e.g. `"United States, India, South Korea, China"`). An equality relationship matches only rows whose country is *exactly* the entitlement value. Of 555 distinct raw strings, most are multi-country lists. A literal equality relationship in Power BI will under-report for every multi-country title. See RLS notes.

## Sets
| Set Name | Source Field | Type (Fixed/Computed) | Members / Condition |
|----------|--------------|-----------------------|---------------------|
| _None (user-defined)_ | | | |

`[Action (Country)]` is present as a `<group>` but carries `user:auto-column='sheet_link'` — it is the auto-generated dashboard-action set for "Filter 1 (generated)", not an authored set. Do not migrate it as a set.

## Groups
| Group Field | Source Dimension | Alias | Member Values |
|-------------|------------------|-------|---------------|
| _None_ | | | |

## Bins
| Bin Field | Source Field | Bin Size |
|-----------|--------------|----------|
| _None_ | | |

## Data Blending
| Primary Datasource | Secondary Datasource | Linking Field(s) |
|--------------------|----------------------|------------------|
| _Single datasource — no blending_ | | |

Both CSVs live inside one federated datasource joined by a logical relationship, so this is a relationship, not a blend.

## Worksheet Filters
| Worksheet | Field | Filter Kind | Detail |
|-----------|-------|-------------|--------|
| Top 10 Genre | `listed_in` | **Top N** | Top **10** ordered by `COUNTD([show_id])` desc |
| Total Movies and TV Shows by Years | `date_added` | Exclude | Excludes `%null%` (11 rows) |
| Description, Duration, Genre, Rating | `type` | Categorical member | `"TV Show"` (filter-group 3) |
| Description, Duration, Genre, Rating | `title` | Categorical | level-members (filter-group 4) |
| _All worksheets except `Country wise distribution` (the action source)_ | `[Action (Country)]` | Dashboard action | level-members |
| _All 9 worksheets_ | `RLS` calc | **User filter** | see RLS section |

> The four card worksheets (Description, Duration, Genre, Rating) are detail cards driven by the `type` + `title` dashboard slicers. The `"TV Show"` member value is the **saved selection state**, not a hard business rule — treat the slicers as user-controlled in Power BI.

## Field Formatting
| Field | Tableau Format String | Kind |
|-------|-----------------------|------|
| _All fields_ | `Default` | — |

No numeric/date `default-format` or `<format attr='format'>` entries exist. Only visual styling is formatted (see theme below).

### Visual Styling Captured (for the report stage)
| Attribute | Value |
|-----------|-------|
| Dashboard background | `#000000` (black) |
| Map style | `dark`, palette `tableau-map-blue-green-light`, geo-area-type `State` |
| Mark color / border | `#aa0000` |
| Accent color | `#ff0000` |
| Text colors | `#ffffff`, `#c0c0c0`, `#000000` |
| Description card background | `#ffffff` |
| Base font size | 10 |

## Row-Level Security (RLS)
- **Detected**: **Yes**

| Detected | Type | Secured Table.Column | Mapping Table.User Column |
|----------|------|----------------------|---------------------------|
| Yes | Hardcoded per-user predicate (as authored) → **Dynamic mapping-table** (as intended) | `netflix_titles.country` | `User_Access.Username` |

| Suggested Role | RLS Type | Secured Table | Entitlement Column | Mapping Table | User Column | Power BI Filter (DAX intent) |
|----------------|----------|---------------|--------------------|---------------|-------------|------------------------------|
| `Country Access` | Dynamic | `netflix_titles` | `country` | `User_Access` | `Username` | `User_Access[Username] = USERPRINCIPALNAME()` on the mapping table, propagated to `netflix_titles` via the country relationship |

### Signal Scan
| Pattern | Hits |
|---------|------|
| `USERNAME()` | 0 |
| `FULLNAME()` | 0 |
| `ISMEMBEROF` | 0 |
| `ISUSERNAME` | 0 |
| `ISFULLNAME` | 0 |
| `User_Access` (mapping table) | 16 |

### Mechanism
The `RLS` boolean calculated field is applied as a **Tableau user filter** (`derivation='User'`, instance `[usr:Calculation_0182254345785358:nk]`) on the `<slices>` of **all 9 worksheets**.

### Entitlement Data (`User_Access.csv`)
| Username | Country |
|----------|---------|
| shashank@maq.com | India |
| user2@maq.com | United States |
| user3@maq.com | United Kingdom |

### ⚠️ Defects in the authored formula — later stages MUST NOT port it literally

1. **Self-comparison.** `CONTAINS(LOWER(IFNULL(ATTR([country]), "")), LOWER(ATTR([country])))` compares `netflix_titles.country` **to itself**. It is always TRUE for any non-null value, so it contributes nothing. The second argument was almost certainly meant to be `ATTR([Country])` — the `User_Access.Country` entitlement (caption `Country1`).
2. **Hardcoded identity.** `LOWER(ATTR([Username])) = "user2@maq.com"` pins the workbook to a single test user. Effectively the whole workbook currently shows only the **United States** slice. This is a development artifact, not a requirement.
3. **Net effect as authored**: `WHERE Username = 'user2@maq.com'` — one static user.

### Reconstructed intent
```
CONTAINS( LOWER(IFNULL([country], "")), LOWER([Country]) )   -- titles list contains the user's country
AND LOWER([Username]) = LOWER(USERNAME())                     -- current user
```

### Power BI implementation guidance
- Build **dynamic RLS**: role filter `User_Access[Username] = USERPRINCIPALNAME()`, with a single-direction relationship `User_Access[Country] → netflix_titles[country]`.
- The `CONTAINS` semantics matter: because `netflix_titles.country` holds comma-separated lists, an equality relationship will miss multi-country titles. Two viable options for the modelling stage to decide:
  - **(Preferred)** Split `country` into a bridge table (one row per title × country) in Power Query, then relate `User_Access[Country] → Bridge[Country] → netflix_titles[show_id]`. Preserves CountD accuracy and keeps RLS a simple equality.
  - **(Fallback)** Keep the flat table and use a role filter of the form `CONTAINSSTRING(netflix_titles[country], LOOKUPVALUE(User_Access[Country], User_Access[Username], USERPRINCIPALNAME()))`. Simpler, but slower and single-country-per-user only.
- Do **not** create a role containing the literal `user2@maq.com`.
- 476 rows have a blank `country` — decide explicitly whether they are visible to all users or to none (recommend: hidden under RLS, and documented).

## Edge Cases for Downstream Stages
| # | Issue | Impacted Stage |
|---|-------|----------------|
| 1 | `RLS` calc is self-comparing and hardcodes `user2@maq.com` | star-schema, pbip-generator (roles) |
| 2 | `country` is a comma-separated multi-value string → needs a bridge table for correct RLS + CountD | star-schema |
| 3 | `Country` vs `country` differ only by case (User_Access vs netflix_titles) | naming / star-schema |
| 4 | `date_added` is text `"September 9, 2019"` → needs explicit `en-US` locale parse; 11 blanks | pbip-generator (Power Query) |
| 5 | No native measures — every metric is `COUNTD(show_id)`; one `%` of total | dax-measures |
| 6 | `Year` parameter is unused | speckit.specify (scope decision) |
| 7 | Dashboard image `C:/Users/ash_s/.../netflix.png` is unavailable | report-visual-migration |
| 8 | Absolute CSV path points to a different folder than the workspace | pbip-generator |
| 9 | Filled map uses Tableau generated Lat/Long + geo-role `ISO3166_2` with `geo-area-type='State'` while data is country-level | report-visual-migration |
| 10 | Saved `type = "TV Show"` selection is slicer state, not a business rule | report-visual-migration |
| 11 | 476 blank `country` values interact with RLS visibility | star-schema, pbip-generator |
