
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from Accounts.stripe_webhook import StripeWebhookView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('Accounts.urls')),
    path('adminpanel/', include('adminpanel.urls')),
    path('tutorpanel/', include('tutorpanel.urls')),
    path('chat/', include('chat.urls')),
    path('notifications/', include('notifications.urls')),
    path('webhooks/stripe/', StripeWebhookView.as_view(), name='stripe-webhook'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
