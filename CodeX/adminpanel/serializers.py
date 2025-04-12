from rest_framework import serializers
from .models import TutorApplications
from Accounts.models import *

class TutorApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorApplications
        fields = '__all__'

    def create(self, validated_data):
        return TutorApplications.objects.create(**validated_data)



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
        fields = ['name', 'plan_type', 'plan_category', 'price', 'description']



class PlanListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name', 'plan_type', 'plan_category', 'price', 'description']


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