import requests
import base64
import hmac
import hashlib
import urllib.parse
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from .Vreels.settings import Settings


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
    hub_name = Settings.AZURE_HUB_NAME
    namespace = Settings.AZURE_NAMESPACE
    key_name = "DefaultFullSharedAccessSignature"
    key = Settings.AZURE_ACCESS_KEY

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
    if platform.lower() == "android":
        notification_payload = {
            "notification": {
                "title": title,
                "body": message,
            },
            "data": {
                "extra_info": "Additional data if needed",
            },
        }
    elif platform.lower() == "ios":
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
        raise ValueError("Unsupported platform. Only 'ios' and 'android' are supported.")

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
        )
