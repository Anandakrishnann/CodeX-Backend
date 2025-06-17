from django.urls import path
from .views import *
from . import views

urlpatterns = [
    path('list_users/', ListUsers.as_view(), name='list_users'),
    path('list_tutors/', ListTutors.as_view(), name='list_tutors'),
    path('list_courses/', ListCoursesView.as_view(), name='list_courses'),
    path('status/', Status.as_view(), name='status'),
    path('tutor-status/', TutorStatus.as_view(), name='tutor-status'),
    path('course_status/<str:id>/', CourseStatusView.as_view(), name='course-status'),
    path('list_applicaions/', ListApplicationsView.as_view(), name='list_applicaions'),
    path('list_course_request/', CourseRequestsView.as_view(), name='list_course_request'),
    path('course_request_status/<str:id>/', CourseStatusView.as_view(), name='course_request_status'),
    path('applications/', TutorApplicationView.as_view(), name='applications'),
    path('create_category/', CreateCategoryView.as_view(), name='create_category'),
    path('edit_category/<str:id>/', EditCategoryView.as_view(), name='edit_category'),
    path('list_category/', ListCategoryView.as_view(), name='list_category'),
    path('category_status/', CategoryStatusView.as_view(), name='category_status'),
    path('create_plan/', CreatePlanView.as_view(), name='create_plan'),
    path('list_plan/', ListPlanView.as_view(), name='list_plan'),
    path('create-checkout-session/<int:plan_id>/', CreateCheckoutSessionView.as_view(), name='create-checkout'),
    path('stripe/webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
    path('application_view/<str:userId>/', TutorApplicationsOverView.as_view(), name='application_view'),
    path('tutor_view/<str:userId>/', TutorOverView.as_view(), name='tutor_view'),
    path('view_course/<str:id>/', CourseOverView.as_view(), name='view_course'),
    path('course_modules/<str:id>/', ListCourseModulesView.as_view(), name='course_modules'),
    path('view_module/<str:id>/', ModuleDetailView.as_view(), name='view_module'),
    path('course_lessons/<str:id>/', ListCourseLessonView.as_view(), name='course_lessons'),
    path('lesson_overview/<str:lessonId>/', LessonOverview.as_view(), name='lesson_overview'),

    path('accept_application/<str:applicationId>/', AcceptApplicationView.as_view(), name='accept_application'),
    path('reject_application/<str:applicationId>/', RejectApplicationView.as_view(), name='reject_application'),

    path('accept_course_request/<str:courseId>/', AcceptCourseRequestView.as_view(), name='accept_course_request'),
    path('reject_course_request/<str:courseId>/', RejectCourseRequestView.as_view(), name='reject_course_request'),

    path('accept_module/<str:id>/', AcceptModuleView.as_view(), name='accept_module'),
    path('reject_module/<str:id>/', RejectModuleView.as_view(), name='reject_module'),

    path('accept_lesson/<str:lessonId>/', AcceptLessonView.as_view(), name='accept_lesson'),
    path('reject_lesson/<str:lessonId>/', RejectLessonView.as_view(), name='reject_lesson'),

    path('module_status/<str:id>/', ModuleStatusView.as_view(), name='module_status'),
    path('lesson_status/<str:lessonId>/', LessonStatusView.as_view(), name='lesson_status'),
]   