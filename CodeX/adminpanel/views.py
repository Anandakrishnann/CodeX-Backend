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
import traceback
from Accounts.models import *
from tutorpanel.models import *
from notifications.utils import send_notification
from Accounts.tasks import send_report_marked_email



class AdminDashboardView(APIView):
    def get(self, request):
        print("\n🔹 [AdminDashboardView] Called")

        try:
            # --- Total counts ---
            total_users = Accounts.objects.filter(role="user").count()
            print(f"✅ Total Users: {total_users}")

            total_tutors = Accounts.objects.filter(role="tutor").count()
            print(f"✅ Total Tutors: {total_tutors}")

            total_courses = Course.objects.count()
            print(f"✅ Total Courses: {total_courses}")

            total_revenue = (
                UserCourseEnrollment.objects.aggregate(total=Sum("course__price"))["total"] or 0
            )
            print(f"✅ Total Revenue: {total_revenue:.2f}")

            # --- Monthly revenue trend ---
            print("🔹 Calculating monthly revenue trend...")
            monthly_revenue_trend = (
                UserCourseEnrollment.objects
                .annotate(month=TruncMonth("enrolled_on"))
                .values("month")
                .annotate(revenue=Sum("course__price"))
                .order_by("month")
            )
            print(f"✅ Monthly Revenue Raw Data: {list(monthly_revenue_trend)}")

            monthly_revenue_trend = [
                {"month": m["month"].strftime("%b"), "revenue": float(m["revenue"] or 0)}
                for m in monthly_revenue_trend if m["month"]
            ]
            print(f"✅ Monthly Revenue Parsed: {monthly_revenue_trend}")

            # --- Yearly revenue trend ---
            print("🔹 Calculating yearly revenue trend...")
            yearly_revenue_trend = (
                UserCourseEnrollment.objects
                .annotate(year=ExtractYear("enrolled_on"))
                .values("year")
                .annotate(revenue=Sum("course__price"))
                .order_by("year")
            )
            print(f"✅ Yearly Revenue Trend: {list(yearly_revenue_trend)}")

            # --- User growth trend ---
            print("🔹 Calculating user growth trend...")
            user_growth = (
                Accounts.objects.filter(role="user")
                .annotate(month=TruncMonth("created_at"))  # ✅ Correct field
                .values("month")
                .annotate(count=Count("id"))
                .order_by("month")
            )
            print(f"✅ User Growth Raw Data: {list(user_growth)}")

            user_growth = [
                {"month": u["month"].strftime("%b"), "count": u["count"]}
                for u in user_growth if u["month"]
            ]
            print(f"✅ User Growth Parsed: {user_growth}")

            # --- Top tutors ---
            print("🔹 Fetching top tutors...")
            top_tutors = (
                UserCourseEnrollment.objects
                .values("course__created_by__account__first_name", "course__created_by__account__last_name")
                .annotate(earnings=Sum("course__price"))
                .order_by("-earnings")[:5]
            )
            print(f"✅ Top Tutors Raw: {list(top_tutors)}")

            top_tutors = [
                {
                    "name": f"{t['course__created_by__account__first_name']} {t['course__created_by__account__last_name']}".strip(),
                    "earnings": float(t["earnings"] or 0),
                }
                for t in top_tutors
            ]
            print(f"✅ Top Tutors Parsed: {top_tutors}")


            # --- Top courses ---
            print("🔹 Fetching top courses...")
            top_courses = (
                UserCourseEnrollment.objects
                .values("course__title")
                .annotate(enrollments=Count("id"))
                .order_by("-enrollments")[:5]
            )
            print(f"✅ Top Courses Raw: {list(top_courses)}")

            top_courses = [
                {"name": c["course__title"] or "Untitled", "enrollments": c["enrollments"]}
                for c in top_courses
            ]
            print(f"✅ Top Courses Parsed: {top_courses}")

            # --- Recent transactions ---
            print("🔹 Fetching recent transactions...")
            recent_transactions = (
                UserCourseEnrollment.objects
                .select_related("user", "course")
                .order_by("-enrolled_on")[:5]
            )
            print(f"✅ Recent Transactions Raw Count: {recent_transactions.count()}")

            transactions_data = [
                {
                    "user": f"{tx.user.first_name} {tx.user.last_name}".strip(),
                    "course": tx.course.title,
                    "amount": float(tx.course.price or 0),
                    "date": tx.enrolled_on.strftime("%b %d, %Y"),
                }
                for tx in recent_transactions
            ]
            print(f"✅ Transactions Parsed: {transactions_data}")

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
                "recent_transactions": transactions_data,
            }

            print("✅ Final dashboard data ready to return.\n")
            return Response(data, status=200)

        except Exception as e:
            import traceback
            print("❌ [AdminDashboardView] ERROR:", str(e))
            print(traceback.format_exc())
            return Response({"error": str(e)}, status=500)




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
                })

            return Response({"users": tutor_data}, status=200)

        except Exception as e:
            print(f"❌ Error: {e}")
            return Response({"error": "Something went wrong"}, status=500)



