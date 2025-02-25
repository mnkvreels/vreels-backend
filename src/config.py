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

    # Azure AD B2C Credentials
    
    TENANT_NAME: str = os.getenv("TENANT_NAME", "vreelsb2c")
    TENANT_ID: str = os.getenv("TENANT_ID", "vreelsb2c.onmicrosoft.com")
    CLIENT_ID: str = os.getenv("CLIENT_ID", "35dcbb83-8de1-4ce9-b3a1-aa4d56e63288")
    CLIENT_SECRET: str = os.getenv("CLIENT_SECRET", "piQ8Q~IAyjmC4AVdvoqNKf_MRp7cOaGs.XBX-aH5")
    B2C_POLICY: str = os.getenv("B2C_POLICY", "B2C_1_vreels")
    ISSUER: str = os.getenv("ISSUER","https://vreelsb2c.b2clogin.com/vreelsb2c.onmicrosoft.com/v2.0/")
    JWKS_URL: str = os.getenv("JWKS_URL", "https://vreelsb2c.b2clogin.com/vreelsb2c.onmicrosoft.com/discovery/v2.0/keys")
    REDIRECT_URI: str = os.getenv("REDIRECT_URI", "https://vreelsb2ctenant.b2clogin.com/vreelsb2ctenant.onmicrosoft.com/oauth2/v2.0/authorize?p=B2C_1_vreelsuserflow&client_id=7ad7cdbd-aead-47da-b9a1-4f5d36c59cd6&nonce=defaultNonce&redirect_uri=https%3A%2F%2Fvreels.azurewebsites.net%2F&scope=openid&response_type=code&prompt=login")

    # JWT Configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "django-insecure-=zzn-uq121w*elzh)_(hapbyq0zk&9ay+1b3flxxa3lnkiz0ao")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 30))

    # Application Settings
    PROJECT_NAME: str = "Vreels"
    VERSION: str = "0.1"
    DESCRIPTION: str = "Engine Behind Vreels"

settings = Settings()
