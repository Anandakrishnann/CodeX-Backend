from django.db import models
from Accounts.models import *

# Create your models here.

class ChatRoom(models.Model):
    participants = models.ManyToManyField(Accounts, related_name="chat_rooms")
    created_at = models.DateTimeField(auto_now_add=True)


class Message(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(Accounts, on_delete=models.CASCADE)
    content = models.TextField(blank=True)
    message_type = models.CharField(
        max_length=10,
        choices=[('text', 'Text'), ('call', 'Call')],
        default='text'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)



class CallSession(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="call_sessions")
    caller = models.ForeignKey(Accounts, on_delete=models.CASCADE, related_name="outgoing_calls")
    callee = models.ForeignKey(Accounts, on_delete=models.CASCADE, related_name="incoming_calls")
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    call_type = models.CharField(max_length=10, choices=[('video', 'Video'), ('audio', 'Audio')], default='video')
    status = models.CharField(max_length=10, choices=[('missed', 'Missed'), ('completed', 'Completed')], default='missed')
