# Frontend Walkthrough

The frontend is a React + Vite app that focuses on validation submission, queue control, history browsing, and dashboard visibility.

## Main Screens And Components

- `App.jsx` is currently the starter shell in the repo and is not the real Pegasus UI.
- `Dashboard.jsx` renders validation trends and pulls history stats from the backend.
- `ValidationPanel.jsx` is the main validation control surface.
- `History.jsx`, `DetailedReport.jsx`, `ValidationResultsModal.jsx`, and related components present run results and mismatch details.
- The mapping components drive column matching and compare-rule setup.

## Validation Submission Flow

- The user chooses source and target paths.
- The user selects CSV or JSON mode and enters UID and delimiter information.
- The panel updates queue settings before starting the validation.
- The request is submitted to the backend and the UI either receives the final result or polls for completion.

## History And Dashboard Flow

- `validationHistory.js` wraps the history API calls.
- The dashboard fetches daily stats and history data to render the trend chart.
- Filters support daily, weekly, monthly, and custom date ranges.
- The page converts timestamps for display and keeps the chart labels readable in the selected range.

## Mapping Wizard Flow

- The mapping wizard previews source and target columns.
- Exact-name suggestions help the user map compare columns quickly.
- Header and footer checks can be toggled as part of the mapping analysis.
- The analysis result is saved as a draft before the final validation run.

## Current Frontend Test Situation

- The repository does not currently contain frontend test files.
- Verification today is mainly through linting, build output, and manual end-to-end flows against the backend.

## What To Watch For

- The frontend depends on `VITE_API_BASE` when the backend is not on the same origin.
- Polling timeouts can make a large validation appear stuck if the timeout is too small.
- Queue controls can change the apparent runtime even when the validation logic is healthy.
