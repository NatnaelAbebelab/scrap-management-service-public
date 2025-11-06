from enum import Enum

class MaterialType(Enum):
    SCRAP = "scrap"
    BUNDLE = "bundle"
    STAFFA = "staffa"
    COILR = "coils"
    REBAR = "rebar"
    CHEMICALE = "chemicale"
    
    @classmethod
    def get_material_type(cls, value):
        for member in cls:
            if member.value == value.lower():
                return member.name
        return None
    
    @classmethod
    def get_material_types(cls):
        """Get status based on the status string"""
        material_types = {}
        for material in cls:
            material_types[material.value] = material.name
        return material_types
            
def is_valid_material(value):
    return value in MaterialType._value2member_map_