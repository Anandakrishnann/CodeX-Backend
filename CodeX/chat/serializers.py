from rest_framework import serializers
from .models import *
from Accounts.models import *
import logging

logger = logging.getLogger(__name__)



class AccountsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accounts
        fields = ['id', 'first_name', 'last_name', 'role']

    def to_representation(self, instance):
        # Ensure participant data is always valid
        data = super().to_representation(instance)
        data['first_name'] = data['first_name'] or "Unknown"
        data['last_name'] = data['last_name'] or "User"
        return data



class ChatRoomSerializer(serializers.ModelSerializer):
    participants = AccountsSerializer(many=True, read_only=True)
    receiver_name = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ['id', 'participants', 'created_at', 'receiver_name']

    def get_receiver_name(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            logger.warning(f"No authenticated user for room {obj.id}")
            return "Chat Room"

        current_user = request.user
        current_user_name = f"{current_user.first_name} {current_user.last_name}".strip().lower()
        logger.debug(f"Room {obj.id} - Current user: {current_user.id}, name: {current_user_name}")

        participants = obj.participants.all()
        if len(participants) < 2:
            logger.warning(f"Room {obj.id} has fewer than 2 participants: {[p.id for p in participants]}")
            return "Chat Room"

        for participant in participants:
            first_name = participant.first_name or "Unknown"
            last_name = participant.last_name or "User"
            participant_name = f"{first_name} {last_name}".strip().lower()
            logger.debug(f"Room {obj.id} - Participant {participant.id}: {participant_name}")
            if participant_name != current_user_name:
                return f"{first_name} {last_name}".strip()
        logger.warning(f"Room {obj.id} - No receiver found, participants: {[p.id for p in participants]}")
        return "Chat Room"



class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.StringRelatedField()
    class Meta:
        model = Message
        fields = ['id', 'room', 'sender', 'content', 'message_type', 'timestamp', 'is_read']