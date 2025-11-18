from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken
from .models import Accounts
from django.conf import settings

class CookieJWTAuthentication(BaseAuthentication):
    
    PUBLIC_PATHS = [
        "/api/login/",
        "/api/signup/",
        "/api/forgot_password/",
        "/api/reset_password/",
        "/admin/",
    ]
    
    def authenticate(self, request):
        
        if getattr(settings, "TESTING", False):
            return None
        
        access_token = request.COOKIES.get("access_token")  
        refresh_token = request.COOKIES.get("refresh_token")


        if not access_token:
            if not refresh_token:
                return None
            return None
        
        try:
            token = AccessToken(access_token)
            user = Accounts.objects.get(id=token["user_id"])
            return (user, token)
        except Exception:
            raise AuthenticationFailed("Invalid or expired access token.")
