from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken
from .models import Accounts

class CookieJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        access_token = request.COOKIES.get("access_token")  
        refresh_token = request.COOKIES.get("refresh_token")

        print(f"refresh_token : {refresh_token}")
        print(f"access_token : {access_token}")

        if not access_token:
            if not refresh_token:
                print("❌ No refresh token found. Raising 401 Unauthorized.")
                return None
            print("⚠️ Access token missing, but refresh token exists. Let frontend handle refresh.")
            return None
        try:
            token = AccessToken(access_token)  # Decode JWT token
            user = Accounts.objects.get(id=token["user_id"])
            return (user, token)
        except Exception:
            print("❌ Invalid or expired access token. Raising 401 Unauthorized.")
            raise AuthenticationFailed("Invalid or expired access token.")  # Raise 401 if token is invalid

          # Successfully authenticated
