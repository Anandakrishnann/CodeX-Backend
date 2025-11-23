from rest_framework.permissions import BasePermission

class IsAuthenticatedUser(BasePermission):
    """
    Allows access only to users is active .
    """

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False

        if user.isblocked:
            return False

        return True