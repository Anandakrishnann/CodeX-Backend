from django.urls import path
from .views import *

urlpatterns = [
    path('tutor_profile/<str:userId>/', TutorProfileView.as_view(), name='tutor_profile'),
    path('edit_tutor/<str:email>/', EditTutorView.as_view(), name='edit_tutor'),

]