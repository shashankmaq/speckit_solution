# Tableau → Power BI Migration Constitution

> **UNIVERSAL** — This constitution is shared across ALL workbook migrations in this workspace.
> It is NEVER overwritten per workbook. It is the single authority for semantic-model design.
> Workbook-specific decisions belong in `specs/{NNN}-{name}/spec.md`, not here.

## Core Principles

### §1. Star Schema First
- Model every workbook as a star schema: one (or few) **fact** table(s) surrounded by **dimension** tables.
- Identify the fact grain explicitly (one row = one business event, e.g., one order line).
- Categorical / descriptive columns become dimensions; numeric event values stay on the fact.
- Always create a **DimDate** dimension when any date field exists; mark it as a Date table and drive all time-intelligence through it.
- Resolve many-to-many (e.g., comma-separated fields) via **bridge tables** with natural keys.
- Avoid snowflaking unless a dimension is genuinely reused across multiple facts.

### §2. Naming Conventions
- **Tables**: PascalCase, singular for dimensions prefixed `Dim` (e.g., `DimCustomer`, `DimDate`), facts prefixed `Fact` (e.g., `FactOrders`). Where a workbook already has clear business table names, the generator may keep descriptive names (e.g., `Orders`, `Customers`) but MUST be consistent.
- **Columns**: Human-friendly Title Case with spaces preserved where meaningful (e.g., `Order Date`, `Customer Name`).
- **Measures**: Descriptive business names, no table prefix (e.g., `Total Sales`, `% Diff Sales`).
- **Keys**: Suffix surrogate keys with `Key` and natural keys with `ID`.
- Remove Tableau auto-generated `(copy)` suffixes; use the user-facing caption.

### §3. DAX Standards
- Prefer **measures** over calculated columns (calculate at query time, smaller model).
- Use `DIVIDE()` for division (safe divide-by-zero), never the `/` operator on measures.
- Use `VAR` / `RETURN` for readability and to avoid recomputation.
- Use `CALCULATE` + filter context for conditional aggregations.
- Map Tableau patterns:
  - Simple aggregations (`SUM`, `AVG`, `COUNTD`) → `SUM`, `AVERAGE`, `DISTINCTCOUNT`.
  - `IF` / `CASE` → `IF()` / `SWITCH(TRUE(), ...)`.
  - Table calculations (`RANK`, `INDEX`, `WINDOW_MIN/MAX/AVG`, `LOOKUP`) → `RANKX`, `MAXX`/`MINX`/`AVERAGEX` over the appropriate table, `OFFSET`, or visual calculations.
  - FIXED / INCLUDE / EXCLUDE LODs → `CALCULATE` with `REMOVEFILTERS` / `ALLEXCEPT` / `VALUES` / `SUMMARIZE`.
  - Year-over-year on a parameter → `CALCULATE([Measure], DimDate[Year] = SELECTEDVALUE(Param[Value]))` and `... - 1` for prior year.
- Organize measures into **display folders** by subject area.
- Never reference a measure directly inside a `CALCULATE` boolean filter — capture it in a `VAR` first.

### §4. Relationships
- Single-source models → relate on **natural keys** that already join in the source.
- Multi-source / merged models → introduce **surrogate keys** for stable joins.
- Default to **single-direction** (one-to-many, dimension → fact) filters.
- Use **bi-directional** filtering only when required (e.g., bridge tables, dynamic RLS) and document why.
- Mark one relationship **active** per pair; additional paths are inactive and activated via `USERELATIONSHIP`.
- Validate referential integrity: every fact foreign key must resolve to a dimension key.

### §5. M Query / Data Loading Safety
- Reference data files by **absolute path** detected from the workspace root (`Data/{subfolder}/...`).
- Match the source connector to the type:
  - CSV → `Csv.Document(File.Contents(...), [Delimiter=...])` — honor the source separator (e.g., `;`).
  - Excel → `Excel.Workbook(File.Contents(...))`.
  - SQL Server → `Sql.Database(...)`; PostgreSQL → `PostgreSQL.Database(...)`; MySQL → `MySQL.Database(...)`; other → `Odbc.DataSource(...)`.
- Promote headers, set explicit column types, and trim only when necessary.
- Keep transformations deterministic and side-effect-free.

### §6. PBIP Structure & Encoding
- Produce a valid `.pbip` thick project: `{Name}.pbip`, `{Name}.SemanticModel/`, `{Name}.Report/`.
- `definition.pbism` version MUST be `"4.2"`; `definition.pbir` version MUST be `"4.0"`.
- `.pbip` MUST contain `$schema` and MUST NOT declare a `dataset` artifact.
- TMDL definition folder layout: `database.tmdl`, `model.tmdl`, `relationships.tmdl`, `tables/{Table}.tmdl`, optional `roles/{Role}.tmdl`, `cultures/`, `expressions.tmdl`.
- All files UTF-8 **without BOM**.
- Include `.platform` files with correct `metadata.type`, `metadata.displayName`, `config.logicalId` (GUID).

### §7. Validation (NON-NEGOTIABLE)
- After generation, run `tmdl-validate` on the SemanticModel `definition/` folder and fix all structural errors.
- Run `validate_pbip.py` on the project root; resolve exit-code 2 errors before proceeding.
- Verify table/column/measure counts, relationship integrity, and that every fact key resolves.
- Confirm the project opens in Power BI Desktop conceptually (entry-point versions, schemas present).

## Parameter Handling
- Integer range/list parameter → **What-If parameter** (disconnected `GENERATESERIES` table) or a field/slicer table.
- String list parameter → **field parameter** or disconnected slicer table.
- Date parameter → slicer on **DimDate**.
- Preserve the source default value.

## Edge-Case Policy
- If a constitution rule cannot be applied to a given workbook, record the exception and rationale in that workbook's `spec.md` — do NOT modify this constitution.
- Scratch / test worksheets with no dashboard placement are candidates for exclusion; flag rather than silently drop unless clearly disposable.

## Governance
- This constitution supersedes ad-hoc decisions. All generated artifacts must comply.
- Amendments are workspace-wide and rare; they require explicit human approval.
- Subagents reference this file by section number (§1–§7) as their rulebook.

**Version**: 1.0.0 | **Ratified**: 2026-06-09 | **Last Amended**: 2026-06-09
