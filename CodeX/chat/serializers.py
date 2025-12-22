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
        data = super().to_representation(instance)
        data['first_name'] = data['first_name'] or "Unknown"
        data['last_name'] = data['last_name'] or "User"
        return data



class ChatRoomSerializer(serializers.ModelSerializer):
    receiver_name = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ["id", "created_at", "receiver_name", "unread_count", "last_message"]

    def get_receiver_name(self, obj):
        request = self.context.get("request")
        current_user = request.user
        receiver = obj.tutor if obj.user == current_user else obj.user
        return f"{receiver.first_name or 'Unknown'} {receiver.last_name or 'User'}".strip()

    def get_unread_count(self, obj):
        request = self.context.get("request")
        current_user = request.user
        
        other_user = obj.tutor if obj.user == current_user else obj.user
        
        return Message.objects.filter(
            room=obj,
            sender=other_user,
            is_read=False
        ).count()

    def get_last_message(self, obj):
        last_msg = Message.objects.filter(room=obj).order_by('-timestamp').first()
        
        if not last_msg:
            return None
            
        return {
            'content': last_msg.content,
            'timestamp': last_msg.timestamp.strftime("%H:%M"),
            'is_read': last_msg.is_read,
        }




class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'room', 'sender', 'sender_id', 'content', 'message_type', 'timestamp', 'is_read']
    
    def get_sender(self, obj):
        return {
            'id': obj.sender.id,
            'first_name': obj.sender.first_name,
            'last_name': obj.sender.last_name,
            'role': obj.sender.role
        }