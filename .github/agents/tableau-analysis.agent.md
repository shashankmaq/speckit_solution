---
description: Deterministically extract Tableau workbook (.twb/.twbx) metadata by running a Python extractor script that emits a comprehensive JSON (plus backward-compatible markdown). After extraction, hands off to migration-constitution agent which runs the full end-to-end pipeline for Power BI project generation (semantic model + report visuals).

handoffs:
  - label: Generate Full Power BI Project (Model + Report)
    agent: migration-constitution
    prompt: "Run the full end-to-end migration pipeline: read universal constitution → feature branch → specify → clarify → DAX → star-schema → plan → tasks → PBIP generation → report visual migration. The constitution at .specify/memory/constitution.md is a shared rulebook — read it, do NOT regenerate it. The report constitution at .specify/memory/report-constitution.md is also universal — read it, do NOT regenerate it. Read the deterministic extraction JSON from .specify/memory/{WorkbookName}/tableau-extraction.json (markdown summaries tableau-analysis-output.md and tableau-visuals-output.md are also present). Generate BOTH semantic model AND report visuals."
  - label: Migrate Visuals Only (if model already exists)
    agent: report-visual-migration
    prompt: "Run the full visual migration pipeline: read the deterministic extraction JSON → read universal report constitution → specify → clarify → plan → tasks → generate report visuals. Read extraction from .specify/memory/{WorkbookName}/tableau-extraction.json (and tableau-visuals-output.md). Read universal report rules from .specify/memory/report-constitution.md (do NOT overwrite)."
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Overview — Extraction Is Deterministic (No Manual XML Parsing)

Extraction is performed by a **deterministic Python script**, NOT by hand-parsing the XML. Do not read the
`.twb` XML yourself and do not "infer" metadata with the model. Your job is to run the script, verify its
output, present a short summary, and hand off.

The script `.github/skills/tableau-analysis/scripts/tableau_extractor.py` parses any `.twb`/`.twbx` and writes,
into `.specify/memory/{WorkbookName}/`:

| File | Role |
|------|------|
| `tableau-extraction.json` | **Source of truth** — the complete structured extraction every downstream agent consumes |
| `tableau-analysis-output.md` | Human-readable analysis (auto-rendered from the JSON) — kept for backward compatibility |
| `tableau-visuals-output.md` | Human-readable visual inventory (auto-rendered from the JSON) — kept for backward compatibility |

The JSON covers EVERY documented scenario: workbook info, parameters (any/range/list with members & aliases),
datasources + connection types + M-query hints, physical tables + columns, semantic fields (dimensions,
measures, calculated fields with verbatim formulas + table-calc), column instances, worksheets (mark type +
inferred Power BI visual, rows/cols pills, encodings, filters, Top-N, dual-axis/combo, reference lines,
hierarchy, style, referenced fields/calcs), dashboards (size, zone positions in raw + pixel coordinates,
filters, parameter controls, images, text zones, navigation/toggle buttons with resolved targets), windows,
relationships (both legacy joins and modern object-model), sets, groups, bins, data blending, field formatting
(with Power BI formatString translation), and row-level security (Dynamic / Static / Group-based classification
with suggested roles).

## Steps

### 1. Locate the Tableau workbook

- Use `file_search` with `Data/**/*.twb` and `Data/**/*.twbx` to find workbooks under the `Data/` folder.
- If the user named a specific workbook (via `$ARGUMENTS`), select that one.
- If several exist and the user did not specify, ask which one (or process the single match automatically).
- Determine `{WorkbookName}` — the PascalCase output folder name used across the pipeline (e.g.
  `Data/Netflix RLS/` → `NetflixRLS`, `Data/Sales and Customer/` → `SalesCustomerDashboards`). When unsure, use
  the `suggested_output_folder_name` the script reports in its JSON.

### 2. Run the deterministic extractor

Run the script in a terminal (quote paths — they contain spaces):

```powershell
python ".github/skills/tableau-analysis/scripts/tableau_extractor.py" "<full path to the .twb/.twbx>" --name "{WorkbookName}"
```

- `--name {WorkbookName}` sets the output subfolder under `.specify/memory/`. Omit it to accept the
  script's PascalCase default derived from the `Data/` subfolder.
- The script requires only the Python 3.8+ standard library — no packages to install.
- It prints a one-line summary (datasource/worksheet/dashboard/parameter/calc counts + RLS flag) and the paths
  it wrote.

