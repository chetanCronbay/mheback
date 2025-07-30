# Django settings for mhe_backend project.

import os
import dj_database_url
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import logging.config # For structured logging (already good)
from typing import List, Dict, Any # For type hints (already good)
from corsheaders.defaults import default_headers



# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(os.path.join(BASE_DIR, '.env'))

# --- Quick-start development settings - unsuitable for production ---
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# It's crucial to set this in your environment variables (e.g., Render.com)
from django.core.exceptions import ImproperlyConfigured

SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY environment variable not set.")

# SECURITY WARNING: don't run with debug turned on in production!
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
DEBUG = ENVIRONMENT == 'development'

# Allowed hosts for your Django application
# In production, only include your actual domain(s) and Render.com's hostname.
# Do NOT include paths like /api.
ALLOWED_HOSTS: List[str] = []
if DEBUG:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'localhost:3000', '192.168.0.135:3000', 'mheback.onrender.com','mhebazar.vercel.app']
else:
    # IMPORTANT: Replace 'mheback.onrender.com' with your actual Render.com hostname
    # and 'your-production-frontend-domain.com' with your actual frontend domain.
    ALLOWED_HOSTS = ['mheback.onrender.com', 'your-production-frontend-domain.com','mhebazar.vercel.app']
    # You might also need to add your Render internal hostname if Render requires it,
    # but typically the external one is sufficient.

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'rest_framework_simplejwt.token_blacklist', # For JWT token blacklisting (logout)
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'dj_rest_auth.registration', # For user registration endpoints
    'rest_framework',
    'rest_framework_simplejwt', # For JWT authentication
    "django_filters", # For filtering in DRF
    "order_management", # Custom app
    "banners",          # Custom app
    "products",         # Custom app
    "users",            # Custom app (contains custom user model)
    "blog",             # Custom app for blog functionality
    "corsheaders",      # For Cross-Origin Resource Sharing
]

# Allauth Social Account Providers Configuration
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.getenv('GOOGLE_CLIENT_ID'),
            'secret': os.getenv('GOOGLE_CLIENT_SECRET'),
            'key': '' # This key is generally not needed for Google
        },
        'SCOPE': ['profile', 'email'], # Requesting profile and email data
        'AUTH_PARAMS': {'access_type': 'online'}, # Requesting refresh token for offline access
    }
}

# REST Framework Configuration (DRF)
REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication', # Primary authentication
        'rest_framework.authentication.SessionAuthentication', # For browsable API and admin
        'rest_framework.authentication.BasicAuthentication', # For browsable API and admin
        # 'util.authentication.APIKeyAuthentication', # Uncomment if you have a custom API key auth.
                                                    # Otherwise, keep commented out.
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated', # Default is to require authentication
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': int(os.getenv('API_PAGE_SIZE', 20)), # Default pagination size
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer', # Useful for development/testing via browser
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle', # Rate limit for unauthenticated users
        'rest_framework.throttling.UserRateThrottle'  # Rate limit for authenticated users
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.getenv('API_THROTTLE_ANON', '100/hour'),
        'user': os.getenv('API_THROTTLE_USER', '1000/hour')
    },
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning', # API versioning strategy
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1', 'v2'], # Supported API versions
    'VERSION_PARAM': 'version', # URL parameter for versioning
}

# Middleware stack
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",         # Must be first for CORS to work correctly
    "whitenoise.middleware.WhiteNoiseMiddleware",     # For serving static files efficiently
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",   # Required for django-allauth
    # Make sure this custom middleware exists at the specified path (e.g., in a 'Middleware' folder at project root)
    "Middleware.security.SecurityHeadersMiddleware",  # For additional security headers
]

# Custom Authentication Backends
AUTHENTICATION_BACKENDS = [
    'users.authentication.EmailBackend',        # Your custom email/password authentication
    'django.contrib.auth.backends.ModelBackend', # Default Django authentication backend
]

ROOT_URLCONF = "mhe_backend.urls"

# Django Templates Configuration
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, 'templates')], # Directory for custom templates (e.g., email templates)
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "mhe_backend.wsgi.application"

# Simple JWT Settings for tokens and cookies
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7), # Access token validity
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),   # Refresh token validity

    # JWT Cookies Configuration (Crucial for secure token handling)
    # The 'access_token' cookie will be HTTP-Only, protecting it from client-side JS.
    # The 'refresh_token' cookie will also be HTTP-Only and ideally set by your backend refresh endpoint.
    'AUTH_COOKIE': 'access_token',     # Name of the cookie for the access token
    'AUTH_COOKIE_SECURE': not DEBUG,   # True in production (HTTPS only), False in development (HTTP allowed)
    'AUTH_COOKIE_HTTP_ONLY': True,     # True: Prevents JavaScript access to the cookie (XSS protection)
    'AUTH_COOKIE_PATH': '/',           # Cookie valid for all paths
    'AUTH_COOKIE_SAMESITE': 'Lax',     # CSRF protection (Lax is a good balance)

    # If you also want to set the refresh token as an HttpOnly cookie, your /token/refresh/ endpoint
    # needs to explicitly set it as a cookie in its response. Simple JWT by default returns it in JSON.
    # You would need to customize the Simple JWT views for this.
    # For now, frontend handles refresh token via js-cookie, which is less secure than HttpOnly.
    # BEST PRACTICE: Both access and refresh tokens should be HttpOnly cookies set by the backend.
}

