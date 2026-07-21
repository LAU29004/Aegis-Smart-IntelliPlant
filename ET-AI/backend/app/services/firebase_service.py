import json
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials

ROOT = Path(__file__).resolve().parents[2]
SERVICE_ACCOUNT = ROOT / "serviceAccountKey.json"

firebase_app = None

if not firebase_admin._apps:

    # Local development
    if SERVICE_ACCOUNT.exists():
        cred = credentials.Certificate(str(SERVICE_ACCOUNT))
        firebase_app = firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized using local serviceAccountKey.json")

    # Production (Render)
    elif os.getenv("FIREBASE_SERVICE_ACCOUNT"):
        service_account = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
        cred = credentials.Certificate(service_account)
        firebase_app = firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized using FIREBASE_SERVICE_ACCOUNT")

    else:
        print("⚠️ Firebase credentials not found. Push notifications are disabled.")