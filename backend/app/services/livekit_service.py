from datetime import timedelta
from livekit.api import AccessToken, VideoGrants
from app.config import settings


def create_token(session_id: str, identity: str, is_instructor: bool = False) -> str:
    grant = VideoGrants(
        room_join=True,
        room=session_id,
        can_publish=is_instructor,
        can_subscribe=True,
        can_publish_data=is_instructor,
    )
    token = AccessToken(
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    )
    token.with_identity(identity).with_name(identity).with_grants(grant).with_ttl(timedelta(minutes=15))
    return token.to_jwt()
