# Pegasus Knowledge Transfer

This folder is the KT pack for Pegasus. It is organized so a new engineer can learn the product in layers instead of reading one large document.

Start with the overview, then move through validation types, backend logic, frontend behavior, the test suite, and the operational playbooks.

## Doc Map

- [Overview](00-overview.md)
- [CSV / delimiter validation](01-validation-csv.md)
- [Fixed-width validation](02-validation-fixed-width.md)
- [JSON validation](03-validation-json.md)
- [Backend logic and orchestration](04-backend-logic.md)
- [Frontend walkthrough](05-frontend.md)
- [All tests in one place](06-tests.md)
- [Troubleshooting](07-troubleshooting.md)
- [FAQ](08-faq.md)
- [Onboarding checklist](09-onboarding-checklist.md)

## How To Use This Pack

Read the overview once, then use the validation-specific pages to understand the supported formats. The backend logic page explains how files move through the system, how queueing works, and where persistence happens. The frontend page covers the UI entry points and API calls. The tests page is the fastest way to understand the current quality coverage.

If you are debugging a production issue, jump first to Troubleshooting. If you are joining the project for the first time, use the onboarding checklist before touching code.
