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
from datetime import timedelta



@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        
        print(f"🔔 Webhook endpoint called")
        print(f"Payload length: {len(payload)}")
        print(f"Signature header: {sig_header}")
        print(f"Webhook secret exists: {bool(webhook_secret)}")
        if webhook_secret:
            print(f"Loaded webhook secret: {webhook_secret[:20]}...")
        else:
            print("❌ STRIPE_WEBHOOK_SECRET is not set!")
            return HttpResponse("Webhook secret not configured", status=500)
        
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
            print("✅ Event verified successfully")
        except ValueError as e:
            print(f"❌ ValueError: {e}")
            return HttpResponse(f"Invalid payload: {e}", status=400)
        except stripe.error.SignatureVerificationError as e:
            print(f"❌ Signature verification failed: {e}")
            return HttpResponse(f"Invalid signature: {e}", status=400)

        print(f"🔔 Webhook received: {event['type']}")

        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            tutor_id = session.get('client_reference_id')
            metadata = session.get('metadata') or {}
            plan_id = metadata.get('plan_id')
            email = (session.get('customer_details') or {}).get('email')
            subscription_id = session.get('subscription')
            customer_id = session.get('customer')

            # Debug the raw session content for visibility
            try:
                import json
                print(f"📦 Session object: {json.dumps(session, indent=2)}")
            except Exception:
                print("📦 Session object could not be JSON-dumped (non-serializable types present)")

            print(f"🔎 Extracted tutor_id={tutor_id}, plan_id={plan_id}, email={email}")
            print(f"🔎 Stripe customer={customer_id}, subscription={subscription_id}")

            try:
                if not plan_id:
                    print("❌ Missing plan_id in session metadata")
                    return HttpResponse("Missing plan_id", status=200)

                if not tutor_id:
                    print("❌ Missing client_reference_id (tutor_id) in session")
                    return HttpResponse("Missing tutor_id", status=200)

                try:
                    plan = Plan.objects.get(id=plan_id)
                except Plan.DoesNotExist:
                    print(f"❌ Plan not found for id={plan_id}")
                    return HttpResponse("Plan not found", status=200)

                try:
                    account = Accounts.objects.get(id=tutor_id)
                except Accounts.DoesNotExist:
                    print(f"❌ Account not found for id={tutor_id}")
                    return HttpResponse("Account not found", status=200)

                try:
                    tutor = TutorDetails.objects.get(account=account)
                except TutorDetails.DoesNotExist:
                    print(f"❌ TutorDetails not found for account id={account.id}")
                    return HttpResponse("TutorDetails not found", status=200)

                if plan.plan_type == 'MONTHLY':
                    expires_on = now() + timedelta(days=30)
                elif plan.plan_type == 'YEARLY':
                    expires_on = now() + timedelta(days=365)
                else:
                    expires_on = now()

                print(f"🧮 Calculated expires_on={expires_on} for plan_type={plan.plan_type}")

                sub_obj, created = TutorSubscription.objects.update_or_create(
                    tutor=tutor,
                    defaults={
                        'plan': plan,
                        'subscribed_on': now(),
                        'expires_on': expires_on,
                        'is_active': True,
                        'stripe_customer_id': customer_id,
                        'stripe_subscription_id': subscription_id,
                    }
                )

                print(f"✅ Subscription {'created' if created else 'updated'} for {email} | tutor_id={tutor_id}")
                print(f"✅ Stored values: plan={plan.id}, is_active={sub_obj.is_active}, expires_on={sub_obj.expires_on}, stripe_sub={sub_obj.stripe_subscription_id}")

            except Exception as e:
                print(f"❌ Error storing subscription: {e}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
                return HttpResponse(f"Error: {str(e)}", status=400)

        else:
            # Log other event types for visibility during debugging
            print(f"ℹ️ Ignored event type: {event['type']}")

        return HttpResponse(status=200)