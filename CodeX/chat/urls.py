# chat/urls.py
from django.urls import path
from .views import *

urlpatterns = [
    path('get-or-create-room/', GetOrCreateChatRoomView.as_view(), name='get_or_create_chat_room'),
    path('participants/<int:room_id>/', GetRoomParticipantsView.as_view(), name='room-participants'),
    path('room_summary/<int:room_id>/', RoomSummaryView.as_view(), name='room-summary'),
    path('rooms/', ChatRoomListView.as_view(), name='chat-room-list'),
    path('messages/<int:room_id>/', MessageListView.as_view(), name='message-list'),
    path('get-zego-token/<int:user_id>/', ZegoTokenView.as_view(), name='get_zego_token'),
]