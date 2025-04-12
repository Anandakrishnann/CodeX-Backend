from django.urls import path
from .views import *

urlpatterns = [
    path('tutor_profile/<str:userId>/', TutorProfileView.as_view(), name='tutor_profile'),
    path('edit_tutor/<str:email>/', EditTutorView.as_view(), name='edit_tutor'),
    path('profile_picture/<str:email>/', UploadTutorProfilePictureView.as_view(), name='profile_picture/'),
    path('create_course/', CreateCourseView.as_view(), name='create_course'),
    path('edit_course/<str:id>/', EditCourseView.as_view(), name='edit_course'),
    path('list_course/', ListCourseView.as_view(), name='list_course'),
    path('course_status/', CourseStatusView.as_view(), name='course_status'),
]