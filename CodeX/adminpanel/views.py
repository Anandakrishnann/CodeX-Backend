from django.shortcuts import get_object_or_404, render
from django.contrib.auth import get_user_model
from rest_framework.views import APIView 
from rest_framework.response import Response 
from rest_framework import status 
from .serializers import TutorApplicationSerializer
from .models import *
from rest_framework.parsers import MultiPartParser, FormParser
import cloudinary.uploader # type: ignore
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
import traceback
import cloudinary.utils # type: ignore
from Accounts.models import *


User = get_user_model()
# Create your views here.

class ListUsers(APIView):
    def get(self, request):
        try:
            users = User.objects.filter(role="user")

            user_data = [{"id": user.id, "email": user.email, "first_name": user.first_name, "last_name":user.last_name, "leetcode_id":user.leetcode_id, "phone":user.phone, "status": bool(user.isblocked), "role":user.role } for user in users]

            response = Response({"users": user_data}, status=200)  # ✅ Ensure we return a Response
            print(response)  # Optional: Debugging

            return response 
        except:
            return Response({"Unauthorized": "Token expired"}, status=401)


class ListTutors(APIView):

    def get(self, request):
        try:
            tutors = User.objects.filter(role="tutor")

            tutor_data = [{"id": tutor.id, "email": tutor.email, "first_name": tutor.first_name, "last_name":tutor.last_name, "leetcode_id":tutor.leetcode_id, "phone":tutor.phone, "status": bool(tutor.isblocked), "role":tutor.role } for tutor in tutors]

            response = Response({"users": tutor_data}, status=200)  # ✅ Ensure we return a Response
            print(response)  # Optional: Debugging

            return response 
        except:
            return Response({"Unauthorized": "Token expired"}, status=401)

class Status(APIView):

    def post(self, request):
        try:
            user_id = request.data.get('id')

            if not user_id:
                return Response({"error": "User ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            user = get_object_or_404(User, id=user_id)

            user.isblocked = not user.isblocked
            user.save()

            return Response({"message": "Status updated successfully", "status": user.isblocked}, status=status.HTTP_200_OK)
        except:
            return Response({"Unauthorized": "Token expired"}, status=401)
        

class TutorStatus(APIView):

    def post(self, request):
        try:
            user_id = request.data.get('id')

            if not user_id:
                return Response({"error": "User ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            user = get_object_or_404(User, id=user_id)

            user.isblocked = not user.isblocked
            user.save()

            return Response({"message": "Status updated successfully", "status": user.isblocked}, status=status.HTTP_200_OK)
        except:
            return Response({"Unauthorized": "Token expired"}, status=401)


class TutorApplicationView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        print(f"data from frontend : {request.data}")
        serializer = TutorApplicationSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TutorApplicationsOverView(APIView):

    def get(self, request, userId):
        try:
            user_application = get_object_or_404(TutorApplications, id=int(userId))  # Ensure ID is an int
            print(f"Found application: {user_application}")
            print(f"userId: {userId}")

            data = {
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
            return Response({"error": str(e)}, status=500)  # Return actual error



class TutorOverView(APIView):

    def get(self, request, userId):
        try:
            tutor = get_object_or_404(Accounts, email=userId)  # Ensure ID is an int
            print(f"Found application: {tutor}")

            deatils = get_object_or_404(TutorDetails, account=tutor)

            data = {
                "username": deatils.full_name,
                "email": tutor.email,
                "date_of_birth": deatils.dob,
                "education": deatils.education,
                "expertise": deatils.expertise,
                "occupation": deatils.occupation,
                "experience": deatils.experience,
                "about":deatils.about,
                "age":deatils.get_age(),
                "phone": tutor.phone,
                "presentation_video": deatils.verification_video if deatils.verification_video else None,
                "verification_file": deatils.verification_file if deatils.verification_file else None,
                "profile_picture": deatils.profile_picture if deatils.profile_picture else None,
                "status":deatils.status
            }
            print(f"data: {data}")

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            print("❌ ERROR OCCURRED:")
            traceback.print_exc()  # Prints full error traceback in logs
            return Response({"error": str(e)}, status=500)  # Return actual error



class AcceptApplicationView(APIView):

    def post(self, request, applicationId):
        try:
            application = get_object_or_404(TutorApplications, id=applicationId)
            
            user = get_object_or_404(Accounts, email=application.email)
            print(f"user object: {user}")

            if not application.dob:
                return Response({"error": "Date of Birth is required"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                tutor = TutorDetails.objects.create(
                    account=user,
                    full_name=application.full_name,
                    dob=application.dob,
                    about=application.about,
                    education=application.education,
                    expertise=application.expertise,
                    occupation=application.occupation,
                    experience=application.experience,
                    profile_picture=application.profile_picture,
                    verification_file=application.verification_file,
                    verification_video=application.verification_video,
                    status="verified"
                )
                print(f"Tutor Created: {tutor}")
            except Exception as e:
                print(f"Error While Creating Tutor: {e}")
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            user.role = "tutor"
            user.save()
            application.status = "accepted"
            application.save()

            return Response({"success": "Tutor Data added successfully"}, status=status.HTTP_201_CREATED)
        except Exception as e:
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
                user = User.objects.get(email=email)
            except Accounts.DoesNotExist:
                return Response({"error":"Account not found"}, status=status.HTTP_404_NOT_FOUND)
            
            # serializer =  
        except Exception as e:
            return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)