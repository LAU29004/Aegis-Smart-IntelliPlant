from pathlib import Path

import firebase_admin
from firebase_admin import credentials

ROOT = Path(__file__).resolve().parents[2]
SERVICE_ACCOUNT = ROOT / "serviceAccountKey.json"

# Initialize Firebase only once
if not firebase_admin._apps:
    cred = credentials.Certificate(str(SERVICE_ACCOUNT))
    firebase_admin.initialize_app(cred)