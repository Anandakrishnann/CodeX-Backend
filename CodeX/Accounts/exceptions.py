from rest_framework.views import exception_handler
from rest_framework.exceptions import NotAuthenticated, AuthenticationFailed
from rest_framework import status

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, NotAuthenticated):
        if "credentials were not provided" in str(exc):
            response.status_code = status.HTTP_401_UNAUTHORIZED
        else:
            response.status_code = status.HTTP_404_NOT_FOUND

    elif isinstance(exc, AuthenticationFailed):
        response.status_code = status.HTTP_401_UNAUTHORIZED

    return response