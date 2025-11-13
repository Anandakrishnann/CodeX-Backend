print("💥 NEW CONSUMER LOADED 💥")
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope["user"]

        # If no token in cookies → Unauthorized
        if user.is_anonymous:
            print("❌ Notification WebSocket: Anonymous user, closing connection")
            await self.accept()         # Accept first (required)
            await self.close(code=4401) # 4401 = Unauthorized
            return

        # Authenticated user
        self.group_name = f"user_{user.id}"
        print(f"✅ Notification WebSocket: User {user.id} connecting to group {self.group_name}")

        await self.channel_layer.group_add(
            self.group_name, 
            self.channel_name
        )

        await self.accept()
        print(f"✅ Notification WebSocket: Connected for user {user.id}")

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            print(f"🔌 Notification WebSocket: Disconnecting from group {self.group_name}, code={close_code}")
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def send_notification(self, event):
        print(f"📨 WS PUSH => {event['message']}")
        await self.send(text_data=json.dumps({
            "id": event.get("id"),
            "message": event["message"],
            "created_at": event["created_at"],
            "is_read": False,
        }))