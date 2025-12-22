from django.db import models
from Accounts.models import *

# Create your models here.

class ChatRoom(models.Model):
    user = models.ForeignKey(Accounts, on_delete=models.CASCADE, related_name="user_rooms")
    tutor = models.ForeignKey(Accounts, on_delete=models.CASCADE, related_name="tutor_rooms")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "tutor")



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

    class Meta:
        indexes = [
            models.Index(fields=['room']),
            models.Index(fields=['sender']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['is_read']),
            models.Index(fields=['room', 'timestamp']),
            models.Index(fields=['sender', 'is_read']),
        ]



class CallSession(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="call_sessions")
    caller = models.ForeignKey(Accounts, on_delete=models.CASCADE, related_name="outgoing_calls")
    callee = models.ForeignKey(Accounts, on_delete=models.CASCADE, related_name="incoming_calls")
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    call_type = models.CharField(max_length=10, choices=[('video', 'Video'), ('audio', 'Audio')], default='video')
    status = models.CharField(max_length=10, choices=[('missed', 'Missed'), ('completed', 'Completed')], default='missed')

    class Meta:
        indexes = [
            models.Index(fields=['room']),
            models.Index(fields=['caller']),
            models.Index(fields=['callee']),
            models.Index(fields=['status']),
            models.Index(fields=['started_at']),
            models.Index(fields=['caller', 'status']),
            models.Index(fields=['room', 'started_at']),
        ]
