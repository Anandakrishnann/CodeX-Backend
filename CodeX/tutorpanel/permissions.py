from rest_framework.permissions import BasePermission
from Accounts.models import TutorSubscription

class IsSubscribed(BasePermission):
    """
    Allows access only to users with an active subscription.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        try:
            subscription = TutorSubscription.objects.get(tutor__account=user)
            return subscription.is_active
        except TutorSubscription.DoesNotExist:
            return False