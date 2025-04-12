from django.urls import path
from .views import *
from . import views

urlpatterns = [
    path('list_users/', ListUsers.as_view(), name='list_users'),
    path('list_tutors/', ListTutors.as_view(), name='list_tutors'),
    path('status/', Status.as_view(), name='status'),
    path('tutor-status/', TutorStatus.as_view(), name='tutor-status'),
    path('list_applicaions/', ListApplicationsView.as_view(), name='list_applicaions'),
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
    path('accept/<str:applicationId>/', AcceptApplicationView.as_view(), name='accept'),
    path('reject/<str:applicationId>/', RejectApplicationView.as_view(), name='reject'),
]   