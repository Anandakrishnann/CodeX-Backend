from rest_framework import serializers # type: ignore
from Accounts.models import *
import hashlib
from django.core.mail import send_mail
from django.contrib.auth import authenticate
import os


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
        fields = ['first_name', 'last_name', 'email', 'phone', 'leetcode_id', 'profile_picture']

class TutorDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorDetails
        exclude = ['id', 'account', 'status', 'verification_file', 'verification_video']

class CombinedUserProfileSerializer(serializers.Serializer):
    user = AccountSerializer()
    tutor = TutorDetailsSerializer()

    def update(self, instance, validated_data):
        # Update Accounts
        user_data = validated_data.get('user', {})
        for attr, value in user_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update TutorDetails
        tutor_data = validated_data.get('tutor', {})
        tutor_instance, created = TutorDetails.objects.get_or_create(account=instance)

        for attr, value in tutor_data.items():
            setattr(tutor_instance, attr, value)
        tutor_instance.full_name = f"{instance.first_name} {instance.last_name}"  # auto-fill
        tutor_instance.save()

        return {
            "user": instance,
            "tutor": tutor_instance
        }

    def to_representation(self, instance):
        tutor_instance = getattr(instance, 'tutor_details', None)
        if tutor_instance.exists():
            tutor_instance = tutor_instance.first()
        else:
            tutor_instance = TutorDetails.objects.filter(account=instance).first()

        return {
            "user": AccountSerializer(instance).data,
            "tutor": TutorDetailsSerializer(tutor_instance).data if tutor_instance else {},
        }