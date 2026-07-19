import os
import json
from datetime import datetime, timezone
import logging

from flask import Flask, request, jsonify
import psycopg2
from flasgger import Swagger
from flask_cors import CORS

from state_machine import (
    get_manual_transition,
    get_worker_transition,
)
from errors import error_response
from logging_config import configure_logging


configure_logging()
logging.getLogger("werkzeug").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = Flask(__name__)
swagger = Swagger(app)
CORS(app)

DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "workflow_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres123")


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


@app.route("/workflows", methods=["POST"])
def create_workflow():
    """
    Create a new workflow.
    ---
    tags:
      - Workflows
    parameters:
      - name: workflow
        in: body
        required: true
        description: Workflow reference and payload.
    responses:
      200:
        description: Workflow created successfully.
      400:
        description: Invalid request.
      500:
        description: Database error.
    """

    data = request.get_json(silent=True)

    if not data:
        return error_response("INVALID_REQUEST", "No JSON received")

    if "reference" not in data:
        return error_response("INVALID_REQUEST", "Reference missing")

    if "payload" not in data:
        return error_response("INVALID_REQUEST", "Payload missing")

    reference = data["reference"]

    payload_data = data["payload"]

    amount = payload_data.get("amount")

    payload = json.dumps(payload_data)

    logger.debug(
        "workflow_creation_requested reference=%s amount=%s",
        reference,
        amount
    )

    created_at = datetime.now(timezone.utc)

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
                INSERT INTO workflows
                    (reference, payload, state, version, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;
                """, (
                    reference,
                    payload,
                    "CREATED",
                    1,
                    created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                ))

        workflow_id = cur.fetchone()[0]
        conn.commit()
        logger.info(
            "workflow_created workflow_id=%s reference=%s amount=%s",
            workflow_id,
            reference,
            amount
        )

    except Exception as e:

        conn.rollback()

        return error_response("DATABASE_ERROR")

    finally:

        cur.close()
        conn.close()

    return jsonify({
        "id": workflow_id,
        "reference": reference,
        "state": "CREATED",
        "version": 1,
        "createdAt": created_at
    })


@app.route("/workflows/<int:workflow_id>", methods=["GET"])
def get_workflow(workflow_id):
    """
    Get workflow details by ID.
    ---
    tags:
      - Workflows
    parameters:
      - name: workflow_id
        in: path
        required: true
        description: Workflow identifier.
    responses:
      200:
        description: Workflow details returned.
      404:
        description: Workflow not found.
    """
    logger.debug(
        "workflow_retrieval_requested workflow_id=%s",
        workflow_id
    )
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
                SELECT id, reference, state, version, created_at, payload
                FROM workflows
                WHERE id = %s
                """, (workflow_id,))

    row = cur.fetchone()

    cur.close()
    conn.close()

    if row is None:
        logger.warning(
            "workflow_not_found workflow_id=%s",
            workflow_id
        )
        return error_response("WORKFLOW_NOT_FOUND")

    logger.debug(
        "workflow_retrieved workflow_id=%s reference=%s state=%s",
        row[0],
        row[1],
        row[2]
    )

    return jsonify({
        "id": row[0],
        "reference": row[1],
        "state": row[2],
        "version": row[3],
        "createdAt": row[4],
        "payload": row[5]
    })


