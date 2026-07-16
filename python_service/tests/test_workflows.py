import pytest
import threading
import uuid

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client


@pytest.fixture
def app_instance():
    app.config["TESTING"] = True
    return app


def create_test_workflow(client):
    response = client.post(
        "/workflows",
        json={
            "reference": f"test-order-{uuid.uuid4()}",
            "payload": {
                "customerId": "customer-1",
                "amount": 100
            }
        }
    )
    print("====>", response.get_json())
    assert response.status_code == 200

    return response.get_json()["id"]


def test_valid_start_validation_transition(client):
    """
    CREATED -> VALIDATING
    """

    workflow_id = create_test_workflow(client)

    response = client.post(
        f"/workflows/{workflow_id}/transitions",
        json={
            "action": "START_VALIDATION"
        }
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["state"] == "VALIDATING"


def test_invalid_transition_is_rejected(client):
    """
    CREATED -> PROCESSING is invalid
    """

    workflow_id = create_test_workflow(client)

    response = client.post(
        f"/workflows/{workflow_id}/transitions",
        json={
            "action": "START_PROCESSING"
        }
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["code"] == "INVALID_TRANSITION"


def test_worker_success_result_moves_workflow_to_approved(client):
    """
    VALIDATING + VALIDATE SUCCESS -> APPROVED
    """

    workflow_id = create_test_workflow(client)

    client.post(
        f"/workflows/{workflow_id}/transitions",
        json={
            "action": "START_VALIDATION"
        }
    )

    response = client.get("/actions/pending")

    actions = response.get_json()

    assert len(actions) > 0

    action_id = actions[0]["id"]

    result = client.post(
        f"/actions/{action_id}/result",
        json={
            "status": "SUCCESS",
            "result": {
                "validated": True
            }
        }
    )

    assert result.status_code == 200

    data = result.get_json()

    assert data["state"] == "APPROVED"


def test_duplicate_worker_result_is_idempotent(client):
    """
    Sending the same worker result twice
    must not create duplicate transitions.
    """

    workflow_id = create_test_workflow(client)

    client.post(
        f"/workflows/{workflow_id}/transitions",
        json={
            "action": "START_VALIDATION"
        }
    )

    actions = client.get(
        "/actions/pending"
    ).get_json()

    ##########
    print("PENDING ACTIONS:", actions)
    action = next(
        a for a in actions
        if a["workflowId"] == workflow_id
    )

    action_id = action["id"]

    payload = {
        "status": "SUCCESS",
        "result": {
            "validated": True
        }
    }

    first = client.post(
        f"/actions/{action_id}/result",
        json=payload
    )

    second = client.post(
        f"/actions/{action_id}/result",
        json=payload
    )

    assert first.status_code == 200
    assert second.status_code == 200

    history = client.get(
        f"/workflows/{workflow_id}/history"
    ).get_json()

    # START_VALIDATION + worker SUCCESS only
    assert len(history) == 2


def test_worker_failure_moves_workflow_to_failed_state(client):
    """
    PROCESSING + PROCESS FAILED -> PROCESSING_FAILED
    """

    workflow_id = create_test_workflow(client)

    # START validation
    client.post(
        f"/workflows/{workflow_id}/transitions",
        json={
            "action": "START_VALIDATION"
        }
    )

    actions = client.get("/actions/pending").get_json()

    validation_action = next(
        a["id"]
        for a in actions
        if a["workflowId"] == workflow_id
        and a["type"] == "VALIDATE"
    )

    # Validation success
    client.post(
        f"/actions/{validation_action}/result",
        json={
            "status": "SUCCESS",
            "result": {
                "validated": True
            }
        }
    )

    # Start processing
    client.post(
        f"/workflows/{workflow_id}/transitions",
        json={
            "action": "START_PROCESSING"
        }
    )

    actions = client.get("/actions/pending").get_json()

    process_action = next(
        a["id"]
        for a in actions
        if a["workflowId"] == workflow_id
        and a["type"] == "PROCESS"
    )

    response = client.post(
        f"/actions/{process_action}/result",
        json={
            "status": "FAILED",
            "error": "External service failed"
        }
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["state"] == "PROCESSING_FAILED"


def test_concurrent_transitions_do_not_corrupt_state(client, app_instance):

    workflow_id = create_test_workflow(client)

    results = []


    def send_transition(action):

        with app_instance.test_client() as thread_client:

            response = thread_client.post(
                f"/workflows/{workflow_id}/transitions",
                json={
                    "action": action
                }
            )

            results.append(response.status_code)

    thread1 = threading.Thread(
        target=send_transition,
        args=("START_VALIDATION",)
    )

    thread2 = threading.Thread(
        target=send_transition,
        args=("START_PROCESSING",)
    )


    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()


    assert results.count(200) == 1

    workflow = client.get(
        f"/workflows/{workflow_id}"
    ).get_json()

    assert workflow["state"] in [
        "VALIDATING",
        "CANCELLED"
    ]
