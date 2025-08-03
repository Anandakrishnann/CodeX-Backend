from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from datetime import datetime
from tutorpanel.models import MeetingBooking
import os

@shared_task
def send_meeting_invite_email(meeting_id, type="scheduled"):
    bookings = MeetingBooking.objects.filter(meeting_id=meeting_id).select_related("user", "meeting")
    
    for booking in bookings:
        user = booking.user
        meeting = booking.meeting
        subject = f"Meeting {'Reminder' if type != 'scheduled' else 'Scheduled'} with Tutor"
        meeting_link = f"http://localhost:3000/room/{meeting.id}/{user.id}/{user.first_name}"


        html_message = render_to_string("meeting_invite.html", {
            "name": user.first_name,
            "meeting_date": meeting.date,
            "meeting_time": meeting.time,
            "meeting_link": meeting_link,
        })

        send_mail(
            subject,
            "",
            os.getenv("EMAIL_HOST_USER"),
            [user.email],
            html_message=html_message,
            fail_silently=False
        )
