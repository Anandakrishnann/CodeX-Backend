from rest_framework import serializers # type: ignore
from Accounts.models import *
from .models import *


class EditUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accounts
        fields = ['first_name', 'last_name', 'phone', 'leetcode_id'] 

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accounts
        fields = ['first_name', 'last_name', 'phone', 'leetcode_id']



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
        fields = ["name", "title", "description", "requirements", "benefits", "price"]

    def validate_name(self, value):
        if Course.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Course with this name already exists.")
        return value


class EditCourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['name', "category_id", "title", "description", "requirements", "benefits", "price"]
        
    def validate_name(self, value):
        if Course.objects.filter(name__iexact=value).exclude(id=getattr(self.instance, 'id', None)).exists():
            raise serializers.ValidationError("Category with this name already exists.")
        return value


class ListCourseSeializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", 'name', "category_id", "title", "description", "requirements", "benefits", "price"]