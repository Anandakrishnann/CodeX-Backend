from django.shortcuts import get_object_or_404, render
from django.contrib.auth import get_user_model
from rest_framework.views import APIView 
from rest_framework.response import Response 
from rest_framework import status 
from .models import *
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
import traceback
from Accounts.models import *
from django.conf import settings
from .serializers import *
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.utils.timezone import now, timedelta
from rest_framework.permissions import AllowAny
from tutorpanel.models import *
import cloudinary.uploader
import stripe # type: ignore
from django.db.models import Sum, Count, F, Avg
from django.db.models.functions import TruncMonth, TruncYear, ExtractYear
from itertools import chain
import traceback
from Accounts.models import *
from tutorpanel.models import *
from tutorpanel.serializers import WalletTransactionSerializer
from notifications.utils import send_notification
from Accounts.tasks import send_report_marked_email
from django.core.mail import send_mail
from decimal import Decimal, InvalidOperation
import re
import os
import logging

logger = logging.getLogger("codex")



class AdminDashboardView(APIView):
    def get(self, request):
        logger.info("[AdminDashboardView] Called")

        # --- Total counts ---
        total_users = Accounts.objects.filter(role="user").count()

        total_tutors = TutorSubscription.objects.filter(is_active=True).select_related(
                "tutor", "tutor__account"
            ).count()

        total_courses = Course.objects.count()
        
        wallet, _ = PlatformWallet.objects.get_or_create(pk=1)

        total_revenue = wallet.total_revenue

        # --- Monthly revenue trend ---
        logger.debug("Calculating monthly revenue trend...")
        monthly_revenue_trend = (
            UserCourseEnrollment.objects
            .annotate(month=TruncMonth("enrolled_on"))
            .values("month")
            .annotate(revenue=Sum("course__price"))
            .order_by("month")
        )

        monthly_revenue_trend = [
            {"month": m["month"].strftime("%b"), "revenue": float(m["revenue"] or 0)}
            for m in monthly_revenue_trend if m["month"]
        ]

        # --- Yearly revenue trend ---
        logger.debug("Calculating yearly revenue trend...")
        yearly_revenue_trend = (
            UserCourseEnrollment.objects
            .annotate(year=ExtractYear("enrolled_on"))
            .values("year")
            .annotate(revenue=Sum("course__price"))
            .order_by("year")
        )

        # --- User growth trend ---
        logger.debug("Calculating user growth trend...")
        user_growth = (
            Accounts.objects.filter(role="user")
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

        user_growth = [
            {"month": u["month"].strftime("%b"), "count": u["count"]}
            for u in user_growth if u["month"]
        ]

        # --- Top tutors ---
        logger.debug("Fetching top tutors...")
        top_tutors = (
            UserCourseEnrollment.objects
            .values("course__created_by__account__first_name", "course__created_by__account__last_name")
            .annotate(earnings=Sum("course__price"))
            .order_by("-earnings")[:5]
        )

        top_tutors = [
            {
                "name": f"{t['course__created_by__account__first_name']} {t['course__created_by__account__last_name']}".strip(),
                "earnings": float(t["earnings"] or 0),
            }
            for t in top_tutors
        ]

        # --- Top courses ---
        logger.debug("Fetching top courses...")
        top_courses = (
            UserCourseEnrollment.objects
            .values("course__title")
            .annotate(enrollments=Count("id"))
            .order_by("-enrollments")[:5]
        )

        top_courses = [
            {"name": c["course__title"] or "Untitled", "enrollments": c["enrollments"]}
            for c in top_courses
        ]

        # --- Recent transactions ---
        logger.debug("Fetching recent transactions...")
        course_transactions = (
            UserCourseEnrollment.objects
            .select_related("user", "course")
            .values(
                "user__first_name",
                "user__last_name",
                "course__title",
                "course__price",
                "enrolled_on"
            )
        )

        subscription_transactions = (
            TutorSubscription.objects
            .select_related("tutor", "plan")
            .values(
                "tutor__account__first_name",
                "tutor__account__last_name",
                "plan__name",
                "plan__price",
                "created_at"
            )
        )

        course_data = [
            {
                "type": "COURSE_PURCHASE",
                "user": f"{tx['user__first_name']} {tx['user__last_name']}".strip(),
                "title": tx["course__title"],
                "amount": float(tx["course__price"] or 0),
                "date": tx["enrolled_on"],
            }
            for tx in course_transactions
        ]

        subscription_data = [
            {
                "type": "SUBSCRIPTION",
                "user": f"{tx['tutor__account__first_name']} {tx['tutor__account__last_name']}".strip(),
                "title": tx["plan__name"],
                "amount": float(tx["plan__price"]),
                "date": tx["created_at"],
            }
            for tx in subscription_transactions
        ]
        
        recent_transactions = sorted(
            chain(course_data, subscription_data),
            key=lambda x: x["date"],
            reverse=True
        )[:5]   


        # --- Final response ---
        data = {
            "total_users": total_users,
            "total_tutors": total_tutors,
            "total_courses": total_courses,
            "total_revenue": float(total_revenue),
            "monthly_revenue_trend": monthly_revenue_trend,
            "yearly_revenue_trend": list(yearly_revenue_trend),
            "user_growth": user_growth,
            "top_tutors": top_tutors,
            "top_courses": top_courses,
            "recent_transactions": recent_transactions,
        }

        logger.info("Final dashboard data ready to return.")
        return Response(data, status=200)



class ListUsers(APIView):
    def get(self, request):
        try:
            users = Accounts.objects.filter(role="user")

            user_data = [{"id": user.id, "email": user.email, "first_name": user.first_name, "last_name":user.last_name, "phone":user.phone, "status": bool(user.isblocked), "role":user.role } for user in users]

            return Response({"users": user_data}, status=200)  # ✅ Ensure we return a Response
            
        except:
            return Response({"Unauthorized": "Token expired"}, status=406)



class ListTutors(APIView):
    def get(self, request):
        try:
            # Get all tutors with active subscriptions
            subscribed_tutors = TutorSubscription.objects.filter(is_active=True).select_related(
                "tutor", "tutor__account"
            )

            tutor_data = []

            for sub in subscribed_tutors:
                account = sub.tutor.account      
                tutor_details = sub.tutor        

                tutor_data.append({
                    "id": tutor_details.id,
                    "first_name": account.first_name,
                    "last_name": account.last_name,
                    "email": account.email,
                    "phone": account.phone,
                    "status": bool(account.isblocked),
                    "role": account.role,
                    "picture": tutor_details.profile_picture,
                    "expertise": tutor_details.expertise,
                    "subscribed_on": sub.subscribed_on
                })

            return Response({"users": tutor_data}, status=200)

        except Exception as e:
            logger.error(f"Error: {e}")
            return Response({"error": "Something went wrong"}, status=500)



class UserStatus(APIView):

    def post(self, request):
        try:
            user_id = request.data.get('id')

            if not user_id:
                return Response({"error": "User ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            user = get_object_or_404(Accounts, id=user_id)

            user.isblocked = not user.isblocked
            user.save()
            if user.isblocked:
                subject = "⚠️ Account Access Restricted — CodeX Learning"

                message = (
                    f"Hello {user.first_name},\n\n"
                    f"We regret to inform you that your access to CodeX Learning has been restricted.\n\n"
                    f"Our team has reviewed multiple reports and found activities that violate our platform guidelines.\n\n"
                    f"As a result, your access to the platform has been temporarily blocked and you will not be able to "
                    f"log in or use CodeX Learning until the review is completed.\n\n"
                    f"If you believe this action was taken in error or you would like to appeal the decision, "
                    f"please reach out to our support team at codexlearninginfo@gmail.com.\n\n"
                    f"Thank you for your understanding.\n\n"
                    f"— CodeX Learning Team"
                )

                send_mail(subject, message, os.getenv("EMAIL_HOST_USER"), [user.email])

                send_notification(user, "Your account was blocked by admin. Please contact support.")
            else:
                
                subject = "✅ Account Access Restored — CodeX Learning"

                message = (
                    f"Hello {user.first_name},\n\n"
                    f"We are happy to inform you that your access to CodeX Learning has been restored.\n\n"
                    f"Our team has reviewed your account and your access to all features of the platform "
                    f"is now fully reactivated.\n\n"
                    f"You can log in and continue using the application as usual.\n\n"
                    f"If you have any questions or need assistance, feel free to contact us at codexlearninginfo@gmail.com.\n\n"
                    f"Welcome back!\n\n"
                    f"— CodeX Learning Team"
                )

                send_notification(user, "Your account was unblocked by admin. You can continue using the app.")

            return Response({"message": "Status updated successfully", "status": user.isblocked}, status=status.HTTP_200_OK)
        except:
            return Response({"Unauthorized": "Token expired"}, status=401)
        


class TutorStatus(APIView):

    def post(self, request):
        try:
            tutor_id = request.data.get('id')
            logger.debug(f"tutor id: {tutor_id}")

            if not tutor_id:
                logger.warning("no users")
                return Response({"error": "Tutor ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            account = get_object_or_404(Accounts, id=tutor_id)
            
            tutor = TutorDetails.objects.get(account=account)
            
            user = tutor.account

            user.isblocked = not user.isblocked
            user.save()


            if user.isblocked:
                
                courses = Course.objects.filter(created_by=tutor, is_draft=False, is_active=True, status="accepted")
            
                for course in courses:
                    if course.is_draft == False:
                        course.is_draft = True
                        course.save()
                
                send_notification(user, "Your account was blocked by admin. Please contact support.")
                
                subject = "⚠️ Tutor Panel Access Restricted — Account Blocked"

                message = (
                    f"Hello {user.first_name},\n\n"
                    f"Your tutor panel access on CodeX Learning has been blocked due to multiple user reports.\n\n"
                    f"As part of this action, your active courses have been moved to draft so new learners cannot enroll. "
                    f"Existing enrolled users will still have access.\n\n"
                    f"If you believe this was a mistake or would like to appeal, please contact us at codexlearninginfo@gmail.com.\n\n"
                    f"— CodeX Learning Team"
                )

                send_mail(subject, message, os.getenv("EMAIL_HOST_USER"), [user.email])
                
            else:
                
                send_notification(user, "Your account was unblocked by admin. ")
                
                
                subject = "✅ Tutor Panel Access Restored — Welcome Back!"

                message = (
                    f"Hello {user.first_name},\n\n"
                    f"After a careful review of the reports associated with your account, "
                    f"we have restored your tutor panel access on CodeX Learning.\n\n"
                    f"Please log in to your dashboard and reactivate any courses that were moved to draft during the block.\n\n"
                    f"If you need support, feel free to contact us at codexlearninginfo@gmail.com.\n\n"
                    f"— CodeX Learning Team"
                )

                send_mail(subject, message, os.getenv("EMAIL_HOST_USER"), [user.email])

            
            return Response({"message": "Status updated successfully", "status": user.isblocked}, status=status.HTTP_200_OK)
        except:
            return Response({"Error": "Error While Chaning the status"}, status=status.HTTP_400_BAD_REQUEST)



class TutorApplicationView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        logger.debug(f"application request data: {request.data}")
        data = {k: v for k, v in request.data.items()}
        logger.debug(f"application data: {data}")

        try:
            if request.FILES.get('profile_picture'):
                profile_file = request.FILES['profile_picture']
                upload_result = cloudinary.uploader.upload(
                    profile_file,
                    folder="profile_picture",
                    resource_type="image"
                )
                data['profile_picture'] = upload_result.get('secure_url')

            if request.FILES.get('verification_file'):
                doc_file = request.FILES['verification_file']
                upload_result = cloudinary.uploader.upload(
                    doc_file,
                    folder="verification_docs",
                    resource_type="raw"
                )
                data['verification_file'] = upload_result.get('secure_url')

            if request.FILES.get('verification_video'):
                video_file = request.FILES['verification_video']
                upload_result = cloudinary.uploader.upload(
                    video_file,
                    folder="verification_videos",
                    resource_type="video"
                )
                data['verification_video'] = upload_result.get('secure_url')

        except Exception as e:
            return Response({"error": "File upload failed", "details": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = TutorApplicationSerializer(data=data, context={"request": request})
        
        if serializer.is_valid():
            serializer.save(account=request.user)
            
            user = request.user
            subject = "📨 Tutor Application Submitted Successfully"
            message = (
                f"Hello {user.first_name},\n\n"
                f"Your tutor application has been submitted successfully.\n"
                f"Our verification team will review your details and documents.\n\n"
                f"Please note that this process typically takes around *2–3 business days*.\n"
                f"We will notify you once your application has been evaluated.\n\n"
                f"Thank you for choosing to become a Tutor at CodeX Learning!\n\n"
                f"— CodeX Learning Team"
            )

            from_email = os.getenv("EMAIL_HOST_USER")
            recipient_list = [user.email]
            
            send_mail(subject, message, from_email, recipient_list)
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class TutorApplicationsOverView(APIView):

    def get(self, request, id):
        try:
            user_application = get_object_or_404(TutorApplications, id=id)
            logger.debug(f"Found application: {user_application}")
            logger.debug(f"userId: {id}")

            data = {
                "id":user_application.id,
                "username": user_application.full_name,
                "email": user_application.email,
                "date_of_birth": user_application.dob,
                "education": user_application.education,
                "expertise": user_application.expertise,
                "occupation": user_application.occupation,
                "experience": user_application.experience,
                "about":user_application.about,
                "age":user_application.get_age(),
                "phone": user_application.phone,
                "presentation_video": user_application.verification_video if user_application.verification_video else None,
                "verification_file": user_application.verification_file if user_application.verification_file else None,
                "profile_picture": user_application.profile_picture if user_application.profile_picture else None,
                "status":user_application.status
            }
            logger.debug(f"data: {data}")

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error("ERROR OCCURRED:")
            return Response({"error": str(e)}, status=500)



class TutorOverView(APIView):

    def get(self, request, userId):
        try:
            deatils = get_object_or_404(TutorDetails, id=userId)
            subscription = get_object_or_404(TutorSubscription, tutor=deatils)

            data = {
                "id":deatils.account.id,
                "is_blocked": deatils.account.isblocked,
                "username": deatils.full_name,
                "email": deatils.account.email,
                "date_of_birth": deatils.dob,
                "education": deatils.education,
                "expertise": deatils.expertise,
                "occupation": deatils.occupation,
                "experience": deatils.experience,
                "about":deatils.about,
                "age":deatils.get_age(),
                "phone": deatils.account.phone,
                "presentation_video": deatils.verification_video if deatils.verification_video else None,
                "verification_file": deatils.verification_file if deatils.verification_file else None,
                "profile_picture": deatils.profile_picture if deatils.profile_picture else None,
                "status":deatils.status,
                "plan_name": subscription.plan.name,
                "plan_category": subscription.plan.plan_category,
                "plan_price": subscription.plan.price,
                "plan_type": subscription.plan.plan_type,
                "plan_expires": subscription.expires_on,
                "paln_subscribed": subscription.subscribed_on
            }

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error("ERROR OCCURRED:")
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)



class AcceptApplicationView(APIView):

    def post(self, request, applicationId):
        try:
            application = get_object_or_404(TutorApplications, id=applicationId)
            user = get_object_or_404(Accounts, email=application.email)
            logger.debug(f"user object: {user}")

            if not application.dob:
                return Response({"error": "Date of Birth is required"}, status=status.HTTP_400_BAD_REQUEST)

            tutor, created = TutorDetails.objects.get_or_create(
                account=user,
                defaults={
                    "full_name": application.full_name,
                    "dob": application.dob,
                    "phone": application.phone,
                    "about": application.about,
                    "education": application.education,
                    "expertise": application.expertise,
                    "occupation": application.occupation,
                    "experience": application.experience,
                    "profile_picture": application.profile_picture,
                    "verification_file": application.verification_file,
                    "verification_video": application.verification_video,
                    "status": "verified"
                }
            )

            if not created:
                tutor.full_name = application.full_name
                tutor.phone = application.phone
                tutor.dob = application.dob
                tutor.about = application.about
                tutor.education = application.education
                tutor.expertise = application.expertise
                tutor.occupation = application.occupation
                tutor.experience = application.experience
                tutor.profile_picture = application.profile_picture
                tutor.verification_file = application.verification_file
                tutor.verification_video = application.verification_video
                tutor.status = "verified"
                tutor.save()
                
            

            send_notification(user, "Your Application accepted by admin. Complete subscription to become a tutor.")
            
            subject = "🎉 Your Tutor Application Has Been Accepted"
            message = (
                f"Hello {user.first_name},\n\n"
                f"Great news! Your tutor application has been *accepted*.\n"
                f"Our team has reviewed your details and verified your documents successfully.\n\n"
                f"You are now officially a Tutor at CodeX Learning.\n"
                f"To start using the platform and access all tutor features, "
                f"please complete your subscription.\n\n"
                f"We are excited to have you on board!\n\n"
                f"— CodeX Learning Team"
            )


            from_email = os.getenv("EMAIL_HOST_USER")
            recipient_list = [user.email]
            
            send_mail(subject, message, from_email, recipient_list)

            # Update user role & application status
            user.role = "tutor"
            user.save()
            application.delete()
            
            

            return Response({"success": "Tutor Data added/updated successfully"}, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error While Creating Tutor: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class RejectApplicationView(APIView):
    def post(self, request, applicationId):
        try:
            application = get_object_or_404(TutorApplications, id=applicationId)
            reason = request.data.get("reason")

            if not reason:
                return Response({"error": "Rejection reason is required"}, status=400)

            application.status = "rejected"
            application.save()

            TutorRejectionHistory.objects.create(application=application, admin=request.user, reason=reason)

            user = application.account

            send_notification(user, "Your application was rejected. Check your email for details.")

            subject = "⚠️ Tutor Application Status Update — Application Rejected"

            message = (
                f"Hello {user.first_name},\n\n"
                f"Your tutor application has been rejected.\n"
                f"Reason: {reason}\n\n"
                f"Before resubmitting, please ensure you upload all relevant and clear verification documents.\n\n"
                f"You can resubmit your application after making the necessary improvements.\n\n"
                f"— CodeX Learning Team"
            )

            send_mail(subject, message, os.getenv("EMAIL_HOST_USER"), [user.email])

            return Response({"success": "Application Rejected"}, status=201)

        except Exception as e:
            return Response({"error": "Something went wrong", "details": str(e)}, status=400)



class RejectedReasonView(APIView):
    def get(self, request, id):
        try:
            
            application = TutorApplications.objects.get(id=id)
            
            data = TutorRejectionHistory.objects.get(application=application)
            
            serializer = TutorRejectedSerializer(data)
            
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class ListApplicationsView(APIView):
    def get(self, request):
        try:
            applications = TutorApplications.objects.all()
            serializer = TutorApplicationSerializer(applications, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class EditUserView(APIView):

    def put(self, request, email):
        try:
            try:
                user = Accounts.objects.get(email=email)
            except Accounts.DoesNotExist:
                return Response({"error":"Account not found"}, status=status.HTTP_404_NOT_FOUND)
            
            # serializer =  
        except Exception as e:
            return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)



class CreateCategoryView(APIView):
    def post(self, request):
        try:
            serializer = CategorySerializer(data=request.data)
            if serializer.is_valid():
                category = serializer.save()
                return Response(ListCategorySerializer(category).data, status=status.HTTP_201_CREATED)
            # Combine errors with custom message
            return Response(
                {"detail": "Data Already Exists.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"CreateCategoryView Error: {e}")
            return Response({"detail": "Something went wrong."}, status=status.HTTP_406_NOT_ACCEPTABLE)



class EditCategoryView(APIView):
    def put(self, request, id):
        try:
            try:
                category = CourseCategory.objects.get(id=id)
            except CourseCategory.DoesNotExist:
                return Response({"detail": "Category Does Not Exist"}, status=status.HTTP_404_NOT_FOUND)

            serializer = EditCategorySerializer(instance=category, data=request.data)
            if serializer.is_valid():
                serializer.save()
                category_data = CourseCategory.objects.all()
                return Response(ListCategorySerializer(category_data, many=True).data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"detail": "Category Name Already Exists", "errors": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.error(f"EditCategoryView Error: {str(e)}")
            return Response({"detail": "Error While Editing Category"}, status=status.HTTP_400_BAD_REQUEST)



class ListCategoryView(APIView):

    def get(self, request):
        try:
            categorys = CourseCategory.objects.all()
            serializer = ListCategorySerializer(categorys, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except:
            return Response({"error": "Data does not exist"}, status=status.HTTP_404_NOT_FOUND)



class CategoryStatusView(APIView):

    def post(self, request):
        try:
            category_id = request.data.get('id')
            logger.debug(f"category_id: {category_id}")
            if not category_id:
                return Response({"Error":"Id is Required"}, status=status.HTTP_400_BAD_REQUEST)
            category = get_object_or_404(CourseCategory, id=category_id)

            category.is_active = not category.is_active
            category.save()
            return Response({"message": "Status updated successfully", "status": category.is_active}, status=status.HTTP_200_OK)
        except:
            return Response({"Error": "Error While Chaning the status"}, status=status.HTTP_400_BAD_REQUEST)



def create_stripe_product_and_price(plan):
    product = stripe.Product.create(name=plan.name)

    interval = "month" if plan.plan_type == "MONTHLY" else "year"

    price = stripe.Price.create(
        unit_amount=int(plan.price * 100),  # in cents
        currency="inr",
        recurring={"interval": interval},
        product=product.id
    )

    return price.id



class CreatePlanView(APIView):

    def post(self, request):
        serializer = PlanSerializer(data=request.data)
        if serializer.is_valid():
            plan = serializer.save()
            price_id = create_stripe_product_and_price(plan)
            plan.stripe_price_id = price_id
            plan.save()
            return Response(PlanSerializer(plan).data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=400)



class ListPlanView(APIView):

    def get(self, request):
        try:
            plans = Plan.objects.all()
            serializer = PlanListSerializer(plans, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except:
            return Response({"error": "Data does not exist"}, status=status.HTTP_404_NOT_FOUND) 
    


class CourseRequestsView(APIView):

    def get(self, request):
        try:
            course_requests = Course.objects.exclude(status="accepted")
            data = []

            for reqeusts in course_requests:
                data.append({
                    "id":reqeusts.id,
                    "name": reqeusts.name,
                    "created_by":reqeusts.created_by.full_name,
                    "category": reqeusts.category_id.name if reqeusts.category_id else None,
                    "category_id":reqeusts.category_id.id if reqeusts.category_id else None,
                    "title": reqeusts.title,
                    "description": reqeusts.description,
                    "requirements": reqeusts.requirements,
                    "benefits": reqeusts.benefits,
                    "price": reqeusts.price,
                    "created_at": reqeusts.created_at,
                    "is_active": reqeusts.is_active,
                    "level": reqeusts.level,
                    "status":reqeusts.status,
                })

            return Response(data, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Fetching Course Request"}, status=status.HTTP_400_BAD_REQUEST)



class CourseStatusView(APIView):

    def post(self, request, id):
        try:
            course = get_object_or_404(Course, id=id)

            course.is_active = not course.is_active
            course.save()

            try:
                tutor = course.created_by
                tutor_user = tutor.account if hasattr(tutor, "account") else None

                if tutor_user:
                    support_email = "codexlearninginfo@gmail.com"

                    if course.is_active:
                        subject = "✅ Course Status Update — Course Activated"
                        message = (
                            f"Hello {tutor_user.first_name},\n\n"
                            f"Your course \"{course.name}\" "
                            f"has been ACTIVATED by the admin.\n\n"
                            f"If you have any concerns, contact {support_email}.\n\n"
                            f"— CodeX Learning Team"
                        )
                        visibility = "activated"
                    else:
                        subject = "⚠️ Course Status Update — Course Deactivated"
                        message = (
                            f"Hello {tutor_user.first_name},\n\n"
                            f"Your course \"{course.name}\" "
                            f"has been DEACTIVATED by the admin.\n\n"
                            f"Reason:\nThis course has been temporarily disabled by the admin.\n\n"
                            f"For more details, contact {support_email}.\n\n"
                            f"— CodeX Learning Team"
                        )
                        visibility = "deactivated"

                    send_mail(
                        subject,
                        message,
                        os.getenv("EMAIL_HOST_USER"),
                        [tutor_user.email],
                        fail_silently=True,
                    )

                    send_notification(tutor_user, f"Your course '{course.name}' was {visibility} by admin.")
            except:
                pass

            return Response(
                {"message": "Status updated successfully", "status": course.is_active},
                status=status.HTTP_200_OK
            )

        except:
            return Response(
                {"Error": "Error While Updating the status"},
                status=status.HTTP_400_BAD_REQUEST
            )



class SetCourseDraftView(APIView):
    
    def post(self, request, id):
        try:
            course = get_object_or_404(Course, id=id)
            if course:
                course.is_draft = not course.is_draft
                course.save()
                return Response({"message":"Course Set To Draft Successfully"}, status=status.HTTP_200_OK)
            else:
                return Response({"error":"Course Doest Not Exists"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)



class ListCoursesView(APIView):

    def get(self, requests):
        try:
            course_requests = Course.objects.filter(status="accepted")
            data = []

            for reqeusts in course_requests:
                data.append({
                    "id":reqeusts.id,
                    "name": reqeusts.name,
                    "created_by":reqeusts.created_by.full_name,
                    "category": reqeusts.category_id.name if reqeusts.category_id else None,
                    "category_id":reqeusts.category_id.id if reqeusts.category_id else None,
                    "title": reqeusts.title,
                    "description": reqeusts.description,
                    "requirements": reqeusts.requirements,
                    "benefits": reqeusts.benefits,
                    "price": reqeusts.price,
                    "created_at": reqeusts.created_at,
                    "is_active": reqeusts.is_active,
                    "is_draft": reqeusts.is_draft,
                    "level":reqeusts.level,
                    "status":reqeusts.status,
                })

            return Response(data, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Fetching Course Request"}, status=status.HTTP_400_BAD_REQUEST)



class CoureseStatusView(APIView):

    def post(self, request, id):
        try:
            course = get_object_or_404(Course, id=id)

            tutor_details = course.created_by
            user = getattr(tutor_details, "account", None)

            if not user or not user.email:
                return Response(
                    {"Error": "Tutor account or email not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            course.is_active = not course.is_active
            course.save()

            support_email = "codexlearninginfo@gmail.com"

            if course.is_active:
                subject = "✅ Course Status Update — Course Activated"
                message = (
                    f"Hello {user.first_name},\n\n"
                    f"Your course \"{course.name}\" has been ACTIVATED by the admin.\n\n"
                    f"If you have any questions or need assistance, please contact {support_email}.\n\n"
                    f"— CodeX Learning Team"
                )
                visibility = "activated"
            else:
                subject = "⚠️ Course Status Update — Course Deactivated"
                message = (
                    f"Hello {user.first_name},\n\n"
                    f"Your course \"{course.name}\" has been DEACTIVATED by the admin.\n\n"
                    f"Reason:\nThis course has been temporarily disabled for review or required corrections.\n\n"
                    f"For more support or clarification, reach out to {support_email}.\n\n"
                    f"— CodeX Learning Team"
                )
                visibility = "deactivated"

            send_mail(
                subject,
                message,
                os.getenv("EMAIL_HOST_USER"),
                [user.email],
                fail_silently=False,
            )

            send_notification(user, f"Your course '{course.name}' was {visibility} by admin.")

            return Response(
                {"message": "Status updated successfully", "status": course.is_active},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"Error": f"Error While Updating the status: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )



class AcceptCourseRequestView(APIView):
    def post(self, request, courseId):
        logger.info(f"[AcceptCourseRequestView] POST request received for courseId={courseId}")

        try:
            course = get_object_or_404(Course, id=courseId)
            logger.debug(f"[DEBUG] Course found: {course.name} (status={course.status})")

            # ✅ FIX: Directly access the related tutor
            tutor = course.created_by
            logger.debug(f"[DEBUG] Tutor fetched from course: {tutor}")

            # ✅ Get tutor's account
            user = get_object_or_404(Accounts, id=tutor.account.id)
            logger.debug("[DEBUG] Tutor's account found | user_id=%s", user.id)

            # ✅ Update course status
            course.status = "accepted"
            course.is_active = True
            course.save()
            logger.info(f"[INFO] Course '{course.name}' accepted successfully.")

            # ✅ Notify tutor
            try:
                send_notification(user, f"🎉 Your course '{course.name}' was accepted by admin.")
                logger.info("[SUCCESS] Notification sent | user_id=%s | course_id=%s", user.id, course.id)
            except Exception as notify_error:
                logger.error(f"[ERROR] Failed to send notification: {notify_error}", exc_info=True)

            return Response({"message": "course accepted successfully"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"[EXCEPTION] Error while accepting course request for courseId={courseId}: {e}")
            return Response({"Error": "Error While Accepting Course Request"}, status=status.HTTP_400_BAD_REQUEST)
        


class RejectCourseRequestView(APIView):

    def post(self, request, courseId):
        try:
            course = get_object_or_404(Course, id=courseId)
            reason = request.data.get("reason")

            if not reason:
                return Response({"error": "Rejection reason is required"}, status=400)
            
            tutor = course.created_by

            user = get_object_or_404(Accounts, id=tutor.account.id)

            if not course:
                return Response({"error":"Course Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            CourseRejectionHistory.objects.create(course=course, admin=request.user, reason=reason)
            
            course.status = "rejected"
            course.is_active = False
            course.save()
            
            send_notification(user, "Your course was rejected. Check your email for details.")

            subject = "⚠️ Course Status Update — Course Rejected"

            message = (
                f"Hello {user.first_name},\n\n" 
                f"Your course \"{course.title}\" has been reviewed and unfortunately it has been rejected.\n\n"
                f"Reason: {reason}\n\n"
                f"Before resubmitting, please make sure your course meets the platform guidelines, "
                f"includes clear structure, proper content, and all required details.\n\n"
                f"You can update the course based on the above reason and resubmit it for review.\n\n"
                f"— CodeX Learning Team"
            )

            send_mail(subject, message, os.getenv("EMAIL_HOST_USER"), [user.email])
            
            return Response({"message":"course rejected successfully"}, status=status.HTTP_200_OK)
        except:
            return Response({"Error": "Error While Rjecting Course Request"}, status=status.HTTP_400_BAD_REQUEST)



class AcceptModuleView(APIView):

    def post(self, request, id):
        try:
            module = get_object_or_404(Modules, id=id)

            if not module:
                return Response({"error":"Module Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            module.status = "accepted"
            module.is_active = True
            module.save()

            # Notify tutor
            try:
                tutor = module.course.created_by
                tutor_user = tutor.account if hasattr(tutor, 'account') else None
                if tutor_user:
                    send_notification(tutor_user, f"Your module '{module.title}' was approved by admin.")
            except Exception:
                pass

            return Response({})
        except:
            return Response({"Error": "Error While Accepting Course Request"}, status=status.HTTP_400_BAD_REQUEST)
        


class RejectModuleView(APIView):

    def post(self, request, id):
        try:
            module = get_object_or_404(Modules, id=id)
            reason = request.data.get("reason")

            if not module:
                return Response({"error":"Module Not Found"}, status=status.HTTP_404_NOT_FOUND)

            if not reason:
                return Response({"error": "Rejection reason is required"}, status=400)
            
            module.status = "rejected"
            module.is_active = False
            module.save()
            
            ModuleRejectionHistory.objects.create(module=module, admin=request.user, reason=reason)

            try:
                tutor = module.course.created_by
                tutor_user = tutor.account if hasattr(tutor, 'account') else None
                if tutor_user:
                    send_notification(
                    tutor_user,
                    "One of your course modules was rejected. Check your email for details."
                )

                subject = "⚠️ Module Status Update — Module Rejected"

                message = (
                    f"Hello {tutor_user.first_name},\n\n"
                    f"Your module \"{module.title}\""
                    f"{f' in the course \"{module.course.title}\"' if module.course else ''} "
                    f"has been reviewed and unfortunately it has been rejected.\n\n"
                    f"Reason: {reason}\n\n"
                    f"Before resubmitting, please make sure this module meets the platform guidelines, "
                    f"has a clear structure, proper explanations, and all required content.\n\n"
                    f"You can update the module based on the above reason and resubmit it for review.\n\n"
                    f"— CodeX Learning Team"
                )

                send_mail(subject, message, os.getenv("EMAIL_HOST_USER"), [tutor_user.email])
            except Exception:
                pass

            return Response({})
        except:
            return Response({"Error": "Error While Accepting Course Request"}, status=status.HTTP_400_BAD_REQUEST)



class ListCourseModulesView(APIView):
    def get(self, request, id):
        try:
            try:
                course = get_object_or_404(Course, id=id)
            except Course.DoesNotExist:
                return Response({"error": "Course Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            try:
                modules = Modules.objects.filter(course=course)
            except:
                return Response({"error": "Modules Not Found"}, status=status.HTTP_404_NOT_FOUND)

            serializer = CourseModuleSerializer(modules, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching course overview: {e}")
            return Response({"error": "Something went wrong"}, status=status.HTTP_400_BAD_REQUEST)



class CourseOverView(APIView):

    def get(self, request, id):
        try:
            try:
                course = get_object_or_404(Course, id=id)
            except Course.DoesNotExist:
                return Response({"error": "Course Not Found"}, status=status.HTTP_404_NOT_FOUND)

            return Response(CourseRequestSerializer(course).data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching course overview: {e}")
            return Response({"error": "Something went wrong"}, status=status.HTTP_400_BAD_REQUEST)



class ModuleDetailView(APIView):

    def get(self, request, id):
        try:
            module = get_object_or_404(Modules, id=id)

            if not module:
                return Response({"error":"Module Does not found"}, status=status.HTTP_404_NOT_FOUND)
            
            return Response(CourseModuleSerializer(module).data, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Fetching Module"}, status=status.HTTP_400_BAD_REQUEST)



class ModuleStatusView(APIView):

    def post(self, request, id):
        try:
            module = get_object_or_404(Modules, id=id)

            module.is_active = not module.is_active
            module.save()

            try:
                tutor = module.course.created_by
                tutor_user = tutor.account if hasattr(tutor, "account") else None

                if tutor_user:
                    support_email = "codexlearninginfo@gmail.com"

                    if module.is_active:
                        subject = "✅ Module Status Update — Module Activated"
                        message = (
                            f"Hello {tutor_user.first_name},\n\n"
                            f"Your module \"{module.title}\" in the course \"{module.course.title}\" "
                            f"has been ACTIVATED by the admin.\n\n"
                            f"If you have any concerns, contact {support_email}.\n\n"
                            f"— CodeX Learning Team"
                        )
                        visibility = "activated"
                    else:
                        subject = "⚠️ Module Status Update — Module Deactivated"
                        message = (
                            f"Hello {tutor_user.first_name},\n\n"
                            f"Your module \"{module.title}\" in the course \"{module.course.title}\" "
                            f"has been DEACTIVATED by the admin.\n\n"
                            f"Reason:\nThis module has been temporarily disabled by the admin.\n\n"
                            f"For more details, contact {support_email}.\n\n"
                            f"— CodeX Learning Team"
                        )
                        visibility = "deactivated"

                    send_mail(
                        subject,
                        message,
                        os.getenv("EMAIL_HOST_USER"),
                        [tutor_user.email],
                        fail_silently=True,
                    )

                    send_notification(tutor_user, f"Your module '{module.title}' was {visibility} by admin.")
            except:
                pass

            return Response({"detail": "Status Changed Successfully"}, status=status.HTTP_200_OK)
        except:
            return Response({"error": "Error While Changing Module Status"}, status=status.HTTP_400_BAD_REQUEST)



class ListCourseLessonView(APIView):

    def get(self, request, id):
        try:
            logger.debug(f"module id: {id}")
            module = get_object_or_404(Modules, id=id)
            lessons = Lessons.objects.filter(module=module)
            
            serializer = LessonOverviewSerializer(lessons, many=True)
            logger.debug(f"serializer: {serializer}")
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Modules.DoesNotExist:
            return Response({"error": "Module Not Found"}, status=status.HTTP_404_NOT_FOUND)

        except Lessons.DoesNotExist:
            return Response({"error": "Lessons Not Found"}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": f"Error While Fetching Lessons: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)



class AcceptLessonView(APIView):

    def post(self, request, lessonId):
        try:
            lesson = get_object_or_404(Lessons, id=lessonId)
            if not lesson:
                return Response({"error":"Lesson Not Found"}, status=status.HTTP_404_NOT_FOUND)
            lesson.status = "accepted"
            lesson.is_active = True
            lesson.save()

            # Notify tutor
            try:
                tutor = lesson.module.course.created_by
                tutor_user = tutor.account if hasattr(tutor, 'account') else None
                if tutor_user:
                    send_notification(tutor_user, f"Your lesson '{lesson.title}' was approved by admin.")
            except Exception:
                pass

            return Response({"detail":"Lesson Accepted Successfully"}, status=status.HTTP_200_OK) 
        except:
            return Response({"error":"Error While Accepting Lesson"}, status=status.HTTP_400_BAD_REQUEST)
        


class RejectLessonView(APIView):

    def post(self, request, lessonId):
        try:
            lesson = get_object_or_404(Lessons, id=lessonId)
            reason = request.data.get("reason")
            
            if not lesson:
                return Response({"error":"Lesson Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            if not reason:
                return Response({"error": "Rejection reason is required"}, status=400)
            
            lesson.status = "rejected"
            lesson.is_active = False
            lesson.save()
            
            LessonRejectionHistory.objects.create(lesson=lesson, admin=request.user, reason=reason)

            try:
                tutor = lesson.module.course.created_by
                tutor_user = tutor.account if hasattr(tutor, 'account') else None
                if tutor_user:
                    send_notification(tutor_user, "One of your lessons was rejected. Check your email for details.")

                    subject = "⚠️ Lesson Status Update — Lesson Rejected"

                    message = (
                        f"Hello {tutor_user.first_name},\n\n"
                        f"Your lesson \"{lesson.title}\" under the module \"{lesson.module.title}\" "
                        f"has been reviewed and unfortunately it has been rejected.\n\n"
                        f"Reason: {reason}\n\n"
                        f"Before resubmitting, please ensure this lesson meets the platform guidelines, "
                        f"provides clear explanations, proper structure, and all required content.\n\n"
                        f"You can update the lesson based on the above reason and resubmit it for review.\n\n"
                        f"— CodeX Learning Team"
                    )

                    send_mail(subject, message, os.getenv("EMAIL_HOST_USER"), [tutor_user.email])

            except Exception:
                pass

            return Response({"detail":"Lesson Rejected Successfully"}, status=status.HTTP_200_OK) 
        except:
            return Response({"error":"Error While Rejecting Lesson"}, status=status.HTTP_400_BAD_REQUEST)



class LessonStatusView(APIView):

    def post(self, request, lessonId):
        try:
            lesson = get_object_or_404(Lessons, id=lessonId)

            lesson.is_active = not lesson.is_active
            lesson.save()

            try:
                tutor = lesson.module.course.created_by
                tutor_user = tutor.account if hasattr(tutor, "account") else None

                if tutor_user:
                    support_email = "codexlearninginfo@gmail.com"

                    if lesson.is_active:
                        subject = "✅ Lesson Status Update — Lesson Activated"
                        message = (
                            f"Hello {tutor_user.first_name},\n\n"
                            f"Your lesson \"{lesson.title}\" in the module \"{lesson.module.title}\" "
                            f"has been ACTIVATED by the admin.\n\n"
                            f"If you have any concerns, contact {support_email}.\n\n"
                            f"— CodeX Learning Team"
                        )
                        visibility = "activated"
                    else:
                        subject = "⚠️ Lesson Status Update — Lesson Deactivated"
                        message = (
                            f"Hello {tutor_user.first_name},\n\n"
                            f"Your lesson \"{lesson.title}\" in the module \"{lesson.module.title}\" "
                            f"has been DEACTIVATED by the admin.\n\n"
                            f"Reason:\nThis lesson has been temporarily disabled by the admin.\n\n"
                            f"For more details, contact {support_email}.\n\n"
                            f"— CodeX Learning Team"
                        )
                        visibility = "deactivated"

                    send_mail(
                        subject,
                        message,
                        os.getenv("EMAIL_HOST_USER"),
                        [tutor_user.email],
                        fail_silently=True,
                    )

                    send_notification(tutor_user, f"Your lesson '{lesson.title}' was {visibility} by admin.")
            except:
                pass

            return Response({"detail": "Status Changed Successfully"}, status=status.HTTP_200_OK)
        except:
            return Response({"error": "Error While Changing Lesson Status"}, status=status.HTTP_400_BAD_REQUEST)



class LessonOverview(APIView):

    def get(self, request, lessonId):
        try:
            lesson = get_object_or_404(Lessons, id=lessonId)
            
            if not lesson:
                return Response({"error":"Lesson Not Found"}, status=status.HTTP_404_NOT_FOUND)

            return Response(LessonOverviewSerializer(lesson).data, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Fetching Lesson Details"}, status=status.HTTP_400_BAD_REQUEST)



class ReportsView(APIView):

    def get(self, request):
        try:
            tutor_reports = TutorReport.objects.all()
            course_reports = CourseReport.objects.all()


            most_reported_tutor = (
                tutor_reports.values("tutor")
                .annotate(count=models.Count("id"))
                .order_by("-count")
                .first()
            )

            if most_reported_tutor:
                tutor_obj = TutorDetails.objects.filter(id=most_reported_tutor["tutor"]).first()
                most_reported_tutor = {
                    "id": tutor_obj.id,
                    "tutor_name": tutor_obj.full_name,
                    "count": most_reported_tutor["count"]
                }


            most_reported_course = (
                course_reports.values("course")
                .annotate(count=models.Count("id"))
                .order_by("-count")
                .first()
            )

            if most_reported_course:
                course_obj = Course.objects.filter(id=most_reported_course["course"]).first()
                most_reported_course = {
                    "id": course_obj.id,
                    "course_name": course_obj.name,
                    "count": most_reported_course["count"]
                }

            response = {
                "tutor_reports": TutorReportSerializer(tutor_reports, many=True).data,
                "most_reported_tutor": most_reported_tutor,
                "course_reports": CourseReportSerializer(course_reports, many=True).data,
                "most_reported_course": most_reported_course
            }

            return Response(response, status=200)

        except Exception as e:
            logger.error(f"Error: {e}")
            return Response({"error": str(e)}, status=400)



class TutorReportMarkView(APIView):
    def post(self, request, id):
        try:
            report = get_object_or_404(TutorReport, id=id)
            
            if not report.is_marked:
                report.is_marked = True
                report.save()
                
                send_report_marked_email.delay(
                    user_email=report.user.email,
                    user_name=report.user.first_name,
                    report_type="tutor",
                    reported_name=report.tutor.full_name
                )
                
                message = (
                    f"Your report against tutor '{report.tutor.full_name}' "
                    "has been reviewed by the admin team. Appropriate action has been taken."
                )
                
                send_notification(report.user, message)

            
                return Response({"message":"Report Marked Successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, id):
        try:
            report = get_object_or_404(TutorReport, id=id)

            report.delete()
            return Response(
                {"message": "Tutor report deleted successfully."},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class CourseReportMarkView(APIView):
    def post(self, request, id):
        try:
            report = get_object_or_404(CourseReport, id=id)
            
            if not report.is_marked:
                report.is_marked = True
                report.save()
                
                send_report_marked_email.delay(
                    user_email=report.user.email,
                    user_name=report.user.first_name,
                    report_type="course",
                    reported_name=report.course.title
                )
                
                message = (
                    f"Your report against course '{report.course.title}' "
                    "has been reviewed by the admin team. Appropriate action has been taken."
                )
                
                send_notification(report.user, message)

            
                return Response({"message":"Report Marked Successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, id):
        try:
            report = get_object_or_404(CourseReport, id=id)

            report.delete()
            return Response(
                {"message": "Course report deleted successfully."},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class PlatformWalletView(APIView):
    
    def get(self, request):
        try:
            wallet, _ = PlatformWallet.objects.get_or_create(id=1)
            
            wallet_transactions = PlatformWalletTransaction.objects.filter(wallet=wallet)
            
            transactions = PlatformWalletTransactionSerializer(wallet_transactions, many=True).data
            
            response_data = {
                "wallet": {
                    "total_revenue": wallet.total_revenue,
                    "created_at": wallet.created_at
                },
                "transactions": transactions
            }
            
            logger.info("Platform wallet details returned successfully")
            return Response(response_data)
            
        except Exception as e:
            logger.error(
                f"Error in Platform wallet view: {str(e)}",
                exc_info=True
            )
            return Response({"error": "Something went wrong"}, status=500)



class PayoutRequestsListView(APIView):
    def get(self, request):
        
        try:
            payouts = PayoutRequest.objects.all()
            logger.debug(f"Fetched {payouts.count()} payout requests")

            payout_serializer = PayoutRequestSerializer(payouts, many=True)
            
            response_data = {
                "payout_requests": payout_serializer.data,
            }

            logger.info("Payout request list returned successfully")
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(
                f"Error in PayoutRequestListView: {str(e)}",
                exc_info=True
            )
            return Response({"error": "Something went wrong"}, status=500)



class PayoutRequestDetailsView(APIView):
    def get(self, request, id):
        try:
            logger.info(f"PayoutRequestDetailsView GET requested id: {id}")

            payout_request = get_object_or_404(PayoutRequest, id=id)

            wallet = get_object_or_404(Wallet, tutor=payout_request.tutor)

            logger.info(f"Wallet fetched for tutor: {wallet.tutor.id}")

            transactions = WalletTransaction.objects.filter(wallet=wallet)
            logger.debug(f"Fetched {transactions.count()} transactions for wallet {wallet.id}")

            total_earned = (
                WalletTransaction.objects.filter(wallet=wallet).aggregate(total=Sum("amount"))["total"] or 0
            )

            pr_list = PayoutRequest.objects.filter(wallet=wallet)

            tx_serializer = WalletTransactionSerializer(transactions, many=True)
            pr_serializer = PayoutRequestSerializer(pr_list, many=True)

            response_data = {
                "tutor_data": {
                    "tutor_name": wallet.tutor.full_name,
                    "balance": wallet.balance,
                    "total_earned": total_earned,
                    "total_redeemed": wallet.total_withdrawn,
                },
                "transactions": tx_serializer.data,
                "payout_requests": pr_serializer.data
            }

            logger.info(f"PayoutRequestDetails returned successfully for tutor {wallet.tutor.id}")
            return Response(response_data)

        except Exception as e:
            logger.error(f"Error in PayoutRequestDetailsView for id={id}: {str(e)}", exc_info=True)
            return Response({"error": "Something went wrong"}, status=500)



class ApprovePayoutRequestView(APIView):
    def post(self, request, id):
        try:
            admin_note = request.data.get("admin_note")

            if not admin_note:
                logger.error("Admin Note is required")
                return Response({"error": "Admin Note Required"}, status=400)

            try:
                payout_request = PayoutRequest.objects.get(id=id, status="PENDING")
            except PayoutRequest.DoesNotExist:
                logger.warning("Payout cancel failed: request_id=%s not found or not pending",id)
                return Response({"error": "Payout request not found or cannot be cancelled."},status=status.HTTP_404_NOT_FOUND)
            
            wallet = Wallet.objects.get(tutor=payout_request.tutor)
            
            UPI_REGEX = r"^[\w\.-]{2,256}@[A-Za-z]{2,64}$"

            if not payout_request.upi_id or not re.match(UPI_REGEX, payout_request.upi_id):
                logger.warning(f"Invalid UPI ID submitted by user {payout_request.tutor.id}")
                return Response({"error": "Invalid UPI ID format."}, status=status.HTTP_400_BAD_REQUEST)

            if payout_request.amount is None or str(payout_request.amount).strip() == "":
                logger.warning(f"Amount missing in payout request by user {payout_request.tutor.id}")
                return Response({"error": "Amount is required."}, status=status.HTTP_400_BAD_REQUEST)

            try:
                amount_decimal = Decimal(str(payout_request.amount))
            except (InvalidOperation, ValueError):
                logger.warning(f"Invalid amount submitted by user {payout_request.tutor.id}")
                return Response({"error": "Amount must be a valid number."}, status=status.HTTP_400_BAD_REQUEST)

            if amount_decimal <= 0:
                logger.warning(f"Non-positive amount submitted by user {payout_request.tutor.id}")
                return Response({"error": "Amount must be greater than 0."}, status=status.HTTP_400_BAD_REQUEST)

            MIN_PAYOUT = Decimal("10")
            if amount_decimal < MIN_PAYOUT:
                logger.warning(f"Payout below minimum amount attempted by user {payout_request.tutor.id}: {amount_decimal}")
                return Response({"error": "Minimum withdrawal amount is $10."}, status=status.HTTP_400_BAD_REQUEST)

            if amount_decimal > wallet.balance:
                logger.warning(f"Insufficient balance for payout - User {payout_request.tutor.id}")
                return Response({"error": "Insufficient wallet balance."}, status=status.HTTP_400_BAD_REQUEST)

            if not payout_request.bank_name:
                logger.warning(f"Bank name missing in payout request by user {payout_request.tutor.id}")
                return Response({"error": "Bank name is required."}, status=status.HTTP_400_BAD_REQUEST)

            logger.info(f"Payout request: {payout_request.id}")

            payout_request.status = "PAID"
            payout_request.admin_note = admin_note
            payout_request.processed_at = now()
            payout_request.save()

            wallet.balance -= payout_request.amount 
            wallet.total_withdrawn += payout_request.amount
            wallet.save()


            subject = "🎉 Payout Request Approved – Amount Will Be Credited Soon" 
            
            message = ( 
                f"Hello {payout_request.tutor.full_name},\n\n" 
                f"Good news! Your payout request has been approved by our finance team.\n\n" 
                f"Payout Summary:\n" 
                f"- Amount: ${payout_request.amount}\n" 
                f"- Bank: {payout_request.bank_name}\n" 
                f"- UPI ID: {payout_request.upi_id}\n\n" 
                f"The amount will be credited to your account within the next 24 hours.\n\n" 
                f"If you have any questions, feel free to contact us at codexlearning@gmail.com.\n\n" 
                f"Thank you for being a valued tutor at CodeX Learning.\n\n" 
                f"— CodeX Learning Team" 
                )

            send_mail(subject, message, os.getenv("EMAIL_HOST_USER"), [payout_request.tutor.account.email])
            logger.info(f"Payout approval email sended")
            
            send_notification(
            payout_request.tutor.account,
            "Your payout request has been approved. Please check your email."
            )

            return Response({"message": "Payout Request Approved Successfully"}, status=200)

        except Exception as e:
            logger.error(f"Error while approving payout request {id}: {str(e)}", exc_info=True)
            return Response({"error": "Something went wrong"}, status=500)



class RejectPayoutRequestView(APIView):
    def post(self, request, id):
        try:
            admin_note = request.data.get("admin_note")

            if not admin_note:
                logger.error("Admin Note is required")
                return Response({"error": "Admin Note Required"}, status=400)

            try:
                payout_request = PayoutRequest.objects.get(id=id, status="PENDING")
            except PayoutRequest.DoesNotExist:
                logger.warning("Payout cancel failed: request_id=%s not found or not pending",id)
                return Response({"error": "Payout request not found or cannot be cancelled."},status=status.HTTP_404_NOT_FOUND)

            logger.info(f"Admin Note: {admin_note}")
            logger.info(f"Payout request: {payout_request.id}")

            payout_request.status = "REJECTED"
            payout_request.admin_note = admin_note
            payout_request.processed_at = now()
            payout_request.save()

            send_notification(
                payout_request.tutor.account,
                "Your payout request has been rejected. Please check your email."
            )

            subject = "❗ Payout Request Rejected – Action Needed" 
            
            message = ( 
                f"Hello {payout_request.tutor.full_name},\n\n" 
                f"We regret to inform you that your recent payout request could not be processed and has been rejected.\n\n" 
                f"Payout Summary:\n" f"- Amount: ${payout_request.amount}\n" f"- Bank: {payout_request.bank_name}\n" 
                f"- UPI ID: {payout_request.upi_id}\n\n" f"Reason for Rejection:\n" 
                f"- {admin_note}\n\n" 
                f"This usually happens due to incorrect bank details, invalid UPI ID, or mismatched account information.\n\n" 
                f"Please review your payout details and submit a new request.\n" 
                f"If you believe this is a mistake or need assistance, feel free to reach out to us at codexlearning@gmail.com.\n\n" 
                f"Thank you for your patience.\n\n" 
                f"— CodeX Learning Team" 
                )

            send_mail(subject, message, os.getenv("EMAIL_HOST_USER"), [payout_request.tutor.account.email])
            logger.info("Payout reject email sent | user_id=%s", payout_request.tutor.account.id)

            return Response({"message": "Payout Request Rejected Successfully"}, status=200)

        except Exception as e:
            logger.error(f"Error while rejecting payout request {id}: {str(e)}", exc_info=True)
            return Response({"error": "Something went wrong"}, status=500)
