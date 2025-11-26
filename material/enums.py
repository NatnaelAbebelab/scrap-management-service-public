from enum import Enum

class Plants(Enum):
    OLD_PLANT = "old_plant"
    NEW_PLANT = "new_plant"

class IssueStatus(Enum):
    NEW = "new"
    ISSUED = "issued"
    APPROVED = "approved"

class RequisitionStatus(Enum):
    NEW = "new"
    REQUESTED = "request_issued"
    APPROVED = "approved"