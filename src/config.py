import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    # Database Configuration
    DB_SERVER: str = os.getenv("DB_SERVER", "sqlddatabbasedemo.database.windows.net")
    DB_NAME: str = os.getenv("DB_NAME", "vreeels_django_database")
    DB_USER: str = os.getenv("DB_USER", "sqladmin")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "MnkLlc@25")  # Consider using environment variables for security

    # Twilio API Credentials
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "ACe67896eb32ba4c8602a0fc916a22678f")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "277d57db2b80515dc3f40e75a629a138")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "+19404355569")

    # JWT Configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "django-insecure-=zzn-uq121w*elzh)_(hapbyq0zk&9ay+1b3flxxa3lnkiz0ao")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 30))

    # Application Settings
    PROJECT_NAME: str = "Vreels"
    VERSION: str = "0.1"
    DESCRIPTION: str = "Engine Behind Vreels"

settings = Settings()
