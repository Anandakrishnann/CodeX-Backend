from django.shortcuts import get_object_or_404, render
from django.contrib.auth import get_user_model
from rest_framework.views import APIView 
from rest_framework.response import Response 
from rest_framework import status 
from .models import *
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from Accounts.models import *
from .serializers import *
from .permissions import IsSubscribed
import cloudinary.uploader
from django.utils.timezone import make_aware, now
from .tasks import *
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta
from django.conf import settings
from django.db.models import Sum, Count, F, Avg
from django.db.models.functions import TruncMonth, TruncYear
import traceback
from notifications.utils import send_notification
import logging

logger = logging.getLogger("codex")


class TutorDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tutor = TutorDetails.objects.get(account=request.user)
        except TutorDetails.DoesNotExist:
            logger.warning(f"TutorDetails not found for user {request.user.id}")
            return Response({"error": "Tutor details not found"}, status=404)

        logger.debug(f"Tutor found: {tutor.id} - {tutor}")

        # Fetch tutor's courses
        courses = Course.objects.filter(created_by=tutor)
        logger.debug(f"Found {courses.count()} courses for this tutor")

        total_courses = courses.count()
        active_courses = courses.filter(is_active=True).count()
        draft_courses = courses.filter(is_draft=True).count()

        pending_courses = courses.filter(status='pending').count()
        accepted_courses = courses.filter(status='accepted').count()
        rejected_courses = courses.filter(status='rejected').count()

        # Enrollments and revenue
        enrollments = UserCourseEnrollment.objects.filter(course__in=courses)
        logger.debug(f"Total enrollments: {enrollments.count()}")

        total_students = enrollments.values('user').distinct().count()
        completed_students = enrollments.filter(status='completed').count()
        ongoing_students = enrollments.filter(status='progress').count()

        total_revenue = enrollments.aggregate(total=Sum('course__price'))['total'] or 0
        monthly_revenue = enrollments.filter(
            enrolled_on__month=timezone.now().month
        ).aggregate(total=Sum('course__price'))['total'] or 0

        avg_progress = enrollments.aggregate(avg=Avg('progress'))['avg'] or 0

        logger.debug(f"Total revenue: {total_revenue}, Monthly revenue: {monthly_revenue}")
        logger.debug(f"Average progress: {avg_progress}")

        recent_enrollments = (
            enrollments.select_related('user', 'course')
            .order_by('-enrolled_on')[:5]
            .values('user__first_name', 'user__last_name', 'course__title', 'enrolled_on', 'status')
        )

        logger.debug(f"Recent enrollments fetched: {len(recent_enrollments)}")

        data = {
            "summary": {
                "total_courses": total_courses,
                "active_courses": active_courses,
                "draft_courses": draft_courses,
                "pending_courses": pending_courses,
                "accepted_courses": accepted_courses,
                "rejected_courses": rejected_courses,
                "total_students": total_students,
                "completed_students": completed_students,
                "ongoing_students": ongoing_students,
                "avg_progress": round(avg_progress, 2),
                "total_revenue": round(total_revenue, 2),
                "monthly_revenue": round(monthly_revenue, 2),
            },
            "recent_enrollments": [
                {
                    "user": f"{e['user__first_name']} {e['user__last_name']}",
                    "course": e["course__title"],
                    "status": e["status"],
                    "date": e["enrolled_on"].strftime("%b %d, %Y")
                }
                for e in recent_enrollments
            ],
        }

        logger.info("TutorDashboardView executed successfully.")
        return Response(data, status=200)



class TutorSubscribedCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != "tutor":
            logger.warning("Not a tutor account.")
            return Response({"subscribed": False}, status=status.HTTP_200_OK)

        try:
            tutor = TutorDetails.objects.get(account=request.user)
        except TutorDetails.DoesNotExist:
            logger.warning("TutorDetails not found for user.")
            return Response({"subscribed": False}, status=status.HTTP_200_OK)

        is_subscribed = TutorSubscription.objects.filter(tutor=tutor, is_active=True).exists()
        logger.info(f"Subscription check for {request.user.email}: {is_subscribed}")

        return Response({"subscribed": is_subscribed}, status=status.HTTP_200_OK)
        
        
        
class TutorApplicationCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        has_pending = TutorApplications.objects.filter(
            account=user,
            status="pending"
        ).exists()

        logger.debug(f"Tutor application check for user {user.id}: {has_pending}")
        return Response({"application": has_pending}, status=status.HTTP_200_OK)



