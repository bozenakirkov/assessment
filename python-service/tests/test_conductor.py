import uuid

import requests

from conftest import FAKE_CONDUCTOR_ID


def create_workflow(client, amount=100):
    reference = f"test-conductor-{uuid.uuid4()}"
    payload = {"customerId": "customer-1", "amount": amount}
    response = client.post(
        "/workflows",
        json={"reference": reference, "payload": payload},
    )
    assert response.status_code == 200
    return response.get_json()["id"], reference, payload


def transition(client, workflow_id, action):
    return client.post(
        f"/workflows/{workflow_id}/transitions",
        json={"action": action},
    )


def pending_action_id(client, workflow_id, action_type):
    actions = client.get("/actions/pending").get_json()
    return next(
        a["id"] for a in actions
        if a["workflowId"] == workflow_id and a["type"] == action_type
    )


def test_start_validation_starts_validation_workflow(client, conductor_calls):
    workflow_id, reference, payload = create_workflow(client)

    response = transition(client, workflow_id, "START_VALIDATION")

    assert response.status_code == 200
    assert response.get_json()["conductorExecutionId"] == FAKE_CONDUCTOR_ID

    assert len(conductor_calls) == 1
    call = conductor_calls[0]
    assert call["workflow_name"] == "validation_workflow"
    assert call["reference"] == reference
    assert call["payload"] == payload
    assert call["action_id"] == pending_action_id(client, workflow_id, "VALIDATE")


def test_start_processing_starts_processing_workflow(client, conductor_calls):
    workflow_id, reference, _ = create_workflow(client)

    transition(client, workflow_id, "START_VALIDATION")
    validate_id = pending_action_id(client, workflow_id, "VALIDATE")
    client.post(f"/actions/{validate_id}/result", json={"status": "SUCCESS"})

    response = transition(client, workflow_id, "START_PROCESSING")

    assert response.status_code == 200
    call = conductor_calls[-1]
    assert call["workflow_name"] == "processing_workflow"
    assert call["reference"] == reference
    assert call["action_id"] == pending_action_id(client, workflow_id, "PROCESS")


def test_cancel_does_not_call_conductor(client, conductor_calls):
    workflow_id, _, _ = create_workflow(client)

    response = transition(client, workflow_id, "CANCEL")

    assert response.status_code == 200
    assert response.get_json()["state"] == "CANCELLED"
    assert conductor_calls == []


def test_conductor_error_rolls_back_transition(client, monkeypatch):
    def failing_start(**kwargs):
        raise requests.ConnectionError("conductor down")

    monkeypatch.setattr("app.start_conductor_workflow", failing_start)
    workflow_id, _, _ = create_workflow(client)

    response = transition(client, workflow_id, "START_VALIDATION")

    assert response.status_code == 502
    assert client.get(f"/workflows/{workflow_id}").get_json()["state"] == "CREATED"
    assert client.get(f"/workflows/{workflow_id}/actions").get_json() == []
    assert client.get(f"/workflows/{workflow_id}/history").get_json() == []


def test_conductor_timeout_returns_504_and_rolls_back(client, monkeypatch):
    def slow_start(**kwargs):
        raise requests.Timeout()

    monkeypatch.setattr("app.start_conductor_workflow", slow_start)
    workflow_id, _, _ = create_workflow(client)

    response = transition(client, workflow_id, "START_VALIDATION")

    assert response.status_code == 504
    assert client.get(f"/workflows/{workflow_id}").get_json()["state"] == "CREATED"
    assert client.get(f"/workflows/{workflow_id}/actions").get_json() == []
