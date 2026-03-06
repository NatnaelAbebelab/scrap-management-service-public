from grn.workflow.transitions import STATUS_TRANSITIONS
from grn.workflow.actions import ACTION_STATUS_MAP


def get_target_status(action):
    return ACTION_STATUS_MAP.get(action)


def is_transition_allowed(role, current_status, target_status):

    role_transitions = STATUS_TRANSITIONS.get(role, {})

    allowed = role_transitions.get(current_status)

    if not allowed:
        return False

    if isinstance(allowed, list):
        return target_status in allowed

    return target_status == allowed