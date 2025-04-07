from django.urls import path
from .views import *

urlpatterns = [
    path('list_users/', ListUsers.as_view(), name='list_users'),
    path('list_tutors/', ListTutors.as_view(), name='list_tutors'),
    path('status/', Status.as_view(), name='status'),
    path('tutor-status/', TutorStatus.as_view(), name='tutor-status'),
    path('list_applicaions/', ListApplicationsView.as_view(), name='list_applicaions'),
    path('applications/', TutorApplicationView.as_view(), name='applications'),
    path('application_view/<str:userId>/', TutorApplicationsOverView.as_view(), name='application_view'),
    path('tutor_view/<str:userId>/', TutorOverView.as_view(), name='tutor_view'),
    path('accept/<str:applicationId>/', AcceptApplicationView.as_view(), name='accept'),
    path('reject/<str:applicationId>/', RejectApplicationView.as_view(), name='reject'),
]   