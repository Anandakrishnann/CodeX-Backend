from rest_framework import serializers
from .models import TutorApplications
from Accounts.models import *

class TutorApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorApplications
        fields = '__all__'

    def create(self, validated_data):
        return TutorApplications.objects.create(**validated_data)


class EditUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accounts
        fields = ['first_name', 'last_name', 'phone', 'leetcode_id']
    
    def update(self, instance, validated_data):
        return super().update(instance, validated_data)