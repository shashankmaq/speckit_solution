# Tableau Workbook Analysis Skill (Deterministic Extractor)

## Purpose

Extract comprehensive metadata from any Tableau workbook (`.twb` or `.twbx`) **deterministically** using a
Python script — not by hand-parsing the XML with the model. The script produces a single authoritative JSON
document (`tableau-extraction.json`) plus two auto-rendered markdown files, and works with any workbook
regardless of domain.

> **Why deterministic?** Hand-parsing 200–800 KB of Tableau XML with an LLM is slow and error-prone (missed
> encodings, hallucinated fields, inconsistent formatting). The script guarantees the same complete output
> every run, so every downstream agent (constitution, DAX, star-schema, PBIP, report visuals) builds on
> identical, trustworthy data.

## When to Use

- As Stage 0 of the Tableau → Power BI migration pipeline, before any generation stage.
- Whenever a workbook's structure must be captured (datasources, fields, calculations, parameters, worksheets,
  dashboards, relationships, sets/groups/bins, blending, formatting, RLS, and full visual metadata).

## How to Run

```powershell
python ".github/skills/tableau-analysis/scripts/tableau_extractor.py" "<path to .twb or .twbx>" --name "{WorkbookName}"
```

- **Input**: a single `.twb`/`.twbx` file, OR a folder (every workbook underneath is processed).
- `--name {WorkbookName}` — output subfolder under `.specify/memory/` (PascalCase, e.g. `NetflixRLS`). Omit to
  accept the default derived from the `Data/` subfolder name.
- `--out-dir DIR` — write artifacts to an explicit directory instead of `.specify/memory/{name}/`.
- `--no-markdown` — emit only the JSON.
- `--stdout` — print the JSON to stdout instead of writing files (useful for piping / inspection).
- Requires only the Python 3.8+ standard library. `.twbx` archives are unpacked automatically.

### Outputs (written to `.specify/memory/{WorkbookName}/`)

| File | Role |
|------|------|
| `tableau-extraction.json` | **Source of truth** — complete structured extraction for downstream agents |
| `tableau-analysis-output.md` | Human-readable analysis, auto-rendered from the JSON (backward compatibility) |
| `tableau-visuals-output.md` | Human-readable visual inventory, auto-rendered from the JSON (backward compatibility) |

## JSON Schema (top-level keys)

Every key is always present; empty categories are `[]`/`None` (never omitted, never fabricated).

| Key | Contents |
|-----|----------|
| `schema_version`, `extractor_version` | Versioning of the output contract |
| `source_file`, `workbook_name`, `data_subfolder`, `suggested_output_folder_name` | Provenance + suggested PascalCase folder |
| `workbook` | `version`, `original_version`, `source_build`, `source_platform` |
| `parameters[]` | name, caption, datatype, role, `domain_type` (any/range/list), `default_value`, `default_formula`, `format`, `range` {min,max,granularity}, `members[]`, `aliases[]` (key→value), `powerbi_mapping` |
| `datasources[]` | name, caption, `connections[]` (class, `connection_type`, `m_query_pattern`, file/server/db), `connection_types[]`, `relations_type`, `physical_tables[]` (name, caption, columns), `joins[]` (legacy), `object_relationships[]` (modern), `columns[]`, `column_instances[]`, `sets[]`, `groups[]`, `bins[]` |
| `datasources[].columns[]` | name, caption, datatype, role (dimension/measure), type, `semantic_role`, `data_category`, aggregation, `format`, `powerbi_format`, `format_kind`, hidden, `physical_table`, `is_calculated`, `calculation` {class, formula (verbatim, decoded), table_calc} |
| `fields` | Convenience flattened `dimensions[]`, `measures[]`, `calculated_fields[]` across all datasources |
| `worksheets[]` | name, title {text,font,size,color,bold,align}, datasource, `mark_type`, `all_marks[]`, `inferred_powerbi_visual`, `rows[]`/`cols[]` (parsed pills: aggregation, date_part, field, caption, is_generated), `hierarchy[]`, `encodings` {color,size,text,label,wedge_size,detail,lod,shape,geometry,angle,path}, `filters[]` (class, field, kind, members, top_n, is_action_filter, range), `top_n`, `dual_axis`, `reference_lines[]`, `referenced_fields[]`, `referenced_calculations[]`, `color_encoding`, `style` |
| `dashboards[]` | name, size {width,height,sizing_mode}, style, `visuals[]` (worksheet + position raw & `_px`), `filters[]`, `parameter_controls[]`, `images[]`, `text_zones[]`, `buttons[]` |
| `dashboards[].buttons[]` | id, `action_type` (goto-sheet/toggle), `target_dashboard` (resolved from window-id GUID) or `target_zone_ids[]`, tooltip, image_path, states[], position, `powerbi_mapping` |
| `windows[]` | class, name, uuid (GUID↔dashboard resolution) |
| `relationships[]` | datasource, left_table, left_column, right_table, right_column, join_type, operator |
| `sets[]`, `groups[]`, `bins[]` | Real user sets/groups/bins (auto-generated dashboard-action groups are excluded) |
| `data_blending` | is_blended, primary, secondary[], linking_fields[], note |
| `field_formatting[]` | field, format (verbatim Tableau), kind (Currency/Percent/Date/Number), `powerbi_format` |
| `row_level_security` | detected, type (Dynamic/Static/Group-based/None), signals[], user_functions[], mapping_table, user_column, entitlement_column, secured_table, roles[] (with `dax_intent`) |
| `summary` | Counts + `connection_types[]` + `rls_detected` |
| `warnings[]` | Any parse ambiguities the script flagged |

