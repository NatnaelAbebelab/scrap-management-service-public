from helperFunctions.status import Status

STATUS_TRANSITIONS = {
    "purchaser": {
        Status.NEW.status_value: [Status.PREPARED.status_value]
    },
    "inspector": {
        Status.PREPARED.status_value: [Status.INSPECTED.status_value]
    },
    "purchase_head": {
        Status.INSPECTED.status_value: [Status.VERIFIED.status_value]
    },
    "supervisor": {
        Status.VERIFIED.status_value: [
            Status.APPROVED.status_value,
            Status.DECLINED.status_value
        ],
        Status.NEW.status_value: [
            Status.APPROVED.status_value,
            Status.DECLINED.status_value
        ]
    },
    "finance": {
        Status.APPROVED.status_value: [Status.PAID.status_value]
    }
}

def get_next_status(role, current_status, target_status=None):
    """
    Returns the next status if allowed for the role and current_status.
    If target_status is provided, check if it is allowed.
    """
    allowed = STATUS_TRANSITIONS.get(role, {}).get(current_status, [])
    if target_status:
        if target_status in allowed:
            return target_status
        return None
    return allowed[0] if allowed else None