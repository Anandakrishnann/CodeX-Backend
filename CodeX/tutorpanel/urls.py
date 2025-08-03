from django.urls import path
from .views import *


urlpatterns = [
    path('tutor_profile/', TutorProfileView.as_view(), name='tutor_profile'),
    path('tutor_subscribed/', TutorSubscribedCheckView.as_view(), name='tutor_subscribed'),
    path('edit_tutor/', EditTutorView.as_view(), name='edit_tutor'),
    path('profile_picture/', UploadTutorProfilePictureView.as_view(), name='profile_picture/'),
    path('create_course/', CreateCourseView.as_view(), name='create_course'),
    path('edit_course/<str:id>/', EditCourseView.as_view(), name='edit_course'),
    path('course_status/<str:id>/', CourseStatusView.as_view(), name='course_status'),
    path('list_course/', ListCourseView.as_view(), name='list_course'),
    path('view_course/<str:id>/', CourseOverView.as_view(), name='view_course'),
    path('create_module/', CreateModuleView.as_view(), name='create_module'),
    path('edit_module/<str:id>/', EditModuleView.as_view(), name='edit_module'),
    path('course_modules/<str:id>/', ListCourseModulesView.as_view(), name='course_modules'),
    path('module_status/<str:id>/', ModuleStatusView.as_view(), name='module_status'),
    path('view_module/<str:id>/', ModuleDetailView.as_view(), name='view_module'),
    path('course_lessons/<str:id>/', ListCourseLessonView.as_view(), name='course_lessons'),
    path('create_lesson/', CreateLessonView.as_view(), name='create_lesson`'),
    path('edit_lesson/<str:pk>/', EditLessonView.as_view(), name='edit_lesson`'),
    path('lesson_status/<str:lessonId>/', LessonStatusView.as_view(), name='lesson_status'),
    path('set_draft/<str:id>/', SetCourseDraftView.as_view(), name='set_draft'),
    path('shedule-meeting/', SheduleMeetingView.as_view(), name='shedule-meeting'),
    path('sheduled-meetings/', SheduledMeetings.as_view(), name='sheduled-meetings/'),
    path('recent-meetings/', RecentMeetingsView.as_view(), name='recent-meetings/'),
    path('get_levels/', get_course_levels, name='get_levels'),
]