from sqlalchemy.orm import Session

from ..database import DeviceToken, User
from .notifications import send_push


def send_to_user(
    db: Session,
    user_id: str,
    title: str,
    body: str,
    data: dict | None = None,
):
    """
    Send a notification to every active device belonging
    to a specific user.
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


def send_to_roles(
    db: Session,
    roles: list[str],
    title: str,
    body: str,
    data: dict | None = None,
):
    """
    Notify every user having one of the supplied roles.
    """

    users = (
        db.query(User)
        .filter(User.role.in_(roles))
        .all()
    )

    response = {}

    for user in users:
        response[user.email] = send_to_user(
            db=db,
            user_id=user.user_id,
            title=title,
            body=body,
            data=data,
        )

    return response

def notify_alert(
    db: Session,
    alert_id: str,
    equipment_id: str,
    severity: str,
    title: str,
    description: str,
):
    """
    Send notifications for newly created alerts.
    """

    if severity == "critical":
        roles = [
            "Plant Manager",
            "Engineer",
            "Safety Officer",
        ]
    elif severity == "warning":
        roles = [
            "Engineer",
            "Plant Manager",
        ]
    else:
        roles = [
            "Engineer",
        ]

    return send_to_roles(
        db=db,
        roles=roles,
        title=f"🚨 {severity.upper()} ALERT",
        body=(f"{title}\n\n"f"Equipment: {equipment_id}"),
        data={
            "type": "ALERT",
            "alert_id": alert_id,
            "equipment_id": equipment_id,
            "severity": severity,
            "screen": "AlertDetail",
            },
            )