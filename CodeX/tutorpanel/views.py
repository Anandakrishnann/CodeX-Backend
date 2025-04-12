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

# Create your views here.

class TutorProfileView(APIView):
    permission_classes=[IsSubscribed]

    def get(self, request, userId):
        try:
            user = Accounts.objects.get(email=userId)
            profile_picture = user.profile_picture
            try:
                details = TutorDetails.objects.get(account=user)
                profile_picture = details.profile_picture
            except:
                return Response({"error": "Something went wrong"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            userData = {
                "first_name":user.first_name,
                "last_name":user.last_name,
                "email":user.email,
                "phone":user.phone,
                "leetcode_id":user.leetcode_id,
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

    def put(self, request, email):
        try:
            print(f"request.data      {request.data}")
            user = Accounts.objects.get(email=email)
        except Accounts.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CombinedUserProfileSerializer(user, data=request.data)
        if serializer.is_valid():
            updated_user = serializer.save()
            return Response(CombinedUserProfileSerializer(updated_user).data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class UploadTutorProfilePictureView(APIView):
    def post(self, request, email):
        try:
            try:
                user = Accounts.objects.get(email=email)
            except Accounts.DoesNotExist:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            
            try:
                tutor = TutorDetails.objects.get(account=user)
            except Accounts.DoesNotExist:
                return Response({"error": "Tutor not found"}, status=status.HTTP_404_NOT_FOUND)
            

            profile_picture_url = request.data.get("profilePictureUrl")
            if not profile_picture_url:
                return Response({"error": "No profilePictureUrl provided"}, status=status.HTTP_400_BAD_REQUEST)

            tutor.profile_picture = profile_picture_url
            tutor.save()

            return Response(profile_picture_url, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Profile Upload"})




class CreateCourseView(APIView):
    permission_classes = [IsSubscribed]
    def post(self, request):
        try:
            serializer = CreateCourseSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(status=status.HTTP_201_CREATED)
            return Response(
                {"detail": "Data Already Exists.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        except:
            return Response({"detail":"Error while Creating Course"}, status=status.HTTP_400_BAD_REQUEST)


class ListCourseView(APIView):
    permission_classes = [IsSubscribed]

    def get(self, request):
        try:
            course = Course.objects.all()
            return Response(ListCourseSeializer(course, many=True).data, status=status.HTTP_200_OK)
        except:
            return Response({"detail":"Error While Fetching Courses"}, status=status.HTTP_400_BAD_REQUEST)


class EditCourseView(APIView):
    permission_classes = [IsSubscribed]

    def put(self, request, id):
        try:
            try:
                course_id = Course.objects.get(id=id)
            except course_id.DoesNotExist:
                return Response({"detail":"Course Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)

            serializer = EditCourseSerializer(instance=course_id, data=request.data)
            if serializer.is_valid():
                serializer.save()
                course = Course.objects.all()
                return Response(ListCourseSeializer(course, many=True).data, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {"detail": "Category Name Already Exists", "errors": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            print("EditCategoryView Error:", str(e))
            return Response({"detail": "Error While Editing Category"}, status=status.HTTP_400_BAD_REQUEST)


class CourseStatusView(APIView):
    permission_classes = [IsSubscribed]

    def post(self, request):
        try:
            course_id = request.data.get('id')

            if not course_id:
                return Response({"Error":"Id is Required"}, status=status.HTTP_400_BAD_REQUEST)
            
            course = get_object_or_404(Course, id=course_id)

            if not course:
                return Response({"Error":"Course Does Not Exists"}, status=status.HTTP_400_BAD_REQUEST)
            
            course.is_active = not course.is_active
            course.save()
            return Response({"message": "Status updated successfully", "status": course.is_active}, status=status.HTTP_200_OK)
        except:
            return Response({"Error": "Error While Updating the status"}, status=status.HTTP_400_BAD_REQUEST)