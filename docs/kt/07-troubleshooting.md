# Troubleshooting

Use this page when something fails and you need the fastest path to root cause.

## First Commands To Run

```bash
cd pegasus-backend
curl -sS http://127.0.0.1:8000/health
pytest tests/test_api_validate_local.py -vv
```

```bash
cd pegasus-frontend
npm run lint
npm run build
```

These commands answer three questions quickly: is the API alive, is the backend validation path healthy, and does the frontend still build.

## Validation Does Not Start

- Confirm the backend is running and reachable from the frontend.
- Confirm `VITE_API_BASE` points to the correct backend host when needed.
- Confirm both file paths exist and are readable by the backend process.
- Confirm the UID column name is not blank.
- Confirm the request body matches the selected file format.

## Delimiter Or Layout Looks Wrong

- Check whether auto-detection chose the wrong delimiter.
- Verify the file is really CSV and not fixed-width or JSON.
- For fixed-width files, inspect the layout preview before validation.
- For mapping runs, confirm the source and target headers actually match what the wizard inferred.
- If the preview is empty, check whether the file has blank lines or an unexpected encoding.

## Validation Hangs Or Takes Too Long

- Check whether the job was accepted into the queue but not yet started.
- Review queue concurrency and auto-tune settings.
- Large files may switch to external-memory reconciliation, which is slower but safer.
- Confirm the host has enough RAM and free disk for the reconciliation path.
- If a run used a background worker, check the job poll endpoint rather than the original submit request.

## History Or Dashboard Is Empty

- Confirm validation persistence is enabled.
- Confirm the database schema exists and migrations have been applied.
- Confirm the history query range actually includes recent runs.
- Confirm the backend can reach the database without connection errors.
- Confirm `PEGASUS_DATABASE_ENCRYPTION_KEY` is set when persistence is enabled.

## Mismatch Counts Look Wrong

- Recheck UID selection.
- Recheck compare columns and column mappings.
- Re-run on a small sample to see whether the issue is data-specific or systemic.
- Compare header and footer validation settings between the run and your expectations.
- Compare the fixture manifest against the actual response when using generated data.

## CORS And Browser Failures

- If the browser says `Failed to fetch`, confirm `PEGASUS_CORS_ORIGINS` includes the frontend origin.
- Confirm the frontend is pointing at the correct backend origin through `VITE_API_BASE`.
- Confirm the browser URL and the allowed origin are the same host and port pair you expect.

## Database And Migration Failures

- Confirm the database exists before running Alembic.
- Confirm the custom schema exists if you use one.
- Run `alembic -c alembic.ini upgrade head` after installing backend dependencies.
- Check for `PEGASUS_DATABASE_URL` precedence over older `DB_*` variables if the connection string looks wrong.

## Recommended Debug Order

1. Reproduce the issue with the smallest possible dataset.
2. Read the backend response body, not just the status code.
3. Check the relevant test file for expected behavior.
4. Inspect the exact validation mode being used.
5. Escalate to queue, resource, or persistence settings only after format and UID checks pass.
