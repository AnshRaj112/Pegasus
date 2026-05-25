# FAQ

## What validation modes does Pegasus support?

CSV / delimiter validation, fixed-width validation, and JSON validation are the primary flows documented in this KT pack.

## Why does the UI ask for queue settings before validation?

The backend can run validations in queued or resource-aware modes. The UI exposes queue controls so users can tune concurrency before starting a heavy job.

## Why do some validations return results immediately and others are polled?

Small runs may complete quickly, while larger runs are accepted first and then completed by a background worker. The frontend polls when the backend responds with an accepted job and a poll URL.

## Why does the dashboard use history APIs instead of reading validation files directly?

The dashboard is designed to show persisted validation activity. It reads history endpoints so the UI reflects the same runs the backend records.

## Why is there no frontend test suite yet?

The current repository does not include frontend test files. The current verification path is linting, build checks, and manual API-backed UI testing.

## What is the most common validation mistake?

The most common mistake is picking the wrong UID column or delimiter. After that, bad file paths and mismatched headers are the usual causes.

## When should I use fixed-width validation instead of CSV?

Use fixed-width when the data is aligned by character positions and there is no real delimiter between fields.

## When should I read the tests page first?

Read it first when a bug looks like a regression. The test file names map directly to the subsystem that is most likely failing.
