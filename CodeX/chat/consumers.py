# chat/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.apps import apps
from Accounts.models import *
from chat.models import *

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        print(f"Connecting to room {self.room_id}")

        try:
            ChatRoom = apps.get_model('chat', 'ChatRoom')
            room = await database_sync_to_async(ChatRoom.objects.get)(id=self.room_id)
        except ChatRoom.DoesNotExist:
            print(f"Room {self.room_id} does not exist")
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        print(f"WebSocket connected for room {self.room_id}")

    async def disconnect(self, close_code):
        print(f"WebSocket disconnected for room {self.room_id}, code: {close_code}")
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            print(f"Received data: {text_data_json}")
            message = text_data_json.get('message')
            sender_id = text_data_json.get('sender_id')

            if not message or not sender_id:
                print(f"Invalid message data: message={message}, sender_id={sender_id}")
                return

            print(f"Received message: {message} from {sender_id}")
            await self.save_message(sender_id, self.room_id, message)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender_id': sender_id,
                }
            )
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
        except Exception as e:
            print(f"Receive error: {e}")

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_id': event['sender_id'],
        }))

    @database_sync_to_async
    def save_message(self, sender_id, room_id, content):
        ChatRoom = apps.get_model('chat', 'ChatRoom')
        Message = apps.get_model('chat', 'Message')
        Accounts = apps.get_model('Accounts', 'Accounts')
        room = ChatRoom.objects.get(id=room_id)
        sender = Accounts.objects.get(id=sender_id)
        Message.objects.create(room=room, sender=sender, content=content)
        
        
        
        
# chat/consumers.py
class CallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'call_{self.room_id}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        # Handle WebRTC signaling messages (offer, answer, ICE candidates)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_message',
                'data': data,
            }
        )

    async def call_message(self, event):
        await self.send(text_data=json.dumps(event['data']))

    @database_sync_to_async
    def save_call_session(self, room_id, caller_id, callee_id, call_type='video', status='missed'):
        room = ChatRoom.objects.get(id=room_id)
        caller = Accounts.objects.get(id=caller_id)
        callee = Accounts.objects.get(id=callee_id)
        CallSession.objects.create(room=room, caller=caller, callee=callee, call_type=call_type, status=status)