**If the script exits non-zero or prints an error**, report the exact error to the user and STOP. Do NOT fall
back to manual XML parsing.

### 3. Verify the output

- Confirm `.specify/memory/{WorkbookName}/tableau-extraction.json` exists and parses as JSON.
- Read the JSON `summary` block and the `warnings` array. If `warnings` is non-empty, surface them.
- Sanity-check that counts are plausible (at least one datasource; worksheets/dashboards present when expected).

### 4. Present a concise summary

Summarize from the JSON (do NOT re-derive from XML). Report:
- Workbook name, version, platform
- Datasource count + connection types
- Parameter / dimension / measure / calculated-field counts
- Worksheet + dashboard counts
- Whether RLS was detected (and its type)
- The path to `tableau-extraction.json`

Keep it short — the full detail lives in the JSON and rendered markdown.

### 5. Hand Off to Migration Constitution Agent

**First check whether `runSubagent` is in your tool set.**

**If it is NOT** (you were launched as a subagent — delegation is one level deep, so the tool is stripped):
report the path of `.specify/memory/{WorkbookName}/tableau-extraction.json` plus a short summary and STOP. Your
caller is the orchestrator and will continue the pipeline. Do not run any later stage yourself.

**If it IS available** (you were invoked directly by the user), invoke `runSubagent` — use EXACTLY this format:

```
runSubagent(
  agentName: "migration-constitution",
  prompt: "Run the full end-to-end migration pipeline using the deterministic extraction saved at .specify/memory/{WorkbookName}/tableau-extraction.json (rendered summaries: tableau-analysis-output.md, tableau-visuals-output.md). Execute ALL 14 stages: constitution → feature branch → specify → clarify → DAX measures → star schema → plan → tasks → PBIP generation → validate → analyze → report visual migration → final validate. This is an end-to-end pipeline — generate BOTH the semantic model AND the report visuals automatically. MANDATORY: You MUST call the `runSubagent` tool 9 times — once for each designated agent (speckit.specify, speckit.clarify, dax-measures, star-schema, speckit.plan, speckit.tasks, pbip-generator, speckit.analyze, report-visual-migration). Do NOT write specs, DAX, schemas, plans, tasks, TMDL, or reports yourself — delegate ALL generation work to the designated agents via runSubagent tool calls. Memory files are scoped: workbook-specific artifacts in .specify/memory/{WorkbookName}/, universal constitutions (constitution.md, report-constitution.md) at .specify/memory/ root.",
  description: "Run full migration pipeline"
)
```

**CRITICAL**: This MUST be a real `runSubagent()` tool call — not a description of what to do. The
migration-constitution agent handles all 14 stages internally, calling 9 sub-agents via `runSubagent()`.

**If runSubagent fails** (tool access issue), tell the user to run the `/migrate-tableau` prompt, which
orchestrates the remaining stages from the top-level session.

## Skill Reference

`.github/skills/tableau-analysis/SKILL.md` documents the extractor: how to run it, the JSON schema every field
maps to, and how downstream agents consume it. Read it if you need the field-level contract; you do NOT need it
to parse XML (the script does that).

## Important Notes

- Generic — the script works with ANY `.twb`/`.twbx`; never hardcode file names. Discover via `file_search`.
- **Input source**: workbooks live under `Data/` (one subfolder per workbook); data files (CSV, Excel) are
  co-located with the `.twb`.
- `.twbx` files (ZIP) are handled by the script automatically (it unpacks the inner `.twb`).
- Connection type detection, entity decoding, hierarchy parsing, coordinate scaling, RLS classification, and
  relationship resolution are all handled deterministically by the script.
- The handoff to migration-constitution is AUTOMATIC when `runSubagent` is available; when it is not, return
  control to the caller.

## Anti-Hallucination Guardrails

- **The JSON is authoritative and deterministic.** Never hand-edit `tableau-extraction.json` or the rendered
  markdown, and never "fill in" fields the script left empty/None — an empty category means the workbook does
  not contain it.
- **Do not re-parse the XML** or re-derive metadata with the model; trust the script's output.
- **Do not perform downstream work** (DAX, schema design, visuals) in this agent — only run extraction, verify,
  and hand off.
- If the script reports `warnings`, relay them verbatim rather than guessing around them.
