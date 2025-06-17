from rest_framework import serializers # type: ignore
from .models import *
import hashlib
from django.core.mail import send_mail
from django.contrib.auth import authenticate
import os
from tutorpanel.models import *
from adminpanel.models import *

class UserRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accounts
        fields = ["first_name", "last_name", "email", "phone", "password"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = Accounts.objects.create(**validated_data)
        user.set_password(password) 
        user.is_active = False
        user.save()

        otp = OTP.generate_otp()
        otp_hash = hashlib.sha256(str(otp).encode()).hexdigest()

        OTP.objects.filter(user=user).delete()
        expires_at = timezone.now() + timedelta(minutes=2)
        OTP.objects.create(user=user, otp=otp_hash, expires_at=expires_at)


        subject = "Your OTP for Verification"
        message = (
            f"Hello {user.first_name},\n\n"
            f"Your OTP for account verification is: {otp}\n\n"
            "This OTP is valid for 2 minutes.\n\n"
            "If you didn't request this, please ignore this email."
        )
        from_email = os.getenv("EMAIL_HOST_USER")
        recipient_list = [user.email]

        send_mail(subject, message, from_email, recipient_list)

        print(f"OTP for {user.email}: {otp}")

        return user



class TutorDetailsSerializer(serializers.ModelSerializer):
    account = serializers.HiddenField(default=serializers.CurrentUserDefault())
    
    class Meta:
        model = TutorDetails
        fields = '__all__'
    
    def create(self, validated_data):
        account = self.context['request'].user
        tutor_details = TutorDetails.objects.create(account=account, **validated_data)
        account.role = 'tutor'
        account.save()
        return tutor_details



class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")
        user = authenticate(email=email, password=password)
        
        if user is None:
            raise serializers.ValidationError("Invalid email or password.")

        if not user.is_active:
            raise serializers.ValidationError("Account is inactive.")
        
        if user.isblocked:
            raise serializers.ValidationError("Account is Blocked.")

        return {"user": user}



class OTPVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)
    def validate(self, data):
        email = data.get("email")
        otp = data.get("otp")
        print(email)
        print(otp)
        try:
            user = Accounts.objects.get(email=email)
            print(user)
            otp_entry = OTP.objects.filter(user=user).latest("created_at")
            print(f"otp_entry{otp_entry}")
        except (Accounts.DoesNotExist, OTP.DoesNotExist):
            raise serializers.ValidationError("Invalid email or OTP.")

        if otp_entry.is_expired():
            raise serializers.ValidationError("OTP has expired.")

        otp_hash = hashlib.sha256(str(otp).encode()).hexdigest()
        print(otp_hash)
        print(otp_hash)
        print(otp_entry.otp)
        print(otp_hash == otp_entry.otp)
        if otp_hash == otp_entry.otp:
            
            user.isblocked = False  
            user.save()

            otp_entry.delete()

            return {"message": "OTP verified successfully", "user_id": user.id}
        else:
            raise serializers.ValidationError("Invalid OTP.")



class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, data):
        email = data.get("email")
        try:
            user = Accounts.objects.get(email=email)
        except Accounts.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")

        OTP.objects.filter(user=user).delete()  
        otp = OTP.generate_otp()
        otp_hash = hashlib.sha256(str(otp).encode()).hexdigest()
        expires_at = timezone.now() + timedelta(minutes=2)
        OTP.objects.create(user=user, otp=otp_hash, expires_at=expires_at)

        print(f"OTP for {user.email}: {otp}")

        return {"message": "OTP has been resent to your email."}
    


class EditUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accounts
        fields = ['first_name', 'last_name', 'phone']

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance



class TutorDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorDetails
        fields = '__all__'



class CourseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseCategory
        fields = '__all__'



class CourseListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = '__all__'



class CourseModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Modules
        fields = '__all__'
        
        
        
class CourseLessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lessons
        fields = '__all__'



class UserCourseEnrollmentSerializer(serializers.ModelSerializer):
    course = CourseListSerializer()

    class Meta:
        model = UserCourseEnrollment
        fields = ['id', 'course', 'status', 'progress', 'enrolled_on']