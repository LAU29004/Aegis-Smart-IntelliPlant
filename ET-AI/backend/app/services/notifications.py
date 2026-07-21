from sqlalchemy.orm import Session
from .firebase_service import firebase_admin
from firebase_admin import messaging
from ..database import DeviceToken


def send_push(
    token: str,
    title: str,
    body: str,
    data: dict | None = None,
):
    """
    Send push notification through Firebase.
    """

    payload = {
        "title": title,
        "body": body,
    }

    if data:
        # Firebase data payload values MUST be strings
        payload.update({k: str(v) for k, v in data.items()})

    message = messaging.Message(
        token=token,
        android=messaging.AndroidConfig(
            priority="high",
        ),
        data=payload,
    )

    try:
        message_id = messaging.send(message)

        print("\n========== FIREBASE PUSH ==========")
        print("TOKEN:", token)
        print("PAYLOAD:", payload)
        print("MESSAGE ID:", message_id)
        print("===================================\n")

        return message_id

    except Exception as e:
        print("\n========== FIREBASE ERROR ==========")
        print(e)
        print("====================================\n")
        raise

def send_to_user(
    db: Session,
    user_id: str,
    title: str,
    body: str,
    data: dict | None = None,
):
    """
    Send notification to all active devices of one user.
    """

    devices = (
        db.query(DeviceToken)
        .filter(
            DeviceToken.user_id == user_id,
            DeviceToken.is_active == True,
        )
        .all()
    )

    results = []

    for device in devices:
        try:
            message_id = send_push(
                device.token,
                title,
                body,
                data,
            )

            results.append(
                {
                    "device_id": device.device_id,
                    "success": True,
                    "message_id": message_id,
                }
            )

        except Exception as e:
            results.append(
                {
                    "device_id": device.device_id,
                    "success": False,
                    "error": str(e),
                }
            )

    return results


def send_to_many(
    db: Session,
    user_ids: list[str],
    title: str,
    body: str,
    data: dict | None = None,
):
    """
    Send notification to multiple users.
    """

    response = {}

    for uid in user_ids:
        response[uid] = send_to_user(
            db,
            uid,
            title,
            body,
            data,
        )

    return response


def broadcast(
    db: Session,
    title: str,
    body: str,
    data: dict | None = None,
):
    """
    Broadcast notification to every active device.
    """

    devices = (
        db.query(DeviceToken)
        .filter(DeviceToken.is_active == True)
        .all()
    )

    results = []

    for device in devices:
        try:
            message_id = send_push(
                device.token,
                title,
                body,
                data,
            )

            results.append(
                {
                    "device_id": device.device_id,
                    "success": True,
                    "message_id": message_id,
                }
            )

        except Exception as e:
            results.append(
                {
                    "device_id": device.device_id,
                    "success": False,
                    "error": str(e),
                }
            )

    return results