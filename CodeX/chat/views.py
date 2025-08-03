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

class GetOrCreateChatRoomView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user1 = request.user
        user2_id = request.data.get("user2_id")

        if not user2_id:
            return Response({"error": "Tutor user ID is required."}, status=400)

        try:
            user2 = Accounts.objects.get(id=user2_id)
        except Accounts.DoesNotExist:
            return Response({"error": "User not found."}, status=404)

        if not TutorDetails.objects.filter(account=user2).exists():
            return Response({"error": "Not a tutor."}, status=400)

        tutor_profile = TutorDetails.objects.get(account=user2)

        # Check if user1 has purchased the tutor's course
        has_purchased = UserCourseEnrollment.objects.filter(
            user=user1,
            course__created_by=tutor_profile
        ).exists()

        if not has_purchased:
            return Response({"error": "Course not purchased."}, status=403)


        chat_rooms = ChatRoom.objects.annotate(num_participants=Count('participants')).filter(
            num_participants=2,
            participants=user1
        )

        for room in chat_rooms:
            participant_ids = set(room.participants.values_list("id", flat=True))
            if participant_ids == {user1.id, user2.id}:
                return Response({"room_id": room.id}, status=200)

        # ✅ Create a new room if not found
        room = ChatRoom.objects.create()
        room.participants.add(user1, user2)

        return Response({"room_id": room.id}, status=200)
    

class GetRoomParticipantsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        room = get_object_or_404(ChatRoom, id=room_id)
        participants = room.participants.all()
        serializer = AccountsSerializer(participants, many=True)
        return Response(serializer.data)


class RoomSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        try:
            room = ChatRoom.objects.get(id=room_id)
            print("room id is this ", room)
            participants = room.participants.all()
            current_user = request.user

            # Get the last message in the room
            last_message = Message.objects.filter(room=room).order_by('-timestamp').first()

            # Prepare participant data with unread count and last message
            participant_data = []
            for participant in participants:
                if participant != current_user:  # Exclude current user
                    unread_count = Message.objects.filter(
                        room=room,
                        is_read=False,
                        sender=participant
                    ).exclude(sender=current_user).count()
                    
                    participant_data.append({
                        'id': participant.id,
                        'first_name': participant.first_name,
                        'last_name': participant.last_name,
                        'role': participant.role,
                        'unread_count': unread_count,
                        'last_message': {
                            'content': last_message.content if last_message else '',
                            'timestamp': last_message.timestamp.strftime('%H:%M') if last_message else '',
                            'is_read': last_message.is_read if last_message else False
                        }
                    })

            return Response({
                'participants': participant_data,
                'last_message': {
                    'content': last_message.content if last_message else '',
                    'timestamp': last_message.timestamp.strftime('%H:%M') if last_message else '',
                    'sender_id': last_message.sender.id if last_message else None,
                    'is_read': last_message.is_read if last_message else False
                }
            })
        except ChatRoom.DoesNotExist:
            print(f"Room {room_id} not found")
            return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error in RoomSummaryView: {str(e)}")
            return Response({"error": "Error fetching room summary"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatRoomListView(APIView):
    def get(self, request):
        try:
            rooms = ChatRoom.objects.filter(participants=request.user)
            serializer = ChatRoomSerializer(rooms, many=True, context={'request': request})
            return Response(serializer.data)
        except Exception as e:
            return Response(str(e), status=status.HTTP_400_BAD_REQUEST)
    

class MessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        room = get_object_or_404(ChatRoom, id=room_id)
        messages = Message.objects.filter(room=room).order_by('timestamp')
        
        # Mark unread messages as read for the current user (recipient)
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