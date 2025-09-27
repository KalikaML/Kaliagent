# settings.py

import os
import io
from pathlib import Path
from google.cloud import secretmanager
import google.auth


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- Google Secret Manager Setup ---
# This function fetches the latest version of a secret from Secret Manager.
# It's the recommended way to handle secrets in production on GCP.

try:
    # Attempt to access Google Cloud project ID and initialize the client
    # This will work automatically in a GCP environment like Cloud Run.
    _, project_id = google.auth.default()
    client = secretmanager.SecretManagerServiceClient()

    def get_secret(secret_id, version_id="latest"):
        """Fetches a secret from Google Cloud Secret Manager."""
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(name=name)
        return response.payload.data.decode("UTF-8")

except Exception:
    # If not in a GCP environment (like local development),
    # fallback to using environment variables from a .env file.
    # This allows you to still run `python manage.py` commands locally.
    from dotenv import load_dotenv
    print("WARNING: Not a GCP environment. Falling back to .env file.")
    load_dotenv(os.path.join(BASE_DIR, '.env'))
    def get_secret(secret_id):
        return os.getenv(secret_id)


# --- Core Django Settings ---
# Set the SECRET_KEY from Secret Manager
SECRET_KEY = get_secret('SECRET_KEY')

# DEBUG must be False in production for security and performance.
# You can set an environment variable `DJANGO_DEBUG` to "True" for local dev.
DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'

# --- Host and Security Settings ---
# ALLOWED_HOSTS is critical for security.
# Cloud Run provides the service URL in the K_SERVICE environment variable.
ALLOWED_HOSTS = []
if K_SERVICE_URL := os.getenv('K_SERVICE_URL'):
    ALLOWED_HOSTS.append(K_SERVICE_URL.split('//')[1])
else:
    # For local development
    ALLOWED_HOSTS.extend(['127.0.0.1', 'localhost'])

# CSRF setting for production when behind a proxy/load balancer.
CSRF_TRUSTED_ORIGINS = [os.getenv('K_SERVICE_URL')] if 'K_SERVICE_URL' in os.environ else []

# Enforce HTTPS in production
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG


# --- API Keys and Credentials (from Secret Manager) ---
GEMINI_API_KEY = get_secret('GEMINI_API_KEY')
YOUTUBE_API_KEY = get_secret('YOUTUBE_API_KEY')
SERPAPI_API_KEY = get_secret('SERPAPI_API_KEY')
SENDGRID_API_KEY = get_secret('SENDGRID_API_KEY')

# --- Installed Apps & Middleware ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'storages',  # For Cloud Storage
    'core',
    'marketing_outreach',
    'procurement',
    'ai_agent_pitch',
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

ROOT_URLCONF = 'command_center.urls'
WSGI_APPLICATION = 'command_center.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.messages',
            ],
        },
    },
]


# --- Database Configuration (for Cloud SQL PostgreSQL) ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': get_secret('DB_NAME'),
        'USER': get_secret('DB_USER'),
        'PASSWORD': get_secret('DB_PASSWORD'),
        # The HOST is a special path for the Cloud SQL Auth Proxy socket.
        # Cloud Run automatically sets this up when connected to a Cloud SQL instance.
        'HOST': f"/cloudsql/{get_secret('DB_CONNECTION_NAME')}",
    }
}


# --- Internationalization & Auth Validators ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- Google Cloud Storage for Static and Media Files ---
# The bucket name will be set as an environment variable in Cloud Run.
GS_BUCKET_NAME = os.getenv('GS_BUCKET_NAME')
if GS_BUCKET_NAME:
    STATICFILES_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
    DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
    STATIC_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/static/'
    MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/media/'
    STATIC_ROOT = "static/" # collectstatic will upload to bucket/static/
    MEDIA_ROOT = "media/"   # media files will upload to bucket/media/
else:
    # Local development settings
    STATIC_URL = 'static/'
    STATIC_ROOT = BASE_DIR / 'staticfiles'
    STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# --- Email Configuration (using Secret Manager) ---
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = get_secret('EMAIL_HOST') # e.g., 'smtp.gmail.com'
EMAIL_PORT = int(get_secret('EMAIL_PORT')) # e.g., 587
EMAIL_USE_TLS = get_secret('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
EMAIL_HOST_USER = get_secret('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = get_secret('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# IMAP settings
GMAIL_IMAP_HOST = get_secret('GMAIL_IMAP_HOST')
GMAIL_ADDRESS = get_secret('GMAIL_ADDRESS')
GMAIL_APP_PASSWORD = get_secret('GMAIL_APP_PASSWORD')


# --- Other Settings ---
SEARXNG_INSTANCE_URL = get_secret('SEARXNG_INSTANCE_URL', 'http://localhost:8080')
SITE_URL = os.getenv('K_SERVICE_URL', 'http://localhost:8000')

# Login/Logout Redirects
LOGIN_URL = 'core:login'
LOGIN_REDIRECT_URL = 'core:agent_selector'
LOGOUT_REDIRECT_URL = 'core:login'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}