@app.route("/workflows", methods=["GET"])
def list_workflows():
    """
    Get all workflows.
    ---
    tags:
      - Workflows
    responses:
      200:
        description: List of workflows.
    """
    logger.debug("workflow_list_requested")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
                SELECT id, reference, state, version, updated_at
                FROM workflows
                ORDER BY id;
                """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    workflows = []

    for row in rows:
        workflows.append({
            "id": row[0],
            "reference": row[1],
            "state": row[2],
            "version": row[3],
            "updatedAt": row[4].strftime("%Y-%m-%dT%H:%M:%SZ")
        })

    logger.debug(
        "workflow_list_returned count=%s",
        len(workflows)
    )

    return jsonify(workflows)


@app.route("/workflows/<int:workflow_id>/transitions", methods=["POST"])
def transition_workflow(workflow_id):
    """
    Apply a manual workflow transition.
    ---
    tags:
      - Workflows
    parameters:
      - name: workflow_id
        in: path
        required: true
        description: Workflow identifier.
      - name: action
        in: body
        required: true
        description: Transition action to execute.
    responses:
      200:
        description: Transition completed successfully.
      400:
        description: Invalid transition or request.
      404:
        description: Workflow not found.
      409:
        description: Stale workflow update.
      500:
        description: Database error.
    """
    data = request.get_json()

    if not data or "action" not in data:
        logger.warning(
            "workflow_transition_invalid_request workflow_id=%s",
            workflow_id
        )
        return error_response("INVALID_REQUEST", "Action is required")

    action = data["action"]

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Lock workflow row
        cur.execute("""
            SELECT state, payload, version
            FROM workflows
            WHERE id = %s
            FOR UPDATE
        """, (workflow_id,))

        row = cur.fetchone()

        if row is None:
            logger.warning(
                "workflow_not_found_for_transition workflow_id=%s action=%s",
                workflow_id,
                action
            )
            return error_response("WORKFLOW_NOT_FOUND")

        current_state = row[0]
        payload = json.dumps(row[1])
        current_version = row[2]

        # Validate transition
        try:
            new_state = get_manual_transition(
                current_state,
                action
            )

        except Exception as e:
            conn.rollback()
            logger.warning(
                "workflow_transition_rejected workflow_id=%s state=%s action=%s reason=%s",
                workflow_id,
                current_state,
                action,
                str(e)
            )

            return error_response("INVALID_TRANSITION", str(e))


        # Check duplicate action BEFORE changing workflow
        action_type = None

        if action == "START_VALIDATION":
            action_type = "VALIDATE"

        elif action == "START_PROCESSING":
            action_type = "PROCESS"


        if action_type:

            cur.execute("""
                SELECT id
                FROM actions
                WHERE workflow_id = %s
                AND type = %s
                AND status = 'PENDING'
            """, (
                workflow_id,
                action_type
            ))

            existing_action = cur.fetchone()

            if existing_action:
                logger.info(
                    "workflow_action_already_exists workflow_id=%s action_type=%s action_id=%s",
                    workflow_id,
                    action_type,
                    existing_action[0]
                )

                conn.commit()

                return jsonify({
                    "workflowId": workflow_id,
                    "state": current_state,
                    "message": "Action already created",
                    "actionId": existing_action[0]
                })


        now = datetime.now(timezone.utc)


        # Update workflow
        cur.execute("""
            UPDATE workflows
            SET
                state = %s,
                version = version + 1,
                updated_at = %s
            WHERE id = %s
            AND version = %s
        """, (
            new_state,
            now,
            workflow_id,
            current_version
        ))

        if cur.rowcount != 1:
            conn.rollback()
            logger.warning(
                "workflow_transition_stale_update workflow_id=%s expected_version=%s",
                workflow_id,
                current_version
            )

            return error_response("STALE_WORKFLOW")


        # Save history
        cur.execute("""
            INSERT INTO workflow_history
            (
                workflow_id,
                from_state,
                to_state,
                action,
                timestamp
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            workflow_id,
            current_state,
            new_state,
            action,
            now
        ))


        # Create action
        if action_type:

            cur.execute("""
                INSERT INTO actions
                (
                    workflow_id,
                    type,
                    status,
                    attempt,
                    payload,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                workflow_id,
                action_type,
                "PENDING",
                1,
                payload,
                now,
                now
            ))


        conn.commit()
        logger.info(
            "workflow_transition_completed workflow_id=%s %s - %s - %s",
            workflow_id,
            current_state,
            new_state,
            action
        )


    except Exception:
        conn.rollback()
        logger.exception(
            "workflow_transition_failed workflow_id=%s action=%s",
            workflow_id,
            action
        )

        return error_response("DATABASE_ERROR")

    finally:
        cur.close()
        conn.close()

    return jsonify({
        "workflowId": workflow_id,
        "state": new_state,
        "message": "Transition completed successfully"
    })


@app.route("/actions/pending", methods=["GET"])
def pending_actions():
    """
    Get pending worker actions.
    ---
    tags:
      - Actions
    responses:
      200:
        description: Pending actions returned.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            workflow_id,
            type,
            attempt,
            payload
        FROM actions
        WHERE status='PENDING'
        ORDER BY id
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    actions = []

    for row in rows:

        actions.append({
            "id": row[0],
            "workflowId": row[1],
            "type": row[2],
            "attempt": row[3],
            "payload": row[4]
        })

    logger.debug(
        "pending_actions_returned count=%s",
        len(actions)
    )

    return jsonify(actions)


@app.route("/actions/<int:action_id>/result", methods=["POST"])
def report_action_result(action_id):
    """
    Report result of a worker action.
    ---
    tags:
      - Actions
    parameters:
      - name: action_id
        in: path
        required: true
        description: Action identifier.
      - name: status
        in: body
        required: true
        description: SUCCESS or FAILED result.
    responses:
      200:
        description: Action result processed.
      400:
        description: Invalid worker result.
      404:
        description: Action or workflow not found.
      500:
        description: Database error.
    """
    data = request.get_json()

    if not data or "status" not in data:
        logger.warning(
            "worker_result_invalid_request action_id=%s",
            action_id
        )
        return error_response("INVALID_REQUEST", "Status is required")

    status = data["status"]

    if status not in ["SUCCESS", "FAILED"]:
        logger.warning(
            "worker_result_invalid_status action_id=%s status=%s",
            action_id,
            status
        )
        return error_response("INVALID_REQUEST", "Invalid status")

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Get action information
        cur.execute("""
            SELECT workflow_id, type, status
            FROM actions
            WHERE id = %s
            FOR UPDATE
        """, (action_id,))

        action_row = cur.fetchone()

        if action_row is None:
            logger.warning(
                "action_not_found action_id=%s",
                action_id
            )
            cur.close()
            conn.close()
            return error_response("ACTION_NOT_FOUND")

        workflow_id = action_row[0]
        action_type = action_row[1]
        action_status = action_row[2]

        if action_status != "PENDING":
            logger.info(
                "worker_result_already_processed action_id=%s current_status=%s",
                action_id,
                action_status
            )
            cur.close()
            conn.close()
            return jsonify({
                "message": "Action already processed",
                "actionId": action_id,
                "status": action_status
            })

        new_state, history_action = get_worker_transition(
            action_type,
            status
        )

    except Exception as e:
        cur.close()
        conn.close()
        logger.warning(
            "invalid_worker_transition action_id=%s error=%s",
            action_id,
            str(e)
        )

        return error_response("INVALID_WORKER_TRANSITION", str(e))

    try:
        cur.execute("""
            SELECT state
            FROM workflows
            WHERE id = %s
            FOR UPDATE
        """, (workflow_id,))

        workflow_row = cur.fetchone()

        if workflow_row is None:
            cur.close()
            conn.close()
            logger.warning(
                "workflow_not_found_for_action action_id=%s workflow_id=%s",
                action_id,
                workflow_id
            )
            return error_response("WORKFLOW_NOT_FOUND")

        current_state = workflow_row[0]

        now = datetime.now(timezone.utc)


        # Update action result
        if status == "SUCCESS":

            result = json.dumps(data.get("result", {}))

            cur.execute("""
                UPDATE actions
                SET
                    status = %s,
                    result = %s,
                    updated_at = %s
                WHERE id = %s
            """, (
                "SUCCESS",
                result,
                now,
                action_id
            ))

        else:

            error = data.get("error", "Unknown error")

            cur.execute("""
                UPDATE actions
                SET
                    status = %s,
                    error = %s,
                    updated_at = %s
                WHERE id = %s
            """, (
                "FAILED",
                error,
                now,
                action_id
            ))


        # Update workflow state
        cur.execute("""
            UPDATE workflows
            SET
                state = %s,
                version = version + 1,
                updated_at = %s
            WHERE id = %s
        """, (
            new_state,
            now,
            workflow_id
        ))

        # Add workflow history
        cur.execute("""
            INSERT INTO workflow_history
            (
                workflow_id,
                from_state,
                to_state,
                action,
                timestamp
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            workflow_id,
            current_state,
            new_state,
            history_action,
            now
        ))

        conn.commit()
        logger.info(
            "action_processed action_id=%s workflow_id=%s %s - %s - %s",
            action_id,
            workflow_id,
            action_type,
            status,
            new_state
        )

    except Exception as e:
        conn.rollback()
        logger.exception(
            "worker_result_processing_failed action_id=%s",
            action_id
        )

        return error_response("DATABASE_ERROR")

    finally:
        cur.close()
        conn.close()

    return jsonify({
        "workflowId": workflow_id,
        "state": new_state,
        "message": "Action result processed successfully"
    })


@app.route("/workflows/<int:workflow_id>/actions", methods=["GET"])
def get_workflow_actions(workflow_id):
    """
    Get actions belonging to a workflow.
    ---
    tags:
      - Workflows
    parameters:
      - name: workflow_id
        in: path
        required: true
        description: Workflow identifier.
    responses:
      200:
        description: Workflow actions returned.
      404:
        description: Workflow not found.
    """
    logger.debug(
        "workflow_actions_requested workflow_id=%s",
        workflow_id
    )
    conn = get_connection()
    cur = conn.cursor()

    # Check workflow exists
    cur.execute("""
        SELECT id
        FROM workflows
        WHERE id = %s
    """, (workflow_id,))

    workflow = cur.fetchone()

    if workflow is None:
        logger.warning(
            "workflow_not_found_for_actions workflow_id=%s",
            workflow_id
        )
        cur.close()
        conn.close()

        return error_response("WORKFLOW_NOT_FOUND")


    # Get all actions for this workflow
    cur.execute("""
        SELECT
            type,
            status,
            attempt,
            created_at,
            updated_at
        FROM actions
        WHERE workflow_id = %s
        ORDER BY id
    """, (workflow_id,))

    rows = cur.fetchall()

    cur.close()
    conn.close()


    actions = []

    for row in rows:
        actions.append({
            "type": row[0],
            "status": row[1],
            "attempt": row[2],
            "createdAt": row[3].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "updatedAt": row[4].strftime("%Y-%m-%dT%H:%M:%SZ")
        })

    logger.debug(
        "workflow_actions_returned workflow_id=%s count=%s",
        workflow_id,
        len(actions)
    )

    return jsonify(actions)


@app.route("/workflows/<int:workflow_id>/history", methods=["GET"])
def get_workflow_history(workflow_id):
    """
    Get workflow transition history.
    ---
    tags:
      - History
    parameters:
      - name: workflow_id
        in: path
        required: true
        description: Workflow identifier.
    responses:
      200:
        description: Workflow history returned.
      404:
        description: Workflow not found.
    """
    logger.debug(
        "workflow_history_requested workflow_id=%s",
        workflow_id
    )
    conn = get_connection()
    cur = conn.cursor()

    # Check if workflow exists
    cur.execute("""
        SELECT id
        FROM workflows
        WHERE id = %s
    """, (workflow_id,))

    workflow = cur.fetchone()

    if workflow is None:
        logger.warning(
            "workflow_not_found_for_history workflow_id=%s",
            workflow_id
        )
        cur.close()
        conn.close()
        return error_response("WORKFLOW_NOT_FOUND")

    # Get history
    cur.execute("""
        SELECT
            from_state,
            to_state,
            action,
            timestamp
        FROM workflow_history
        WHERE workflow_id = %s
        ORDER BY timestamp
    """, (workflow_id,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    history = []

    for row in rows:
        history.append({
            "fromState": row[0],
            "toState": row[1],
            "action": row[2],
            "timestamp": row[3].strftime("%Y-%m-%dT%H:%M:%SZ")
        })

    logger.debug(
        "workflow_history_returned workflow_id=%s count=%s",
        workflow_id,
        len(history)
    )

    return jsonify(history)



if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
