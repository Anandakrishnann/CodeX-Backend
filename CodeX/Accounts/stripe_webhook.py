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
from django.http import HttpResponse
from datetime import timedelta
import logging
logger = logging.getLogger("codex")

@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET

        if not webhook_secret:
            logger.error("Stripe webhook secret not configured")
            return HttpResponse("Webhook secret not configured", status=500)

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            logger.info("Stripe webhook signature verified successfully")
        except ValueError as e:
            logger.error("Invalid Stripe webhook payload", exc_info=True)
            return HttpResponse("Invalid payload", status=400)
        except stripe.error.SignatureVerificationError:
            logger.error("Stripe webhook signature verification failed", exc_info=True)
            return HttpResponse("Invalid signature", status=400)

        event_type = event.get("type")
        logger.info("Stripe webhook received | event_type=%s", event_type)

        if event_type == "checkout.session.completed":
            session = event["data"]["object"]

            tutor_id = session.get("client_reference_id")
            metadata = session.get("metadata") or {}
            plan_id = metadata.get("plan_id")
            subscription_id = session.get("subscription")
            customer_id = session.get("customer")

            if not tutor_id or not plan_id:
                logger.warning(
                    "Stripe webhook missing required data | tutor_id=%s | plan_id=%s",
                    tutor_id,
                    plan_id,
                )
                return HttpResponse(status=200)

            try:
                plan = Plan.objects.get(id=plan_id)
                account = Accounts.objects.get(id=tutor_id)
                tutor = TutorDetails.objects.get(account=account)

                if plan.plan_type == "MONTHLY":
                    expires_on = now() + timedelta(days=30)
                elif plan.plan_type == "YEARLY":
                    expires_on = now() + timedelta(days=365)
                else:
                    expires_on = now()

                subscription, created = TutorSubscription.objects.update_or_create(
                    tutor=tutor,
                    defaults={
                        "plan": plan,
                        "subscribed_on": now(),
                        "expires_on": expires_on,
                        "is_active": True,
                        "stripe_customer_id": customer_id,
                        "stripe_subscription_id": subscription_id,
                    },
                )

                wallet, _ = PlatformWallet.objects.get_or_create(pk=1)
                wallet.total_revenue += plan.price
                wallet.save()

                PlatformWalletTransaction.objects.create(
                    wallet=wallet,
                    amount=plan.price,
                    transaction_type="SUBSCRIPTION",
                    user=account,
                    tutor=tutor,
                )

                logger.info(
                    "Tutor subscription updated successfully | tutor_id=%s | plan_id=%s",
                    tutor.id,
                    plan.id,
                )

            except Plan.DoesNotExist:
                logger.warning("Plan not found | plan_id=%s", plan_id)
            except Accounts.DoesNotExist:
                logger.warning("Account not found | account_id=%s", tutor_id)
            except TutorDetails.DoesNotExist:
                logger.warning("Tutor details not found | account_id=%s", tutor_id)
            except Exception:
                logger.exception("Error processing checkout.session.completed webhook")

        elif event_type == "customer.subscription.deleted":
            subscription_data = event["data"]["object"]
            stripe_subscription_id = subscription_data.get("id")

            try:
                subscription = TutorSubscription.objects.get(
                    stripe_subscription_id=stripe_subscription_id
                )
                subscription.is_active = False
                subscription.save()

                logger.info(
                    "Tutor subscription deactivated | stripe_subscription_id=%s",
                    stripe_subscription_id,
                )

            except TutorSubscription.DoesNotExist:
                logger.warning(
                    "Subscription not found for deletion | stripe_subscription_id=%s",
                    stripe_subscription_id,
                )

        else:
            logger.info("Unhandled Stripe event type | event_type=%s", event_type)

        return HttpResponse(status=200)
