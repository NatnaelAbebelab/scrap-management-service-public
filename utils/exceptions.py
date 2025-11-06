from rest_framework.views import exception_handler
from rest_framework import status

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None and 'detail' in response.data:
        if response.data['detail'] == 'Authentication credentials were not provided.':
            response.data = {
                'result': 'error',
                'message': 'please log to your account'
            }
            response.status_code = status.HTTP_401_UNAUTHORIZED 

    return response

class StatusException(Exception):
    def __init__(self, message, data=None, code=status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.data = data
        self.code = code
        super().__init__(message, data)

    def __str__(self):
        return self.message, self.data

class FilterException(Exception):
    def __init__(self, message, data=None, code=status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.data = data
        self.code = code
        super().__init__(message, data)

    def __str__(self):
        return self.message, self.data

class DailyPerformanceException(Exception):
    def __init__(self, message, data=None, code=status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.data = data
        self.code = code
        super().__init__(message, data)

    def __str__(self):
        return self.message, self.data