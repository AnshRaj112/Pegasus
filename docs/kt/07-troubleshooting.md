# Troubleshooting

Use this page when something fails and you need the fastest path to root cause.

## Validation Does Not Start

- Confirm the backend is running and reachable from the frontend.
- Confirm `VITE_API_BASE` points to the correct backend host when needed.
- Confirm both file paths exist and are readable by the backend process.
- Confirm the UID column name is not blank.

## Delimiter Or Layout Looks Wrong

- Check whether auto-detection chose the wrong delimiter.
- Verify the file is really CSV and not fixed-width or JSON.
- For fixed-width files, inspect the layout preview before validation.
- For mapping runs, confirm the source and target headers actually match what the wizard inferred.

## Validation Hangs Or Takes Too Long

- Check whether the job was accepted into the queue but not yet started.
- Review queue concurrency and auto-tune settings.
- Large files may switch to external-memory reconciliation, which is slower but safer.
- Confirm the host has enough RAM and free disk for the reconciliation path.

## History Or Dashboard Is Empty

- Confirm validation persistence is enabled.
- Confirm the database schema exists and migrations have been applied.
- Confirm the history query range actually includes recent runs.
- Confirm the backend can reach the database without connection errors.

## Mismatch Counts Look Wrong

- Recheck UID selection.
- Recheck compare columns and column mappings.
- Re-run on a small sample to see whether the issue is data-specific or systemic.
- Compare header and footer validation settings between the run and your expectations.

## Recommended Debug Order

1. Reproduce the issue with the smallest possible dataset.
2. Read the backend response body, not just the status code.
3. Check the relevant test file for expected behavior.
4. Inspect the exact validation mode being used.
5. Escalate to queue, resource, or persistence settings only after format and UID checks pass.
