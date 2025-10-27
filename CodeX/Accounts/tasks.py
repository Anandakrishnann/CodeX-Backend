from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from datetime import datetime
from tutorpanel.models import MeetingBooking
from django.utils.timezone import now
import traceback
import os

@shared_task
def send_meeting_invite_email(meeting_id, type="scheduled", user_id=None):
    bookings = MeetingBooking.objects.filter(meeting_id=meeting_id).select_related("user", "meeting")
    
    if user_id:
        bookings = bookings.filter(user_id=user_id)

    for booking in bookings:
        user = booking.user
        meeting = booking.meeting
        subject = f"Meeting Reminder with Tutor"
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


@shared_task
def send_meeting_confimation_email(meeting_id, type="scheduled", user_id=None):
    bookings = MeetingBooking.objects.filter(meeting_id=meeting_id).select_related("user", "meeting")
    
    if user_id:
        bookings = bookings.filter(user_id=user_id)

    for booking in bookings:
        user = booking.user
        meeting = booking.meeting
        subject = f"Meeting scheduled with Tutor"

        html_message = render_to_string("meeting_confirmation.html", {
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
def mark_meeting_completed(booking_id):
    print(f"🚀 mark_meeting_completed STARTED {booking_id} at {now()}")
    try:
        booking = MeetingBooking.objects.get(id=booking_id)
        booking.meeting_completed = True
        booking.save()
        print(f"✅ Meeting {booking_id} marked as completed.")
    except MeetingBooking.DoesNotExist:
        print(f"❌ Booking {booking_id} not found.")
    except Exception as e:
        print(f"🔥 ERROR in mark_meeting_completed: {e}")
        traceback.print_exc()
