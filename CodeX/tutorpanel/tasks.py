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
from Accounts.models import *


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
def send_meeting_created_email(meeting_id):

    meeting = Meetings.objects.select_related("tutor", "tutor__account").get(id=meeting_id)

    tutor_name = meeting.tutor.account.first_name if meeting.tutor and meeting.tutor.account else "Tutor"

    # STEP 1: Find all courses created by this tutor
    tutor_courses = Course.objects.filter(created_by=meeting.tutor)

    # STEP 2: Find users enrolled in these tutor courses
    enrolled_users = UserCourseEnrollment.objects.filter(
        course__in=tutor_courses,
        status="progress"   # user must be actively studying the course
    ).values_list("user_id", flat=True)

    # STEP 3: Filter users with any module in progress
    users_with_module_progress = ModuleProgress.objects.filter(
        user_id__in=enrolled_users,
        status="progress"
    ).select_related("user").values_list("user_id", flat=True).distinct()

    users = Accounts.objects.filter(id__in=users_with_module_progress)

    # Send email to each user
    for user in users:
        html_message = render_to_string("meeting_created_email.html", {
            "name": user.first_name,
            "tutor_name": tutor_name,
            "meeting_date": meeting.date,
            "meeting_time": meeting.time,
        })

        send_mail(
            subject="New Meeting Scheduled by Your Tutor",
            message="",
            from_email=os.getenv("EMAIL_HOST_USER"),
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )


@shared_task
def send_meeting_rescheduled_email(meeting_id, user_id=None):
    bookings = MeetingBooking.objects.filter(meeting_id=meeting_id).select_related("user", "meeting", "meeting__tutor")
    if user_id:
        bookings = bookings.filter(user_id=user_id)

    for booking in bookings:
        user = booking.user
        meeting = booking.meeting

        # Tutor name added here
        tutor_name = meeting.tutor.account.first_name if meeting.tutor and meeting.tutor.account else "Tutor"

        subject = "Meeting Rescheduled by Tutor"

        html_message = render_to_string("meeting_resheduled.html", {
            "name": user.first_name,
            "meeting_date": meeting.date,
            "meeting_time": meeting.time,
            "tutor_name": tutor_name,  # <-- ADDED
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
def send_meeting_cancelled_email(meeting_id, user_id=None):
    bookings = MeetingBooking.objects.filter(meeting_id=meeting_id).select_related("user", "meeting", "meeting__tutor")
    if user_id:
        bookings = bookings.filter(user_id=user_id)

    for booking in bookings:
        user = booking.user
        meeting = booking.meeting

        # Tutor name added here
        tutor_name = meeting.tutor.account.first_name if meeting.tutor and meeting.tutor.account else "Tutor"

        subject = "Meeting Cancelled"

        html_message = render_to_string("meeting_cancelled.html", {
            "name": user.first_name,
            "meeting_date": meeting.date,
            "meeting_time": meeting.time,
            "tutor_name": tutor_name,  # <-- ADDED
        })

        send_mail(
            subject,
            "",
            os.getenv("EMAIL_HOST_USER"),
            [user.email],
            html_message=html_message,
            fail_silently=False
        )
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