class Status(APIView):

    def post(self, request):
        try:
            user_id = request.data.get('id')

            if not user_id:
                return Response({"error": "User ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            user = get_object_or_404(Accounts, id=user_id)

            user.isblocked = not user.isblocked
            user.save()
            if user.isblocked:
                send_notification(user, "Your account was blocked by admin. Please contact support.")
            else:
                send_notification(user, "Your account was unblocked by admin. You can continue using the app.")

            return Response({"message": "Status updated successfully", "status": user.isblocked}, status=status.HTTP_200_OK)
        except:
            return Response({"Unauthorized": "Token expired"}, status=401)
        


class TutorStatus(APIView):

    def post(self, request):
        try:
            user_id = request.data.get('id')
            print(user_id)

            if not user_id:
                print("no userss")
                return Response({"error": "User ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            user = get_object_or_404(Accounts, id=user_id)

            user.isblocked = not user.isblocked
            user.save()

            if user.isblocked:
                send_notification(user, "Your account was blocked by admin. Please contact support.")
            else:
                send_notification(user, "Your account was unblocked by admin. You can continue using the app.")
            
            return Response({"message": "Status updated successfully", "status": user.isblocked}, status=status.HTTP_200_OK)
        except:
            return Response({"Error": "Error While Chaning the status"}, status=status.HTTP_400_BAD_REQUEST)



class TutorApplicationView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        data = {k: v for k, v in request.data.items()}
        print("\n🟩 Incoming Tutor Application Request")
        print("Incoming data:", data)
        print("Incoming files:", request.FILES)

        # 🔍 Detailed debug for each file
        for key, file in request.FILES.items():
            print(f"➡️ File field: {key}")
            print(f"   Name: {file.name}")
            print(f"   Content type: {file.content_type}")
            print(f"   Size: {file.size / (1024 * 1024):.2f} MB")

        # Upload files
        try:
            if request.FILES.get('profile_picture'):
                profile_file = request.FILES['profile_picture']
                print(f"📸 Uploading profile picture ({profile_file.name}, {profile_file.size / (1024 * 1024):.2f} MB)")
                upload_result = cloudinary.uploader.upload(
                    profile_file,
                    folder="profile_picture",
                    resource_type="image"
                )
                data['profile_picture'] = upload_result.get('secure_url')

            if request.FILES.get('verification_file'):
                doc_file = request.FILES['verification_file']
                print(f"📄 Uploading verification file ({doc_file.name}, {doc_file.size / (1024 * 1024):.2f} MB)")
                upload_result = cloudinary.uploader.upload(
                    doc_file,
                    folder="verification_docs",
                    resource_type="raw"
                )
                data['verification_file'] = upload_result.get('secure_url')

            if request.FILES.get('verification_video'):
                video_file = request.FILES['verification_video']
                print(f"🎥 Uploading verification video ({video_file.name}, {video_file.size / (1024 * 1024):.2f} MB)")
                print("📊 Cloudinary upload starting...")
                upload_result = cloudinary.uploader.upload(
                    video_file,
                    folder="verification_videos",
                    resource_type="video"
                )
                print("✅ Cloudinary upload success:", upload_result.get('secure_url'))
                data['verification_video'] = upload_result.get('secure_url')

        except Exception as e:
            print("❌ Cloudinary upload failed:", e)
            return Response({"error": "File upload failed", "details": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Continue with serializer
        serializer = TutorApplicationSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            serializer.save(account=request.user)
            print("✅ Tutor application saved successfully.")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            print("❌ Serializer errors:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class TutorApplicationsOverView(APIView):

    def get(self, request, email):
        try:
            user_application = get_object_or_404(TutorApplications, email=email)  # Ensure ID is an int
            print(f"Found application: {user_application}")
            print(f"userId: {email}")

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
            print(f"data: {data}")

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            print("❌ ERROR OCCURRED:")
            return Response({"error": str(e)}, status=500)



class TutorOverView(APIView):

    def get(self, request, userId):
        try:
            deatils = get_object_or_404(TutorDetails, id=userId)

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
                "status":deatils.status
            }
            print(f"data: {data}")

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            print("❌ ERROR OCCURRED:")
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)



class AcceptApplicationView(APIView):

    def post(self, request, applicationId):
        try:
            application = get_object_or_404(TutorApplications, id=applicationId)
            user = get_object_or_404(Accounts, email=application.email)
            print(f"user object: {user}")

            if not application.dob:
                return Response({"error": "Date of Birth is required"}, status=status.HTTP_400_BAD_REQUEST)

            tutor, created = TutorDetails.objects.get_or_create(
                account=user,
                defaults={
                    "full_name": application.full_name,
                    "dob": application.dob,
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
            print(f"Tutor Created or Updated: {tutor}")

            # Update user role & application status
            user.role = "tutor"
            user.save()
            application.status = "verified"
            application.save()

            return Response({"success": "Tutor Data added/updated successfully"}, status=status.HTTP_201_CREATED)

        except Exception as e:
            print(f"Error While Creating Tutor: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class RejectApplicationView(APIView):

    def post(self, request, applicationId):
        try:
            print(applicationId)
            application = get_object_or_404(TutorApplications, id=applicationId)
            print(application)

            if not application:
                return Response({"error":"Application not found"}, status=status.HTTP_404_NOT_FOUND)
            
            application.status = "rejected"
            application.save()

            user = get_object_or_404(Accounts, email=application.email)
            print(f"user object: {user}")
            
            send_notification(user, "Your Application rejected by admin contact help serivce.")

            return Response({"success":"Application Rejected"}, status=status.HTTP_201_CREATED)
        
        except:

            return Response({"error":"Something went wrong"}, status=status.HTTP_400_BAD_REQUEST)



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
            print(f"CreateCategoryView Error: {e}")
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
            print("EditCategoryView Error:", str(e))
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
            print(f"category_id   {category_id}")
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

    def post(self, requests, id):
        try:
            course = get_object_or_404(Course, id=id)

            if not course:
                return Response({"Error":"Course Does Not Exists"}, status=status.HTTP_400_BAD_REQUEST)
            
            course.is_active = not course.is_active
            course.save()
            
            tutor_user = course.created_by.account  
            
            send_notification(tutor_user, "Your Course Status Changed by admin. Please contact support.")
            
            return Response({"message": "Status updated successfully", "status": course.is_active}, status=status.HTTP_200_OK)
        except:
            return Response({"Error": "Error While Updating the status"}, status=status.HTTP_400_BAD_REQUEST)



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
            
            tutor = get_object_or_404(TutorDetails, id=course.created_by)
            
            user = get_object_or_404(Accounts, id=tutor.account)

            if not course:
                return Response({"Error":"Course Does Not Exists"}, status=status.HTTP_400_BAD_REQUEST)
            
            course.is_active = not course.is_active
            course.save()
            
            if course.is_active == True:
                send_notification(user, f"Your {course.name} course status was changed by admin.")
            else:
                send_notification(user, f"Your {course.name} course was deactivated by admin. Please contact support if needed.")
                
            return Response({"message": "Status updated successfully", "status": course.is_active}, status=status.HTTP_200_OK)
        except:
            return Response({"Error": "Error While Updating the status"}, status=status.HTTP_400_BAD_REQUEST)
        

import logging
# Configure logger
logger = logging.getLogger(__name__)

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
            logger.debug(f"[DEBUG] Tutor's account found: {user.email}")

            # ✅ Update course status
            course.status = "accepted"
            course.is_active = True
            course.save()
            logger.info(f"[INFO] Course '{course.name}' accepted successfully.")

            # ✅ Notify tutor
            try:
                send_notification(user, f"🎉 Your course '{course.name}' was accepted by admin.")
                logger.info(f"[SUCCESS] Notification sent to {user.email} for course '{course.name}'.")
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

            tutor = course.created_by

            user = get_object_or_404(Accounts, id=tutor.account.id)

            if not course:
                return Response({"error":"Course Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            course.status = "rejected"
            course.is_active = False
            course.save()
            
            send_notification(user, f"Your {course.name} course was rejected by admin. Please contact support.")
            
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

            if not module:
                return Response({"error":"Module Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            module.status = "rejected"
            module.is_active = False
            module.save()

            # Notify tutor
            try:
                tutor = module.course.created_by
                tutor_user = tutor.account if hasattr(tutor, 'account') else None
                if tutor_user:
                    send_notification(tutor_user, f"Your module '{module.title}' was rejected by admin.")
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
            print(f"Error fetching course overview: {e}")
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
            print(f"Error fetching course overview: {e}")
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

            if not module:
                return Response({"error":"Module Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            module.is_active = not module.is_active
            module.save()

            # Notify tutor about visibility change
            try:
                tutor = module.course.created_by
                tutor_user = tutor.account if hasattr(tutor, 'account') else None
                if tutor_user:
                    visibility = "activated" if module.is_active else "deactivated"
                    send_notification(tutor_user, f"Your module '{module.title}' was {visibility} by admin.")
            except Exception:
                pass

            return Response({"detail":"Status Changed Successfully"}, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Changing Module Status"}, status=status.HTTP_400_BAD_REQUEST)



class ListCourseLessonView(APIView):

    def get(self, request, id):
        try:
            print(id)
            module = get_object_or_404(Modules, id=id)
            lessons = Lessons.objects.filter(module=module)
            
            serializer = LessonOverviewSerializer(lessons, many=True)
            print(serializer)
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
            if not lesson:
                return Response({"error":"Lesson Not Found"}, status=status.HTTP_404_NOT_FOUND)
            lesson.status = "rejected"
            lesson.is_active = False
            lesson.save()

            # Notify tutor
            try:
                tutor = lesson.module.course.created_by
                tutor_user = tutor.account if hasattr(tutor, 'account') else None
                if tutor_user:
                    send_notification(tutor_user, f"Your lesson '{lesson.title}' was rejected by admin.")
            except Exception:
                pass

            return Response({"detail":"Lesson Rejected Successfully"}, status=status.HTTP_200_OK) 
        except:
            return Response({"error":"Error While Rejecting Lesson"}, status=status.HTTP_400_BAD_REQUEST)



class LessonStatusView(APIView):

    def post(self, request, lessonId):
        try:
            lesson = get_object_or_404(Lessons, id=lessonId)

            if not lesson:
                return Response({"error":"Lesson Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            lesson.is_active = not lesson.is_active
            lesson.save()

            # Notify tutor about visibility change
            try:
                tutor = lesson.module.course.created_by
                tutor_user = tutor.account if hasattr(tutor, 'account') else None
                if tutor_user:
                    visibility = "activated" if lesson.is_active else "deactivated"
                    send_notification(tutor_user, f"Your lesson '{lesson.title}' was {visibility} by admin.")
            except Exception:
                pass

            return Response({"detail":"Status Changed Successfully"}, status=status.HTTP_200_OK)
        except: 
            return Response({"error":"Error While Changing Lesson Status"}, status=status.HTTP_400_BAD_REQUEST)



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
            print(e)
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