# Database Configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME', 'new_mhe'),
        'USER': os.getenv('DB_USER', 'root'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'pass'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '3306'),
        'CONN_MAX_AGE': 600, # Connection pooling
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# Use dj_database_url for dynamic database configuration based on DATABASE_URL env var (e.g., Render.com)
if os.getenv('DATABASE_URL'):
    db_config = dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600, # Same as above
        ssl_require=ENVIRONMENT == 'production' # Require SSL in production
    )
    DATABASES['default'].update(db_config)


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (user uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# In production, use cloud storage for media files for scalability and persistence
if ENVIRONMENT == 'production':
    # Example for AWS S3 - UNCOMMENT AND CONFIGURE WHEN DEPLOYING TO PRODUCTION
    # Install 'django-storages' and 'boto3' first: pip install django-storages boto3
    # DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    # AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    # AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    # AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    # AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')
    # AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com' # Optional, for direct serving
    # AWS_QUERYSTRING_AUTH = False # Optional: Prevents query string authentication for public files
    pass

# File validation settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_PERMISSIONS = 0o644 # Read/write for owner, read-only for group/others

# Set appropriate file retention policies (e.g., for temporary files)
FILE_RETENTION_DAYS = int(os.getenv('FILE_RETENTION_DAYS', 365))

# Security settings for production (uncommented and applied when ENVIRONMENT is 'production')
if ENVIRONMENT == 'production':
    SECURE_SSL_REDIRECT = True # Force HTTPS for all requests
    # Essential if you are behind a proxy (like Render.com) that handles SSL termination
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True # Ensures session cookies are only sent over HTTPS
    CSRF_COOKIE_SECURE = True    # Ensures CSRF cookies are only sent over HTTPS
    
    # Other recommended security headers
    SECURE_BROWSER_XSS_FILTER = True      # Protects against XSS attacks
    SECURE_CONTENT_TYPE_NOSNIFF = True    # Prevents browser from MIME-sniffing content-types
    SECURE_HSTS_SECONDS = 31536000        # HSTS: One year (31,536,000 seconds = 1 year)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True # Include subdomains in HSTS policy
    SECURE_HSTS_PRELOAD = False           # Set to True once HSTS is fully working and stable
                                          # (requires registration with browser preload list)
    X_FRAME_OPTIONS = 'DENY' # Prevents clickjacking: 'DENY' or 'SAMEORIGIN'
    
    # Content Security Policy (CSP)
    # IMPORTANT: CSP can easily break your frontend if not configured correctly.
    # Test this thoroughly. Use 'unsafe-inline' sparingly or replace with hashes/nonces.
    # CSP_DEFAULT_SRC = ("'self'",)
    # CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "https://accounts.google.com") # Add google for social login
    # CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
    # CSP_IMG_SRC = ("'self'", "data:", "https:")
    # CSP_FONT_SRC = ("'self'", "https:")
    # Use django-csp package for robust CSP implementation: https://github.com/mozilla/django-csp
    # Example: CSP_REPORT_ONLY = True # Report violations without blocking
    # CSP_REPORT_URI = "/csp-report/" # Endpoint to send reports
    pass # Keep pass if you are not enabling these yet

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom user model
AUTH_USER_MODEL = 'users.User'

# CORS Configuration (Cross-Origin Resource Sharing)
# IMPORTANT: Never use CORS_ALLOW_ALL_ORIGINS = True in production!
CORS_ALLOW_ALL_ORIGINS = DEBUG # Allows all origins ONLY in DEBUG mode

CORS_ALLOWED_ORIGINS: List[str] = []
if not DEBUG:
    # IMPORTANT: Replace with your actual production frontend domains
    CORS_ALLOWED_ORIGINS = [
        "https://your-production-frontend-domain.com",
        "https://mheback.onrender.com", # If your backend itself needs to make CORS requests to itself
    ]
else:
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.0.135:3000", # For testing from a specific IP on local network
        "https://mhebazar.vercel.app",
        # Add other development origins as needed
    ]

# Specify allowed HTTP methods for CORS requests
CORS_ALLOWED_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS', # Always include OPTIONS for pre-flight requests
    'PATCH',
    'POST',
    'PUT',
]

# Specify allowed headers for CORS requests
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-api-key", # Custom API key header, if used
    "content-disposition",
]
CORS_ALLOW_HEADERS = list(default_headers) + [
    "content-disposition",
]

# Allow credentials (cookies, HTTP authentication) to be sent with cross-origin requests
CORS_ALLOW_CREDENTIALS = True # Necessary when using cookies (JWT or session)

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 465)) # Changed to 465 for SMTPS
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False').lower() == 'true' # Changed to False for SMTPS
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'True').lower() == 'true' # Added for SMTPS
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')

DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'no-reply@yourdomain.com')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@yourdomain.com')
CONTACT_RECEIVER_EMAIL = os.getenv('CONTACT_RECEIVER_EMAIL', 'contact@yourdomain.com') # Added this line


# Frontend URL (for redirects, e.g., after social login)
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')

# Structured logging configuration
# settings.py

# In settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        # ... other loggers ...
    },
}
# Razorpay Configuration
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', 'rzp_test_eXK5DmzmpQXzFh')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', 'b1xOotX38KU5QziqN37v7SVT')

