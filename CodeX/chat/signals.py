from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import datetime, timedelta
from tutorpanel.models import Meetings
from .tasks import send_meeting_invite_email  # Task is also inside chat/tasks.py

@receiver(post_save, sender=Meetings)
def schedule_meeting_tasks(sender, instance, created, **kwargs):
    if created:
        # 1. Send immediately after scheduling
        send_meeting_invite_email.delay(instance.id, "scheduled")

        # 2. 5 minutes before meeting
        five_min_before = datetime.combine(instance.date, instance.time) - timedelta(minutes=5)
        send_meeting_invite_email.apply_async(args=[instance.id, "5-min-reminder"], eta=five_min_before)

        # 3. Exactly at meeting time
        meeting_time = datetime.combine(instance.date, instance.time)
        send_meeting_invite_email.apply_async(args=[instance.id, "start-now"], eta=meeting_time)
