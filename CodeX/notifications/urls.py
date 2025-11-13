from django.urls import path
from .views import NotificationListView, NotificationMarkReadView, NotificationMarkAllReadView


urlpatterns = [
    path('', NotificationListView.as_view(), name='notifications-list'),  # GET /notifications/
    path('<int:id>/read/', NotificationMarkReadView.as_view(), name='notification-mark-read'),  # PATCH /notifications/{id}/read/
    path('mark-all-read/', NotificationMarkAllReadView.as_view(), name='notifications-mark-all-read'),  # POST /notifications/mark-all-read/
]

