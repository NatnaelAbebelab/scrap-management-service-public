from enum import Enum

class Grade(Enum):
    HEAVY = "H"
    MEDIUM = "M"
    LIGHT = "L"
    
def is_valid_grade(value):
    return value in Grade._value2member_map_