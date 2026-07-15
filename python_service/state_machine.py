MANUAL_TRANSITIONS = {
    ("CREATED", "START_VALIDATION"): "VALIDATING",
    ("APPROVED", "START_PROCESSING"): "PROCESSING",

    ("CREATED", "CANCEL"): "CANCELLED",
    ("VALIDATING", "CANCEL"): "CANCELLED",
    ("APPROVED", "CANCEL"): "CANCELLED",
}


WORKER_TRANSITIONS = {
    ("VALIDATE", "SUCCESS"): ("APPROVED", "APPROVE"),
    ("VALIDATE", "FAILED"): ("VALIDATION_FAILED", "REJECT"),

    ("PROCESS", "SUCCESS"): ("COMPLETED", "COMPLETE"),
    ("PROCESS", "FAILED"): ("PROCESSING_FAILED", "FAIL"),
}


def get_manual_transition(current, action):

    key = (current, action)

    if key not in MANUAL_TRANSITIONS:
        raise ValueError(
            f"Cannot apply {action} while workflow is in {current} state"
        )

    return MANUAL_TRANSITIONS[key]


def get_worker_transition(action_type, result):

    key = (action_type, result)

    if key not in WORKER_TRANSITIONS:
        raise ValueError(
            f"Invalid worker result {result}"
        )

    return WORKER_TRANSITIONS[key]