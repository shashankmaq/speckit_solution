# Tableau Visual Extraction Skill (Router)

## Purpose

Extract visualization metadata from a Tableau workbook (.twb) — chart types, field placements, encodings, formatting, filters, layout positions, and navigation buttons — needed to recreate equivalent Power BI visuals. This is a **thin router** — each rule area lives in its own focused skill so nothing is skipped. Read the focused skill for the step you are on.

## When to Use

- After `tableau-analysis` has run and `tableau-extraction.json` exists
- When migrating Tableau visuals/dashboards to the Power BI report layer
- Before generating Power BI report visuals

## ✅ Read the Deterministic JSON First (do NOT re-parse XML)

The deterministic extractor (`.github/skills/tableau-analysis/scripts/tableau_extractor.py`) already captured
**all** visual metadata into `.specify/memory/{WorkbookName}/tableau-extraction.json`:

- `worksheets[]` — `mark_type`, `inferred_powerbi_visual`, `rows[]`/`cols[]` pills, `encodings`
  (color/size/text/wedge_size/lod/detail/geometry…), `filters[]`, `top_n`, `dual_axis`, `reference_lines[]`,
  `hierarchy[]`, `title`, `style`, `color_encoding`.
- `dashboards[]` — `size`, per-zone `visuals[]`/`filters[]`/`parameter_controls[]`/`images[]`/`text_zones[]`
  with raw **and** pixel (`*_px`) positions, and `buttons[]` with resolved `target_dashboard`/`target_zone_ids`.

**Read the JSON — do not hand-parse the `.twb`.** The focused skills below are the reference for *interpreting*
these JSON fields (chart-type rules, encoding meaning, format translation) and for the rare case where you must
confirm a raw attribute the JSON does not carry. Only if `tableau-extraction.json` is missing should you re-run
the extractor (see `tableau-analysis/SKILL.md`).

## What to Read for Each Task (focused skills)

| Task | Read this skill |
|------|-----------------|
| Map a Tableau mark to a Power BI visualType (canonical, incl. Automatic inference) | **`.github/skills/tableau-mark-mapping/SKILL.md`** |
| Extract per-worksheet encodings (mark, rows/cols, color/size/text, combo, reference lines) | **`.github/skills/tableau-worksheet-extraction/SKILL.md`** |
| Extract dashboard layout (size, zones, navigation buttons, containers, title) | **`.github/skills/tableau-dashboard-extraction/SKILL.md`** |
| Translate format strings + write the extraction output document | **`.github/skills/tableau-format-translation/SKILL.md`** |

## Extraction Order

1. Load `.specify/memory/{WorkbookName}/tableau-extraction.json` (also present: `tableau-visuals-output.md`).
2. For each `worksheets[]` entry: use `inferred_powerbi_visual` (interpret via `tableau-mark-mapping` if you
   need to justify/adjust it) and the `encodings`/`rows`/`cols` fields -> `tableau-worksheet-extraction`.
3. For each `dashboards[]` entry: use `size`, zone `*_px` positions, and `buttons[]` -> `tableau-dashboard-extraction`.
4. Translate `field_formatting[]`/per-field `powerbi_format` -> `tableau-format-translation`.

## Completeness Gate (before handoff)

- Every `worksheets[]` entry has a `mark_type` + `inferred_powerbi_visual` (the extractor guarantees this).
- Dashboard zone positions (`*_px`) present for ALL `dashboards[]`; `buttons[]` present where the workbook had them.
- Dual-axis/combo and reference/trend lines are read from `dual_axis` / `reference_lines[]` (value or empty).

If `tableau-extraction.json` is missing or a `worksheets[]` entry is empty, **re-run the deterministic
extractor** (`tableau-analysis/SKILL.md`) before proceeding — do not hand-parse the XML.

## Anti-Hallucination

- Extract only what the XML contains; write `None`/`Default` for empty categories.
- Copy format strings verbatim (after entity decoding); never rewrite or guess. Resolve `goto-sheet` targets to real dashboards.
