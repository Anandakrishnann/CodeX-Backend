from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import BasePermission

class IsNotBlocked(BasePermission):
    def has_permission(self, request, view):
        print()
        if request.user.is_authenticated and getattr(request.user, "isblocked", False):
            return False 
        return True 

class UserBlockCheckMixin:
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and getattr(request.user, "isblocked", False):
            return Response(
                {"error": "Your account has been blocked. Please contact support."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().dispatch(request, *args, **kwargs)