## How Downstream Agents Consume It

- **migration-constitution / speckit.specify / speckit.clarify** — read `datasources`, `fields`, `parameters`,
  `relationships`, `data_blending`, `row_level_security` to scope the spec.
- **dax-measures** — read `fields.calculated_fields` (verbatim formulas + table_calc) and `field_formatting`.
- **star-schema** — read `datasources[].physical_tables`, `relationships`, `data_blending`, and
  `row_level_security` (mapping table + roles).
- **report-visual-migration** — read `worksheets` (mark_type, inferred visual, encodings, filters, top_n) and
  `dashboards` (sizes, zone `_px` positions, buttons, slicers, images).

## Source-Type Detection (handled by the script)

| Tableau connection class | Detected type | Power BI M pattern |
|---|---|---|
| `textscan` / `textclean` | CSV | `Csv.Document(File.Contents(...))` |
| `excel-direct` / `excel` | Excel | `Excel.Workbook(File.Contents(...))` |
| `sqlserver` | SQL Server | `Sql.Database(...)` |
| `postgres` | PostgreSQL | `PostgreSQL.Database(...)` |
| `mysql` | MySQL | `MySQL.Database(...)` |
| `oracle`, `snowflake`, `databricks`, `bigquery`, `redshift`, … | mapped | vendor connector / `Odbc.DataSource(...)` |

## Anti-Hallucination Rules (MANDATORY)

1. **The script is the only extractor.** Do not hand-parse the `.twb` XML, and do not re-derive or "improve"
   any field with the model.
2. **The JSON is authoritative.** Never edit `tableau-extraction.json` (or the rendered markdown) by hand.
3. **Empty means empty.** A category emitted as `[]`/`None` means the workbook does not contain it — never fill
   it in with plausible entries.
4. **Formulas and formats are verbatim.** The script copies them after XML-entity decoding; do not rewrite them.
5. **Surface warnings.** If `warnings[]` is non-empty, relay it rather than guessing around the ambiguity.
6. **No downstream design here.** This stage EXTRACTS only — DAX, star-schema, and visuals are later stages.

## Notes

- GENERIC — never hardcode file names; discover dynamically via `file_search`.
- Auto-generated dashboard-action groups (`user:auto-column='sheet_link'`) are intentionally excluded from
  `sets`/`groups`.
- Dashboard zone coordinates are provided in both raw (0–100000) and pixel form (`*_px`, scaled to the
  dashboard size) for direct use by the report layer.
- Ref: https://learn.microsoft.com/en-us/power-bi/guidance/
