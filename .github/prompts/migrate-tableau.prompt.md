---
agent: migration-constitution
description: Run the full Tableau → Power BI migration pipeline (analysis → semantic model → report visuals) end to end.
---

## User Input

```text
$ARGUMENTS
```

You are running in the top-level chat session, so the `runSubagent` tool IS available to you.
Delegation is one level deep only — that is why this pipeline is a prompt file and not a subagent.

## Stage 0 — Analyze the Workbook (via tableau-analysis agent)

Before Stage 1, resolve the target workbook and run the deterministic extraction:

1. If the user input names a workbook or subfolder, use it. Otherwise list `Data/` and, when more than one
   workbook is present, ask which one to migrate before continuing.
2. Derive `{WorkbookName}` as the PascalCase, space-free form of the `Data/` subfolder name — this is also
   the `Output/{WorkbookName}/` folder name and the `.specify/memory/{WorkbookName}/` scope.
3. Call the analysis agent (it runs the deterministic Python extractor — it does NOT hand-parse XML):

```
runSubagent(
  agentName: "tableau-analysis",
  prompt: "Run the deterministic Tableau extractor on Data/{subfolder}/{workbook}.twb by executing `python \".github/skills/tableau-analysis/scripts/tableau_extractor.py\" \"Data/{subfolder}/{workbook}.twb\" --name \"{WorkbookName}\"`. This writes .specify/memory/{WorkbookName}/tableau-extraction.json (the deterministic source of truth) plus tableau-analysis-output.md and tableau-visuals-output.md. Verify the JSON parses and relay its summary + any warnings. Do NOT attempt to hand off to another agent — return your summary to me and I will continue the pipeline.",
  description: "Extract Tableau workbook"
)
```

4. Confirm `.specify/memory/{WorkbookName}/tableau-extraction.json` exists before proceeding.

## Stages 1–14 — Run the Pipeline

Now execute Stages 1 through 14 exactly as defined in your instructions, calling `runSubagent` for each of the
nine designated stage agents and running both plugin validators at the Stage 11 and Stage 14 gates.

Do not write spec, clarification, DAX, star schema, plan, tasks, TMDL, or PBIR content yourself — your role is
sequencing, context handoff, and validation gates only.
