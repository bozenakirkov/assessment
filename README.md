# Workflow Execution Service

A small workflow management system that executes long-running business processes using a state machine.

The application allows users to create workflows, trigger manual actions, 
and monitor automated worker-driven transitions.

Example workflow:

```
CREATED → VALIDATING → APPROVED → PROCESSING → COMPLETED
```

Possible failure and cancellation states:

```
VALIDATION_FAILED
PROCESSING_FAILED
CANCELLED
```


# Architecture

The application is divided into four components.

## Python API

The Python service is the main application component. 
It owns the workflow state machine and is responsible for all workflow changes.

Responsibilities:
- create and retrieve workflows;
- validate allowed state transitions;
- store workflow history;
- create actions for background processing;
- handle worker results;
- protect workflow updates from conflicting changes.

The API communicates with PostgreSQL for persistence.


## PostgreSQL Database

PostgreSQL stores all workflow-related data:

- workflows;
- workflow actions;
- workflow transition history.

Database transactions are used when a workflow transition modifies multiple records. 
Row-level locking and version checks prevent inconsistent updates when multiple requests modify the same workflow.


## Node.js Worker

The worker simulates background processing.

The flow is:

1. The worker requests pending actions from the API.
2. The worker executes the simulated operation.
3. The worker reports the result back to the API.
4. The API updates the workflow state based on the result.

The worker does not modify workflow state directly. 
The Python API remains responsible for all workflow transitions and persistence.


## Frontend

The frontend is a small static HTML/JavaScript application.

It provides:
- workflow creation;
- workflow list view;
- workflow details;
- manual transition buttons;
- workflow history and action information.

The frontend communicates only with the Python API.


# Running the application

Requirements:

- Docker
- Docker Compose

Start all services:

```bash
docker compose up --build
```

The API is available at:

```
http://localhost:5000
```

Run tests:

```bash
docker compose run tests
```


# API Documentation

Swagger/OpenAPI documentation is available at:

```
http://localhost:5000/apidocs/
```

It contains available endpoints, required parameters, and response descriptions.


# Frontend

The frontend is a static HTML/JavaScript application.

Open:

```
frontend/index.html
```

in a browser while the backend API is running.

The frontend communicates with:

```
http://localhost:5000
```


# Persistence Choice

PostgreSQL was selected because the application requires transactional updates and safe handling of concurrent requests.

A single workflow transition can update several records, such as workflow state, workflow history, and worker actions. 

These changes need to be committed together to keep the data consistent.

PostgreSQL transactions, row-level locking, and version checks are used to protect workflow updates.

The database is included in the Docker Compose setup and starts automatically with the application.


# State Machine Design

Workflow transition rules are separated from API handlers and implemented in `state_machine.py`.

Manual transitions:

```
CREATED + START_VALIDATION  → VALIDATING
APPROVED + START_PROCESSING  → PROCESSING

CREATED + CANCEL             → CANCELLED
VALIDATING + CANCEL          → CANCELLED
APPROVED + CANCEL            → CANCELLED
```

Worker-driven transitions:

```
VALIDATE + SUCCESS           → APPROVED
VALIDATE + FAILED            → VALIDATION_FAILED

PROCESS + SUCCESS            → COMPLETED
PROCESS + FAILED             → PROCESSING_FAILED
```

Keeping these rules outside the API layer prevents invalid state changes and keeps the workflow logic in one place.


# Design Decisions

## Automated transitions

Worker results are translated internally into APPROVE/REJECT/COMPLETE/FAIL history actions.

The transitions `COMPLETE` and `FAIL` are not available through the public API.

They are triggered only after the worker reports the result of a background action.

This keeps manual user actions separate from system-generated state changes and ensures 

that a workflow can only complete after the related processing has actually finished.


## Idempotency

Worker results are handled idempotently.

If the same worker result is submitted multiple times:

- the workflow transition is not executed again;
- duplicate history records are not created;
- the workflow state remains consistent.

Already processed actions return the existing action status.


## Concurrency Protection

Workflow updates are protected using database locking and version checks.

When a transition is performed:

- the workflow record is locked during processing;
- the expected version is checked before updating;
- stale updates are rejected.


# Logging

The application uses Python logging with the following levels:

- `INFO` for important workflow events (creation, transitions, worker results);
- `WARNING` for invalid requests, rejected transitions, and errors;
- `DEBUG` for read-only operations and detailed inspection logs;
- `ERROR` (using `logger.exception` to include stack traces) for unexpected failures.

Flask request logs are reduced to `WARNING` level to avoid excessive noise.


# API Examples

## Create workflow

Request:

```
POST /workflows
```

Body:

```json
{
  "reference": "order-123",
  "payload": {
    "amount": 120.50
  }
}
```

Response:

```json
{
  "id": 1,
  "reference": "order-123",
  "state": "CREATED",
  "updatedAt": "2026-07-19T18:44:47Z",
  "version": 1
}
```


## Start validation

Request:

```
POST /workflows/1/transitions
```

Body:

```json
{
  "action": "START_VALIDATION"
}
```


Response:

```json
{
  "workflowId": 1,
  "state": "VALIDATING",
  "message": "Transition completed successfully"
}
```


## Worker result

Request:

```
POST /actions/1/result
```

Body:

```json
{
  "status": "SUCCESS",
  "result": {
    "validated": true
  }
}
```


# Testing

The test suite covers:

- successful workflow transition;
- invalid transition rejection;
- worker success handling;
- worker failure handling;
- duplicate worker result handling;
- stale workflow update rejection.

Run tests:

```bash
docker compose run tests
```


# Known Limitations

The current implementation intentionally focuses on the core workflow functionality.

Known limitations:

- no retry mechanism for failed actions;
- no action leasing for multiple workers;
- no production monitoring or metrics;
- database connection management is implemented directly in the API layer 
  and could be improved with a dedicated database module and context-managed connections;
- exception handling could be improved with more specific application exceptions;


# Possible Improvements

With more time, I would add:

- improve exception handling with more specific application exceptions;
- add database connection timeout;
- extract database connection management into a dedicated database module;
- use database context managers for consistent PostgreSQL connection and cursor cleanup;
- add retry support with configurable maximum attempts for failed actions;
- add dead-letter handling for permanently failed actions;
- add correlation IDs across API, worker, and frontend requests;
- add more integration tests (complete workflow lifecycle scenario, cancellation flow, 
  invalid workflow creation requests such as missing reference or invalid amount);
- improve frontend layout by making workflow details easier to access when viewing large workflow lists 
  (for example, using a side panel or a dedicated details section);

# AI Usage

AI tools were used as a development assistant during implementation. 

The generated suggestions were reviewed, adapted, and integrated into the application.

AI was also used to improve documentation.

All final architectural decisions, code changes, and implementation details were manually verified.


