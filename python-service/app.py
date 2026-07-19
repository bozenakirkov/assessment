import os
import json
from datetime import datetime

from flask import Flask, request, jsonify
import psycopg2

from state_machine import (
    get_manual_transition,
    get_worker_transition,
)
from errors import error_response

app = Flask(__name__)

from flask_cors import CORS
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

    data = request.get_json(silent=True)

    if not data:
        return error_response("INVALID_REQUEST", "No JSON received")

    if "reference" not in data:
        return error_response("INVALID_REQUEST", "Reference missing")

    print("===========")
    print("data", data)

    if "payload" not in data:
        return error_response("INVALID_REQUEST", "Payload missing")

    reference = data["reference"]

    payload = json.dumps(data["payload"])

    created_at = datetime.now()

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
                    created_at,
                    created_at
                ))

        workflow_id = cur.fetchone()[0]
        conn.commit()

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
        return error_response("WORKFLOW_NOT_FOUND")

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
            "updatedAt": row[4]
        })

    return jsonify(workflows)


@app.route("/workflows/<int:workflow_id>/transitions", methods=["POST"])
def transition_workflow(workflow_id):

    data = request.get_json()

    if not data or "action" not in data:
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

                conn.commit()

                return jsonify({
                    "workflowId": workflow_id,
                    "state": current_state,
                    "message": "Action already created",
                    "actionId": existing_action[0]
                })


        now = datetime.now()


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


    except Exception:

        conn.rollback()

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

    return jsonify(actions)


@app.route("/actions/<int:action_id>/result", methods=["POST"])
def report_action_result(action_id):

    data = request.get_json()

    if not data or "status" not in data:
        return error_response("INVALID_REQUEST", "Status is required")

    status = data["status"]

    if status not in ["SUCCESS", "FAILED"]:
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
            cur.close()
            conn.close()
            return error_response("ACTION_NOT_FOUND")

        workflow_id = action_row[0]
        action_type = action_row[1]
        action_status = action_row[2]

        if action_status != "PENDING":
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
            return error_response("WORKFLOW_NOT_FOUND")

        current_state = workflow_row[0]

        now = datetime.now()


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

    except Exception as e:
        conn.rollback()

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
            "createdAt": row[3],
            "updatedAt": row[4]
        })


    return jsonify(actions)


@app.route("/workflows/<int:workflow_id>/history", methods=["GET"])
def get_workflow_history(workflow_id):

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
            "timestamp": row[3]
        })

    return jsonify(history)



if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
