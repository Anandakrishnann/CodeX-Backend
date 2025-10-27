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


class TutorDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            
            tutor = TutorDetails.objects.get(account=request.user)

            print(f"✅ Tutor found: {tutor.id} - {tutor}")

            # Fetch tutor’s courses
            courses = Course.objects.filter(created_by=tutor)
            print(f"📚 Found {courses.count()} courses for this tutor")

            total_courses = courses.count()
            active_courses = courses.filter(is_active=True).count()
            draft_courses = courses.filter(is_draft=True).count()

            pending_courses = courses.filter(status='pending').count()
            accepted_courses = courses.filter(status='accepted').count()
            rejected_courses = courses.filter(status='rejected').count()

            # Enrollments and revenue
            enrollments = UserCourseEnrollment.objects.filter(course__in=courses)
            print(f"👥 Total enrollments: {enrollments.count()}")

            total_students = enrollments.values('user').distinct().count()
            completed_students = enrollments.filter(status='completed').count()
            ongoing_students = enrollments.filter(status='progress').count()

            total_revenue = enrollments.aggregate(total=Sum('course__price'))['total'] or 0
            monthly_revenue = enrollments.filter(
                enrolled_on__month=timezone.now().month
            ).aggregate(total=Sum('course__price'))['total'] or 0

            avg_progress = enrollments.aggregate(avg=Avg('progress'))['avg'] or 0

            print(f"💰 Total revenue: {total_revenue}, Monthly revenue: {monthly_revenue}")
            print(f"📈 Average progress: {avg_progress}")

            recent_enrollments = (
                enrollments.select_related('user', 'course')
                .order_by('-enrolled_on')[:5]
                .values('user__first_name', 'user__last_name', 'course__title', 'enrolled_on', 'status')
            )

            print(f"🕓 Recent enrollments fetched: {len(recent_enrollments)}")

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

            print("✅ TutorDashboardView executed successfully.")
            return Response(data, status=200)

        except Exception as e:
            print("❌ ERROR in TutorDashboardView:", e)
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)


class TutorSubscribedCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tutor = get_object_or_404(TutorDetails, account=request.user)
            is_subscribed = TutorSubscription.objects.filter(tutor=tutor).exists()
            return Response({"subscribed": is_subscribed}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"subscribed": False}, status=status.HTTP_200_OK)



