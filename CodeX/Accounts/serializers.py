from rest_framework import serializers # type: ignore
from .models import *
import hashlib
from django.core.mail import send_mail
from django.contrib.auth import authenticate
import os
from tutorpanel.models import *
from adminpanel.models import *
from django.db.models import Sum, Count, F, Avg



class UserRegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50)
    email = serializers.EmailField()
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate_first_name(self, value):
        if not value.isalpha():
            raise serializers.ValidationError("First name must contain only letters.")
        if len(value) < 2:
            raise serializers.ValidationError("First name is too short.")
        return value

    def validate_last_name(self, value):
        if not value.isalpha():
            raise serializers.ValidationError("Last name must contain only letters.")
        if len(value) < 1:
            raise serializers.ValidationError("Last name is too short.")
        return value

    def validate_phone(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Phone must contain only digits.")
        if len(value) != 10:
            raise serializers.ValidationError("Phone must be 10 digits.")
        return value

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        if value.isdigit():
            raise serializers.ValidationError("Password cannot be only numbers.")
        return value



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
    


class EditUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accounts
        fields = ['first_name', 'last_name', 'phone']

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance



class DashboardCourseSerializer(serializers.ModelSerializer):
    progress = serializers.DecimalField(max_digits=5, decimal_places=2)
    modules_total = serializers.SerializerMethodField()
    modules_completed = serializers.SerializerMethodField()
    lessons_total = serializers.SerializerMethodField()
    lessons_completed = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'level', 'progress', 'status',
            'modules_total', 'modules_completed', 'lessons_total', 'lessons_completed'
        ]

    def get_modules_total(self, obj):
        return obj.modules_set.count()

    def get_modules_completed(self, obj):
        user = self.context['request'].user
        return ModuleProgress.objects.filter(
            user=user, module__course=obj, status='completed'
        ).count()

    def get_lessons_total(self, obj):
        return obj.modules_set.prefetch_related('lessons_set').aggregate(total=Count('lessons'))['total']

    def get_lessons_completed(self, obj):
        user = self.context['request'].user
        return LessonProgress.objects.filter(
            user=user, lesson__module__course=obj, status='completed'
        ).count()



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
        
        

class SheduledMeetingsSerializer(serializers.ModelSerializer):
    tutor_name = serializers.SerializerMethodField()
    course_name = serializers.SerializerMethodField()

    class Meta:
        model = Meetings
        fields = ['id', 'tutor', 'date', 'time', 'limit', 'left', 'created_at', 'tutor_name', 'course_name']

    def get_tutor_name(self, obj):
        return obj.tutor.full_name if obj.tutor else None
    
    def get_course_name(self, obj):
        return obj.course.title if obj.course else None
    


class TutorFeedbackSerializer(serializers.ModelSerializer):
    tutor_name = serializers.CharField(source="tutor.full_name", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = TutorFeedback
        fields = ["id","tutor","tutor_name","user","user_name","rating","review","created_at",]
        read_only_fields = ["id", "created_at", "tutor_name", "user_name"]

    def validate_rating(self, value):
        if value is not None and (value < 1 or value > 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def validate(self, data):
        if not data.get("rating") and not data.get("review"):
            raise serializers.ValidationError("Provide rating or review.")
        return data



class CourseFeedbackSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source="course.name", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = CourseFeedback
        fields = ["id","course","course_name","user","user_name","rating","review","created_at",]
        read_only_fields = ["id", "created_at", "course_name", "user_name"]

    def validate_rating(self, value):
        if value is not None and (value < 1 or value > 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def validate(self, data):
        if not data.get("rating") and not data.get("review"):
            raise serializers.ValidationError("Provide rating or review.")
        return data



class TutorReportSerializer(serializers.ModelSerializer):
    tutor_name = serializers.CharField(source="tutor.full_name", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = TutorReport
        fields = ["id", "tutor", "tutor_name", "user", "user_name", "reason", "created_at"]
        read_only_fields = ["id", "created_at", "tutor_name", "user_name"]



class CourseReportSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source="course.name", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = CourseReport
        fields = ["id", "course", "course_name", "user", "user_name", "reason", "created_at"]
        read_only_fields = ["id", "created_at", "course_name", "user_name"]