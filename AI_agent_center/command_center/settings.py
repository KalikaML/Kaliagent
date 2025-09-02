import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Security settings
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

# Quick-start development settings
SECRET_KEY = os.getenv('SECRET_KEY')
SERPAPI_API_KEY = None 



DEBUG = True
ALLOWED_HOSTS = ['*']  # Restrict in production

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
    'ai_agent_pitch',
    'shorts_app',  # Add this line
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
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
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

STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email Configuration (SendGrid)
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')
DEFAULT_FROM_NAME = 'Kalika AI'
SITE_URL = os.getenv('SITE_URL', 'http://localhost:8000')


# In settings.py
SEARXNG_INSTANCE_URL = 'http://localhost:8080'

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
# Used for sending RFQs to suppliers
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER') # Your sending email address
# IMPORTANT: Use a Gmail "App Password" if using Gmail
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


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