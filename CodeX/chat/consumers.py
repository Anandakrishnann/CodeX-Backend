import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Message, ChatRoom
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        event_type = data.get("type")

        if event_type == "chat":
            message = data["message"]
            sender_id = data["sender_id"]

            sender = await sync_to_async(User.objects.get)(id=sender_id)
            room = await sync_to_async(ChatRoom.objects.get)(id=self.room_id)

            await sync_to_async(Message.objects.create)(
                room=room,
                sender=sender,
                content=message,
                message_type="text"
            )

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": message,
                    "sender_id": sender_id
                }
            )

        elif event_type in ["offer", "answer", "candidate"]:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "signal_message",
                    "data": data
                }
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "chat",
            "message": event["message"],
            "sender_id": event["sender_id"]
        }))

    async def signal_message(self, event):
        await self.send(text_data=json.dumps(event["data"]))
