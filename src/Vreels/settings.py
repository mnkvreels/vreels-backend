

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# =======================
# 🔐 Security & Debugging
# =======================
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-=zzn-uq121w*elzh)_(hapbyq0zk&9ay+1b3flxxa3lnkiz0ao")
DEBUG = False
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost").split(",")

# =======================
# ⚙️ Azure Credentials
# =======================
'''
AZURE_CREDENTIALS = {
    "clientId": os.getenv("AZURE_CLIENT_ID"),
    "clientSecret": os.getenv("AZURE_CLIENT_SECRET"),
    "subscriptionId": os.getenv("AZURE_SUBSCRIPTION_ID"),
    "tenantId": os.getenv("AZURE_TENANT_ID"),
    "activeDirectoryEndpointUrl": os.getenv("AZURE_AD_ENDPOINT", "https://login.microsoftonline.com"),
    "resourceManagerEndpointUrl": os.getenv("AZURE_RM_ENDPOINT", "https://management.azure.com/"),
    "activeDirectoryGraphResourceId": os.getenv("AZURE_GRAPH_RESOURCE_ID", "https://graph.windows.net/"),
    "sqlManagementEndpointUrl": os.getenv("AZURE_SQL_ENDPOINT", "https://management.core.windows.net:8443/"),
    "galleryEndpointUrl": os.getenv("AZURE_GALLERY_ENDPOINT", "https://gallery.azure.com/"),
    "managementEndpointUrl": os.getenv("AZURE_MGMT_ENDPOINT", "https://management.core.windows.net/")
}
'''

AZURE_WEBAPP_NAME = os.getenv("AZURE_WEBAPP_NAME")
AZURE_RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP")
AZURE_SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")

# =======================
# 📦 Notification Hubs
# =======================
NOTIFICATION_HUB_NAME = os.getenv("NOTIFICATION_HUB_NAME")
NOTIFICATION_HUB_CONNECTION_STRING = os.getenv("NOTIFICATION_HUB_CONNECTION_STRING")
AZURE_NAMESPACE = os.getenv("AZURE_NAMESPACE")
AZURE_ACCESS_KEY = os.getenv("AZURE_ACCESS_KEY")
AZURE_HUB_NAME = os.getenv("AZURE_HUB_NAME")

# =======================
# 🔌 Application
# =======================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'accounts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'Vreels.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'Vreels.wsgi.application'

# =======================
# 🛢 Database
# =======================
DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': os.getenv("DB_NAME"),
        'USER': os.getenv("DB_USER"),
        'PASSWORD': os.getenv("DB_PASSWORD"),
        'HOST': os.getenv("DB_HOST"),
        'PORT': os.getenv("DB_PORT", "1433"),
        'OPTIONS': {
            'driver': os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
        },
    }
}

# =======================
# ☁️ Azure Blob Storage
# =======================
DEFAULT_FILE_STORAGE = 'storages.backends.azure_storage.AzureStorage'
AZURE_ACCOUNT_NAME = os.getenv("AZURE_ACCOUNT_NAME")
AZURE_ACCOUNT_KEY = os.getenv("AZURE_ACCOUNT_KEY")
AZURE_CONTAINER =  "media"

# =======================
# 🌐 Site & Email
# =======================
SITE_ID = 1
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000")

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "palle.saisneha@gmail.com")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "muvr mwlc wjdu dhll")

# =======================
# 🔐 Password Validators
# =======================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# =======================
# 🌍 Internationalization
# =======================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# =======================
# 📁 Static Files
# =======================
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

DEFAULT_FILE_STORAGE = 'storages.backends.azure_storage.AzureStorage'
AZURE_ACCOUNT_NAME = os.getenv("AZURE_ACCOUNT_NAME")
AZURE_ACCOUNT_KEY = os.getenv("AZURE_ACCOUNT_KEY")
AZURE_CONTAINER = '$logs'