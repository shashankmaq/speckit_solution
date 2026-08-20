# How to Run the Tableau → Power BI Migration Pipeline

This guide explains how to run the automated pipeline that converts a Tableau workbook (`.twb`) into a complete Power BI project (`.pbip`) — including both the **semantic model** and the **report visuals**.

---

## Prerequisites

- **VS Code** with GitHub Copilot (agent mode enabled).
- **Python** installed and on `PATH` (used by `validate_pbip.py`).
- **PowerShell** (Windows) — the validation and helper scripts use PowerShell.
- **Power BI Desktop** (to open the generated `.pbip` output).

---

## Step 1 — Add Your Tableau Workbook

Place your Tableau workbook and its data files in a **subfolder** under `Data/`, one folder per workbook.

```
Data/
└── MyDashboard/
    ├── MyDashboard.twb        ← the Tableau workbook
    ├── data1.csv             ← source data file(s)
    └── data2.csv
```

> Each workbook gets its own subfolder. Include every CSV/Excel source the workbook references.

---

## Step 2 — Run the Pipeline

Open Copilot Chat in agent mode and invoke the entry-point agent. Any of these will start the full pipeline:

- Run the **`tableau-analysis`** agent, **or**
- Ask in chat: **"analyze the Tableau workbook in Data/MyDashboard"**

The pipeline then runs **automatically end-to-end** — no manual steps between stages.

---

## Step 3 — What Happens Automatically

The `tableau-analysis` agent parses the `.twb` and hands off to `migration-constitution`, which orchestrates all remaining stages by calling specialized subagents:

| Stage | Agent | Output |
|-------|-------|--------|
| 1 | `tableau-analysis` | Parse `.twb`, extract metadata |
| 2 | (constitution) | Read universal migration rulebook |
| 3 | (branch setup) | Create feature branch + speckit dir |
| 4 | `speckit.specify` | `spec.md` |
| 5 | `speckit.clarify` | Clarified spec |
| 6 | `dax-measures` | DAX measures |
| 7 | `star-schema` | Fact/dimension design |
| 8 | `speckit.plan` | `plan.md` |
| 9 | `speckit.tasks` | `tasks.md` |
| 10 | `pbip-generator` | PBIP semantic model (TMDL) |
| 11 | (validation) | TMDL + PBIP validators |
| 12 | `speckit.analyze` | Cross-artifact consistency check |
| 13 | `report-visual-migration` | Report visuals (PBIR JSON) |
| 14 | (validation) | Full end-to-end validation |

---

## Step 4 — Find the Output

Generated Power BI artifacts are saved to `Output/{WorkbookName}/`:

```
Output/
└── MyDashboard/
    ├── MyDashboard.pbip
    ├── MyDashboard.Report/
    │   ├── definition.pbir
    │   └── report.json
    └── MyDashboard.SemanticModel/
        ├── definition.pbism
        ├── diagramLayout.json
        └── definition/
            ├── database.tmdl
            ├── model.tmdl
            ├── relationships.tmdl
            └── tables/
```

Open **`MyDashboard.pbip`** in Power BI Desktop.

---

## Step 5 — Validate (runs automatically, can re-run manually)

Validation runs during the pipeline, but you can re-run any validator manually.

**TMDL structural syntax:**
```powershell
& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\MyDashboard\MyDashboard.SemanticModel\definition"
```

**Cross-cutting PBIP structure:**
```powershell
python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\MyDashboard"
```
Exit codes: `0` = clean, `1` = warnings, `2` = errors, `3` = usage error.

**Report JSON syntax:**
```powershell
Get-ChildItem "Output\MyDashboard\MyDashboard.Report" -Recurse -Include "*.json","*.pbir" |
  ForEach-Object { try { Get-Content $_.FullName -Raw | ConvertFrom-Json | Out-Null }
  catch { Write-Error "Invalid JSON: $($_.FullName) — $_" } }
```

---

## Regenerate Only the Report Layer (optional)

If the semantic model already exists in `Output/{WorkbookName}/` and you only need to rebuild the visuals:

- Run the **`report-visual-migration`** agent, **or**
- Ask: **"migrate visuals from Tableau to Power BI for MyDashboard"**

---

## Supported Data Sources

| Source | M Query Pattern |
|--------|-----------------|
| CSV | `Csv.Document(File.Contents(...))` |
| SQL Server | `Sql.Database(...)` |
| PostgreSQL | `PostgreSQL.Database(...)` |
| Excel | `Excel.Workbook(File.Contents(...))` |
| MySQL | `MySQL.Database(...)` |
| Generic ODBC | `Odbc.DataSource(...)` |

---

## Folder Reference

| Folder | Purpose |
|--------|---------|
| `Data/` | **Input** — Tableau workbooks + source data (one subfolder per workbook) |
| `Output/` | **Output** — Generated PBIP projects (one subfolder per workbook) |
| `specs/` | Speckit artifacts (`spec.md`, `plan.md`, `tasks.md`) per feature branch |
| `.specify/memory/` | Analysis, constitution, DAX, star-schema, and visuals memory artifacts |
| `plugins/` | Validators and skills for TMDL / PBIR / DAX / report design |

---

## Troubleshooting

- **Validator exit code 2 (errors):** Fix the reported errors before opening in Power BI Desktop.
- **TMDL syntax issues:** Check indentation (tabs), property ordering, and name quoting.
- **PBIR JSON rejected by Desktop:** `visual.json` allows only `$schema`, `name`, `position`, and `visual`/`visualGroup` at the root — no extra properties.
- **Missing data:** Ensure every CSV/Excel file referenced by the `.twb` is present in the workbook's `Data/` subfolder.

---

## Key References

- Power BI Guidance: https://learn.microsoft.com/en-us/power-bi/guidance/
- Star Schema: https://learn.microsoft.com/en-us/power-bi/guidance/star-schema
- PBIP Format: https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset
- Report JSON Schema: https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report
