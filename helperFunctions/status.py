from enum import Enum

class Status(Enum):
    NEW = ("new", ["super_admin", "weight_man", "purchaser", "supervisor", "purchase_head"])
    PENDING = ("pending", ["super_admin", "purchaser", "supervisor"])
    APPROVED = ("approved", ["super_admin", "supervisor", "factory_manager", "manager", "finance"])
    DECLINED = ("declined", ["super_admin", "supervisor"])
    PREPARED = ("prepared", ["super_admin", "purchaser", "inspector", "purchase_head"])
    INSPECTED = ("inspected", ["super_admin", "inspector", "purchase_head"])
    VERIFIED = ("verified", ["super_admin", "purchase_head", "supervisor"])
    PAID = ("paid", ["super_admin", "finance", "manager"])
    APPROVED_MANAGER = ("approved_manager", ["super_admin", "supervisor", "factory_manager", "finance"])

    def __init__(self, status_value, roles):
        self.status_value = status_value
        self.roles = roles

    def __str__(self):
        return self.status
    
    @classmethod
    def get_status(cls, status_str):
        """Get status based on the status string"""
        for status in cls:
            if status.status_value == status_str:
                return status
        return None  # Return None if not found
    
    @classmethod
    def get_roles(cls):
        """Get roles based on the status string"""
        for status in cls:
            return status.roles  # Return the list of roles
        return None  # Return None if not found
    
    @classmethod
    def get_roles_by_status(cls, status_str):
        """Get roles based on the status string"""
        for status in cls:
            if status.status_value == status_str:
                return status.roles  # Return the list of roles
        return None  # Return None if not found
    
    @classmethod
    def get_status_by_role(cls, role_str):
        """Get status based on a role"""
        statuses_with_role = []
        for status in cls:
            if role_str in status.roles:
                statuses_with_role.append(status.status_value)
        return statuses_with_role if statuses_with_role else None
    
    @classmethod
    def get_status_by_role_object(cls, role_str):
        """Get status based on a role"""
        statuses_with_role = {}
        for status in cls:
            if role_str in status.roles:
                statuses_with_role[status.status_value] = status.name
        return statuses_with_role if statuses_with_role else None
    
    @staticmethod
    def get_previous_status(status):
        """ Get the previous status for 'DECLINED' transitions """
        transition_map = {
            Status.NEW.status_value: Status.NEW.status_value,
            Status.PREPARED.status_value: Status.NEW.status_value,  # Purchaser can go back to 'NEW' if declined
            Status.INSPECTED.status_value: Status.PREPARED.status_value,  # Inspector can go back to 'PREPARED' if declined
            Status.VERIFIED.status_value: Status.INSPECTED.status_value,  # Purchase head can go back to 'INSPECTED' if declined
        }
        return transition_map.get(status)

    @staticmethod
    def is_declined(status):
        """ Checks if the current status is 'DECLINED' """
        return status == Status.DECLINED.status_value
def is_valid_status(value):
    return any(status.status_value == value for status in Status)