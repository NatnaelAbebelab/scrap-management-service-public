from django.db.models import DateTimeField, Func, CharField, Value, DateField
from datetime import datetime
import uuid, re

class ToDateTime(Func):
    function = 'TO_DATE'
    template = "%(function)s(%(expressions)s, 'DD.MM.YYYY')"
    output_field = DateTimeField()

class ToDate(Func):
    function = "TO_DATE"
    template = "%(function)s(%(expressions)s, 'DD.MM.YYYY')"
    output_field = DateField()

class ToFormalDateTime(Func):
    function = 'TO_DATE'
    template = "%(function)s(%(expressions)s, 'YYYY-MM-DD')"
    output_field = DateTimeField()

class ToFormalDate(Func):
    function = 'TO_DATE'
    template = "%(function)s(%(expressions)s, 'YYYY-MM-DD')"
    output_field = DateField()

class CastToDate(Func):
    """
    Helper to cast string fields to DateField for filtering.
    """
    function = "DATE"
    template = "%(function)s(%(expressions)s)"
    output_field = DateField()

class StrToDate(Func):
    """Convert string to DATE format in Django ORM"""
    function = "STR_TO_DATE"
    template = "%(function)s(%(expressions)s, %(format)s)"
    output_field = CharField()

class ToTimestamp(Func):
    function = 'to_timestamp'
    output_field = DateTimeField()

    def __init__(self, expression, date_format='DD.MM.YYYY', **extra):
        super().__init__(expression, Value(date_format), **extra)

def clean_tin(tin):
    # Ensure only numeric characters (no decimals, no alphabets)
    tin = tin.strip()  # remove leading/trailing spaces
    tin = re.sub(r"\D", "", tin)  # remove all non-digit characters
    if not tin:
        raise ValueError("TIN is empty or invalid after cleaning.")
    return tin

def is_valid_number(value):
    """Check if the value is a valid positive number string."""
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False

def is_valid_date(date_str, date_format="%Y-%m-%d"):
    try:
        datetime.strptime(date_str, date_format)  # Try parsing the date
        return True
    except ValueError:
        return False  # If parsing fails, it's not a valid date

def is_digit(value):
    if not value.isdigit():
        raise Exception("Record no should only contain digits, no decimals or letters.")
    return value

def is_valid_uuid(uuid_string):
    try:
        uuid_obj = uuid.UUID(uuid_string, version=4)  # You can change version if needed
        return str(uuid_obj) == uuid_string  # Ensure it's properly formatted
    except ValueError:
        return False

def normalize_date(date_val):
    if isinstance(date_val, str):
        return datetime.strptime(date_val, "%Y-%m-%d").date()
    return date_val