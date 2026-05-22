# Frontend Walkthrough

The frontend is a React + Vite app that focuses on validation submission, queue control, history browsing, and dashboard visibility.

## Routes And Entrypoints

- `/` renders the main app shell.
- `/report` renders the detailed report view.
- The actual Pegasus validation experience is driven by feature components rather than the starter `App.jsx` scaffold.

## Main Screens And Components

- `Dashboard.jsx` renders validation trends and pulls history stats from the backend.
- `ValidationPanel.jsx` is the main validation control surface.
- `History.jsx`, `DetailedReport.jsx`, `ValidationResultsModal.jsx`, and related components present run results and mismatch details.
- `MappingWizard.jsx`, `Step1_DataSource.jsx`, `Step2_FilePicker.jsx`, `Step3_Configure.jsx`, and `ActionBar.jsx` drive the mapping flow.
- `ParallelValidationModal.jsx` and `ParallelValidationResourceForm.jsx` control queue and concurrency settings.
- `MismatchSampleRows.jsx`, `Missing.jsx`, `Extra.jsx`, and `Mismatched.jsx` render the final discrepancy views.

## Validation Submission Flow

1. The user chooses source and target paths.
2. The user selects CSV or JSON mode and enters UID and delimiter information.
3. The panel updates queue settings before starting the validation.
4. The request is submitted to the backend and the UI either receives the final result or polls for completion.
5. When the backend returns a poll URL, the panel continues until the job is completed or failed.

## History And Dashboard Flow

- `validationHistory.js` wraps the history API calls.
- The dashboard fetches daily stats and history data to render the trend chart.
- Filters support daily, weekly, monthly, and custom date ranges.
- The page converts timestamps for display and keeps the chart labels readable in the selected range.
- The chart uses the persisted history so it reflects actual backend runs, not client-side guesses.

## Mapping Wizard Flow

- The mapping wizard previews source and target columns.
- Exact-name suggestions help the user map compare columns quickly.
- Header and footer checks can be toggled as part of the mapping analysis.
- The analysis result is saved as a draft before the final validation run.
- The preview endpoints help the user decide whether delimiter detection or manual mappings are needed.

## API Calls The UI Makes

- `POST /api/v1/validate/local` starts a local validation.
- `GET /api/v1/validate/queue` reads queue state.
- `PATCH /api/v1/validate/queue` updates max concurrency and auto-tuning.
- `GET /api/v1/validate/history` lists prior runs.
- `GET /api/v1/validate/history/daily-stats` fetches chart data.
- `GET /api/v1/validate/local/columns` fetches column previews for mapping.

## Environment And Runtime Notes

- `VITE_API_BASE` should point at the backend when the UI and API do not share the same origin.
- The UI assumes the backend allows the browser origin through CORS.
- Polling timeouts can make a large validation appear stuck if the timeout is too small.
- Queue controls can change the apparent runtime even when the validation logic is healthy.

## Current Frontend Test Situation

- The repository does not currently contain frontend test files.
- Verification today is mainly through linting, build output, and manual end-to-end flows against the backend.

## What To Watch For

- If the validation screen looks blank, check the API base URL first.
- If charts are empty, confirm history persistence is enabled and the backend has data.
- If the queue modal shows stale numbers, refresh the page and re-read the queue endpoint.
