# System Design

This page explains Pegasus as a system, not just as a set of endpoints or scripts.

It covers the major components, how requests move through the stack, where compute happens, how large jobs are isolated, and how the frontend, backend, worker pool, and database relate to each other.

## High-Level Goal

Pegasus validates two datasets, computes mismatch output, and preserves enough metadata for users to inspect history and understand what changed.

The design has three priorities:

- Correctness of comparison results.
- Scalability for large files.
- Traceability through persisted history and mismatch records.

## System Components

### Frontend

The frontend is the browser-facing application.

It is responsible for:

- File selection and validation submission.
- Queue controls and job status presentation.
- Dashboard charts and history browsing.
- Mapping preview and compare-rule configuration.

The frontend does not do the actual comparison work. It always delegates to the API.

### API Server

The FastAPI server is the public entry point for all validation and history actions.

It is responsible for:

- Validating request payloads.
- Resolving local or cloud file inputs.
- Selecting the correct validation path.
- Applying queue and runtime policy.
- Returning validation results or job polling state.
- Serving persisted history data.

### Validation Service

The validation service is the heart of the system.

It decides:

- How the files should be parsed.
- Whether CSV, fixed-width, or JSON logic applies.
- Whether the job can run in memory.
- Whether reconciliation should spill to disk or partition work.
- Whether header/footer validation should run.

If you understand this service, you understand most of the backend behavior.

### Comparison Engine

The comparison engine is the part of the system that turns two inputs into a mismatch report.

It includes:

- Readers and parsers.
- UID pairing logic.
- Compare-rule resolution.
- UID-based comparators.
- Reconciliation strategies for large runs.

### Worker Pool And Queue

Large validations are not meant to block a single request thread.

Instead, Pegasus uses a concurrency-limited queue and worker pool so multiple runs can be scheduled safely without overwhelming the host.

This layer handles:

- FIFO admission of jobs.
- Host-aware concurrency caps.
- Background validation execution.
- Worker shutdown and cleanup.

### Storage Layer

The storage layer persists validation run metadata and mismatch rows when persistence is enabled.

It also stores encrypted fields so sensitive paths and payload fragments are not saved as plain text.

## Design Philosophy

### 1. Compare By UID, Not Row Position

Row order is not trusted.

The system assumes the same logical record can appear in a different physical position in each file, so it matches rows by UID and then checks compared columns.

This is why the same fixture can be shuffled and still validate correctly.

### 2. Prefer Streaming Or Partitioned Processing For Large Jobs

The system is designed to degrade gracefully when files get too large for a simple in-memory comparison.

Instead of trying to keep everything in RAM, Pegasus can:

- Spill partitions.
- Reconcile in external memory.
- Compare sorted streams.
- Use sliding-window or hash-partition strategies depending on the runtime configuration.

### 3. Keep The UI Thin

The frontend is intentionally a shell around backend APIs.

The design keeps the real validation logic server-side so the same engine can serve the browser UI, CLI-driven scripts, and future integrations.

### 4. Persist Enough To Debug, Not Everything Forever

The persisted model stores the run summary and mismatch rows needed for history and troubleshooting.

It does not try to become a full data warehouse.

## End-To-End Request Flow

1. The user selects source and target inputs in the browser.
2. The frontend sends the request to the FastAPI server.
3. The API validates the request and resolves inputs.
4. The validation service determines the execution strategy.
5. The comparison engine reads, normalizes, and compares the files.
6. The result is returned to the client and optionally persisted.
7. If persistence is enabled, the run appears in history and dashboard charts.

## Runtime Paths

### Small CSV Run

For small files, the system can load both datasets into memory and compare them directly.

This is the simplest path:

- Easy to debug.
- Lowest orchestration overhead.
- Best for small fixtures and local testing.

### Large CSV Run

For larger files, the system shifts to reconciliation.

The exact strategy depends on runtime configuration and host capacity, but the goal is the same:

- Avoid loading the entire comparison into RAM.
- Maintain throughput.
- Keep the job safe on limited hardware.

### Fixed-Width Run

Fixed-width runs are treated as slice-based comparisons.

The system first verifies that the slice layout and date formats are sane, then performs a streaming comparison so large files do not need to be materialized entirely in memory.

### JSON Run

JSON runs are document-based rather than column-delimited.

They still follow the same overall model:

- Validate input.
- Compare keys or nested fields.
- Build mismatch records.
- Persist the run if configured.

## Scaling Strategy

Pegasus scales using a layered strategy.

### Input Layer

The backend avoids trusting the browser to do any real work.

### Execution Layer

The validation service chooses between in-memory, external-memory, hash-partition, ordered-stream, or sliding-window behavior.

### Worker Layer

When jobs are large enough or numerous enough, work is isolated in background workers so the API remains responsive.

### Storage Layer

Persistence is optional, but when enabled it gives the system a stable operational record.

## Observability And Debugging

The system is designed to be explainable.

Useful signals include:

- API response status.
- Validation summary counts.
- Queue status and effective concurrency.
- Validation history entries.
- Mismatch artifacts and row detail.
- Database persistence failures.

When debugging, the first question is usually whether the failure is in input resolution, comparison logic, queueing, or persistence.

## Key Tradeoffs

### Accuracy Versus Speed

Detailed row detail and long-form mismatch rows make debugging easier, but they cost memory and I/O.

### Generality Versus Specialization

Pegasus supports several file types, but each one has a dedicated path rather than one universal parser.

### Simplicity Versus Scale

The system remains simple for small runs, but adds worker, partition, and spill complexity when data size requires it.

## How The Diagram Fits The Code

The repository diagram in [docs/diagrams/system_architecture.mmd](../diagrams/system_architecture.mmd) maps directly to the implementation:

- Browser UI -> FastAPI server.
- FastAPI server -> Validation service.
- Validation service -> Validation engine / reconciliation.
- Validation engine -> temp storage and database.
- Validation service / API -> worker pool and queue.

That diagram is a good mental model for onboarding and troubleshooting.

## What To Read Next

- [Backend logic](04-backend-logic.md) for the request path and validation branches.
- [Database design](12-database-design.md) for persistence and schema details.
- [Tests](06-tests.md) for behavior coverage.
