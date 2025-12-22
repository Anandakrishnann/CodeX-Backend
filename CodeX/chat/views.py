# chat/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import ChatRoom, Message
from Accounts.models import *
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .serializers import *
from django.db.models import Count
from django.conf import settings
from rest_framework.permissions import AllowAny 
from django.http import JsonResponse
import time, base64, hmac, hashlib, json
from django.views.decorators.csrf import csrf_exempt
import jwt
import logging
from django.db.models import Q

logger = logging.getLogger("codex")



class GetChatRoomView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, tutor_id):
        user = request.user

        try:
            tutor_profile = TutorDetails.objects.get(id=tutor_id)
            tutor = tutor_profile.account
        except TutorDetails.DoesNotExist:
            return Response({"room_id": None})

        room = ChatRoom.objects.filter(
            user=user,
            tutor=tutor
        ).first()

        return Response({"room_id": room.id if room else None})



class SendFirstMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        tutor_id = request.data.get("tutor_id")
        content = request.data.get("content")

        if not content:
            return Response({"error": "Message required"}, status=400)

        try:
            tutor_profile = TutorDetails.objects.get(id=tutor_id)
            tutor = tutor_profile.account
        except TutorDetails.DoesNotExist:
            return Response({"error": "Tutor not found"}, status=404)


        if user.role != "user":
            return Response(
                {"error": "Tutor cannot initiate chat"},
                status=403
            )

        if not UserCourseEnrollment.objects.filter(
            user=user,
            course__created_by=tutor_profile
        ).exists():
            return Response(
                {"error": "Course not purchased"},
                status=403
            )

        room, created = ChatRoom.objects.get_or_create(
            user=user,
            tutor=tutor
        )

        if not room:
            room = ChatRoom.objects.create()
            room.participants.add(user, tutor)

        Message.objects.create(
            room=room,
            sender=user,
            content=content
        )

        return Response({"room_id": room.id}, status=200)



    
class GetRoomParticipantsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        room = get_object_or_404(ChatRoom, id=room_id)
        participants = [room.user, room.tutor]
        serializer = AccountsSerializer(participants, many=True)
        return Response(serializer.data)



class RoomSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        room = get_object_or_404(ChatRoom, id=room_id)
        current_user = request.user

        if current_user == room.user:
            other_user = room.tutor
        elif current_user == room.tutor:
            other_user = room.user
        else:
            return Response(
                {"error": "You are not a participant of this room"},
                status=status.HTTP_403_FORBIDDEN
            )

        last_message = (
            Message.objects
            .filter(room=room)
            .order_by("-timestamp")
            .first()
        )

        unread_count = Message.objects.filter(
            room=room,
            sender=other_user,
            is_read=False
        ).count()

        return Response({
            "participants": [
                {
                    "id": other_user.id,
                    "first_name": other_user.first_name or "Unknown",
                    "last_name": other_user.last_name or "User",
                    "role": other_user.role,
                    "unread_count": unread_count,
                }
            ],
            "last_message": {
                "content": last_message.content if last_message else "",
                "timestamp": (
                    last_message.timestamp.strftime("%H:%M")
                    if last_message else ""
                ),
                "sender_id": last_message.sender.id if last_message else None,
                "is_read": last_message.is_read if last_message else False,
            }
        })



class ChatRoomListView(APIView):
    def get(self, request):
        rooms = ChatRoom.objects.filter(Q(user=request.user) | Q(tutor=request.user))
        logger.debug(f"Found {rooms.count()} chat rooms for user {request.user.id}")
        try:
            serializer = ChatRoomSerializer(rooms, many=True, context={'request': request})
            return Response(serializer.data)
        except Exception as e:
            logger.exception("Error serializing chat rooms")
            return Response({"error": "Error fetching chat rooms"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    

class MessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        room = get_object_or_404(ChatRoom, id=room_id)
        messages = Message.objects.filter(room=room).order_by('timestamp')
        
        unread_messages = messages.filter(is_read=False).exclude(sender=request.user)
        unread_messages.update(is_read=True)

        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)



class ZegoTokenView(APIView):
    def get(self, request, user_id):
        room_id = request.GET.get("room_id")
        if not room_id:
            return JsonResponse({"error": "Missing room_id"}, status=400)

        app_id = int(settings.ZEGOCLOUD_APP_ID)
        server_secret = settings.ZEGOCLOUD_SERVER_SECRET
        effective_time = 3600  # 1 hour

        payload = {
            "app_id": app_id,
            "user_id": str(user_id),
            "room_id": str(room_id),
            "privilege": {
                "room_login": 1,
                "publish_stream": 1,
                "play_stream": 1
            },
            "create_time": int(time.time()),
            "expire_time": int(time.time()) + effective_time,
            "nonce": int(time.time()),
            "token_version": 1
        }

        payload_str = json.dumps(payload, separators=(",", ":"))
        signature = hmac.new(
            server_secret.encode(), payload_str.encode(), hashlib.sha256
        ).digest()
        sig_b64 = base64.b64encode(signature).decode()
        token_raw = f"{sig_b64}:{payload_str}"
        kit_token = base64.b64encode(token_raw.encode()).decode()

        return JsonResponse({"kitToken": kit_token})