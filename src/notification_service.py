import asyncio
import firebase_admin
from firebase_admin import credentials, messaging
import os


# ✅ Resolve absolute path to serviceAccountKey.json
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

service_account_info = {
    "type": os.getenv("GOOGLE_APPLICATION_CREDENTIALS_TYPE"),
    "project_id": os.getenv("GOOGLE_PROJECT_ID"),
    "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("GOOGLE_PRIVATE_KEY"),
    "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
    "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
    "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_CERT_URL"),
    "universe_domain": os.getenv("GOOGLE_UNIVERSE_DOMAIN")
}

# ✅ Load credentials using correct path
cred = credentials.Certificate(service_account_info)

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(cred)


async def send_push_notification(device_token: str, platform: str, title: str, message: str):
    """
        Send FCM push notification asynchronously to a specific device.

        Args:
            device_token (str): FCM device registration token.
            platform (str): 'android' or 'ios' (can be used for platform-specific configs).
            title (str): Notification title.
            message (str): Notification body.
        """
    # Platform-specific options (optional)
    android_config = messaging.AndroidConfig(
        priority='high',
    )

    apns_config = messaging.APNSConfig(
        headers={"apns-priority": "10"},
    )

    message_payload = messaging.Message(
        notification=messaging.Notification(title=title, body=message),
        token=device_token,
        android=android_config if platform.lower() == "android" else None,
        apns=apns_config if platform.lower() == "ios" else None,
    )

    # Wrap blocking call in asyncio's thread pool
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(None, messaging.send, message_payload)
        print(f"Notification sent successfully to {response}! 🎉")
        return {"status": "success", "message_id": response}
    except Exception as e:
        print(f"Failed to send notification: {e}")
        return {"status": "error", "message": str(e)}

'''import requests
import base64
import hmac
import hashlib
import urllib.parse
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException


def generate_sas_token(url: str, key_name: str, key: str) -> str:
    """
    Generate a Shared Access Signature (SAS) token for Azure Notification Hub.
    """
    expiry = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
    string_to_sign = f"{urllib.parse.quote(url, safe='')}\\n{expiry}"
    key_bytes = base64.b64decode(key.encode("utf-8"))
    signature = base64.b64encode(hmac.new(key_bytes, string_to_sign.encode("utf-8"), hashlib.sha256).digest()).decode(
        "utf-8"
    )
    return f"SharedAccessSignature sr={urllib.parse.quote(url, safe='')}&sig={urllib.parse.quote(signature, safe='')}&se={expiry}&skn={key_name}"


async def send_push_notification(device_token: str, platform: str, title: str, message: str):
    """
    Send push notification using Azure Notification Hub REST API.

    Args:
        device_token (str): The device token for the recipient.
        platform (str): The platform to send notification to ('ios' or 'android').
        title (str): Notification title.
        message (str): Notification message.
    """
    hub_name = "VreelsNotificationHub"
    namespace = "VreelsNotificationNamespace"
    key_name = "DefaultFullSharedAccessSignature"
    key = "iRo5EDWXy5AtjZHhSApCVR3licfJOvvB2psF1IdoUKw="

    # Azure API endpoint
    url = f"https://{namespace}.servicebus.windows.net/{hub_name}/messages/{device_token}?api-version=2015-01"

    # Generate SAS token
    sas_token = generate_sas_token(url, key_name, key)

    # Define the headers
    headers = {
        "Authorization": sas_token,
        "Content-Type": "application/json",
        "ServiceBusNotification-Format": "gcm" if platform == "android" else "apple",
    }

    # Define notification payload for Android and iOS
    if platform and platform.lower() == "android":
        notification_payload = {
            "notification": {
                "title": title,
                "body": message,
            },
            "data": {
                "extra_info": "Additional data if needed",
            },
        }
    elif platform and platform.lower() == "ios":
        notification_payload = {
            "aps": {
                "alert": {
                    "title": title,
                    "body": message,
                },
                "sound": "default",
            }
        }
    else:
        return {"Unsupported platform. Only 'ios' and 'android' are supported."}

    # Send the notification
    response = requests.post(url, json=notification_payload, headers=headers)

    # Check response
    if response.status_code == 201:
        print(f"Notification sent successfully to {device_token}! 🎉")
        return True
    else:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to send notification: {response.text}",
        )'''
