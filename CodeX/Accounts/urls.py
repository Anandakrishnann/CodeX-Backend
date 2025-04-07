from django.urls import path
from .views import *

urlpatterns = [
    path('signup/', UserRegisterView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('user_profile/<str:userId>/', UserProfileView.as_view(), name='user_profile'),
    path('edit_user/<str:email>/', EditUserView.as_view(), name='edit_user'),
    path('verify_otp/', OTPVerificationView.as_view(), name='verify_otp'),
    path('resend_otp/', ResendOTPView.as_view(), name='resend_otp'),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
]