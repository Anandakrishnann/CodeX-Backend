from rest_framework import serializers
from .models import TutorApplications
from Accounts.models import *
from tutorpanel.models import *



class TutorApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorApplications
        fields = '__all__'



class TutorRejectedSerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorRejectionHistory
        fields = '__all__'



class TutorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accounts
        fields = '__all__'



class EditUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accounts
        fields = ['first_name', 'last_name', 'phone', 'leetcode_id']
    
    def update(self, instance, validated_data):
        return super().update(instance, validated_data)



class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['name', 'plan_type', 'plan_category', 'price', 'description', 'deactivate']



class PlanListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name', 'plan_type', 'plan_category', 'price', 'description', 'is_active']



class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseCategory
        fields = ['name', 'description']

    def validate_name(self, value):
        if CourseCategory.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Category with this name already exists.")
        return value



class EditCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseCategory
        fields = ['name', 'description']
        
    def validate_name(self, value):
        if CourseCategory.objects.filter(name__iexact=value).exclude(id=getattr(self.instance, 'id', None)).exists():
            raise serializers.ValidationError("Category with this name already exists.")
        return value



class ListCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseCategory
        fields = ['id', 'name', 'description', 'is_active', 'created_at']



class CourseRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = "__all__"     



class CourseModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Modules
        fields = "__all__"



class LessonOverviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lessons
        fields = "__all__"   



class TutorReportSerializer(serializers.ModelSerializer):
    tutor_name = serializers.CharField(source="tutor.full_name", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = TutorReport
        fields = ["id", "tutor", "tutor_name", "user", "user_name", "reason", "is_marked", "created_at"]



class CourseReportSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source="course.name", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = CourseReport
        fields = ["id", "course", "course_name", "user", "user_name", "reason", "is_marked", "created_at"]



class PlatformWalletTransactionSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    tutor_name = serializers.SerializerMethodField()

    class Meta:
        model = PlatformWalletTransaction
        fields = "__all__"

    # Return user's full name
    def get_user_name(self, obj):
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip()
        return None

    # Return tutor's name
    def get_tutor_name(self, obj):
        if obj.tutor:
            return f"{obj.tutor.full_name}".strip()
        return None



class PayoutRequestSerializer(serializers.ModelSerializer):
    
    tutor_name = serializers.SerializerMethodField()
    
    class Meta:
        model = PayoutRequest
        fields = "__all__"
        
    def get_tutor_name(self, obj):
        return obj.tutor.full_name 