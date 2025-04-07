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

# Create your views here.

class TutorProfileView(APIView):

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
    def put(self, request, email):
        try:
            user = Accounts.objects.get(email=email)
        except Accounts.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CombinedUserProfileSerializer(user, data=request.data)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(CombinedUserProfileSerializer(updated['user']).data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)