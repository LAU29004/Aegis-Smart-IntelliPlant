from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db, User
from ..security import get_current_user
from ..envelope import ok
from ..database import DeviceToken
from ..services.notifications import send_to_user

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
)

class RegisterTokenBody(BaseModel):
    token: str
    device_id: str
    platform: str
    app_version: str


@router.post("/register")
def register_token(
    body: RegisterTokenBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    existing = (
    db.query(DeviceToken)
    .filter(
        DeviceToken.user_id == user.user_id,
        DeviceToken.device_id == body.device_id,
    )
    .first()
)

    if existing:
        existing.token = body.token
        existing.platform = body.platform
        existing.app_version = body.app_version
        existing.is_active = True
    else:
        db.add(
        DeviceToken(
            user_id=user.user_id,
            device_id=body.device_id,
            token=body.token,
            platform=body.platform,
            app_version=body.app_version,
            is_active=True,
        )
    )

    db.commit()

    return ok({"message": "Device registered"})

@router.post("/test")
def test_notification(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = send_to_user(
        db=db,
        user_id=user.user_id,
        title="IntelliPlant 🚀",
        body="Push notifications are working!",
        data={"screen": "Dashboard"},
    )

    return ok({
        "message": "Notification sent",
        "result": result,
    })