class TutorProfileView(APIView):
    permission_classes=[IsSubscribed]

    def get(self, request):
        try:
            user = request.user
            profile_picture = user.profile_picture
            try:
                details = TutorDetails.objects.get(account=user)
                profile_picture = details.profile_picture
            except:
                return Response({"error": "Tutor Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)
            
            userData = {
                "first_name":user.first_name,
                "last_name":user.last_name,
                "email":user.email,
                "phone":user.phone,
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
            print(userData)
            return Response(userData, status=status.HTTP_200_OK)
        except Exception as e:
            print("❌ ERROR OCCURRED:")
            return Response({"error": str(e)}, status=500)  # Return actual error



class EditTutorView(APIView):
    permission_classes = [IsSubscribed]

    def put(self, request):
        try:
            user = request.user
        
            serializer = CombinedUserProfileSerializer(user, data=request.data)
            if serializer.is_valid():
                updated_user = serializer.save()
                return Response(CombinedUserProfileSerializer(updated_user).data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)



class UploadTutorProfilePictureView(APIView):
    def post(self, request):
        try:
            user = request.user

            try:
                tutor = TutorDetails.objects.get(account=user)
            except TutorDetails.DoesNotExist:
                return Response({"error": "Tutor not found"}, status=status.HTTP_404_NOT_FOUND)

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
            tutor.profile_picture = profile_picture_url
            tutor.save()

            return Response(profile_picture_url, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "Error While Profile Upload", "details": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class CreateCourseView(APIView):
    permission_classes = [IsSubscribed]  # Use AllowAny for testing if needed

    def post(self, request):
        try:
            tutor = request.user
            if not tutor.role == 'tutor':
                return Response({"detail": "Tutor Details Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)
            
            try:
                tutor_detail = TutorDetails.objects.get(account=tutor, status="verified")
            except TutorDetails.DoesNotExist:
                return Response({"detail": "Tutor Details Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)

            category_id = request.data.get("category_id")  # Use .get() to avoid KeyError
            if not category_id:
                return Response({"detail": "Category ID is required"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                category = CourseCategory.objects.get(id=category_id, is_active=True)
            except CourseCategory.DoesNotExist:
                return Response({"detail": "Category Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)

            serializer = CreateCourseSerializer(data=request.data, context={'tutor': tutor_detail, 'category': category})
            if serializer.is_valid():
                course = serializer.save()

                return Response({"id": course.id}, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {"detail": "Invalid data", "errors": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            print(f"Error: {e}")  # Log the error for debugging
            return Response({"detail": "Error while Creating Course"}, status=status.HTTP_400_BAD_REQUEST)



def get_course_levels(request):
    levels = [{"id": key, "name": value} for key, value in Course.CHOICES]
    return JsonResponse(levels, safe=False)



class ListCourseView(APIView):
    permission_classes = [IsSubscribed]

    def get(self, request):
        try:
            tutor = request.user
            if not tutor.role == 'tutor':
                return Response({"detail": "Tutor Details Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)
            
            try:
                tutor_details = TutorDetails.objects.get(account=tutor)
            except Accounts.DoesNotExist:
                return Response({"error":"Tutor Details Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)
            

            courses = Course.objects.filter(created_by=tutor_details)
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
                    "status": course.status,
                })

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            print("ERROR:", str(e))
            return Response({"detail": "Error while fetching courses", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class EditCourseView(APIView):
    permission_classes = [IsSubscribed]

    def put(self, request, id):
        print("request data", request.data)
        try:
            try:
                course_instance = Course.objects.get(id=id)
            except Course.DoesNotExist:
                return Response({"detail": "Course Does Not Exist"}, status=status.HTTP_404_NOT_FOUND)

            serializer = EditCourseSerializer(instance=course_instance, data=request.data)
            if serializer.is_valid():
                serializer.save()
                
                course_instance.status = 'pending'
                course_instance.save()
                
                courses = Course.objects.all()

                return Response(ListCourseSerializer(courses, many=True).data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"detail": "Validation Error", "errors": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            print("EditCourseView Error:", str(e))
            return Response({"detail": "Error While Editing Course"}, status=status.HTTP_400_BAD_REQUEST)



class CourseStatusView(APIView):
    permission_classes = [IsSubscribed]

    def post(self, request, id):
        try:
            print(id)
            course = get_object_or_404(Course, id=id)

            if not course:
                return Response({"Error":"Course Does Not Exists"}, status=status.HTTP_400_BAD_REQUEST)
            
            course.is_active = not course.is_active
            course.save()
            return Response({"message": "Status updated successfully", "status": course.is_active}, status=status.HTTP_200_OK)
        except:
            return Response({"Error": "Error While Updating the status"}, status=status.HTTP_400_BAD_REQUEST)



class CourseOverView(APIView):
    permission_classes = [IsSubscribed]

    def get(self, request, id):
        try:
            try:
                course = get_object_or_404(Course, id=id)
            except Course.DoesNotExist:
                return Response({"error": "Course Not Found"}, status=status.HTTP_404_NOT_FOUND)

            return Response(CourseDetailsSerializer(course).data, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error fetching course overview: {e}")
            return Response({"error": "Something went wrong"}, status=status.HTTP_400_BAD_REQUEST)



class ListCourseModulesView(APIView):
    permission_classes = [IsSubscribed]
    
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
     


class CreateModuleView(APIView):
    permission_classes = [IsSubscribed]

    def post(self, request):
        try:
            tutor = request.user
            if not tutor.role == 'tutor':
                return Response({"detail": "Tutor Details Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)
            
            
            try:
                tutor_detail = TutorDetails.objects.get(account=tutor)
            except TutorDetails.DoesNotExist:
                return Response({"details":"Tutor Details Does not exists"}, status=status.HTTP_404_NOT_FOUND)
            
            course_id = request.data.pop("course_id")
            try:
                course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                return Response({"details":"course Does not exists"}, status=status.HTTP_404_NOT_FOUND)
            serializer = CreateModuleSerializer(data=request.data, context={'tutor': tutor_detail, 'course': course})
            if serializer.is_valid():
                serializer.save()
                return Response(ListModuleSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_406_NOT_ACCEPTABLE)
        except:
            return Response({"details":"Error While Creating Course"}, status=status.HTTP_400_BAD_REQUEST)
        


class EditModuleView(APIView):
    permission_classes = [IsSubscribed]
    
    def put(self, request, id):
        try:
            module = get_object_or_404(Modules, id=id)
            
            serializer = EditModuleSerializer(instance=module, data=request.data)
            if serializer.is_valid():
                serializer.save()
                module.status = 'pending'
                module.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print("Edit error:", e)
            return Response({"error": "Error While Editing"}, status=status.HTTP_400_BAD_REQUEST)



class ModuleStatusView(APIView):
    permission_classes = [IsSubscribed]
    
    def post(self, request, id):
        try:
            module = get_object_or_404(Modules, id=id)

            if not module:
                return Response({"error":"Module Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            module.is_active = not module.is_active
            module.save()
            return Response({"detail":"Status Changed Successfully"}, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Changing Module Status"}, status=status.HTTP_400_BAD_REQUEST)
        


class ModuleDetailView(APIView):
    permission_classes = [IsSubscribed]

    def get(self, request, id):
        try:
            module = get_object_or_404(Modules, id=id)

            if not module:
                return Response({"error":"Module Does not found"}, status=status.HTTP_404_NOT_FOUND)
            
            return Response(CourseModuleSerializer(module).data, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Fetching Module"}, status=status.HTTP_400_BAD_REQUEST)
        


class ListCourseLessonView(APIView):
    permission_classes = [IsSubscribed]

    def get(self, request, id):
        try:
            print(id)
            module = get_object_or_404(Modules, id=id)
            lessons = Lessons.objects.filter(module=module)
            
            serializer = CourseLessonsSerializer(lessons, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Modules.DoesNotExist:
            return Response({"error": "Module Not Found"}, status=status.HTTP_404_NOT_FOUND)

        except Lessons.DoesNotExist:
            return Response({"error": "Lessons Not Found"}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": f"Error While Fetching Lessons: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)



class CreateLessonView(APIView):
    permission_classes = [IsSubscribed]

    def post(self, request):
        try:
            tutor_id = request.user
            if not tutor_id.role == 'tutor':
                return Response({"detail": "Tutor Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)   
            
            try:
                tutor = get_object_or_404(TutorDetails, account=tutor_id)
            except TutorDetails.DoesNotExist:
                return Response({"error":"Tutor Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)
            
            module_id = request.data.pop('module_id')

            try:
                module = get_object_or_404(Modules, id=module_id)
            except Modules.DoesNotExist:
                return Response({"error":"Module Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            data = request.data.dict() 
            
            for field in ['title','description']:
                if field in data:
                    data[field] = str(data[field])

            try:
                if 'thumbnail' in request.FILES:
                    thumbnail = request.FILES['thumbnail']
                    upload_result = cloudinary.uploader.upload(thumbnail, folder="thumbnail", resource_type="image")
                    data['thumbnail'] = upload_result.get('secure_url')

                if 'documents' in request.FILES:
                    documents = request.FILES['documents']
                    upload_result = cloudinary.uploader.upload(documents, folder="documents", resource_type="raw")
                    data['documents'] = upload_result.get('secure_url')

                if 'video' in request.FILES:
                    video = request.FILES['video']
                    upload_result = cloudinary.uploader.upload(video, folder="videos", resource_type="video")
                    data['video'] = upload_result.get('secure_url')
                    
            except Exception as e:
                return Response({"error": "File upload failed", "details": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = CreateLessonSerializer(data=data, context={'tutor': tutor, 'module': module})
            if serializer.is_valid():
                serializer.save()
                return Response(ListModuleSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_406_NOT_ACCEPTABLE)
            
        except Exception as e:
            return Response({"detail": f"Error Creating lesson: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)



class EditLessonView(APIView):
    permission_classes = [IsSubscribed]
    
    def put(self, request, pk):
        try:
            # Verify tutor role
            tutor = request.user
            if tutor.role != 'tutor':
                return Response({"detail": "Unauthorized: Not a tutor"}, status=status.HTTP_403_FORBIDDEN)

            # Get lesson
            lesson = get_object_or_404(Lessons, pk=pk, created_by__account=tutor)

            # Validate data
            serializer = CreateLessonSerializer(lesson, data=request.data, partial=True)
            if not serializer.is_valid():
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
                except cloudinary.exceptions.Error as e:
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
                except cloudinary.exceptions.Error as e:
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
                except cloudinary.exceptions.Error as e:
                    return Response({"detail": f"Video upload failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

            # Update lesson
            serializer.save()
            return Response(CourseLessonsSerializer(lesson).data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"detail": f"Error editing lesson: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)



class LessonStatusView(APIView):
    permission_classes = [IsSubscribed]

    def post(self, request, lessonId):
        try:
            lesson = get_object_or_404(Lessons, id=lessonId)

            if not lesson:
                return Response({"error":"Lesson Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            lesson.is_active = not lesson.is_active
            lesson.save()
            return Response({"detail":"Status Changed Successfully"}, status=status.HTTP_200_OK)
        except: 
            return Response({"error":"Error While Changing Lesson Status"}, status=status.HTTP_400_BAD_REQUEST)
        


class SetCourseDraftView(APIView):
    permission_classes = [IsSubscribed]
    
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
        


class SheduleMeetingView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            serializer = SheduleMeetingSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            try:
                tutor = TutorDetails.objects.get(account=request.user)
            except TutorDetails.DoesNotExist:
                return Response({"error": "Tutor does not exist"}, status=status.HTTP_404_NOT_FOUND)

            with transaction.atomic():
                meeting = Meetings.objects.create(
                    tutor=tutor,
                    date=serializer.validated_data['date'],
                    time=serializer.validated_data['time'],
                    limit=serializer.validated_data['limit'],
                    left=serializer.validated_data['limit'],  
                )   

                # Combine and ensure timezone-aware datetime in IST
                meeting_datetime = timezone.make_aware(
                    datetime.combine(meeting.date, meeting.time),
                    timezone=timezone.get_default_timezone() 
                )

                # Ensure meeting is in the future
                current_time = timezone.now()
                if meeting_datetime <= current_time:
                    raise ValueError("Meeting time must be in the future.")

                # Run 1 minute before meeting
                run_time = meeting_datetime - timedelta(minutes=15)


                # Compare with aware current time
                if run_time <= current_time:
                    raise ValueError("Cannot schedule meeting — start time is too soon.")

                # Schedule task and log task ID
                task = mark_meeting_complete.apply_async((meeting.id,), eta=run_time)

                transaction.on_commit(
                    lambda: mark_meeting_complete.apply_async((meeting.id,), eta=run_time)
                )

            return Response(
                {"message": "Meeting scheduled successfully", "task_id": task.id},
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            print(f"Error: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class EditMeetingView(APIView):
    permission_classes = [IsAuthenticated, IsSubscribed]
    
    def post(self, request):
        try:
            print(request.data)
            meeting_id = request.data.get("meeting_id")
            print("meeting id is ", meeting_id)
            if not meeting_id:
                print("meeting id not given")
                return Response({"error": "Meeting ID is required"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                meeting = Meetings.objects.get(id=meeting_id, is_completed=False)
            except Meetings.DoesNotExist:
                print("meeting id is not found")
                return Response({"error": "Meeting does not exist"}, status=status.HTTP_404_NOT_FOUND)

            # Parse and validate date
            date_str = request.data.get("date")
            if date_str:
                try:
                    meeting.date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    return Response({"error": "Invalid date format. Expected YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

            # Parse and validate time
            time_str = request.data.get("time")
            if time_str:
                try:
                    meeting.time = datetime.strptime(time_str, "%H:%M:%S").time()
                except ValueError:
                    return Response({"error": "Invalid time format. Expected HH:MM:SS."}, status=status.HTTP_400_BAD_REQUEST)

            
            
            limit_value = request.data.get("limit")
            if limit_value is not None:
                try:
                    new_limit = int(limit_value)
                except ValueError:
                    return Response({"error": "Limit must be a number."}, status=status.HTTP_400_BAD_REQUEST)

                # Calculate already booked users
                booked_count = meeting.limit - meeting.left  

                # Prevent reducing limit below already booked users
                if new_limit < booked_count:
                    return Response({"error": "Cannot set limit less than already booked users."}, status=status.HTTP_400_BAD_REQUEST)

                meeting.limit = new_limit
                meeting.left = new_limit - booked_count

            meeting.save()

            booked_users = MeetingBooking.objects.filter(
                meeting=meeting,
                meeting_completed = False
            ).select_related("user")
            
            if not booked_users:
                return Response({"error": "booked users not found."}, status=status.HTTP_400_BAD_REQUEST)
            for booking in booked_users:
                send_meeting_rescheduled_email(meeting.id, booking.user.id)

            return Response({"details": "Meeting edited successfully"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class DeleteMeetingView(APIView):
    permission_classes = [IsAuthenticated, IsSubscribed]

    def post(self, request):
        try:
            meeting_id = request.data.get("meeting_id")
            if not meeting_id:
                return Response({"error": "Meeting ID not given"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                meeting = Meetings.objects.get(id=meeting_id, is_completed=False)
            except Meetings.DoesNotExist:
                return Response({"error": "Meeting not found"}, status=status.HTTP_404_NOT_FOUND)

            # Build meeting datetime and ensure tz awareness matches 'now'
            naive_dt = datetime.combine(meeting.date, meeting.time)

            if settings.USE_TZ:
                tz = timezone.get_current_timezone()
                meeting_dt = timezone.make_aware(naive_dt, tz) if timezone.is_naive(naive_dt) else naive_dt
                current_dt = timezone.now()  # aware
            else:
                meeting_dt = naive_dt
                current_dt = datetime.now()  # naive

            # Block deletion within 30 minutes of start
            if meeting_dt - current_dt < timedelta(minutes=30):
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

                return Response({"details": "Meeting cancelled and users notified."}, status=status.HTTP_200_OK)

            # No bookings: delete record
            meeting.delete()
            return Response({"details": "Meeting deleted successfully (no bookings)."}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
            


class SheduledMeetings(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            try:
                tutor = TutorDetails.objects.get(account=request.user)
            except TutorDetails.DoesNotExist:
                
                return Response({"error": "Tutor does not exist"}, status=status.HTTP_404_NOT_FOUND)
            
            meetings = Meetings.objects.filter(tutor=tutor, is_completed=False)
            
            serializer = SheduledMeetingsSerializer(meetings, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        


class RecentMeetingsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            try:
                tutor = TutorDetails.objects.get(account=request.user)
            except TutorDetails.DoesNotExist:
                return Response({"error": "Tutor does not exist"}, status=status.HTTP_404_NOT_FOUND)
            
            meetings = Meetings.objects.filter(tutor=tutor, is_completed=True)
            
            serializer = SheduledMeetingsSerializer(meetings, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CourseMonthlyTrendsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, id):
        try:
            try:
                course = Course.objects.get(id=id)
            except Course.DoesNotExist:
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

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)