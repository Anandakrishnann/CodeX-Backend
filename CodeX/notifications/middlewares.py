from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken

@database_sync_to_async
def get_user(token):
    try:
        from Accounts.models import Accounts
        access = AccessToken(token)
        return Accounts.objects.get(id=access["user_id"])
    except Exception:
        return AnonymousUser()


def JwtAuthMiddleware(inner):
    async def middleware(scope, receive, send):

        # Convert headers to dict
        headers = dict(scope.get("headers", []))
        cookies_raw = headers.get(b"cookie", b"").decode()

        cookies = {}
        for item in cookies_raw.split(";"):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                cookies[k] = v

        token = cookies.get("access_token")

        if token:
            scope["user"] = await get_user(token)
        else:
            scope["user"] = AnonymousUser()

        return await inner(scope, receive, send)

    return middleware