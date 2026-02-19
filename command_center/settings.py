import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Security settings
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Quick-start development settings
SECRET_KEY = os.getenv('SECRET_KEY')
SERPAPI_API_KEY = os.getenv('SERPAPI_API_KEY')

# Google Sheets Configuration
GOOGLE_SHEETS_CREDENTIALS_FILE = os.path.join(BASE_DIR, 'config', 'gsheet_key_suppliers_list.json')
GOOGLE_SHEET_ID = '1ptrQDPIwdzBDrqgjTpkS4wp9CRFNU9qQ3GS2e-AQHnU'
# Historical suppliers CSV default: prefer your uploaded file name, fallback to previous_suppliers.csv
_csv_candidate_1 = BASE_DIR / 'config' / 'procurement_Suppliers_list - All Suppliers Data.csv'
_csv_candidate_2 = BASE_DIR / 'config' / 'previous_suppliers.csv'
if os.path.exists(_csv_candidate_1):
    PREVIOUS_SUPPLIERS_CSV = str(_csv_candidate_1)
else:
    PREVIOUS_SUPPLIERS_CSV = None
    print(f"Warning: No historical suppliers CSV found at {_csv_candidate_1}")




DEBUG = os.getenv('DEBUG', 'False') == 'True'
# ALLOWED_HOSTS: Read from environment variable or default to localhost for local dev
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

# CSRF_TRUSTED_ORIGINS: Read from environment variable for production
csrf_origins_env = os.getenv('CSRF_TRUSTED_ORIGINS', '')
if csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins_env.split(',')]
else:
    CSRF_TRUSTED_ORIGINS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'marketing_outreach',
    'procurement',
    'linkedin_automation',
    'command_center',
    
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'command_center.urls'

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
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'command_center.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
# Django automatically collects from each installed app's static/ folder
# Only list directories here that are NOT inside installed apps
STATICFILES_DIRS = [
    BASE_DIR / 'static',  # For global/shared static files
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --- MEDIA FILES CONFIGURATION ---IN DEVELOPMENT MODE, MEDIA_URL is /media/ and files are stored locally in BASE_DIR/media/
# Media files configuration
#MEDIA_URL = '/media/'
#MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Ensure media directories exist
#os.makedirs(os.path.join(MEDIA_ROOT, 'uploads'), exist_ok=True)

# Use Google Cloud Storage in production, local filesystem in development
if os.getenv('USE_GCS', 'False') == 'True':
    # Production: Google Cloud Storage
    GS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', 'kaliagents-media')
    GS_PROJECT_ID = os.getenv('GCP_PROJECT_ID')
    GS_CREDENTIALS = None  # Uses default credentials in Cloud Run
    MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')  # Define for compatibility
    
    # Configure Django STORAGES (new format for Django 4.2+)
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    print(f"📦 Using Google Cloud Storage: {GS_BUCKET_NAME}")
else:
    # Development: Local filesystem
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
    # Ensure media directories exist
    os.makedirs(os.path.join(MEDIA_ROOT, 'uploads'), exist_ok=True)
    print(f"📁 Using local media storage: {MEDIA_ROOT}")


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'




# SearXNG instance URL (leave empty to disable fallback)
# Example: https://searxng.example.com
SEARXNG_INSTANCE_URL = os.getenv('SEARXNG_INSTANCE_URL', '').rstrip('/')

# LinkedIn Automation Agent - Reddit API
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT', 'Kaliagents LinkedIn AI v1.0')

# LinkedIn Automation Agent - Image APIs
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')
GIPHY_API_KEY = os.getenv('GIPHY_API_KEY')

# LinkedIn Automation Agent - LinkedIn Posting API
LINKEDIN_ACCESS_TOKEN = os.getenv('LINKEDIN_ACCESS_TOKEN')
LINKEDIN_PERSON_URN = os.getenv('LINKEDIN_PERSON_URN')


# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'debug.log',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
# --- EMAIL SENDING (SMTP) ---
def _dequote(val):
    if val is None:
        return val
    v = str(val).strip()
    if len(v) >= 2 and ((v[0] == v[-1]) and v[0] in ('"', "'")):
        return v[1:-1]
    return v

# Used for sending RFQs to suppliers
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = _dequote(os.environ.get('EMAIL_HOST', 'smtp.gmail.com'))
_port = _dequote(os.environ.get('EMAIL_PORT', '587'))
EMAIL_PORT = int(_port) if _port else 587
EMAIL_USE_TLS = _dequote(os.environ.get('EMAIL_USE_TLS', 'True')) == 'True'
EMAIL_HOST_USER = _dequote(os.environ.get('EMAIL_HOST_USER'))  # Your sending email address
# IMPORTANT: Use a Gmail "App Password" if using Gmail
EMAIL_HOST_PASSWORD = _dequote(os.environ.get('EMAIL_HOST_PASSWORD'))
DEFAULT_FROM_EMAIL = _dequote(os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or '')) or EMAIL_HOST_USER


# --- EMAIL READING (IMAP) ---
# Used for reading and parsing incoming quotes
GMAIL_IMAP_HOST = os.environ.get('GMAIL_IMAP_HOST', 'imap.gmail.com')
GMAIL_ADDRESS = os.environ.get('GMAIL_ADDRESS') # Your monitored inbox address
# IMPORTANT: Use a Gmail "App Password" if using Gmail
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD')

# Django ko batayein ki aapka custom login page kahan hai.
LOGIN_URL = 'core:login'

# Login karne ke baad user ko kahan bhejna hai.
LOGIN_REDIRECT_URL = 'core:agent_selector'

# Logout karne ke baad user ko kahan bhejna hai.
LOGOUT_REDIRECT_URL = 'core:login'

# Use SQLite for tests to avoid external DB dependency
import sys
if 'test' in sys.argv:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'test_db.sqlite3',
        }
    }