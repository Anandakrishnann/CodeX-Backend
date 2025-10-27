from rest_framework.views import APIView 
from rest_framework.permissions import AllowAny 
from .serializers import *
from .models import *
from django.utils.timezone import now
from adminpanel.models import *
from tutorpanel.models import *
from django.conf import settings
import stripe # type: ignore
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import HttpResponse, Http404



@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET

        print(f"payload is {payload}")
        print(f"request is {request}")
        print(f"sig_header is {sig_header}")
        print(f"webhook secret is {webhook_secret}")
        
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError:
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            return HttpResponse(status=400)

        print("🔔 Webhook received:", event['type'])

        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            tutor_id = session.get('client_reference_id')
            metadata = session.get('metadata') or {}
            plan_id = metadata.get('plan_id')
            email = (session.get('customer_details') or {}).get('email')

            try:
                plan = Plan.objects.get(id=plan_id)
                account = Accounts.objects.get(id=tutor_id)
                tutor = TutorDetails.objects.get(account=account)

                if plan.plan_type == 'MONTHLY':
                    expires_on = now() + timedelta(days=30)
                elif plan.plan_type == 'YEARLY':
                    expires_on = now() + timedelta(days=365)
                else:
                    expires_on = now()

                TutorSubscription.objects.update_or_create(
                    tutor=tutor,
                    defaults={
                        'plan': plan,
                        'subscribed_on': now(),
                        'expires_on': expires_on,
                        'is_active': True,
                        'stripe_customer_id': session.get('customer'),
                        'stripe_subscription_id': session.get('subscription'),
                    }
                )
                print(f"✅ Subscription stored for {email}")

            except Exception as e:
                print(f"❌ Error storing subscription: {e}")
                return HttpResponse(status=400)

        return HttpResponse(status=200)