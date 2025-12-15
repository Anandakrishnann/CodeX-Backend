from rest_framework.views import APIView 
from rest_framework.response import Response 
from rest_framework import status 
from rest_framework.permissions import AllowAny 
from rest_framework_simplejwt.tokens import RefreshToken 
from rest_framework.decorators import permission_classes
from django.contrib.auth import get_user_model
from .serializers import *
from django.shortcuts import redirect
from random import randint
from .models import *
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenRefreshView
from django.core.exceptions import ObjectDoesNotExist
from django.utils.crypto import get_random_string
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.hashers import make_password
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.timezone import localtime
from django.utils.timezone import now
from adminpanel.models import *
from tutorpanel.models import *
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import logging
import requests
from django.conf import settings
import cloudinary.uploader
from .utils.certificate import generate_certificate_image
from django.core.mail import EmailMessage
from django.http import FileResponse
from PIL import Image, ImageDraw, ImageFont
from django.http import HttpResponse, Http404
from datetime import datetime, timedelta
from io import BytesIO
import stripe # type: ignore
import traceback
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils.timezone import make_aware
from .permissions import IsAuthenticatedUser
from .tasks import *
from django.core.cache import cache
import hashlib, random
from decimal import Decimal
import os

logger = logging.getLogger("codex")


User = get_user_model()

stripe.api_key = settings.STRIPE_SECRET_KEY
endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

User = get_user_model()



class UserRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = UserRegisterSerializer(data=request.data)

            if not serializer.is_valid():
                logger.warning(f"User registration validation failed: {serializer.errors}")
                return Response(serializer.errors, status=400)

            user_data = serializer.validated_data
            email = user_data["email"].strip()

            if Accounts.objects.filter(email=email).exists():
                logger.warning(f"Registration failed: User already exists ({email})")
                return Response({"error": "User already exists"}, status=400)

            # Generate OTP
            otp = randint(100000, 999999)
            otp_hash = hashlib.sha256(str(otp).encode()).hexdigest()

            # Store user data for 10 minutes
            reg_key = f"pending_register:{email}"
            cache.set(reg_key, {
                "user_data": user_data,
                "attempts": 0
            }, timeout=600)  # 10 minutes

            # Store OTP for 2 minutes
            otp_key = f"otp:{email}"
            cache.set(otp_key, otp_hash, timeout=120)  # 2 minutes

            # Sending Email
            try:
                send_mail(
                    "Your OTP for Verification",
                    f"Your OTP is: {otp}",
                    settings.EMAIL_HOST_USER,
                    [email]
                )
            except Exception:
                logger.exception(f"Email sending failed for OTP to {email}")
                return Response({"error": "Failed to send OTP email"}, status=500)

            logger.info(f"OTP generated for {email}: {otp}")
            return Response({"message": "OTP sent to your email"}, status=200)

        except Exception:
            logger.exception("Unexpected error during user registration")
            return Response({"error": "Something went wrong"}, status=500)



class OTPVerificationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            email = request.data.get("email", "").strip()
            otp = request.data.get("otp")

            if not email or not otp:
                logger.warning("OTP verification attempt with missing fields")
                return Response({"error": "Email and OTP are required"}, status=400)

            reg_key = f"pending_register:{email}"
            otp_key = f"otp:{email}"

            data = cache.get(reg_key)
            otp_hash = cache.get(otp_key)

            if not data:
                logger.warning(f"Registration expired for {email}")
                return Response({"error": "Registration expired. Please register again."}, status=400)

            if not otp_hash:
                logger.warning(f"OTP expired for {email}")
                return Response({"error": "OTP expired. Please request a new OTP."}, status=400)

            if data["attempts"] >= 5:
                logger.warning(f"OTP verification blocked for {email}: Too many attempts")
                return Response({"error": "Too many attempts. Try again later"}, status=429)

            entered_hash = hashlib.sha256(str(otp).encode()).hexdigest()

            if entered_hash != otp_hash:
                data["attempts"] += 1
                cache.set(reg_key, data, timeout=600)
                logger.warning(f"Invalid OTP for {email}. Attempts: {data['attempts']}")
                return Response({"error": "Invalid OTP"}, status=400)

            # OTP correct --> create user
            user_data = data["user_data"]
            password = user_data.pop("password")

            user = Accounts.objects.create(**user_data)
            user.set_password(password)
            user.is_active = True
            user.save()

            # Cleanup
            cache.delete(reg_key)
            cache.delete(otp_key)

            logger.info(f"User created after OTP verification: {email}")

            try:
                send_mail(
                    "Account Activated Successfully",
                    "Your CodeX Learning account is now active.",
                    settings.EMAIL_HOST_USER,
                    [email]
                )
            except Exception:
                logger.exception(f"Activation email sending failed for {email}")

            return Response({"message": "Account created successfully"}, status=200)

        except Exception:
            logger.exception("Unexpected error during OTP verification")
            return Response({"error": "Something went wrong"}, status=500)



class ResendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            email = request.data.get("email", "").strip()

            if not email:
                logger.warning("Resend OTP attempt with missing email")
                return Response({"error": "Email is required"}, status=400)

            reg_key = f"pending_register:{email}"
            otp_key = f"otp:{email}"

            data = cache.get(reg_key)

            if not data:
                logger.warning(f"Resend OTP failed - no pending registration for {email}")
                return Response({"error": "No pending registration found"}, status=400)

            # Generate new OTP
            otp = randint(100000, 999999)
            otp_hash = hashlib.sha256(str(otp).encode()).hexdigest()

            # Save OTP for 2 minutes
            cache.set(otp_key, otp_hash, timeout=120)

            cache.set(reg_key, data, timeout=600)

            try:
                send_mail(
                    "Your OTP for Verification",
                    f"Your OTP is: {otp}",
                    settings.EMAIL_HOST_USER,
                    [email]
                )
            except Exception:
                logger.exception(f"Failed to resend OTP email to {email}")
                return Response({"error": "Failed to resend OTP email"}, status=500)

            logger.info(f"OTP resent to {email}: {otp}")
            return Response({"message": "OTP resent successfully"}, status=200)

        except Exception:
            logger.exception("Unexpected error during resend OTP")
            return Response({"error": "Something went wrong"}, status=500)



class GoogleVerifiedCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, email):
        try:
            account = Accounts.objects.get(email=email)

            if account.google_verified:
                return Response(
                    {"error": "⚠️ This account is linked with Google. Please use 'Login with Google' to sign in."},
                    status=status.HTTP_201_CREATED
                )

            return Response(
                {"message": "Google verification not required for this account."},
                status=status.HTTP_200_OK
            )

        except Accounts.DoesNotExist:
            return Response(
                {"error": "❌ No account found with this email."},
                status=status.HTTP_404_NOT_FOUND
            )



