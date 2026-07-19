from flask import jsonify


ERRORS = {

    "INVALID_REQUEST": {
        "http": 400,
        "message": "Invalid request"
    },

    "INVALID_TRANSITION": {
        "http": 400,
        "message": "Workflow transition is not allowed"
    },

    "INVALID_WORKER_TRANSITION": {
        "http": 400,
        "message": "Invalid worker result"
    },

    "WORKFLOW_NOT_FOUND": {
        "http": 404,
        "message": "Workflow not found"
    },

    "ACTION_NOT_FOUND": {
        "http": 404,
        "message": "Action not found"
    },

    "STALE_WORKFLOW": {
        "http": 409,
        "message": "Workflow was modified by another request"
    },

    "DATABASE_ERROR": {
        "http": 500,
        "message": "Database operation failed"
    }

}


def error_response(code, message=None):

    error = ERRORS[code]

    return jsonify({
        "code": code,
        "message": message or error["message"]
    }), error["http"]