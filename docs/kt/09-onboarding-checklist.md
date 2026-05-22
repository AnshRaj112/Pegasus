# Onboarding Checklist

Use this checklist when you are joining the project or switching into a new area of the codebase.

## Day 1 Setup

- Read the KT overview and the backend logic page.
- Install backend dependencies and run the backend locally.
- Install frontend dependencies and run the frontend locally.
- Confirm the backend and frontend can talk to each other.
- Inspect the `scripts/` folder and understand which utilities are interactive.

## Environment Setup Checklist

- Create a Python virtual environment in `pegasus-backend/`.
- Install backend runtime and dev dependencies.
- Set `PEGASUS_DATABASE_URL` or the older `DB_*` variables.
- Set `PEGASUS_DATABASE_ENCRYPTION_KEY` if persistence is enabled.
- Set `PEGASUS_CORS_ORIGINS` to include the Vite dev origin.
- Run Alembic migrations before attempting persistence-backed features.

## Core Understanding

- Understand the difference between CSV, fixed-width, and JSON validation.
- Understand how UID-based comparison works.
- Understand where persistence happens and how history is queried.
- Understand how queue settings and resource tuning affect large runs.
- Understand the difference between local validation, history browsing, and background job polling.

## Practical Checks

- Run at least one small validation end to end.
- Inspect the validation history endpoint after a successful run.
- Open the dashboard and confirm the chart updates.
- Review one or two tests from each major subsystem.
- Generate one fixture with a script and validate it through the API.

## Before Making Changes

- Identify the owning subsystem first.
- Check whether a matching test already exists.
- Verify whether the change affects API behavior, validation logic, history, or UI.
- Prefer the smallest change that proves the behavior you want.
- If the change touches the queue or persistence, verify the runtime settings first.

## Good First Tasks

- Improve docs or examples in the mapping flow.
- Add coverage for a missing edge case in the backend tests.
- Add frontend test scaffolding if you are working in the UI area.
- Improve error messages in a single validation path.
- Add one more fixture command example to the scripts guide.
