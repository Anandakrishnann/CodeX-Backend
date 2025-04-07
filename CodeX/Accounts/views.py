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


User = get_user_model()

class UserRegisterView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {"message": "User registered successfully. Please check your email for OTP."},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class OTPVerificationView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)

        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class ResendOTPView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        if serializer.is_valid():
            return Response(
                {"message": "OTP has been resent to your email."},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            print(f"user     {user}")

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            response = Response(
                {
                    "message": "Login successful",
                    "user": {
                        'id': user.id,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'email': user.email,
                        'leetcode_id': user.leetcode_id,
                        'phone': user.phone,
                        'role': user.role,
                        'streak':user.streak,
                        'is_superuser': user.is_superuser,
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



# class CustomTokenRefreshView(TokenRefreshView):
#     permission_classes = [AllowAny]

#     def post(self, request, *args, **kwargs):
#         refresh_token = request.COOKIES.get("refresh_token")

#         if not refresh_token:
#             return Response({"error": "Refresh token missing"}, status=status.HTTP_401_UNAUTHORIZED)

#         request.data["refresh"] = refresh_token
#         response = super().post(request, *args, **kwargs)

#         if "access" in response.data:
#             response.set_cookie(
#                 key="access_token",
#                 value=response.data["access"],
#                 httponly=True,
#                 secure=False,
#                 samesite="None",
#                 max_age=1800  # 30 minutes
#             )
#         else:
#             return Response({"error": "Invalid refresh token"}, status=status.HTTP_401_UNAUTHORIZED)

#         return response


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
                print("Token blacklisting error:", e)

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




class UserProfileView(APIView):

    def get(self, request, userId):
        try:
            user = User.objects.get(email=userId)
            profile_picture = user.profile_picture
            try:
                details = TutorDetails.objects.get(account=user)
                
            except:
                print("No Profile Picture")
            userData = {
                "first_name":user.first_name,
                "last_name":user.last_name,
                "email":user.email,
                "phone":user.phone,
                "leetcode_id":user.leetcode_id,
                "streak":user.streak,
                "last_completed":user.last_completed_task,
                "profile_picture": user.profile_picture
            }
            print(userData)
            return Response(userData, status=status.HTTP_200_OK)
        except Exception as e:
            print("❌ ERROR OCCURRED:")
            return Response({"error": str(e)}, status=500)  # Return actual error


class EditUserView(APIView):
    def put(self, request, email):
        try:
            user = Accounts.objects.get(email=email)
        except Accounts.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = EditUserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()

            data = {
                "first_name":user.first_name,
                "last_name":user.last_name,
                "email":user.email,
                "phone":user.phone,
                "leetcode_id":user.leetcode_id,
                "streak":user.streak,
                "last_completed":user.last_completed_task,
                "profile_picture": user.profile_picture
            }
            
            return Response(data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)