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

# Create your views here.

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