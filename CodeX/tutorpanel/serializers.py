from rest_framework import serializers # type: ignore
from datetime import datetime, timedelta
from rest_framework.exceptions import ValidationError
from Accounts.models import *
from .models import *


class EditUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accounts
        fields = ['first_name', 'last_name', 'phone'] 

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance



class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accounts
        fields = ['first_name', 'last_name', 'phone']



class TutorDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorDetails
        fields = ["dob", "education", "expertise", "occupation", "experience", "about"]



class CombinedUserProfileSerializer(serializers.Serializer):
    user = AccountSerializer()
    tutor = TutorDetailsSerializer()

    def to_representation(self, instance):
        """
        Custom representation to combine user and tutor details.
        """
        # Account instance is passed as `instance`
        tutor_instance = TutorDetails.objects.filter(account=instance).first()
        return {
            "user": AccountSerializer(instance).data,
            "tutor": TutorDetailsSerializer(tutor_instance).data if tutor_instance else {}
        }

    def update(self, instance, validated_data):
        # Update Accounts
        user_data = validated_data.get('user', {})
        for attr, value in user_data.items():
            print(f"attr:{attr}, value{value}")
            setattr(instance, attr, value)
        instance.save()
        print(instance)

        tutor_data = validated_data.get('tutor', {})
        tutor_instance, _ = TutorDetails.objects.get_or_create(account=instance)

        for attr, value in tutor_data.items():
            print(f"attr:{attr}, value{value}")
            setattr(tutor_instance, attr, value)
        tutor_instance.full_name = f"{instance.first_name} {instance.last_name}"
        tutor_instance.save()

        return instance



class CreateCourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = '__all__'
        read_only_fields = ['created_by', 'category_id']

    def create(self, validated_data):
        category = self.context['category']
        tutor = self.context['tutor']
        course = Course.objects.create(
            **validated_data,
            created_by=tutor,
            category_id=category
        )
        return course



class EditCourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['name', 'category_id', 'title', 'level', 'description', 'requirements', 'benefits', 'price']

    def validate_name(self, value):
        if Course.objects.filter(name__iexact=value).exclude(id=getattr(self.instance, 'id', None)).exists():
            raise serializers.ValidationError("Course with this name already exists.")
        return value



class ListCourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = '__all__'



class CreateModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Modules
        fields = '__all__'
        read_only_fields = ['created_by', 'course']

    def create(self, validated_data):
        course = self.context['course']
        tutor = self.context['tutor']
        module = Modules.objects.create(
            **validated_data,
            created_by=tutor,
            course=course
        )
        return module



class ListModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Modules
        fields = '__all__'



class EditModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Modules
        fields = ["title", "description"]
        
    def validate_name(self, value):
        if Modules.objects.filter(title__iexact=value).exclude(id=getattr(self.instance, 'id', None)).exists():
            raise serializers.ValidationError("Module with this name already exists.")
        return value



class CourseDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = "__all__"



class CourseModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Modules
        fields = "__all__"
        


class CourseLessonsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lessons
        fields = "__all__"



class CreateLessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lessons
        fields = '__all__'
        read_only_fields = ['created_by', 'module']

    def create(self, validated_data):
        module = self.context['module']
        tutor = self.context['tutor']
        lessons = Lessons.objects.create(
            **validated_data,
            created_by=tutor,
            module=module
        )
        return lessons
    


class SheduleMeetingSerializer(serializers.Serializer):
    date = serializers.DateField()
    time = serializers.TimeField()
    limit = serializers.IntegerField(min_value=1)
    
    def validate(self, data):
        scheduled_datetime = datetime.combine(data["date"], data["time"])
        # if scheduled_datetime < datetime.now() + timedelta(minutes=30):
        #     raise ValidationError("Meeting must be scheduled at least 30 minutes in the future.")
        return data
    


class SheduledMeetingsSerializer(serializers.ModelSerializer):
    tutor_name = serializers.SerializerMethodField()

    class Meta:
        model = Meetings
        fields = ['id', 'tutor', 'date', 'time', 'limit', 'left', 'created_at', 'tutor_name']

    def get_tutor_name(self, obj):
        return obj.tutor.full_name if obj.tutor else None
