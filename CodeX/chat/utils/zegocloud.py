import time
import jwt  # PyJWT

def generate_zego_kit_token(app_id: int, server_secret: str, room_id: str, user_id: str, effective_time: int = 3600) -> str:
    """Generate a ZegoCloud KitToken for React frontend."""
    current_time = int(time.time())
    payload = {
        "app_id": app_id,
        "user_id": user_id,
        "room_id": room_id,
        "privilege": {
            "room_login": 1,
            "publish_stream": 1,
            "play_stream": 1
        },
        "create_time": current_time,
        "expire_time": current_time + effective_time,
        "nonce": current_time,
        "token_version": 1
    }

    jwt_token = jwt.encode(payload, server_secret, algorithm="HS256")
    return f"{jwt_token}:{payload}"