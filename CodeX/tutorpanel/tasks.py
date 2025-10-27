# tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from datetime import datetime
from django.utils.timezone import make_aware
from tutorpanel.models import Meetings
from .models import *
import os
from celery import shared_task
from django.utils.timezone import now
import traceback


@shared_task
def mark_meeting_complete(meeting_id):
    print(f"🚀 mark_meeting_complete STARTED {meeting_id} at {now()}")
    try:
        meeting = Meetings.objects.get(id=meeting_id)
        print(f"✅ Found meeting: {meeting}")
        meeting.is_completed = True
        meeting.save()
        print("💾 Saved successfully")
    except Exception as e:
        print(f"🔥 ERROR: {e}")
        traceback.print_exc()


@shared_task
def send_meeting_rescheduled_email(meeting_id, user_id=None):
    bookings = MeetingBooking.objects.filter(meeting_id=meeting_id).select_related("user", "meeting")
    
    if user_id:
        bookings = bookings.filter(user_id=user_id)

    for booking in bookings:
        user = booking.user
        meeting = booking.meeting
        subject = f"Meeting Rescheduled with Tutor"

        html_message = render_to_string("meeting_resheduled.html", {
            "name": user.first_name,
            "meeting_date": meeting.date,
            "meeting_time": meeting.time,
        })

        send_mail(
            subject,
            "",
            os.getenv("EMAIL_HOST_USER"),
            [user.email],
            html_message=html_message,
            fail_silently=False
        )


@shared_task
def send_meeting_cancelled_email(meeting_id, user_id):
    try:
        booking = MeetingBooking.objects.select_related("user", "meeting").get(meeting_id=meeting_id, user_id=user_id)
    except MeetingBooking.DoesNotExist:
        return

    user = booking.user
    meeting = booking.meeting
    subject = "Meeting Cancelled"

    html_message = render_to_string("meeting_cancelled.html", {
        "name": user.first_name,
        "meeting_date": meeting.date,
        "meeting_time": meeting.time,
    })

    send_mail(
        subject,
        "",
        os.getenv("EMAIL_HOST_USER"),
        [user.email],
        html_message=html_message,
        fail_silently=False
    )