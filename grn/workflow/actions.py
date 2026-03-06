from helperFunctions.status import Status

ACTION_STATUS_MAP = {
    "prepare": Status.PREPARED.status_value,
    "inspect": Status.INSPECTED.status_value,
    "verify": Status.VERIFIED.status_value,
    "approve": Status.APPROVED.status_value,
    "approve_manager": Status.APPROVED_MANAGER.status_value,
    "pay": Status.PAID.status_value,
    "decline": Status.DECLINED.status_value
}

ROLE_ACTION_STATUS = {
    "purchaser": "prepared",
    "inspector": "inspected",
    "purchase_head": "verified",
    "supervisor": "approved",
    "finance": "paid",
}