class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        email = request.data.get("email")
        try:
            account = Accounts.objects.get(email=email)
            if account.google_verified:
                logger.warning(f"User {email} attempted regular login but account is Google verified")
                return Response({"error":"⚠️ Unable to log you in. Please sign in using your Google account to continue."}, status=status.HTTP_406_NOT_ACCEPTABLE)
        except Accounts.DoesNotExist:
            logger.warning(f"Login attempt for non-existent user: {email}")
            return Response({"error":"User Does Not Found"}, status=status.HTTP_404_NOT_FOUND)
        if serializer.is_valid():
            user = serializer.validated_data["user"]

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)
            subscribed = False
            plan_details = None
            categories = None
            try:
                tutor_details = TutorDetails.objects.get(account=user)
            except ObjectDoesNotExist:
                logger.warning("TutorDetails not found for user.")
                tutor_details = None

            if tutor_details:
                try:
                    subscription = TutorSubscription.objects.get(tutor=tutor_details)
                    subscribed = subscription.is_active
                    plan = subscription.plan
                    categories_list = CourseCategory.objects.filter(is_active=True)
                    categories = CourseCategorySerializer(categories_list, many=True).data
                    if plan:
                        plan_details = {
                            "name":plan.name,
                            "plan_type":plan.plan_type,
                            "plan_category":plan.plan_category,
                            "price":plan.price,
                            "is_active":plan.is_active,
                            "expires_on":subscription.expires_on,
                            "subscribed_on":subscription.subscribed_on,
                        }
                    else:
                        logger.warning("No plan associated with the subscription.")
                except ObjectDoesNotExist:
                    logger.warning("Subscription not found for tutor.")
                    subscribed = False
                    plan_details = None

                except Exception as e:
                    logger.error(f"Unexpected error fetching subscription or plan: {e}")
            

            response = Response(
                {
                    "message": "Login successful",
                    "user": {
                        'id': user.id,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'email': user.email,
                        'phone': user.phone,
                        'role': user.role,
                        'subscribed':subscribed,
                        'streak':user.streak,
                        'is_superuser': user.is_superuser,
                        'plan_details':plan_details,
                        'categories':categories,
                    },
                      
                },
                status=status.HTTP_200_OK,
            )

            response.set_cookie(
                key="access_token",
                value=access_token,
                httponly=True,
                secure=True,
                samesite="None",
                max_age=1800  # 30 minutes
            )

            response.set_cookie(
                key="refresh_token",
                value=refresh_token,
                httponly=True,
                secure=True,
                samesite="None",
                max_age=90000  # 1 day and 30 minutes
            )

            return response

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token")

        if not token:
            return Response({"error": "Token not provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            id_info = id_token.verify_oauth2_token(token, google_requests.Request())

            email = id_info.get("email")
            first_name = id_info.get("given_name", "")
            last_name = id_info.get("family_name", "")
            picture = id_info.get("picture", "")

        except ValueError as e:
            error_message = str(e)
            return Response({"error": f"Invalid Google token: {error_message}"}, status=status.HTTP_406_NOT_ACCEPTABLE)
        except Exception as e:
        
            return Response({"error": f"An unexpected error occurred during Google login"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        user, created = Accounts.objects.get_or_create(email=email, defaults={
            "first_name": first_name,
            "last_name": last_name,
        })

        if created:
            user.set_unusable_password()
            user.is_active = True
            user.google_verified = True
            user.profile_picture = picture
            user.save()


        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        subscribed = False
        plan_details = None
        categories = None

        try:
            tutor_details = TutorDetails.objects.get(account=user)
            subscription = TutorSubscription.objects.get(tutor=tutor_details)
            subscribed = subscription.is_active
            plan = subscription.plan
            categories_list = CourseCategory.objects.filter(is_active=True)
            categories = CourseCategorySerializer(categories_list, many=True).data

            if plan:
                plan_details = {
                    "name": plan.name,
                    "plan_type": plan.plan_type,
                    "plan_category": plan.plan_category,
                    "price": plan.price,
                    "is_active": plan.is_active,
                    "expires_on": subscription.expires_on,
                    "subscribed_on": subscription.subscribed_on,
                }
        except ObjectDoesNotExist:
            pass


        response = Response({
            "message": "Google login successful",
            "user": {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'phone': user.phone,
                'role': user.role,
                'subscribed': subscribed,
                'streak': user.streak,
                'is_superuser': user.is_superuser,
                'plan_details': plan_details,
                'categories': categories
            },
        }, status=status.HTTP_200_OK)

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="None",
            max_age=1800
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="None",
            max_age=90000
        )

        return response



class CustomTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response({"error": "Refresh token missing"}, status=status.HTTP_401_UNAUTHORIZED)

        # ✅ Manually add refresh token to request data
        request.data["refresh"] = refresh_token
        
        # Call parent post method
        response = super().post(request, *args, **kwargs)

        if "access" in response.data:
            response.set_cookie(
                key="access_token",
                value=response.data["access"],
                httponly=True,
                secure=True,
                samesite="None",
                max_age=1800,  # 30 minutes
            )
            
        else:
            return Response({"error": "Invalid refresh token"}, status=status.HTTP_401_UNAUTHORIZED)

        return response



class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception as e:
                logger.error(f"Token blacklisting error: {e}")

        response = Response({"message": "Logout successful"}, status=status.HTTP_200_OK)

        # ✅ Set access_token and refresh_token to empty strings
        response.set_cookie(
            key="access_token",
            value="",
            httponly=True,
            secure=True,
            samesite="None",
            expires=0  # Expire immediately
        )
        response.set_cookie(
            key="refresh_token",
            value="",
            httponly=True,
            secure=True,
            samesite="None",
            expires=0  # Expire immediately
        )

        return response



class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, email):
        try:
            user = get_object_or_404(Accounts, email=email)
            token = PasswordResetTokenGenerator().make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            reset_url = f"http://localhost:3000/reset-password/{uid}/{token}/"

            subject = "Reset your password"
            from_email = "codexlearninginfo@gmail.com"
            to_email = user.email

            text_content = f"Click the link to reset your password: {reset_url}"
            html_content = f"""
                <html>
                    <body style="font-family: Arial, sans-serif; text-align: center; padding: 20px;">
                        <h2>Reset Your Password</h2>
                        <p>Click the button below to reset your password:</p>
                        <a href="{reset_url}" style="
                            display: inline-block;
                            padding: 10px 20px;
                            margin-top: 10px;
                            background-color: #4CAF50;
                            color: white;
                            text-decoration: none;
                            border-radius: 5px;
                        ">Reset Password</a>
                        <p>If you didn’t request this, please ignore this email.</p>
                    </body>
                </html>
            """

            email_message = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
            email_message.attach_alternative(html_content, "text/html")
            email_message.send()

            return Response({"message": "Reset link sent"}, status=200)

        except Accounts.DoesNotExist:
            return Response({"error": "User not found"}, status=404)



class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, uidb64, token):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = Accounts.objects.get(pk=uid)

            if not PasswordResetTokenGenerator().check_token(user, token):
                return Response({"error": "Invalid or expired token"}, status=400)

            new_password = request.data.get("password")
            user.password = make_password(new_password)
            user.save()
            
            subject = "✅ Password Updated Successfully"
            message = (
                f"Hello {user.first_name},\n\n"
                f"Your password for CodeX Learning was successfully reset.\n\n"
                f"You can now log in using your new password.\n\n"
                f"**Security Alert:** If you did NOT change your password, please contact CodeX Learning support immediately.\n\n"
                f"The CodeX Learning Team"
            )
            from_email = os.getenv("EMAIL_HOST_USER")
            recipient_list = [user.email]
            
            send_mail(subject, message, from_email, recipient_list)

            return Response({"message": "Password reset successful"}, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=400)



class UserDashboardView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def get(self, request):
        user = request.user
        logger.debug(f"User: {user.id} {user.email}")

        # ======== Basic Stats ========
        active_courses = UserCourseEnrollment.objects.filter(user=user, status='progress').count()
        completed_courses = UserCourseEnrollment.objects.filter(user=user, status='completed').count()
        logger.debug(f"Active Courses: {active_courses}")
        logger.debug(f"Completed Courses: {completed_courses}")

        achievements = 0  
        day_streak = 0   

        # ======== Current Active Course ========
        current_enrollment = (
            UserCourseEnrollment.objects
            .filter(user=user, status='progress')
            .select_related('course')
            .first()
        )
        logger.debug(f"Current Enrollment: {current_enrollment}")

        current_course_data = None
        if current_enrollment:
            course = current_enrollment.course
            logger.debug(f"Current Course: {course.title} {course.id}")

            # Debugging module & lesson queries
            total_modules = ModuleProgress.objects.filter(module__course=course, user=user).count()
            total_lessons = LessonProgress.objects.filter(lesson__module__course=course, user=user).count()
            logger.debug(f"Total Modules: {total_modules}")
            logger.debug(f"Total Lessons: {total_lessons}")

            completed_modules = ModuleProgress.objects.filter(module__course=course, user=user, status='completed').count()
            completed_lessons = LessonProgress.objects.filter(lesson__module__course=course, user=user, status='completed').count()
            logger.debug(f"Completed Modules: {completed_modules}")
            logger.debug(f"Completed Lessons: {completed_lessons}")

            current_course_data = {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "level": course.level,
                "progress": float(current_enrollment.progress),
                "status": current_enrollment.status,
                "last_accessed": current_enrollment.enrolled_on,
                "modules_total": total_modules,
                "modules_completed": completed_modules,
                "lessons_total": total_lessons,
                "lessons_completed": completed_lessons
            }
        else:
            logger.warning("No current active course found for user")

        # ======== All Completed Courses ========
        completed_enrollments = (
            UserCourseEnrollment.objects
            .filter(user=user, status='completed')
            .select_related('course')
            .order_by('-completed_at')
        )
        logger.debug(f"Completed Enrollments: {completed_enrollments.count()}")

        completed_courses_list = []
        for enrollment in completed_enrollments:
            course = enrollment.course
            completed_courses_list.append({
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "completed_on": enrollment.completed_at,
            })

        # ======== Final Response ========
        # Backward compatibility: also expose the first completed course as completed_course
        first_completed = completed_courses_list[0] if completed_courses_list else None

        response = {
            "stats": {
                "active_courses": active_courses,
                "completed_courses": completed_courses,
                "achievements": achievements,
                "day_streak": day_streak
            },
            "current_course": current_course_data,
            "completed_courses": completed_courses_list,
            "completed_course": first_completed
        }

        logger.debug(f"Final Response: {response}")
        return Response(response, status=status.HTTP_200_OK)



class UserProfileView(APIView):
    
    permission_classes = [IsAuthenticatedUser]

    def get(self, request):
        user = request.user
        userData = {
            "first_name":user.first_name,
            "last_name":user.last_name,
            "email":user.email,
            "phone":user.phone,
            "streak":user.streak,
            "last_completed":user.last_completed_task,
            "profile_picture": user.profile_picture
        }
        logger.debug(f"User data retrieved for user {user.id}")
        return Response(userData, status=status.HTTP_200_OK)



class EditUserView(APIView):
    
    permission_classes = [IsAuthenticatedUser]
    
    def put(self, request):
        user = request.user
        serializer = EditUserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()

            data = {
                "first_name":user.first_name,
                "last_name":user.last_name,
                "email":user.email,
                "phone":user.phone,
                "streak":user.streak,
                "last_completed":user.last_completed_task,
                "profile_picture": user.profile_picture
            }
            
            return Response(data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class UploadUserProfilePictureView(APIView):
    permission_classes = [IsAuthenticatedUser]
    def post(self, request):
        try:
            user = request.user  # Already authenticated user
            profile_picture = request.FILES.get("profilePicture")

            if not profile_picture:
                return Response({"error": "No profilePicture provided"}, status=status.HTTP_400_BAD_REQUEST)
            
            upload_result = cloudinary.uploader.upload(
                profile_picture,
                folder="profile_picture",
                resource_type="image"
            )
            profile_picture_url = upload_result.get('secure_url')

            user.profile_picture = profile_picture_url
            user.save()

            return Response(profile_picture_url, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Profile Upload"})



class TutorHomeView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def get(self, request):
        try:
            user = request.user

            # Defaults
            subscribed = False
            plan_details = None
            categories = CourseCategorySerializer(
                CourseCategory.objects.filter(is_active=True), 
                many=True
            ).data

            # Check TutorDetails
            try:
                tutor_details = TutorDetails.objects.get(account=user)
            except TutorDetails.DoesNotExist:
                tutor_details = None

            # If tutor exists, load subscription details
            if tutor_details:
                try:
                    subscription = TutorSubscription.objects.get(tutor=tutor_details)
                    subscribed = subscription.is_active
                    plan = subscription.plan

                    if plan:
                        plan_details = {
                            "name": plan.name,
                            "plan_type": plan.plan_type,
                            "plan_category": plan.plan_category,
                            "price": plan.price,
                            "status": tutor_details.status,
                            "is_active": plan.is_active,
                            "expires_on": subscription.expires_on,
                            "subscribed_on": subscription.subscribed_on,
                        }
                except TutorSubscription.DoesNotExist:
                    pass  # No subscription for tutor

            # Always return user object
            return Response({
                "message": "Success",
                "user": {
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'phone': user.phone,
                    'role': user.role,
                    'subscribed': subscribed,
                    'streak': user.streak,
                    'is_superuser': user.is_superuser,
                    'plan_details': plan_details,
                    'categories': categories,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"TutorHome Error: {e}")
            return Response({"error": "Error Fetching Tutor Data"}, status=status.HTTP_400_BAD_REQUEST)



class ListCourseView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            search_query = request.GET.get('search', '').strip()
            
            course_requests = Course.objects.filter(is_active=True, is_draft=False)
            
            if search_query:
                from django.db.models import Q
                course_requests = course_requests.filter(
                    Q(title__icontains=search_query) |
                    Q(description__icontains=search_query) |
                    Q(category_id__name__icontains=search_query) |
                    Q(created_by__full_name__icontains=search_query) |
                    Q(level__icontains=search_query)
                )
            
            data = []
            for course in course_requests:
                data.append({
                    "id": course.id,
                    "name": course.name,
                    "created_by": course.created_by.full_name,
                    "category": course.category_id.name if course.category_id else None,
                    "category_id": course.category_id.id if course.category_id else None,
                    "title": course.title,
                    "description": course.description,
                    "requirements": course.requirements,
                    "benefits": course.benefits,
                    "price": course.price,
                    "created_at": course.created_at,
                    "is_active": course.is_active,
                    "level": course.level
                })

            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "Error While Fetching Course Request"}, status=status.HTTP_400_BAD_REQUEST)



class ListCategoriesView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):
        try:
            categories = CourseCategory.objects.filter(is_active=True)
            serializer = CourseCategorySerializer(categories, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return Response({"error": "Error while fetching categories"}, status=status.HTTP_400_BAD_REQUEST)



class CheckUserEnrollmentView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        user_email = request.query_params.get('user_email')
        course_id = request.query_params.get('course_id')

        if not user_email or not course_id:
            return Response({"error": "Missing parameters"}, status=status.HTTP_400_BAD_REQUEST)

        is_enrolled = UserCourseEnrollment.objects.filter(
            user__email=user_email,
            course_id=course_id
        ).exists()

        return Response({"enrolled": is_enrolled}, status=status.HTTP_200_OK)



class CheckCourseTutor(APIView):
    
    permission_classes = [AllowAny]
    
    def get(self, request, course_id):
        try:
            try:
                tutor = TutorDetails.objects.get(account=request.user)
            except:
                return Response({"is_tutor":False}, status=status.HTTP_200_OK)
        
            is_tutor = Course.objects.filter(created_by=tutor, id=course_id).exists()
            
            return Response({"is_tutor": is_tutor}, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error":"Error while checking tutor course"}, status=status.HTTP_400_BAD_REQUEST)
 
        

class CourseDetailsView(APIView):

    permission_classes = [AllowAny]


    def get(self, request, id):
        try:

            course = Course.objects.get(id=id)

            if not course:
                return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)


            modules = Modules.objects.filter(course=course)
            lessons = Lessons.objects.filter(module__in=modules)


            module_data = []
            if modules or lessons:
                for module in modules:
                    module_lessons = [
                        {
                            "id": lesson.id,
                            "title": lesson.title,
                            "description": lesson.description,
                            "documents": lesson.documents,
                            "video": lesson.video,
                            "thumbnail": lesson.thumbnail,
                            "created_at": lesson.created_at.strftime("%Y-%m-%d"),
                        }
                        for lesson in lessons if lesson.module_id == module.id
                    ]
                    module_data.append({
                        "id": module.id,
                        "title": module.title,
                        "description": module.description,
                        "created_at": module.created_at.strftime("%Y-%m-%d"),
                        "lessons": module_lessons
                    })
                
            tutor_details = TutorDetails.objects.get(id=course.created_by.id)
            tutor = Accounts.objects.get(id=tutor_details.account.id)

            data = {
                "id": course.id,
                "name": course.name,
                "tutor_id":tutor.id,
                "first_name": tutor.first_name,
                "last_name":tutor.last_name,
                "profile_picture":tutor_details.profile_picture,
                "category": course.category_id.name if course.category_id else None,
                "category_id": course.category_id.id if course.category_id else None,
                "title": course.title,
                "description": course.description,
                "requirements": course.requirements,
                "benefits": course.benefits,
                "price": str(course.price),
                "created_at": course.created_at.strftime("%Y-%m-%d"),
                "is_active": course.is_active,
                "level": course.level,
                "status": course.status,
                "module_data": module_data
            }

            return Response(data, status=status.HTTP_200_OK)

        except Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error while fetching course details: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)



class CreateCheckoutSessionView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def post(self, request, plan_id):
        plan = get_object_or_404(Plan, id=plan_id)
        domain = "http://localhost:3000"

        if request.user.role != "tutor":
            return Response({"detail": "Only tutors can subscribe."}, status=403)

        if not plan.stripe_price_id:
            return Response({"detail": "Plan does not have a Stripe Price ID."}, status=400)

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                mode='subscription',
                line_items=[{
                    'price': plan.stripe_price_id,
                    'quantity': 1,
                }],
                success_url=f'{domain}/success?session_id={{CHECKOUT_SESSION_ID}}',
                cancel_url=f'{domain}/cancel',
                customer_email=request.user.email,
                client_reference_id=str(request.user.id),
                metadata={
                    "plan_id": str(plan.id),
                    "tutor_email": request.user.email,
                },
            )

            logger.info(f"Stripe Session created successfully. Session ID: {session.id}, client_reference_id: {request.user.id}, metadata: {{'plan_id': {plan.id}}}")

            return Response({'checkout_url': session.url}, status=200)

        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            return Response({'detail': str(e)}, status=400)



class StripeSuccessView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        session_id = request.GET.get('session_id')
        redirect_url = request.GET.get('redirect', 'http://localhost:3000/success')
        
        if not session_id:
            return Response({"error": "No session ID provided"}, status=400)
        
        try:
            # Retrieve the checkout session from Stripe
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Extract data from the session
            tutor_id = session.get('client_reference_id')
            metadata = session.get('metadata') or {}
            plan_id = metadata.get('plan_id')
            customer_id = session.get('customer')
            subscription_id = session.get('subscription')
            
            logger.info(f"Success page accessed with session_id={session_id}, tutor_id={tutor_id}, plan_id={plan_id}")
            
            try:
                # Get the objects
                plan = Plan.objects.get(id=plan_id)
                account = Accounts.objects.get(id=tutor_id)
                tutor = TutorDetails.objects.get(account=account)
                
                # Calculate expiration date
                if plan.plan_type == 'MONTHLY':
                    expires_on = now() + timedelta(days=30)
                elif plan.plan_type == 'YEARLY':
                    expires_on = now() + timedelta(days=365)
                else:
                    expires_on = now()
                
                # Create or update subscription
                subscription, created = TutorSubscription.objects.update_or_create(
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
                
                logger.info(f"Subscription {'created' if created else 'updated'}: {subscription}")
                
                # Redirect to frontend success page
                return redirect(redirect_url)
                
            except Exception as e:
                logger.error(f"Error creating subscription: {e}")
                import traceback
                traceback.print_exc()
                # Still redirect even on error
                return redirect(f"{redirect_url}?error={str(e)}")
                
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e}")
            return redirect(f"{redirect_url}?error=Invalid session")



class TutorDetailsView(APIView):

    permission_classes = [AllowAny]


    def get(self, requests, id):
        try:
            try:
                tutor = Accounts.objects.get(id=id, role='tutor')
            except Accounts.DoesNotExist:
                return Response({"error":"Tutor Does Not Found"}, status=status.HTTP_404_NOT_FOUND)
            try:
                tutor_details = TutorDetails.objects.get(account=tutor)
            except TutorDetails.DoesNotExist:
                return Response({"error":"Tutor Details Does Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            course_requests = Course.objects.filter(created_by=tutor_details, is_active=True)
            tutor_data = TutorDetailsSerializer(tutor_details).data
            age = tutor_details.get_age()
            tutor_data.update({"age":age})
            tutor_data.update({"email":tutor_details.account.email})
            courses = []

            for reqeusts in course_requests:
                courses.append({
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
                    "level":reqeusts.level
                })
                

            return Response({"tutor":tutor_data, "courses":courses}, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Fetching Course Request"}, status=status.HTTP_400_BAD_REQUEST)
        


class PaymentVerificationView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def post(self, request):
        try:
            user_email = request.data.get("user_email")
            course_id = request.data.get("course_id")

            try:
                user = Accounts.objects.get(email=user_email)
            except Accounts.DoesNotExist:
                return Response({"error":"User Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)
            
            try:
                course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                return Response({"error":"Course Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)
            
            if TutorDetails.objects.filter(account=user).exists():
                return Response({"error": "Tutor Cannot Buy Their Own Course"}, status=status.HTTP_400_BAD_REQUEST)

            if UserCourseEnrollment.objects.filter(user=user, course=course).exists():
                return Response({"error": "User already enrolled in this course"}, status=status.HTTP_400_BAD_REQUEST)


            if user.isblocked:
                return Response({"error":"User Account Has Been Blocked Contact Support"}, status=status.HTTP_404_NOT_FOUND)
            
            if not course.is_active:
                return Response({"error":"Course Has Been Blocked Cannot Complete Payment"}, status=status.HTTP_404_NOT_FOUND)


            return Response({"message":"Verification Successfull"}, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class PayPalSuccessView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def post(self, request):
        try:
            logger.info("PayPalSuccessView triggered")

            user_email = request.data.get("user_email")
            course_id = request.data.get("course_id")
            order_id = request.data.get("orderID")

            logger.info(f"Incoming Payload --> user_email={user_email}, course_id={course_id}, order_id={order_id}")

            if not user_email or not course_id or not order_id:
                logger.warning("Missing required fields in PayPalSuccessView request")
                return Response(
                    {"error": "Missing required fields"},
                    status=status.HTTP_400_BAD_REQUEST,
                )


            logger.info("Attempting PayPal OAuth authentication")

            auth_response = requests.post(
                settings.PAYPAL_OAUTH_URL,
                data={"grant_type": "client_credentials"},
                auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET_KEY),
            )

            logger.info(f"PayPal Auth Response Code: {auth_response.status_code}")

            if auth_response.status_code != 200:
                logger.error(f"PayPal authentication failed: {auth_response.text}")
                return Response({"error": "PayPal authentication failed"}, status=400)

            access_token = auth_response.json().get("access_token")


            logger.info(f"Fetching PayPal order details for order_id={order_id}")

            order_response = requests.get(
                f"{settings.PAYPAL_ORDER_URL}{order_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )

            logger.info(f"Order Verification Status Code: {order_response.status_code}")

            if order_response.status_code != 200:
                logger.error(f"Failed to fetch PayPal order details: {order_response.text}")
                return Response({"error": "Failed to fetch order details"}, status=400)

            order_data = order_response.json()
            logger.debug(f"PayPal Order Response JSON: {order_data}")

            if order_data.get("status") != "COMPLETED":
                logger.warning(f"Order {order_id} is not completed. Status: {order_data.get('status')}")
                return Response({"error": "Payment not completed"}, status=400)

            purchase_unit = order_data["purchase_units"][0]


            paypal_reference_id = purchase_unit.get("reference_id")
            paypal_custom_id = purchase_unit.get("custom_id")
            paypal_amount = float(purchase_unit["amount"]["value"])

            logger.info(
                f"Extracted PayPal Metadata --> reference_id={paypal_reference_id}, "
                f"custom_id={paypal_custom_id}, amount={paypal_amount}"
            )

            try:
                user = Accounts.objects.get(email=user_email)
                logger.info(f"User validated: {user.email}")
            except Accounts.DoesNotExist:
                logger.error(f"User does not exist: {user_email}")
                return Response({"error": "User does not exist"}, status=404)

            try:
                course = Course.objects.get(id=course_id)
                logger.info(f"Course validated: {course.title}")
            except Course.DoesNotExist:
                logger.error(f"Course does not exist: {course_id}")
                return Response({"error": "Course does not exist"}, status=404)

            if user.isblocked:
                logger.warning(f"Blocked user attempted purchase: {user.email}")
                return Response({"error": "User account is blocked"}, status=403)

            if not course.is_active:
                logger.warning(f"Inactive course purchase attempt: {course.title}")
                return Response({"error": "Course is inactive"}, status=400)


            logger.info("Performing security validation checks")

            if paypal_reference_id != f"COURSE_{course_id}":
                logger.error("Reference ID mismatch --> Possible tampering attempt")
                return Response(
                    {"error": "Payment does not match this course (ref mismatch)"},
                    status=400,
                )

            if str(paypal_custom_id) != str(course_id):
                logger.error("Custom ID mismatch --> Possible fraudulent payload")
                return Response(
                    {"error": "Invalid purchase attempt (custom_id mismatch)"},
                    status=400,
                )

            if paypal_amount != float(course.price):
                logger.error(f"Amount mismatch --> PayPal: {paypal_amount}, Course: {course.price}")
                return Response({"error": "Payment amount mismatch"}, status=400)

            if UserCourseEnrollment.objects.filter(user=user, course=course).exists():
                logger.info(f"Duplicate purchase attempt — user already enrolled: {user.email}")
                return Response({"message": "Course already purchased"}, status=200)


            UserCourseEnrollment.objects.create(
                user=user,
                course=course,
                payment_id=order_id,
            )

            tutor_amount = course.price * Decimal("0.70")
            platform_amount = course.price * Decimal("0.30")

            tutor_wallet, created = Wallet.objects.get_or_create(
                tutor=course.created_by,
                defaults={"balance": tutor_amount}
            )


            if not created:
                tutor_wallet.balance += tutor_amount
                tutor_wallet.save()

            WalletTransaction.objects.create(
                wallet=tutor_wallet,
                amount=tutor_amount,
                description=f"{course.title} purchased by {user.first_name} {user.last_name}"
            )
            
            platform_wallet, _ = PlatformWallet.objects.get_or_create(pk=1)

            platform_wallet.total_revenue += platform_amount
            platform_wallet.save()
            
            PlatformWalletTransaction.objects.create(
                wallet=platform_wallet,
                amount=platform_amount,
                transaction_type="COURSE_PURCHASE",
                user=user,
                tutor=course.created_by,
            )

            logger.info(f"Course enrollment successful --> user={user.email}, course={course.title}")

            return Response(
                {"message": "Course purchased successfully!"},
                status=200,
            )

        except Exception as e:
            logger.exception(f"Unhandled PayPal Success Error: {str(e)}")
            return Response({"error": "Internal Server Error"}, status=500)



class EnrolledCoursesView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def get(self, request):
        enrollments = UserCourseEnrollment.objects.filter(user=request.user)
        
        response_data = []

        if not enrollments.exists():
            logger.debug(f"No enrollments found for user {request.user.id}")
            return Response([], status=status.HTTP_200_OK)

        for enrollment in enrollments:
            course = enrollment.course
            user = enrollment.user

            total_modules = course.modules_set.count()
            
            completed_modules = ModuleProgress.objects.filter(
                user=user,
                module__course=course,
                status='completed'
            ).count()

            progress = round((completed_modules / total_modules) * 100, 2) if total_modules > 0 else 0.0

            enrollment.progress = progress

            if completed_modules == total_modules and total_modules > 0 and enrollment.status != 'completed':
                enrollment.status = 'completed'
                enrollment.completed_at = now()
            
            enrollment.save()

            enrollment_data = {
                "id": enrollment.id,
                "status": enrollment.status,
                "progress": progress,
                "completed_on": enrollment.enrolled_on if enrollment.status == 'completed' else None,
                "enrolled_on":enrollment.enrolled_on,
                "course": {
                    "id": course.id,
                    "title": course.title,
                    "description": course.description,
                    "level": course.level,
                    "price": str(course.price),
                    "category": course.category_id.name if course.category_id else None,
                }
            }
            response_data.append(enrollment_data)

        logger.debug(f"Returning {len(response_data)} enrollments for user {request.user.id}")
        return Response(response_data)
        


class StartCourseView(APIView):

    permission_classes = [IsAuthenticatedUser]

    def post(self, request, id):
        try:
            enrolled_course = UserCourseEnrollment.objects.get(course=id, user=request.user)
        except UserCourseEnrollment.DoesNotExist:
            logger.warning(f"Course enrollment not found for course {id} and user {request.user.id}")
            return Response({"error":"Course Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)
        
        enrolled_course.status = "progress"
        enrolled_course.save()
        logger.info(f"Course {id} started for user {request.user.id}")
        return Response({"message":"Course Started Successfully"}, status=status.HTTP_200_OK)



class StartedCourseDetailsView(APIView):
    
    permission_classes = [IsAuthenticatedUser]
    
    def get(self, request, id):
        try:
            course = Course.objects.get(id=id)
            if not course:
                return Response({"error":"Course Not Found"}, status=status.HTTP_404_NOT_FOUND)
            return Response(CourseListSerializer(course).data, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Fetching Course Details"}, status=status.HTTP_400_BAD_REQUEST)



class CourseTutorView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def get(self, request, id):
        try:
            course = Course.objects.get(id=id)
        except Course.DoesNotExist:
            logger.warning(f"Course {id} not found")
            return Response({"error": "Course not found."}, status=status.HTTP_404_NOT_FOUND)

        if not course.created_by:
            logger.warning(f"Course {id} does not have an associated tutor")
            return Response({"error": "This course does not have an associated tutor."}, status=status.HTTP_404_NOT_FOUND)

        tutor_account_id = course.created_by.id
        logger.debug(f"Tutor account ID {tutor_account_id} for course {id}")
        return Response(tutor_account_id, status=status.HTTP_200_OK)



class StartedCourseModulesView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def get(self, request):
        user = request.user
        course_id = request.GET.get("course_id")
        
        if not course_id:
            logger.warning("course_id is required")
            return Response({"error":"course_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            logger.warning(f"Course {course_id} not found")
            return Response({"error":"Course Not Found"}, status=status.HTTP_404_NOT_FOUND)
        
        modules = Modules.objects.filter(course=course, is_active=True)
        logger.debug(f"Found {modules.count()} modules for course {course_id}")
        
        data = []

        for module in modules:
            lessons = Lessons.objects.filter(module=module, is_active=True)
            total_lessons = lessons.count()
            completed_lessons = LessonProgress.objects.filter(user=user, lesson__in=lessons, completed=True).count()
            progress = (completed_lessons / total_lessons) * 100 if total_lessons > 0 else 0

            # Get or create module progress entry
            module_progress, created = ModuleProgress.objects.get_or_create(user=user, module=module)

        
            data.append({
                "modules": {
                    "id": module.id,
                    "title": module.title,
                    "description": module.description
                },
                "started_at":module_progress.started_at,
                "status": module_progress.status,
                "progress": round(progress, 2),
                "completed_on": module_progress.completed_at.date() if module_progress.completed_at else None
            })

        return Response(data, status=200)



class StartModuleView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def post(self, request):
        module_id = request.data.get("module_id")
        
        try:
            module = Modules.objects.get(id=module_id)
        except Modules.DoesNotExist:
            logger.warning(f"Module {module_id} not found")
            return Response({"error": "Module does not exist."}, status=status.HTTP_404_NOT_FOUND)

        course = module.course
        user = request.user

        # Ensure user is enrolled in the course
        try:
            enrollment = UserCourseEnrollment.objects.get(user=user, course=course)
        except UserCourseEnrollment.DoesNotExist:
            logger.warning(f"User {user.id} not enrolled in course {course.id}")
            return Response({"error": "You are not enrolled in this course."}, status=status.HTTP_400_BAD_REQUEST)

        if enrollment.status == "pending":
            enrollment.status = "progress"
            enrollment.save()

        # Check for existing progress in this course
        existing_progress = ModuleProgress.objects.filter(
            user=user,
            module__course=course,
            status="progress"
        ).exclude(module__id=module_id).first()

        if existing_progress:
            logger.warning(f"User {user.id} already has module {existing_progress.module.id} in progress")
            return Response(
                {"error": "You already have a module in progress."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create ModuleProgress
        progress_obj, created = ModuleProgress.objects.get_or_create(
            user=user,
            module=module
        )

        if progress_obj.status == "completed":
            logger.info(f"Module {module_id} already completed for user {user.id}")
            return Response(
                {"message": "This module is already completed."},
                status=status.HTTP_200_OK
            )

        progress_obj.status = "progress"
        progress_obj.started_at = timezone.now()
        progress_obj.save()

        logger.info(f"Module {module_id} started for user {user.id}")
        return Response({"message": "Module started successfully."}, status=status.HTTP_200_OK)



class StartedModuleDetailsView(APIView):
    
    permission_classes = [IsAuthenticatedUser]
    
    def get(self, request, id):
        try:
            module = Modules.objects.get(id=id)
        except Modules.DoesNotExist:
            logger.warning(f"Module {id} not found")
            return Response({"error":"module Not Found"}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            serializer = CourseModuleSerializer(module)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error serializing module {id}")
            return Response({"error":"Error While Fetching module Details"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class StartedModuleLessonsView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def get(self, request):
        user = request.user
        
        module_id = request.GET.get("module_id")
        if not module_id:
            logger.warning("module_id is required")
            return Response({"error": "module_id is required"}, status=400)

        try:
            module = Modules.objects.get(id=module_id, is_active=True)
        except Modules.DoesNotExist:
            logger.warning(f"Module {module_id} not found or inactive")
            return Response({"error": "Module not found"}, status=status.HTTP_404_NOT_FOUND)

        lessons = Lessons.objects.filter(module=module, is_active=True)

        total_lessons = lessons.count()
        completed_lessons = LessonProgress.objects.filter(
            user=user, lesson__in=lessons, completed=True
        ).count()
        progress = (completed_lessons / total_lessons) * 100 if total_lessons > 0 else 0

        # Ensure module progress exists
        ModuleProgress.objects.get_or_create(user=user, module=module)

        data = []

        for lesson in lessons:
            lesson_progress, _ = LessonProgress.objects.get_or_create(user=user, lesson=lesson)
            
            
            data.append({
                "lesson": {
                    "id": lesson.id,
                    "title": lesson.title,
                    "description": lesson.description,
                    "video": lesson.video,
                    "documents": lesson.documents,
                    "thumbnail": lesson.thumbnail
                },
                "started_at":lesson_progress.started_at,
                "status": lesson_progress.status,
                "progress": progress,
                "completed_on": lesson_progress.completed_at.date() if lesson_progress.completed_at else None
                
            })

        logger.debug(f"Returning {len(data)} lessons for module {module_id}")
        return Response(data, status=200)
    
    

class StartLessonView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def post(self, request):
        try:
            user = request.user
            lesson_id = request.data.get("lesson_id")

            if not lesson_id:
                return Response({"error": "lesson_id is required"}, status=400)

            lesson = Lessons.objects.get(id=lesson_id)

            # Check if any other lesson is in progress
            existing_progress = LessonProgress.objects.filter(user=user, status='progress').exclude(lesson=lesson).first()
            if existing_progress:
                return Response({
                    "error": "Another lesson is already in progress. Please complete it first.",
                    "current_lesson_id": existing_progress.lesson.id
                }, status=400)

            # Get or create the current lesson progress
            progress, created = LessonProgress.objects.get_or_create(user=user, lesson=lesson)
            progress.status = 'progress'
            progress.started_at = now()
            progress.save()

            return Response({"message": "Lesson started successfully."}, status=200)
        except Lessons.DoesNotExist:
            return Response({"error": "Lesson not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        
        

class StartedLessonDetailsView(APIView):
    
    permission_classes = [IsAuthenticatedUser]
    
    def get(self, request, id):
        try:
            lesson = Lessons.objects.get(id=id)
            if not lesson:
                return Response({"error":"lesson Not Found"}, status=status.HTTP_404_NOT_FOUND)
            return Response(CourseLessonSerializer(lesson).data, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Fetching lesson Details"}, status=status.HTTP_400_BAD_REQUEST)
        


class CompleteLessonView(APIView):

    permission_classes = [IsAuthenticatedUser]

    def post(self, request):
        try:
            user = request.user
            lesson_id = request.data.get("lesson_id")

            if not lesson_id:
                return Response({"error": "lesson_id is required"}, status=400)

            lesson = Lessons.objects.get(id=lesson_id)

            progress, _ = LessonProgress.objects.get_or_create(user=user, lesson=lesson)

            if progress.status == 'completed':
                return Response({
                    "error": "Lesson is already completed.",
                    "current_lesson_id": progress.lesson.id
                }, status=400)

            progress.status = 'completed'
            progress.completed = True
            progress.completed_at = now()
            progress.save()

            module = lesson.module  

            module_lessons = Lessons.objects.filter(module=module)
            user_progresses = LessonProgress.objects.filter(user=user, lesson__in=module_lessons)

            all_completed = all(p.status == 'completed' for p in user_progresses)

            if all_completed:
                module_progress, _ = ModuleProgress.objects.get_or_create(user=user, module=module)
                module_progress.status = 'completed'
                module_progress.completed_at = now()
                module_progress.save()

            course = module.course

            total_modules = Modules.objects.filter(course=course, is_active=True).count()
            completed_modules = ModuleProgress.objects.filter(
                user=user,
                module__course=course,
                status='completed'
            ).count()

            course_progress = (completed_modules / total_modules) * 100 if total_modules > 0 else 0

            enrollment = UserCourseEnrollment.objects.get(user=user, course=course)
            enrollment.progress = course_progress

            if course_progress == 100:
                enrollment.status = "completed"
                enrollment.completed_at = now()

            enrollment.save()

            return Response({"message": "Lesson marked as completed."}, status=200)

        except Lessons.DoesNotExist:
            return Response({"error": "Lesson not found"}, status=404)

        except Exception as e:
            return Response({"error": str(e)}, status=500)
        


class GenerateCertificateView(APIView): 
    permission_classes = [IsAuthenticatedUser]

    def get(self, request, course_id):
        try:
            user = request.user
            course = Course.objects.get(id=course_id)

            enrollment = UserCourseEnrollment.objects.filter(
                user=user, course=course, status='completed'
            ).first()

            if not enrollment:
                return Response({"error": "User has not completed the course."}, status=status.HTTP_400_BAD_REQUEST)

            tutor_name = course.created_by.full_name if course.created_by else "Instructor"
            completion_date = enrollment.completed_at.strftime('%B %d, %Y') if enrollment.completed_at else datetime.now().strftime('%B %d, %Y')

            from PIL import Image, ImageDraw, ImageFont
            from io import BytesIO
            import random
            import math
            from datetime import datetime

            # Create high-resolution certificate
            width, height = 2000, 1414
            image = Image.new("RGB", (width, height), color=(255, 255, 255))
            draw = ImageDraw.Draw(image)

            # Fonts - with better fallback handling
            try:
                # Try to use system fonts that are more likely to be available
                heading_font = ImageFont.truetype("Arial Bold", 72)
                subheading_font = ImageFont.truetype("Arial Bold", 48)
                italic_font = ImageFont.truetype("Arial Italic", 42)
                normal_font = ImageFont.truetype("Arial", 36)
                bold_font = ImageFont.truetype("Arial Bold", 42)
                signature_font = ImageFont.truetype("Arial Italic", 48)
                stamp_font = ImageFont.truetype("Arial Bold", 28)
                small_font = ImageFont.truetype("Arial", 24)
                tiny_font = ImageFont.truetype("Arial", 18)
            except:
                # If specific fonts fail, try generic ones
                try:
                    heading_font = ImageFont.truetype("arial.ttf", 72)
                    subheading_font = ImageFont.truetype("arial.ttf", 48)
                    italic_font = ImageFont.truetype("arial.ttf", 42)
                    normal_font = ImageFont.truetype("arial.ttf", 36)
                    bold_font = ImageFont.truetype("arial.ttf", 42)
                    signature_font = ImageFont.truetype("arial.ttf", 48)
                    stamp_font = ImageFont.truetype("arial.ttf", 28)
                    small_font = ImageFont.truetype("arial.ttf", 24)
                    tiny_font = ImageFont.truetype("arial.ttf", 18)
                except:
                    # Final fallback to default font
                    default_font = ImageFont.load_default()
                    heading_font = default_font
                    subheading_font = default_font
                    italic_font = default_font
                    normal_font = default_font
                    bold_font = default_font
                    signature_font = default_font
                    stamp_font = default_font
                    small_font = default_font
                    tiny_font = default_font

            def draw_centered_text(text, y, font, color="black", shadow=False):
                bbox = draw.textbbox((0, 0), text, font=font)
                w = bbox[2] - bbox[0]
                x = (width - w) / 2
                
                if shadow:
                    # Use solid color for shadow instead of rgba which might not be supported
                    draw.text((x+2, y+2), text, fill=(0, 0, 0), font=font)
                
                draw.text((x, y), text, fill=color, font=font)
                return y + bbox[3] - bbox[1] + 10  # Return the y position after this text

            # Create elegant background with subtle pattern
            # Add a light parchment texture - simplified to avoid performance issues
            for i in range(0, width, 20):
                for j in range(0, height, 20):
                    noise = random.randint(245, 255)
                    draw.point((i, j), fill=(noise, noise, noise-5))

            # Elegant border
            margin = 60
            border_width = 6
            
            # Main border
            draw.rectangle([margin, margin, width-margin, height-margin], 
                          outline=(120, 120, 120), width=border_width)
            
            # Inner decorative border
            draw.rectangle([margin+20, margin+20, width-margin-20, height-margin-20], 
                          outline=(0, 100, 0), width=3)
            
            # Ornate corners - simplified
            corner_size = 80
            
            # Top-left corner
            draw.arc([margin+30, margin+30, margin+30+corner_size*2, margin+30+corner_size*2], 
                    180, 270, fill=(0, 120, 0), width=3)
            
            # Top-right corner
            draw.arc([width-margin-30-corner_size*2, margin+30, width-margin-30, margin+30+corner_size*2], 
                    270, 360, fill=(0, 120, 0), width=3)
            
            # Bottom-left corner
            draw.arc([margin+30, height-margin-30-corner_size*2, margin+30+corner_size*2, height-margin-30], 
                    90, 180, fill=(0, 120, 0), width=3)
            
            # Bottom-right corner
            draw.arc([width-margin-30-corner_size*2, height-margin-30-corner_size*2, width-margin-30, height-margin-30], 
                    0, 90, fill=(0, 120, 0), width=3)

            # ENHANCED MEDAL with more detail and dimension
            medal_x, medal_y = 150, 150
            medal_size = 120
            
            # Create a more detailed gold medal with multiple layers and shading
            # Outer rim with gradient effect
            for r in range(medal_size, medal_size-10, -1):
                # Create gold gradient from outer to inner
                gold_shade = 200 + (medal_size - r) * 5
                if gold_shade > 255: gold_shade = 255
                draw.ellipse([medal_x-r, medal_y-r, medal_x+r, medal_y+r], 
                            fill=(gold_shade, int(gold_shade*0.8), 0))
            
            # Main medal body
            draw.ellipse([medal_x-medal_size+10, medal_y-medal_size+10, 
                         medal_x+medal_size-10, medal_y+medal_size-10], 
                        fill=(255, 215, 0))
            
            # Add a decorative ring
            draw.ellipse([medal_x-medal_size+15, medal_y-medal_size+15, 
                         medal_x+medal_size-15, medal_y+medal_size-15], 
                        outline=(212, 175, 55), width=3)
            
            # Inner circle with gradient
            for r in range(int(medal_size*0.7), int(medal_size*0.4), -1):
                gold_shade = 255 - (int(medal_size*0.7) - r) * 2
                if gold_shade < 220: gold_shade = 220
                draw.ellipse([medal_x-r, medal_y-r, medal_x+r, medal_y+r], 
                            fill=(gold_shade, int(gold_shade*0.85), 0))
            
            # Add decorative dots around the medal
            num_dots = 24
            dot_radius = 5
            dot_distance = medal_size - 20
            for i in range(num_dots):
                angle = 2 * math.pi * i / num_dots
                dot_x = medal_x + dot_distance * math.cos(angle)
                dot_y = medal_y + dot_distance * math.sin(angle)
                draw.ellipse([dot_x-dot_radius, dot_y-dot_radius, 
                             dot_x+dot_radius, dot_y+dot_radius], 
                            fill=(212, 175, 55))
            
            # Enhanced star with more points and detail
            star_points = []
            star_size = medal_size * 0.5
            num_points = 16  # More points for a more detailed star
            for i in range(num_points*2):
                angle = math.pi/2 + i * math.pi/num_points
                r = star_size if i % 2 == 0 else star_size * 0.6  # Less dramatic difference for smoother star
                x = medal_x + r * math.cos(angle)
                y = medal_y + r * math.sin(angle)
                star_points.append((x, y))
            
            # Draw star with gradient fill
            draw.polygon(star_points, fill=(255, 223, 0))
            
            # Add highlight to star center
            draw.ellipse([medal_x-star_size*0.2, medal_y-star_size*0.2, 
                         medal_x+star_size*0.2, medal_y+star_size*0.2], 
                        fill=(255, 240, 150))
            
            # Enhanced ribbons with more detail
            # Left ribbon with fold detail
            ribbon_points1 = [
                (medal_x-medal_size*0.3, medal_y+medal_size*0.8),  # Top connection
                (medal_x-medal_size*0.7, medal_y+medal_size*1.5),  # Bottom outer
                (medal_x-medal_size*0.5, medal_y+medal_size*1.3),  # Fold point
                (medal_x-medal_size*0.1, medal_y+medal_size*1.2),  # Bottom inner
            ]
            draw.polygon(ribbon_points1, fill=(180, 0, 0))
            
            # Add highlight to left ribbon
            highlight_points1 = [
                (medal_x-medal_size*0.3, medal_y+medal_size*0.8),
                (medal_x-medal_size*0.6, medal_y+medal_size*1.4),
                (medal_x-medal_size*0.5, medal_y+medal_size*1.3),
            ]
            draw.polygon(highlight_points1, fill=(220, 0, 0))
            
            # Right ribbon with fold detail
            ribbon_points2 = [
                (medal_x+medal_size*0.3, medal_y+medal_size*0.8),  # Top connection
                (medal_x+medal_size*0.7, medal_y+medal_size*1.5),  # Bottom outer
                (medal_x+medal_size*0.5, medal_y+medal_size*1.3),  # Fold point
                (medal_x+medal_size*0.1, medal_y+medal_size*1.2),  # Bottom inner
            ]
            draw.polygon(ribbon_points2, fill=(180, 0, 0))
            
            # Add highlight to right ribbon
            highlight_points2 = [
                (medal_x+medal_size*0.3, medal_y+medal_size*0.8),
                (medal_x+medal_size*0.6, medal_y+medal_size*1.4),
                (medal_x+medal_size*0.5, medal_y+medal_size*1.3),
            ]
            draw.polygon(highlight_points2, fill=(220, 0, 0))

            # Certificate content with improved spacing
            y_pos = 160
            
            # Title with shadow effect
            y_pos = draw_centered_text("Certificate of Achievement", y_pos, heading_font, color=(0, 80, 0), shadow=True)
            
            # Decorative line under title
            line_y = y_pos + 20
            line_width = 500
            draw.line([width/2 - line_width/2, line_y, width/2 + line_width/2, line_y], 
                     fill=(0, 120, 0), width=3)
            
            y_pos = line_y + 60
            y_pos = draw_centered_text("This is to certify that", y_pos, italic_font)
            
            # Student name with prominence
            name_y = y_pos + 30
            student_name = f"{user.first_name} {user.last_name}"
            
            # Name with shadow and highlight
            name_bbox = draw.textbbox((0, 0), student_name, font=heading_font)
            name_width = name_bbox[2] - name_bbox[0]
            name_x = (width - name_width) / 2
            
            # Draw subtle highlight behind name
            highlight_padding = 20
            draw.rectangle([
                name_x - highlight_padding, 
                name_y - highlight_padding/2, 
                name_x + name_width + highlight_padding, 
                name_y + (name_bbox[3] - name_bbox[1]) + highlight_padding/2
            ], fill=(245, 255, 245), outline=None)
            
            # Draw name with shadow
            draw.text((name_x+2, name_y+2), student_name, fill=(0, 0, 0), font=heading_font)
            draw.text((name_x, name_y), student_name, fill=(0, 80, 0), font=heading_font)
            
            y_pos = name_y + (name_bbox[3] - name_bbox[1]) + 50
            y_pos = draw_centered_text("has successfully completed the course", y_pos, italic_font)
            
            # Course title with emphasis
            course_y = y_pos + 30
            course_title = f"\"{course.title}\""
            
            # Course title with decorative elements
            course_bbox = draw.textbbox((0, 0), course_title, font=bold_font)
            course_width = course_bbox[2] - course_bbox[0]
            course_x = (width - course_width) / 2
            
            # Draw subtle highlight behind course title
            highlight_padding = 15
            draw.rectangle([
                course_x - highlight_padding, 
                course_y - highlight_padding/2, 
                course_x + course_width + highlight_padding, 
                course_y + (course_bbox[3] - course_bbox[0]) + highlight_padding/2
            ], fill=(245, 255, 245), outline=None)
            
            # Draw course title with shadow
            draw.text((course_x+2, course_y+2), course_title, fill=(0, 0, 0), font=bold_font)
            draw.text((course_x, course_y), course_title, fill=(0, 100, 0), font=bold_font)
            
            y_pos = course_y + (course_bbox[3] - course_bbox[1]) + 50
            
            # Additional text
            y_pos = draw_centered_text("This certificate recognizes the outstanding dedication and effort", 
                                      y_pos, normal_font)
            y_pos = draw_centered_text("demonstrated by the learner in acquiring knowledge and skills.", 
                                      y_pos + 10, normal_font)
            
            # Instructor and date with better spacing
            y_pos += 40
            y_pos = draw_centered_text(f"Instructor: {tutor_name}", y_pos, bold_font)
            y_pos = draw_centered_text(f"Completion Date: {completion_date}", y_pos + 10, italic_font)
            
            # Branding - CodeXLearning with enhanced styling
            brand_y = y_pos + 80
            
            # Draw platform name with enhanced styling
            brand_parts = [("Code", (0, 0, 0)), ("X", (0, 150, 0)), ("Learning", (0, 0, 0))]
            
            # Calculate total width for centering
            total_width = 0
            for text, _ in brand_parts:
                text_bbox = draw.textbbox((0, 0), text, font=subheading_font)
                total_width += text_bbox[2] - text_bbox[0]
                
            brand_x = (width - total_width) / 2
            
            # Draw each part with its color
            for text, color in brand_parts:
                text_bbox = draw.textbbox((0, 0), text, font=subheading_font)
                text_width = text_bbox[2] - text_bbox[0]
                
                # Add shadow effect
                draw.text((brand_x+1, brand_y+1), text, font=subheading_font, fill=(0, 0, 0))
                draw.text((brand_x, brand_y), text, font=subheading_font, fill=color)
                
                brand_x += text_width
            
            # Enhanced signature with realistic appearance
            signature_x = width // 3
            signature_y = height - 220
            
            # Signature line
            draw.line([signature_x, signature_y + 50, signature_x + 300, signature_y + 50], 
                     fill=(0, 0, 0), width=1)
            
            # Create a more realistic signature using curves
            points = [
                (signature_x, signature_y+20),
                (signature_x+20, signature_y-10),
                (signature_x+40, signature_y+30),
                (signature_x+60, signature_y-5),
                (signature_x+80, signature_y+10),
                (signature_x+100, signature_y+15),
                (signature_x+120, signature_y+5),
                (signature_x+140, signature_y+20),
                (signature_x+160, signature_y-15),
                (signature_x+180, signature_y+25),
                (signature_x+200, signature_y-5),
                (signature_x+220, signature_y+15),
                (signature_x+240, signature_y+5),
            ]
            
            # Draw the signature with varying thickness
            for i in range(len(points)-1):
                # Vary line thickness for realism
                thickness = random.randint(2, 4)
                draw.line([points[i], points[i+1]], fill=(0, 0, 120), width=thickness)
            
            # Signature label
            draw.text((signature_x + 80, signature_y + 60), "Instructor Signature", 
                     font=normal_font, fill=(100, 100, 100))
            
            # REDESIGNED STAMP SECTION - replace just this part in your code
            # ENHANCED STAMP with more elegant and professional design
            stamp_center_x, stamp_center_y = width - 300, height - 220
            stamp_radius = 120

            # Create an elegant, professional stamp
            # Clean outer ring with subtle gradient
            for r in range(stamp_radius, stamp_radius-8, -1):
                green_shade = 100 + (stamp_radius - r) * 5
                if green_shade > 150: green_shade = 150
                draw.ellipse([
                    stamp_center_x - r, 
                    stamp_center_y - r, 
                    stamp_center_x + r, 
                    stamp_center_y + r
                ], outline=(0, green_shade, 0), width=1)

            # Main outer ring - clean and bold
            draw.ellipse([
                stamp_center_x - stamp_radius, 
                stamp_center_y - stamp_radius, 
                stamp_center_x + stamp_radius, 
                stamp_center_y + stamp_radius
            ], outline=(0, 120, 0), width=3)

            # Secondary ring - thin and elegant
            draw.ellipse([
                stamp_center_x - stamp_radius + 15, 
                stamp_center_y - stamp_radius + 15, 
                stamp_center_x + stamp_radius - 15, 
                stamp_center_y + stamp_radius - 15
            ], outline=(0, 100, 0), width=1)

            # Inner circle with subtle fill
            draw.ellipse([
                stamp_center_x - stamp_radius + 25, 
                stamp_center_y - stamp_radius + 25, 
                stamp_center_x + stamp_radius - 25, 
                stamp_center_y + stamp_radius - 25
            ], fill=(245, 255, 245), outline=None)

            # Add subtle radial pattern
            for i in range(0, 360, 15):  # Every 15 degrees
                angle_rad = math.radians(i)
                inner_x = stamp_center_x + (stamp_radius - 70) * math.cos(angle_rad)
                inner_y = stamp_center_y + (stamp_radius - 70) * math.sin(angle_rad)
                outer_x = stamp_center_x + (stamp_radius - 30) * math.cos(angle_rad)
                outer_y = stamp_center_y + (stamp_radius - 30) * math.sin(angle_rad)
                draw.line([(inner_x, inner_y), (outer_x, outer_y)], fill=(0, 100, 0), width=1)

            # Add elegant border pattern
            num_elements = 36
            for i in range(num_elements):
                angle = 2 * math.pi * i / num_elements
                r1 = stamp_radius - 15
                r2 = stamp_radius - 25
                x1 = stamp_center_x + r1 * math.cos(angle)
                y1 = stamp_center_y + r1 * math.sin(angle)
                x2 = stamp_center_x + r2 * math.cos(angle)
                y2 = stamp_center_y + r2 * math.sin(angle)
                draw.line([(x1, y1), (x2, y2)], fill=(0, 120, 0), width=1)

            # Top text - clean and professional
            top_text = "CODEX LEARNING"
            top_text_bbox = draw.textbbox((0, 0), top_text, font=stamp_font)
            top_text_width = top_text_bbox[2] - top_text_bbox[0]
            draw.text((stamp_center_x - top_text_width/2, stamp_center_y - 70), 
                    top_text, font=stamp_font, fill=(0, 100, 100))

            # Decorative line under top text
            draw.line([
                (stamp_center_x - top_text_width/2 - 10, stamp_center_y - 45),
                (stamp_center_x + top_text_width/2 + 10, stamp_center_y - 45)
            ], fill=(0, 120, 0), width=1)

            # Bottom text - clean and professional
            bottom_text = "CERTIFICATE OF EXCELLENCE"
            bottom_text_bbox = draw.textbbox((0, 0), bottom_text, font=small_font)
            bottom_text_width = bottom_text_bbox[2] - bottom_text_bbox[0]
            draw.text((stamp_center_x - bottom_text_width/2, stamp_center_y + 45), 
                    bottom_text, font=small_font, fill=(0, 100, 0))

            # Decorative line above bottom text
            draw.line([
                (stamp_center_x - bottom_text_width/2 - 10, stamp_center_y + 40),
                (stamp_center_x + bottom_text_width/2 + 10, stamp_center_y + 40)
            ], fill=(0, 120, 0), width=1)

            # Elegant X in the center
            x_text = "X"
            x_bbox = draw.textbbox((0, 0), x_text, font=heading_font)
            x_width = x_bbox[2] - x_bbox[0]
            x_height = x_bbox[3] - x_bbox[1]

            # Draw with subtle shadow for depth
            draw.text((stamp_center_x - x_width/2 + 2, stamp_center_y - x_height/2 + 2), 
                    x_text, font=heading_font, fill=(220, 240, 220))

            # Main X with vibrant green
            draw.text((stamp_center_x - x_width/2, stamp_center_y - x_height/2 - 5), 
                    x_text, font=heading_font, fill=(0, 150, 0))

            # Add subtle decorative elements around the X
            x_decoration_radius = 25
            for angle in range(0, 360, 45):  # 8 small dots around the X
                angle_rad = math.radians(angle)
                dot_x = stamp_center_x + x_decoration_radius * math.cos(angle_rad)
                dot_y = stamp_center_y + x_decoration_radius * math.sin(angle_rad)
                draw.ellipse([dot_x-2, dot_y-2, dot_x+2, dot_y+2], fill=(0, 120, 0))
            
            # Output high-quality image
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            buffer.seek(0)
            
            # Set filename for download
            response = HttpResponse(buffer.getvalue(), content_type="image/png")
            response['Content-Disposition'] = f'attachment; filename="codex_certificate_{course_id}.png"'
            return response

        except Course.DoesNotExist:
            raise Http404("Course not found")
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Certificate generation error: {error_details}")
            return HttpResponse(f"Error generating certificate: {str(e)}", status=500)
        


class AvailableMeetingsView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def get(self, request):
        enrolled_courses = UserCourseEnrollment.objects.filter(
            user=request.user,
            status__in=["progress", "completed"]
        ).values_list("course_id", flat=True)

        if not enrolled_courses.exists():
            logger.debug("No course enrolled by the user")
            return Response([], status=status.HTTP_200_OK)

        
        tutor_ids = Course.objects.filter(
            id__in=enrolled_courses
        ).values_list("created_by", flat=True)

        if not tutor_ids.exists():
            return Response([], status=status.HTTP_200_OK)

        
        booked_meeting_ids = MeetingBooking.objects.filter(
            user=request.user
        ).values_list("meeting_id", flat=True)
        
        meetings = Meetings.objects.filter(
            is_completed=False,
            tutor_id__in=tutor_ids
        ).exclude(id__in=booked_meeting_ids)
        
        try:
            serializer = SheduledMeetingsSerializer(meetings, many=True)
            logger.debug(f"Found {len(serializer.data)} available meetings for user {request.user.id}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Error serializing available meetings")
            return Response({"error": "Error fetching meetings"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class BookedMeetingsView(APIView):
    permission_classes = [IsAuthenticatedUser]
    
    def get(self, request):
        bookings = MeetingBooking.objects.filter(user=request.user, meeting_completed=False).select_related("meeting")

        meetings = [booking.meeting for booking in bookings]
        logger.debug(f"Found {len(meetings)} booked meetings for user {request.user.id}")

        try:
            serializer = SheduledMeetingsSerializer(meetings, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Error serializing booked meetings")
            return Response({"error": "Error fetching meetings"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class BookMeetingView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def post(self, request, *args, **kwargs):
        meeting_id = request.data.get("meeting_id")
        if not meeting_id:
            logger.warning("Meeting ID is required")
            return Response({"error": "Meeting ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            meeting = Meetings.objects.get(id=meeting_id)
        except Meetings.DoesNotExist:
            logger.warning(f"Meeting {meeting_id} not found")
            return Response({"error": "Meeting not found."}, status=status.HTTP_404_NOT_FOUND)

        if meeting.is_completed:
            logger.warning(f"Attempted to book already completed meeting {meeting_id}")
            return Response({"error": "This meeting is already completed."}, status=status.HTTP_400_BAD_REQUEST)

        if meeting.left <= 0:
            logger.warning(f"Attempted to book fully booked meeting {meeting_id}")
            return Response({"error": "This meeting is fully booked."}, status=status.HTTP_400_BAD_REQUEST)

        if MeetingBooking.objects.filter(meeting=meeting, user=request.user, meeting_completed=False).exists():
            logger.warning(f"User {request.user.id} already booked meeting {meeting_id}")
            return Response({"error": "You have already booked this meeting."}, status=status.HTTP_400_BAD_REQUEST)

        # Create booking
        booking = MeetingBooking.objects.create(meeting=meeting, user=request.user)
        meeting.left -= 1
        meeting.save()
        
        send_meeting_confimation_email.delay(meeting.id, "scheduled", request.user.id)

        # Calculate reminder time
        meeting_datetime = make_aware(datetime.combine(meeting.date, meeting.time))
        reminder_time = meeting_datetime - timedelta(minutes=10)
        completion_time = meeting_datetime + timedelta(minutes=10)

        # Only schedule if reminder is still in the future
        if reminder_time > now():
            send_meeting_invite_email.apply_async(
                args=[meeting.id, "reminder", request.user.id],
                eta=reminder_time
            )
        
        if completion_time > now():
            mark_meeting_completed.apply_async(
                args=[booking.id],
                eta=completion_time
            )

        logger.info(f"Meeting {meeting_id} booked successfully by user {request.user.id}")
        return Response({"message": "Meeting booked successfully & reminder scheduled."}, status=status.HTTP_201_CREATED)
        


class RecentMeetingsView(APIView):
    permission_classes = [IsAuthenticatedUser]
    
    def get(self, request):
        enrolled_courses = UserCourseEnrollment.objects.filter(
            user=request.user,
            status__in=["progress", "completed"]
        ).values_list("course_id", flat=True)

        if not enrolled_courses.exists():
            return Response([], status=status.HTTP_200_OK)

        tutor_ids = Course.objects.filter(
            id__in=enrolled_courses
        ).values_list("created_by", flat=True)

        if not tutor_ids.exists():
            return Response([], status=status.HTTP_200_OK)

        booked_meeting_ids = MeetingBooking.objects.filter(
            user=request.user,
            meeting_completed = True
        ).values_list("meeting_id", flat=True)

        if not booked_meeting_ids.exists():
            return Response([], status=status.HTTP_200_OK)

        meetings = Meetings.objects.filter(
            is_completed=True,
            tutor_id__in=tutor_ids,
            id__in=booked_meeting_ids
        )

        try:
            serializer = SheduledMeetingsSerializer(meetings, many=True)
            logger.debug(f"Found {len(serializer.data)} recent meetings for user {request.user.id}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Error serializing recent meetings")
            return Response({"error": "Error fetching meetings"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class TutorFeedbackView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def post(self, request):
        try:
            logger.debug(f"[POST] Raw request data: {request.data}")

            data = request.data.copy()
            data["user"] = request.user.id
            tutor_id = data.get("tutor")

            purchased = UserCourseEnrollment.objects.filter(
                user=request.user,
                course__created_by_id=tutor_id
            ).exists()

            if not purchased:
                return Response(
                    {"error": "You must purchase at least one course from this tutor to submit feedback."},
                    status=400
                )

            if TutorFeedback.objects.filter(tutor_id=tutor_id, user=request.user).exists():
                return Response({"error": "You already submitted feedback for this tutor."}, status=400)

            serializer = TutorFeedbackSerializer(data=data)

            if not serializer.is_valid():
                return Response(serializer.errors, status=400)

            serializer.save()
            return Response(serializer.data, status=201)

        except Exception as e:
            logger.exception(f"[POST] Unexpected error: {str(e)}")
            return Response({"error": str(e)}, status=400)
    
    def get(self, request, tutor_id): 
        try: 
            feedback = TutorFeedback.objects.filter(tutor_id=tutor_id) 
            
            avg_rating = feedback.aggregate(avg=models.Avg("rating"))["avg"] 

            serializer = TutorFeedbackSerializer(feedback, many=True) 
            
            return Response({ "average_rating": round(avg_rating, 1) 
                            if avg_rating else 0, 
                            "total_feedback": feedback.count(),
                            "feedback": serializer.data }, status=200)
            
        except Exception as e: 
            return Response({"error": str(e)}, status=400) 
    
    def delete(self, request, tutor_id): 
        try: 
            feedback = TutorFeedback.objects.filter( tutor_id=tutor_id, user=request.user ).first() 
            
            if not feedback: 
                return Response( {"error": "No feedback found for this tutor from this user."}, status=status.HTTP_404_NOT_FOUND ) 
            
            feedback.delete() 
            
            return Response({"message": "Feedback deleted successfully."}, status=200) 
        
        except Exception as e: 
            return Response({"error": str(e)}, status=400)



class CourseFeedbackView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def post(self, request):
        try:
            data = request.data.copy()
            data["user"] = request.user.id
            course_id = data.get("course")

            purchased = UserCourseEnrollment.objects.filter(
                user=request.user,
                course_id=course_id
            ).exists()

            if not purchased:
                return Response(
                    {"error": "You must purchase this course to submit feedback."},
                    status=400
                )

            if CourseFeedback.objects.filter(course_id=course_id, user=request.user).exists():
                return Response(
                    {"error": "You already submitted feedback for this course."},
                    status=400
                )

            serializer = CourseFeedbackSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            return Response(serializer.data, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=400)

    def get(self, request, course_id):
        try: 
            feedback = CourseFeedback.objects.filter(course_id=course_id) 
            
            avg_rating = feedback.aggregate(avg=models.Avg("rating"))["avg"] 
            
            serializer = CourseFeedbackSerializer(feedback, many=True) 
            
            return Response({ "average_rating": round(avg_rating, 1) 
                             if avg_rating else 0, "total_feedback": feedback.count(), 
                             "feedback": serializer.data }, status=200) 
            
        except Exception as e: return Response({"error": str(e)}, status=400) 
    
    def delete(self, request, course_id): 
        try: 
            feedback = CourseFeedback.objects.filter(course_id=course_id,user=request.user).first() 
            
            if not feedback: 
                return Response({"error": "No feedback found for this course from this user."},status=status.HTTP_404_NOT_FOUND) 
            
            feedback.delete() 
            
            return Response({"message": "Feedback deleted successfully."}, status=200) 
        
        except Exception as e: 
            return Response({"error": str(e)}, status=400)



class TutorReportView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def post(self, request):
        try:
            data = request.data.copy()
            data["user"] = request.user.id
            tutor_id = data.get("tutor")

            purchased = UserCourseEnrollment.objects.filter(
                user=request.user,
                course__created_by_id=tutor_id
            ).exists()

            if not purchased:
                return Response({"error": "You must purchase at least one course from this tutor to send a report."}, status=400)

            if TutorReport.objects.filter(tutor_id=tutor_id, user=request.user).exists():
                return Response({"error": "You already reported this tutor."}, status=400)

            serializer = TutorReportSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            report = serializer.instance

            # Send email using Celery
            send_report_email.delay(
                user_email=report.user.email,
                user_name=report.user.first_name,
                report_type="tutor",
                reported_name=report.tutor.full_name
            )

            return Response(serializer.data, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=400)

    def get(self, request, tutor_id):
        reports = TutorReport.objects.filter(tutor_id=tutor_id)
        serializer = TutorReportSerializer(reports, many=True)
        return Response(serializer.data, status=200)



class CourseReportView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def post(self, request):
        try:
            data = request.data.copy()
            data["user"] = request.user.id
            course_id = data.get("course")

            purchased = UserCourseEnrollment.objects.filter(
                user=request.user,
                course_id=course_id
            ).exists()

            if not purchased:
                return Response({"error": "You must purchase this course to send a report."}, status=400)

            if CourseReport.objects.filter(course_id=course_id, user=request.user).exists():
                return Response({"error": "You already reported this course."}, status=400)

            serializer = CourseReportSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            report = serializer.instance

            # Send email using Celery
            send_report_email.delay(
                user_email=report.user.email,
                user_name=report.user.first_name,
                report_type="course",
                reported_name=report.course.title
            )

            return Response(serializer.data, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=400)

    def get(self, request, course_id):
        reports = CourseReport.objects.filter(course_id=course_id)
        serializer = CourseReportSerializer(reports, many=True)
        return Response(serializer.data, status=200)
