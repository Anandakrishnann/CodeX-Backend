from rest_framework.permissions import BasePermission
from Accounts.models import TutorSubscription

class IsSubscribed(BasePermission):
    """
    Allows access only to unblocked tutors with an active subscription.
    """

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False

        if user.role != "tutor":
            return False
        
        if user.isblocked:
            return False

        try:
            subscription = TutorSubscription.objects.get(tutor__account=user)
            return subscription.is_active
        except TutorSubscription.DoesNotExist:
            return False