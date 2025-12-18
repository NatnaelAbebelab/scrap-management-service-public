from enum import Enum

class Plants(Enum):
    ROLLING_MILL_1 = "rolling_mill_1"
    ROLLING_MILL_2 = "rolling_mill_2"
    NEW_MELTING_PLANT = "new_melting_plant"

class IssueStatus(Enum):
    NEW = "new"
    ISSUED = "issued"
    APPROVED = "approved"

class RequisitionStatus(Enum):
    NEW = "new"
    REQUESTED = "request_issued"
    APPROVED = "approved"