"""Standard response envelope: { success, data, error, timestamp }."""
from datetime import datetime, timezone


def ok(data) -> dict:
    return {
        "success": True,
        "data": data,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def err(message: str) -> dict:
    return {
        "success": False,
        "data": None,
        "error": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
