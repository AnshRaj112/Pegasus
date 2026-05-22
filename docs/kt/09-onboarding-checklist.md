# Onboarding Checklist

Use this checklist when you are joining the project or switching into a new area of the codebase.

## Day 1 Setup

- Read the KT overview and the backend logic page.
- Install backend dependencies and run the backend locally.
- Install frontend dependencies and run the frontend locally.
- Confirm the backend and frontend can talk to each other.

## Core Understanding

- Understand the difference between CSV, fixed-width, and JSON validation.
- Understand how UID-based comparison works.
- Understand where persistence happens and how history is queried.
- Understand how queue settings and resource tuning affect large runs.

## Practical Checks

- Run at least one small validation end to end.
- Inspect the validation history endpoint after a successful run.
- Open the dashboard and confirm the chart updates.
- Review one or two tests from each major subsystem.

## Before Making Changes

- Identify the owning subsystem first.
- Check whether a matching test already exists.
- Verify whether the change affects API behavior, validation logic, history, or UI.
- Prefer the smallest change that proves the behavior you want.

## Good First Tasks

- Improve docs or examples in the mapping flow.
- Add coverage for a missing edge case in the backend tests.
- Add frontend test scaffolding if you are working in the UI area.
- Improve error messages in a single validation path.