class TutorProfileView(APIView):
    permission_classes=[IsSubscribed]

    def get(self, request):
        user = request.user
        profile_picture = user.profile_picture
        
        try:
            details = TutorDetails.objects.get(account=user)
            profile_picture = details.profile_picture
        except TutorDetails.DoesNotExist:
            logger.warning(f"TutorDetails not found for user {user.id}")
            return Response({"error": "Tutor Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)
        
        userData = {
            "first_name":user.first_name,
            "last_name":user.last_name,
            "email":user.email,
            "phone":details.phone,
            "streak":user.streak,
            "last_completed":user.last_completed_task,
            "profile_picture": profile_picture,
            "dob":details.dob,
            "age": details.get_age(), 
            "about":details.about,
            "education":details.education,
            "expertise": details.expertise,
            "occupation": details.occupation,
            "experience": details.experience,
            "verification_file": details.verification_file,
            "verification_video": details.verification_video
        }
        logger.debug(f"User data retrieved for tutor {user.id}")
        return Response(userData, status=status.HTTP_200_OK)



class EditTutorView(APIView):
    permission_classes = [IsSubscribed]

    def put(self, request):
        user = request.user
    
        serializer = CombinedUserProfileSerializer(user, data=request.data)
        if serializer.is_valid():
            updated_user = serializer.save()
            logger.info(f"Tutor profile updated for user {user.id}")
            return Response(CombinedUserProfileSerializer(updated_user).data, status=status.HTTP_200_OK)
        else:
            logger.warning(f"Tutor profile validation failed for user {user.id}: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class UploadTutorProfilePictureView(APIView):
    
    permission_classes = [IsSubscribed]
    
    def post(self, request):
        user = request.user

        try:
            tutor = TutorDetails.objects.get(account=user)
        except TutorDetails.DoesNotExist:
            logger.warning(f"TutorDetails not found for user {user.id}")
            return Response({"error": "Tutor not found"}, status=status.HTTP_404_NOT_FOUND)

        profile_picture = request.FILES.get("profilePicture")
        if not profile_picture:
            logger.warning("No profilePicture provided in request")
            return Response({"error": "No profilePicture provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            upload_result = cloudinary.uploader.upload(
                profile_picture,
                folder="profile_picture",
                resource_type="image"
            )
            profile_picture_url = upload_result.get('secure_url')

            user.profile_picture = profile_picture_url
            user.save()
            tutor.profile_picture = profile_picture_url
            tutor.save()

            logger.info(f"Profile picture uploaded successfully for tutor {user.id}")
            return Response(profile_picture_url, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Error while uploading profile picture")
            return Response({"error": "Error While Profile Upload", "details": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class CreateCourseView(APIView):
    
    permission_classes = [IsSubscribed]

    def post(self, request):
        tutor = request.user
        if not tutor.role == 'tutor':
            logger.warning(f"User {tutor.id} is not a tutor")
            return Response({"detail": "Tutor Details Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            tutor_detail = TutorDetails.objects.get(account=tutor, status="verified")
        except TutorDetails.DoesNotExist:
            logger.warning(f"TutorDetails not found or not verified for user {tutor.id}")
            return Response({"detail": "Tutor Details Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)

        category_id = request.data.get("category_id")
        if not category_id:
            logger.warning("Category ID is required")
            return Response({"detail": "Category ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            category = CourseCategory.objects.get(id=category_id, is_active=True)
        except CourseCategory.DoesNotExist:
            logger.warning(f"Category {category_id} not found or inactive")
            return Response({"detail": "Category Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CreateCourseSerializer(data=request.data, context={'tutor': tutor_detail, 'category': category})
        if serializer.is_valid():
            course = serializer.save()
            logger.info(f"Course created successfully: {course.id} by tutor {tutor.id}")
            return Response({"id": course.id}, status=status.HTTP_201_CREATED)
        else:
            logger.warning(f"Course creation validation failed: {serializer.errors}")
            return Response(
                {"detail": "Invalid data", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )



def get_course_levels(request):
    levels = [{"id": key, "name": value} for key, value in Course.CHOICES]
    return JsonResponse(levels, safe=False)



class ListCourseView(APIView):
    
    permission_classes = [IsSubscribed]

    def get(self, request):
        tutor = request.user
        if not tutor.role == 'tutor':
            logger.warning(f"User {tutor.id} is not a tutor")
            return Response({"detail": "Tutor Details Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            tutor_details = TutorDetails.objects.get(account=tutor)
        except TutorDetails.DoesNotExist:
            logger.warning(f"TutorDetails not found for user {tutor.id}")
            return Response({"error":"Tutor Details Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)
        

        courses = Course.objects.filter(created_by=tutor_details)
        logger.debug(f"Found {courses.count()} courses for tutor {tutor_details.id}")
        data = []

        for course in courses:
            data.append({
                "id":course.id,
                "name": course.name,
                "category": course.category_id.name if course.category_id else None,
                "category_id":course.category_id.id if course.category_id else None,
                "title": course.title,
                "level":course.level,
                "description": course.description,
                "requirements": course.requirements,
                "benefits": course.benefits,
                "price": course.price,
                "created_at": course.created_at,
                "is_active": course.is_active,
                "is_draft": course.is_draft,
                "status": course.status,
            })

        return Response(data, status=status.HTTP_200_OK)



class EditCourseView(APIView):
    
    permission_classes = [IsSubscribed]

    def put(self, request, id):
        logger.debug(f"request data: {request.data}")
        try:
            course_instance = Course.objects.get(id=id)
        except Course.DoesNotExist:
            logger.warning(f"Course {id} not found")
            return Response({"detail": "Course Does Not Exist"}, status=status.HTTP_404_NOT_FOUND)

        serializer = EditCourseSerializer(instance=course_instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            
            course_instance.status = 'pending'
            course_instance.save()
            
            courses = Course.objects.all()

            logger.info(f"Course {id} updated successfully")
            return Response(ListCourseSerializer(courses, many=True).data, status=status.HTTP_200_OK)
        else:
            logger.warning(f"Course edit validation failed: {serializer.errors}")
            return Response(
                {"detail": "Validation Error", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )



class CourseStatusView(APIView):
    
    permission_classes = [IsSubscribed]

    def post(self, request, id):
        logger.debug(f"course id: {id}")
        try:
            course = Course.objects.get(id=id)
        except Course.DoesNotExist:
            logger.warning(f"Course {id} not found")
            return Response({"Error":"Course Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)
        
        purchased_course = UserCourseEnrollment.objects.filter(
            course=course,
            status__in=["pending", "progress"]
        )
        
        if purchased_course.exists():
            logger.warning(f"Cannot change status for course {id} - already purchased by users")
            return Response(
                {
                    "message": (
                        "This course has already been purchased by user's. "
                        "You cannot change its status. "
                        "If needed, you may switch the course to draft mode."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        course.is_active = not course.is_active
        course.save()
        logger.info(f"Course {id} status changed to {course.is_active}")
        return Response({"message": "Status updated successfully", "status": course.is_active}, status=status.HTTP_200_OK)



class CourseOverView(APIView):
    
    permission_classes = [IsSubscribed]

    def get(self, request, id):
        try:
            course = Course.objects.get(id=id)
        except Course.DoesNotExist:
            logger.warning(f"Course {id} not found")
            return Response({"error": "Course Not Found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            serializer = CourseDetailsSerializer(course)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error serializing course {id}")
            return Response({"error": "Something went wrong"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class ListCourseModulesView(APIView):
    
    permission_classes = [IsSubscribed]
    
    def get(self, request, id):
        try:
            course = Course.objects.get(id=id)
        except Course.DoesNotExist:
            logger.warning(f"Course {id} not found")
            return Response({"error": "Course Not Found"}, status=status.HTTP_404_NOT_FOUND)
        
        modules = Modules.objects.filter(course=course)
        logger.debug(f"Found {modules.count()} modules for course {id}")

        try:
            serializer = CourseModuleSerializer(modules, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error serializing modules for course {id}")
            return Response({"error": "Something went wrong"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
     


class CreateModuleView(APIView):
    
    permission_classes = [IsSubscribed]

    def post(self, request):
        tutor = request.user
        if not tutor.role == 'tutor':
            logger.warning(f"User {tutor.id} is not a tutor")
            return Response({"detail": "Tutor Details Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            tutor_detail = TutorDetails.objects.get(account=tutor)
        except TutorDetails.DoesNotExist:
            logger.warning(f"TutorDetails not found for user {tutor.id}")
            return Response({"details":"Tutor Details Does not exists"}, status=status.HTTP_404_NOT_FOUND)
        
        course_id = request.data.pop("course_id")
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            logger.warning(f"Course {course_id} not found")
            return Response({"details":"course Does not exists"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = CreateModuleSerializer(data=request.data, context={'tutor': tutor_detail, 'course': course})
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Module created successfully: {serializer.instance.id} in course {course_id}")
            return Response(ListModuleSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)
        else:
            logger.warning(f"Module creation validation failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_406_NOT_ACCEPTABLE)
        


class EditModuleView(APIView):
    permission_classes = [IsSubscribed]
    
    def put(self, request, id):
        try:
            module = Modules.objects.get(id=id)
        except Modules.DoesNotExist:
            logger.warning(f"Module {id} not found")
            return Response({"error": "Module not found"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = EditModuleSerializer(instance=module, data=request.data)
        if serializer.is_valid():
            serializer.save()
            module.status = 'pending'
            module.save()
            logger.info(f"Module {id} updated successfully")
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            logger.warning(f"Module edit validation failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class ModuleStatusView(APIView):
    permission_classes = [IsSubscribed]
    
    def post(self, request, id):
        try:
            module = Modules.objects.get(id=id)
        except Modules.DoesNotExist:
            logger.warning(f"Module {id} not found")
            return Response({"error":"Module Not Found"}, status=status.HTTP_404_NOT_FOUND)
        
        module.is_active = not module.is_active
        module.save()
        logger.info(f"Module {id} status changed to {module.is_active}")
        return Response({"detail":"Status Changed Successfully"}, status=status.HTTP_200_OK)
        


class ModuleDetailView(APIView):
    permission_classes = [IsSubscribed]

    def get(self, request, id):
        try:
            module = Modules.objects.get(id=id)
        except Modules.DoesNotExist:
            logger.warning(f"Module {id} not found")
            return Response({"error":"Module Does not found"}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            serializer = CourseModuleSerializer(module)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error serializing module {id}")
            return Response({"error":"Error While Fetching Module"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


class ListCourseLessonView(APIView):
    permission_classes = [IsSubscribed]

    def get(self, request, id):
        logger.debug(f"module id: {id}")
        try:
            module = Modules.objects.get(id=id)
        except Modules.DoesNotExist:
            logger.warning(f"Module {id} not found")
            return Response({"error": "Module Not Found"}, status=status.HTTP_404_NOT_FOUND)

        lessons = Lessons.objects.filter(module=module)
        logger.debug(f"Found {lessons.count()} lessons for module {id}")
        
        try:
            serializer = CourseLessonsSerializer(lessons, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error serializing lessons for module {id}")
            return Response({"error": "Error While Fetching Lessons"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class CreateLessonView(APIView):
    permission_classes = [IsSubscribed]

    def post(self, request):
        logger.debug(f"Incoming Data: {request.data}")
        tutor_id = request.user

        # Validate tutor role
        if tutor_id.role != 'tutor':
            logger.warning(f"User {tutor_id.id} is not a tutor")
            return Response({"detail": "Tutor does not exist"}, status=status.HTTP_404_NOT_FOUND)

        try:
            tutor = TutorDetails.objects.get(account=tutor_id)
        except TutorDetails.DoesNotExist:
            logger.warning(f"TutorDetails not found for user {tutor_id.id}")
            return Response({"error": "Tutor not found"}, status=status.HTTP_404_NOT_FOUND)

        # Extract normal form data
        data = dict(request.data)
        module_id = request.data.get('module_id')

        if not module_id:
            logger.warning("Module ID is required")
            return Response({"error": "Module ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            module = Modules.objects.get(id=int(module_id))
        except Modules.DoesNotExist:
            logger.warning(f"Module {module_id} not found")
            return Response({"error": "Module not found"}, status=status.HTTP_404_NOT_FOUND)

        # Convert string fields
        data['title'] = request.data.get('title')
        data['description'] = request.data.get('description')

        # Handle Cloudinary uploads
        try:
            upload_fields = [
                ('thumbnail', 'thumbnail', 'image'),
                ('documents', 'documents', 'auto'),
                ('video', 'videos', 'video'),
            ]

            for field, folder, rtype in upload_fields:
                if field in request.FILES:
                    file_obj = request.FILES[field]
                    upload_result = cloudinary.uploader.upload(
                        file_obj,
                        folder=folder,
                        resource_type=rtype
                    )
                    data[field] = upload_result.get('secure_url')

        except Exception as e:
            logger.exception("Cloudinary upload error")
            return Response(
                {"error": "File upload failed", "details": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create lesson
        serializer = CreateLessonSerializer(
            data=data,
            context={'tutor': tutor, 'module': module}
        )

        if serializer.is_valid():
            serializer.save()
            logger.info(f"Lesson created successfully: {serializer.instance.id} in module {module_id}")
            return Response(
                ListModuleSerializer(serializer.instance).data,
                status=status.HTTP_201_CREATED
            )

        logger.warning(f"Lesson creation validation failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_406_NOT_ACCEPTABLE)



class EditLessonView(APIView):
    permission_classes = [IsSubscribed]
    
    def put(self, request, pk):
        # Verify tutor role
        tutor = request.user
        if tutor.role != 'tutor':
            logger.warning(f"User {tutor.id} is not a tutor")
            return Response({"detail": "Unauthorized: Not a tutor"}, status=status.HTTP_400_BAD_REQUEST)

        # Get lesson
        try:
            lesson = Lessons.objects.get(pk=pk, created_by__account=tutor)
        except Lessons.DoesNotExist:
            logger.warning(f"Lesson {pk} not found or not owned by tutor {tutor.id}")
            return Response({"error": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND)

        # Validate data
        serializer = CreateLessonSerializer(lesson, data=request.data, partial=True)
        if not serializer.is_valid():
            logger.warning(f"Lesson edit validation failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Handle file uploads
        validated_data = serializer.validated_data

        # Upload documents
        if 'documents' in request.FILES:
            documents_file = request.FILES['documents']
            try:
                documents_upload = cloudinary.uploader.upload(
                    documents_file,
                    resource_type="raw",
                    folder="lessons/documents"
                )
                validated_data['documents'] = documents_upload['secure_url']
            except Exception as e:
                logger.exception("Document upload failed")
                return Response({"detail": f"Document upload failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        # Upload thumbnail
        if 'thumbnail' in request.FILES:
            thumbnail_file = request.FILES['thumbnail']
            try:
                thumbnail_upload = cloudinary.uploader.upload(
                    thumbnail_file,
                    resource_type="image",
                    folder="lessons/thumbnails"
                )
                validated_data['thumbnail'] = thumbnail_upload['secure_url']
            except Exception as e:
                logger.exception("Thumbnail upload failed")
                return Response({"detail": f"Thumbnail upload failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        # Upload video
        if 'video' in request.FILES:
            video_file = request.FILES['video']
            try:
                video_upload = cloudinary.uploader.upload(
                    video_file,
                    resource_type="video",
                    folder="lessons/videos"
                )
                validated_data['video'] = video_upload['secure_url']
            except Exception as e:
                logger.exception("Video upload failed")
                return Response({"detail": f"Video upload failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        # Update lesson
        serializer.save()
        logger.info(f"Lesson {pk} updated successfully")
        return Response(CourseLessonsSerializer(lesson).data, status=status.HTTP_200_OK)



class LessonStatusView(APIView):
    permission_classes = [IsSubscribed]

    def post(self, request, lessonId):
        try:
            lesson = Lessons.objects.get(id=lessonId)
        except Lessons.DoesNotExist:
            logger.warning(f"Lesson {lessonId} not found")
            return Response({"error":"Lesson Not Found"}, status=status.HTTP_404_NOT_FOUND)
        
        lesson.is_active = not lesson.is_active
        lesson.save()
        logger.info(f"Lesson {lessonId} status changed to {lesson.is_active}")
        return Response({"detail":"Status Changed Successfully"}, status=status.HTTP_200_OK)
        


class SetCourseDraftView(APIView):
    permission_classes = [IsSubscribed]
    
    def post(self, request, id):
        try:
            course = Course.objects.get(id=id)
        except Course.DoesNotExist:
            logger.warning(f"Course {id} not found")
            return Response({"error":"Course Doest Not Exists"}, status=status.HTTP_404_NOT_FOUND)
        
        course.is_draft = not course.is_draft
        course.save()
        logger.info(f"Course {id} draft status changed to {course.is_draft}")
        return Response({"message":"Course Set To Draft Successfully"}, status=status.HTTP_200_OK)
   
   
   
class CourseRejectionHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        courses = Course.objects.filter(created_by__account=user)
        logger.debug(f"Fetching rejection history for {courses.count()} courses for user {user.id}")

        rejected_courses = []

        for course in courses:
            logs = CourseRejectionHistory.objects.filter(course=course).order_by("-created_at")

            if logs.exists():
                rejected_courses.append({
                    "course_id": course.id,
                    "course_title": course.title,
                    "rejections": [
                        {
                            "id": log.id,
                            "reason": log.reason,
                            "created_at": log.created_at,
                            "admin": log.admin.full_name() if log.admin else None,
                        }
                        for log in logs
                    ]
                })

        return Response({"rejected_courses": rejected_courses}, status=200)



class ModuleRejectionHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        modules = Modules.objects.filter(course_id=course_id)
        logger.debug(f"Fetching rejection history for {modules.count()} modules in course {course_id}")

        rejected_modules = []

        for module in modules:
            if ModuleRejectionHistory.objects.filter(module=module).exists():
                rejected_modules.append({
                    "module_id": module.id,
                    "module_title": module.title,
                    "rejections": [
                        {
                            "id": r.id,
                            "reason": r.reason,
                            "created_at": r.created_at,
                            "admin": r.admin.full_name() if r.admin else None,
                        }
                        for r in ModuleRejectionHistory.objects.filter(module=module)
                    ],
                })

        return Response({"rejected_modules": rejected_modules}, status=200)



class LessonRejectionHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, module_id):
        lessons = Lessons.objects.filter(module_id=module_id)
        logger.debug(f"Fetching rejection history for {lessons.count()} lessons in module {module_id}")

        rejected_lessons = []

        for lesson in lessons:
            if LessonRejectionHistory.objects.filter(lesson=lesson).exists():
                rejected_lessons.append({
                    "lesson_id": lesson.id,
                    "lesson_title": lesson.title,
                    "rejections": [
                        {
                            "id": r.id,
                            "reason": r.reason,
                            "created_at": r.created_at,
                            "admin": r.admin.full_name() if r.admin else None,
                        }
                        for r in LessonRejectionHistory.objects.filter(lesson=lesson)
                    ],
                })

        return Response({"rejected_lessons": rejected_lessons}, status=200)



class SheduleMeetingView(APIView):
    permission_classes = [IsSubscribed]

    def post(self, request):
        try:
            serializer = SheduleMeetingSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            logger.warning(f"Meeting schedule validation failed: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tutor = TutorDetails.objects.get(account=request.user)
        except TutorDetails.DoesNotExist:
            logger.warning(f"TutorDetails not found for user {request.user.id}")
            return Response({"error": "Tutor does not exist"}, status=status.HTTP_404_NOT_FOUND)

        date = serializer.validated_data["date"]
        time = serializer.validated_data["time"]
        limit = serializer.validated_data["limit"]

        if Meetings.objects.filter(tutor=tutor, date=date, time=time).exists():
            logger.warning(f"Meeting already exists for tutor {tutor.id} at {date} {time}")
            return Response(
                {"error": "A meeting at this date & time already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                meeting = Meetings.objects.create(
                    tutor=tutor,
                    date=date,
                    time=time,
                    limit=limit,
                    left=limit,
                )

                meeting_dt = timezone.make_aware(
                    datetime.combine(meeting.date, meeting.time),
                    timezone.get_default_timezone(),
                )

                if meeting_dt <= timezone.now():
                    raise ValueError("Meeting time must be in the future.")

                eligible_users = UserCourseEnrollment.objects.filter(
                    course__created_by=tutor,
                    status__in=["pending", "progress"]
                ).select_related("user")

                user_ids = list(eligible_users.values_list("user__id", flat=True))

                transaction.on_commit(
                    lambda: send_meeting_created_to_users.delay(user_ids, meeting.id)
                )

                transaction.on_commit(
                    lambda: mark_meeting_complete.apply_async(
                        (meeting.id,), eta=meeting_dt + timedelta(minutes=15)
                    )
                )

            logger.info(f"Meeting {meeting.id} scheduled successfully by tutor {tutor.id}")
            return Response(
                {"message": "Meeting scheduled successfully"},
                status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            logger.warning(f"Invalid meeting time: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error creating meeting")
            return Response({"error": "Error scheduling meeting"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class EditMeetingView(APIView):
    permission_classes = [IsSubscribed]

    def post(self, request):
        meeting_id = request.data.get("meeting_id")
        if not meeting_id:
            logger.warning("Meeting ID is required")
            return Response({"error": "Meeting ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            meeting = Meetings.objects.get(id=meeting_id, is_completed=False)
        except Meetings.DoesNotExist:
            logger.warning(f"Meeting {meeting_id} not found or already completed")
            return Response({"error": "Meeting does not exist"}, status=status.HTTP_404_NOT_FOUND)

        old_date = meeting.date
        old_time = meeting.time

        date_changed = False
        time_changed = False

        date_str = request.data.get("date")
        if date_str:
            try:
                new_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if new_date != meeting.date:
                    meeting.date = new_date
                    date_changed = True
            except ValueError:
                logger.warning(f"Invalid date format: {date_str}")
                return Response({"error": "Invalid date format"}, status=status.HTTP_400_BAD_REQUEST)

        time_str = request.data.get("time")
        if time_str:
            try:
                if len(time_str.split(":")) == 2:
                    new_time = datetime.strptime(time_str, "%H:%M").time()
                else:
                    new_time = datetime.strptime(time_str, "%H:%M:%S").time()

                if new_time != meeting.time:
                    meeting.time = new_time
                    time_changed = True
            except ValueError:
                logger.warning(f"Invalid time format: {time_str}")
                return Response({"error": "Invalid time format"}, status=status.HTTP_400_BAD_REQUEST)

        limit_value = request.data.get("limit")
        if limit_value is not None:
            try:
                new_limit = int(limit_value)
            except ValueError:
                logger.warning(f"Invalid limit value: {limit_value}")
                return Response({"error": "Limit must be numeric"}, status=status.HTTP_400_BAD_REQUEST)

            booked_count = meeting.limit - meeting.left
            if new_limit < booked_count:
                logger.warning(f"Limit {new_limit} cannot be less than booked users {booked_count}")
                return Response({"error": "Limit cannot be less than already booked users"}, status=status.HTTP_400_BAD_REQUEST)

            meeting.limit = new_limit
            meeting.left = new_limit - booked_count

        meeting.save()

        booked_users = MeetingBooking.objects.filter(
            meeting=meeting,
            meeting_completed=False
        ).select_related("user")

        if (date_changed or time_changed) and booked_users.exists():
            for booking in booked_users:
                send_meeting_rescheduled_email.delay(meeting.id, booking.user.id)
                try:
                    send_notification(
                        booking.user,
                        "Your meeting was rescheduled by the tutor. Check your email for details."
                    )
                except Exception as e:
                    logger.warning(f"Failed to send notification to user {booking.user.id}: {e}")

        logger.info(f"Meeting {meeting_id} edited successfully")
        return Response({"details": "Meeting edited successfully"}, status=status.HTTP_200_OK)



class DeleteMeetingView(APIView):
    permission_classes = [IsSubscribed]

    def post(self, request):
        meeting_id = request.data.get("meeting_id")
        if not meeting_id:
            logger.warning("Meeting ID not given")
            return Response({"error": "Meeting ID not given"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            meeting = Meetings.objects.get(id=meeting_id, is_completed=False)
        except Meetings.DoesNotExist:
            logger.warning(f"Meeting {meeting_id} not found or already completed")
            return Response({"error": "Meeting not found"}, status=status.HTTP_404_NOT_FOUND)

        # Build meeting datetime and ensure tz awareness matches 'now'
        naive_dt = datetime.combine(meeting.date, meeting.time)

        if settings.USE_TZ:
            tz = timezone.get_current_timezone()
            meeting_dt = timezone.make_aware(naive_dt, tz) if timezone.is_naive(naive_dt) else naive_dt
            current_dt = timezone.now()
        else:
            meeting_dt = naive_dt
            current_dt = datetime.now()

        # Block deletion within 30 minutes of start
        if meeting_dt - current_dt < timedelta(minutes=30):
            logger.warning(f"Cannot delete meeting {meeting_id} within 30 minutes of start time")
            return Response(
                {"error": "Cannot delete a meeting within 30 minutes of start time."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # If there are bookings: mark completed and email each user
        booked_users = MeetingBooking.objects.filter(meeting=meeting, meeting_completed=False).select_related("user")
        if booked_users.exists():
            meeting.is_completed=True
            meeting.save()

            # send to each user individually
            for booking in booked_users:
                booking.meeting_completed=True
                booking.save()
                send_meeting_cancelled_email.delay(meeting.id, booking.user_id)
                try:
                    send_notification(booking.user, "Your meeting was cancelled by the tutor. Check email for details.")
                except Exception as e:
                    logger.warning(f"Failed to send notification to user {booking.user.id}: {e}")

            logger.info(f"Meeting {meeting_id} cancelled and users notified")
            return Response({"details": "Meeting cancelled and users notified."}, status=status.HTTP_200_OK)

        # No bookings: delete record
        meeting.delete()
        logger.info(f"Meeting {meeting_id} deleted successfully (no bookings)")
        return Response({"details": "Meeting deleted successfully (no bookings)."}, status=status.HTTP_200_OK)
            
            

class SheduledMeetings(APIView):
    permission_classes = [IsSubscribed]
    
    def get(self, request):
        try:
            tutor = TutorDetails.objects.get(account=request.user)
        except TutorDetails.DoesNotExist:
            logger.warning(f"TutorDetails not found for user {request.user.id}")
            return Response({"error": "Tutor does not exist"}, status=status.HTTP_404_NOT_FOUND)
        
        meetings = Meetings.objects.filter(tutor=tutor, is_completed=False)
        logger.debug(f"Found {meetings.count()} scheduled meetings for tutor {tutor.id}")
        
        try:
            serializer = SheduledMeetingsSerializer(meetings, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Error serializing scheduled meetings")
            return Response({"error": "Error fetching meetings"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


class RecentMeetingsView(APIView):
    permission_classes = [IsSubscribed]
    
    def get(self, request):
        try:
            tutor = TutorDetails.objects.get(account=request.user)
        except TutorDetails.DoesNotExist:
            logger.warning(f"TutorDetails not found for user {request.user.id}")
            return Response({"error": "Tutor does not exist"}, status=status.HTTP_404_NOT_FOUND)
        
        meetings = Meetings.objects.filter(tutor=tutor, is_completed=True)
        logger.debug(f"Found {meetings.count()} recent meetings for tutor {tutor.id}")
        
        try:
            serializer = SheduledMeetingsSerializer(meetings, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Error serializing recent meetings")
            return Response({"error": "Error fetching meetings"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class CourseMonthlyTrendsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, id):
        try:
            course = Course.objects.get(id=id)
        except Course.DoesNotExist:
            logger.warning(f"Course {id} not found")
            return Response({"error": "Course ID does not exist"}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

        enrollments = UserCourseEnrollment.objects.filter(course=course)

        total_users = enrollments.values("user").distinct().count()
        monthly_purchases = enrollments.filter(enrolled_on__gte=start_of_month).count()
        yearly_purchases = enrollments.filter(enrolled_on__gte=start_of_year).count()

        total_revenue = enrollments.aggregate(total=Sum(F("course__price")))["total"] or 0
        monthly_revenue = enrollments.filter(enrolled_on__gte=start_of_month).aggregate(total=Sum(F("course__price")))["total"] or 0
        yearly_revenue = enrollments.filter(enrolled_on__gte=start_of_year).aggregate(total=Sum(F("course__price")))["total"] or 0

        prev_month_start = (start_of_month - timedelta(days=1)).replace(day=1)
        prev_month_end = start_of_month - timedelta(seconds=1)
        prev_month_count = enrollments.filter(enrolled_on__range=(prev_month_start, prev_month_end)).count()

        growth_rate = 0
        if prev_month_count > 0:
            growth_rate = ((monthly_purchases - prev_month_count) / prev_month_count) * 100

        average_revenue_per_user = total_revenue / total_users if total_users > 0 else 0

        monthly_trends_qs = (
            enrollments
            .filter(enrolled_on__year=now.year)
            .annotate(month=TruncMonth("enrolled_on"))
            .values("month")
            .annotate(
                purchases=Count("id"),
                revenue=Sum(F("course__price")),
            )
            .order_by("month")
        )
        monthly_trends = [
            {
                "month": m["month"].strftime("%b %Y"),
                "purchases": m["purchases"],
                "revenue": m["revenue"] or 0
            }
            for m in monthly_trends_qs
        ]

        yearly_trends_qs = (
            enrollments
            .annotate(year=TruncYear("enrolled_on"))
            .values("year")
            .annotate(
                purchases=Count("id"),
                revenue=Sum(F("course__price")),
            )
            .order_by("year")
        )
        yearly_trends = [
            {
                "year": y["year"].year,
                "purchases": y["purchases"],
                "revenue": y["revenue"] or 0
            }
            for y in yearly_trends_qs
        ]

        data = {
            "total_users": total_users,
            "monthly_purchases": monthly_purchases,
            "yearly_purchases": yearly_purchases,
            "total_revenue": round(total_revenue, 2),
            "monthly_revenue": round(monthly_revenue, 2),
            "yearly_revenue": round(yearly_revenue, 2),
            "growth_rate": round(growth_rate, 2),
            "average_revenue_per_user": round(average_revenue_per_user, 2),
            "monthly_trends": monthly_trends,
            "yearly_trends": yearly_trends,
        }

        logger.debug(f"Course monthly trends calculated for course {id}")
        return Response(data, status=status.HTTP_200_OK)