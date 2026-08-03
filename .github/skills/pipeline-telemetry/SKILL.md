---
name: pipeline-telemetry
description: "Record Tableau-to-Power-BI migration stage timing, retries, model and token usage, artifact hashes, and validation outcomes in workbook-scoped pipeline-state.json. Use during every migration pipeline stage and retry."
---

# Pipeline Telemetry

Use `.github/scripts/pipeline_telemetry.py` from the repository root. State is
written atomically to `.specify/memory/{WorkbookName}/pipeline-state.json`.

## Required Protocol

1. Initialize once at the beginning of a migration. Do not use `--reset` when
  resuming an existing run. Use `init --new-run` for a deliberate full rerun;
  this archives prior stage telemetry under `run_history`.
2. Start a new attempt immediately before each stage or subagent call.
3. Complete or fail that attempt immediately afterward. Re-running `start` for
   the same stage creates a retry attempt and preserves prior attempts.
4. Record each validator invocation under `validation_results`.
5. Finish the run only after all stages have a terminal status.

```powershell
py ".github/scripts/pipeline_telemetry.py" init --workbook "{WorkbookName}"

# Deliberate rerun after the previous run finished
py ".github/scripts/pipeline_telemetry.py" init --workbook "{WorkbookName}" --new-run

py ".github/scripts/pipeline_telemetry.py" start `
  --workbook "{WorkbookName}" --stage "04-specify" `
  --name "Write specification" --agent "speckit.specify" --model "{ModelName}"

py ".github/scripts/pipeline_telemetry.py" complete `
  --workbook "{WorkbookName}" --stage "04-specify" `
  --input-tokens {InputTokens} --output-tokens {OutputTokens} `
  --artifact "specs/{FeatureName}/spec.md"

py ".github/scripts/pipeline_telemetry.py" fail `
  --workbook "{WorkbookName}" --stage "04-specify" --error "{FailureSummary}"

py ".github/scripts/pipeline_telemetry.py" validation `
  --workbook "{WorkbookName}" --stage "11-model-validation" `
  --validator "validate_pbip" --status passed --exit-code 0 --summary "0 errors"

py ".github/scripts/pipeline_telemetry.py" run-finish `
  --workbook "{WorkbookName}" --status completed
```

## Usage Rules

- Pass token arguments only when the runtime returns actual counts. Omit them
  when unavailable; the state records the attempt under `unknown_token_attempts`.
- Never estimate or infer token counts from text length.
- Pass the selected model name when known. Do not fabricate it.
- Use `--artifact` repeatedly for all primary outputs. Files and directories are
  hashed with SHA-256 so checkpoint validity can be tested later.
- Capture validator output to a file and pass `--output` when detailed findings
  are available. Never write credentials, access tokens, prompts containing
  secrets, source data rows, or full customer data into telemetry.

## Known Limitation: Token Usage Is Almost Always Unknown

Subagent tool results never expose the invoking model's real token usage, so
`start`/`complete`/`fail` are called without `--input-tokens`/`--output-tokens`
in virtually every run. This is expected, not a bug — every prior run's
`known_token_attempts: 0` reflects that no real number was ever available at
record time, not a recorder defect.

**Real usage may exist only in the local session store, and only when cloud
sync is enabled** (`chat.sessionSync.enabled`). Verify the backend before
attempting reconciliation: query `session_store_sql` for
`SELECT 1 FROM events LIMIT 1`. If it errors with `no such table: events`, the
active backend is local SQLite, which has no per-turn token columns, and
reconciliation is not possible for this run — do not fabricate numbers to fill
the gap.

If the `events` table exists (cloud backend), reconcile after a stage
completes:

1. Query `session_store_sql` for rows where `type = 'assistant.usage'` and
   `timestamp` falls between the stage attempt's `started_at`/`ended_at`
   (join `sessions` on `session_id` and scope to the active session/branch).
2. Sum `usage_input_tokens`/`usage_output_tokens` and note `usage_model`.
3. Attach the real numbers to the already-terminal attempt with
   `update-usage` — this does not require reopening the stage:

```powershell
py ".github/scripts/pipeline_telemetry.py" update-usage `
  --workbook "{WorkbookName}" --stage "04-specify" `
  --input-tokens {RealInputTokens} --output-tokens {RealOutputTokens} `
  --source "session-store-reconciliation"
```

`--attempt {N}` targets a specific retry attempt instead of the latest one.
`update-usage` rejects a still-running attempt (complete/fail it first),
rejects a call with no token values, and requires `--source` so reconciled
numbers are always distinguishable from `source: "runtime"` values recorded
directly by `complete`/`fail`.

## Canonical Stage IDs

`01-analysis`, `02-constitution`, `03-feature`, `04-specify`, `05-clarify`,
`06-dax`, `07-star-schema`, `08-plan`, `09-tasks`, `10-model-generation`,
`11-model-validation`, `12-cross-artifact-analysis`, `13-report-generation`,
`14-final-validation`.
