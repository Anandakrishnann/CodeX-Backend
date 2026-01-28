import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.apps import apps
from django.contrib.auth.models import AnonymousUser
from notifications.utils import send_notification

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")

        # If JWT cookie missing -> Unauthorized WS close
        if user is None or user.is_anonymous:
            await self.accept()
            await self.close(code=4401)
            return

        self.user = user
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'

        print(f"[CHAT] Connecting user {user.id} to room {self.room_id}")

        # Check if room exists
        ChatRoom = apps.get_model('chat', 'ChatRoom')
        try:
            room = await database_sync_to_async(ChatRoom.objects.get)(id=self.room_id)
        except ChatRoom.DoesNotExist:
            print(f"Room {self.room_id} does not exist")
            await self.close()
            return

        # Add user to chat group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        print(f"[CHAT] WebSocket connected for room {self.room_id}")


    async def disconnect(self, close_code):
        print(f"[CHAT] WebSocket disconnected from room {self.room_id}, code: {close_code}")

        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )


    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            print(f"[CHAT] Received: {data}")

            message = data.get("message")
            sender_id = data.get("sender_id")

            if not message or not sender_id:
                print("[CHAT] Invalid message data")
                return

            await self.save_message(sender_id, self.room_id, message)

            # Broadcast to room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": message,
                    "sender_id": sender_id,
                }
            )

        except Exception as e:
            print(f"[CHAT] Error receiving message: {e}")


    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "message": event["message"],
            "sender_id": event["sender_id"],
        }))


    @database_sync_to_async
    def save_message(self, sender_id, room_id, content):
        ChatRoom = apps.get_model('chat', 'ChatRoom')
        Message = apps.get_model('chat', 'Message')
        Accounts = apps.get_model('Accounts', 'Accounts')

        from notifications.utils import send_notification

        room = ChatRoom.objects.get(id=room_id)
        sender = Accounts.objects.get(id=sender_id)

        if sender not in [room.user, room.tutor]:
            raise PermissionError("Sender not part of room")

        # Save message
        Message.objects.create(
            room=room,
            sender=sender,
            content=content
        )

        receiver = room.tutor if sender == room.user else room.user

        send_notification(
            receiver,
            f"💬 New message from {sender.first_name}"
        )


# ----------------------------------------------------------
# CALL CONSUMER (Also needs JWT cookie authentication support)
# ----------------------------------------------------------

class CallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")

        # Unauthorized -> close
        if user is None or user.is_anonymous:
            await self.accept()
            await self.close(code=4401)
            return

        self.user = user
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'call_{self.room_id}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        print(f"[CALL] WebSocket connected for call room {self.room_id}")


    async def disconnect(self, close_code):
        print(f"[CALL] Disconnected call room {self.room_id}, code={close_code}")

        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )


    async def receive(self, text_data):
        data = json.loads(text_data)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_message',
                'data': data,
            }
        )


    async def call_message(self, event):
        await self.send(text_data=json.dumps(event['data']))