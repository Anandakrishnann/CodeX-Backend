from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Notification

def send_notification(user, message):
    if not user:
        return

    notification = Notification.objects.create(
        user=user,
        message=message
    )

    channel_layer = get_channel_layer()

    try:
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "send_notification",
                "message": notification.message,
                "created_at": str(notification.created_at),
                "id": notification.id,
            }
        )
        print(f"📤 Notification sent via WebSocket to user_{user.id}: {notification.message}")
    except Exception as e:
        print(f"❌ Error sending notification via WebSocket: {str(e)}")

    return notification