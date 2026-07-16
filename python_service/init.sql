CREATE TABLE workflows (
    id SERIAL PRIMARY KEY,
    reference VARCHAR(255) UNIQUE NOT NULL,
    payload JSONB NOT NULL,
    state VARCHAR(50) NOT NULL,
    version INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE actions (
    id SERIAL PRIMARY KEY,
    workflow_id INTEGER NOT NULL REFERENCES workflows(id),
    type VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    payload JSONB NOT NULL,
    result JSONB,
    error TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE workflow_history (
    id SERIAL PRIMARY KEY,
    workflow_id INTEGER NOT NULL REFERENCES workflows(id),
    from_state VARCHAR(30),
    to_state VARCHAR(30),
    action VARCHAR(30),
    timestamp TIMESTAMP NOT NULL
);
