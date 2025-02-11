import aiosmtplib
from email.mime.text import MIMEText

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USERNAME = "palle.saisneha@gmail.com"
EMAIL_PASSWORD = "muvr mwlc wjdu dhll"

async def send_reset_email(email: str, token: str):
    message = MIMEText(f"Click the link to reset your password: http://localhost:8000/reset-password/{token}")
    message["From"] = EMAIL_USERNAME
    message["To"] = email
    message["Subject"] = "Reset Your Password"

    await aiosmtplib.send(
        message,
        hostname=SMTP_SERVER,
        port=SMTP_PORT,
        username=EMAIL_USERNAME,
        password=EMAIL_PASSWORD,
        use_tls=False
    )
