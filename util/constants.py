"""Constants for MHE Backend application.

Apply Rules: Use constants files for magic numbers and strings.
Apply Rules: Use clear, descriptive names following Python/Django conventions.
"""
from typing import Dict, List, Tuple

# HTTP Status Codes
HTTP_200_OK = 200
HTTP_201_CREATED = 201
HTTP_400_BAD_REQUEST = 400
HTTP_401_UNAUTHORIZED = 401
HTTP_403_FORBIDDEN = 403
HTTP_404_NOT_FOUND = 404
HTTP_429_TOO_MANY_REQUESTS = 429
HTTP_500_INTERNAL_SERVER_ERROR = 500

# Product Types
PRODUCT_TYPE_NEW = 'new'
PRODUCT_TYPE_USED = 'used'
PRODUCT_TYPE_RENTAL = 'rental'

PRODUCT_TYPE_CHOICES = (
    (PRODUCT_TYPE_NEW, 'New'),
    (PRODUCT_TYPE_USED, 'Used'),
    (PRODUCT_TYPE_RENTAL, 'Rental'),
)

# Quote/Rental Status
STATUS_PENDING = 'pending'
STATUS_APPROVED = 'approved'
STATUS_REJECTED = 'rejected'
STATUS_RETURNED = 'returned'

QUOTE_STATUS_CHOICES = (
    (STATUS_PENDING, 'Pending'),
    (STATUS_APPROVED, 'Approved'),
    (STATUS_REJECTED, 'Rejected'),
)

RENTAL_STATUS_CHOICES = (
    (STATUS_PENDING, 'Pending'),
    (STATUS_APPROVED, 'Approved'),
    (STATUS_REJECTED, 'Rejected'),
    (STATUS_RETURNED, 'Returned'),
)

# File Upload Settings
MAX_FILE_SIZE_MB = 10
MAX_IMAGE_SIZE_MB = 5
MAX_DOCUMENT_SIZE_MB = 20

ALLOWED_IMAGE_TYPES = [
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp'
]

ALLOWED_DOCUMENT_TYPES = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain'
]

# Email Templates
EMAIL_TEMPLATE_QUOTE_CUSTOMER = 'quote_customer_confirmation'
EMAIL_TEMPLATE_QUOTE_ADMIN = 'quote_admin_notification'
EMAIL_TEMPLATE_RENTAL_CUSTOMER = 'rental_customer_confirmation'
EMAIL_TEMPLATE_RENTAL_ADMIN = 'rental_admin_notification'
EMAIL_TEMPLATE_USER_VERIFICATION = 'user_verification'
EMAIL_TEMPLATE_PASSWORD_RESET = 'password_reset'

# Cache Keys
CACHE_KEY_USER_PROFILE = 'user_profile_{user_id}'
CACHE_KEY_PRODUCT_DETAILS = 'product_{product_id}'
CACHE_KEY_CATEGORY_PRODUCTS = 'category_{category_id}_products'
CACHE_KEY_POPULAR_PRODUCTS = 'popular_products'

# Cache Timeouts (in seconds)
CACHE_TIMEOUT_SHORT = 300  # 5 minutes
CACHE_TIMEOUT_MEDIUM = 1800  # 30 minutes
CACHE_TIMEOUT_LONG = 3600  # 1 hour
CACHE_TIMEOUT_VERY_LONG = 86400  # 24 hours

# Rate Limiting
RATE_LIMIT_LOGIN_ATTEMPTS = 5
RATE_LIMIT_QUOTE_REQUESTS = 3
RATE_LIMIT_RENTAL_REQUESTS = 3
RATE_LIMIT_CONTACT_FORMS = 2

# Rate Limit Timeouts (in seconds)
RATE_LIMIT_TIMEOUT_SHORT = 900  # 15 minutes
RATE_LIMIT_TIMEOUT_MEDIUM = 3600  # 1 hour
RATE_LIMIT_TIMEOUT_LONG = 86400  # 24 hours

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# User Roles (should match database)
ROLE_ADMIN = 'admin'
ROLE_MANAGER = 'manager'
ROLE_CUSTOMER = 'customer'
ROLE_VENDOR = 'vendor'

# Security Settings
MAX_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_DURATION = 1800  # 30 minutes
PASSWORD_RESET_TIMEOUT = 3600  # 1 hour
EMAIL_VERIFICATION_TIMEOUT = 86400  # 24 hours

# Business Logic Constants
MIN_RENTAL_DAYS = 1
MAX_RENTAL_DAYS = 365
MIN_PRODUCT_PRICE = 0.01
MAX_PRODUCT_PRICE = 999999.99

# Notification Types
NOTIFICATION_QUOTE_CREATED = 'quote_created'
NOTIFICATION_QUOTE_APPROVED = 'quote_approved'
NOTIFICATION_QUOTE_REJECTED = 'quote_rejected'
NOTIFICATION_RENTAL_CREATED = 'rental_created'
NOTIFICATION_RENTAL_APPROVED = 'rental_approved'
NOTIFICATION_RENTAL_REJECTED = 'rental_rejected'
NOTIFICATION_RENTAL_RETURNED = 'rental_returned'

# API Response Messages
MSG_SUCCESS = 'Operation completed successfully'
MSG_CREATED = 'Resource created successfully'
MSG_UPDATED = 'Resource updated successfully'
MSG_DELETED = 'Resource deleted successfully'
MSG_NOT_FOUND = 'Resource not found'
MSG_UNAUTHORIZED = 'Authentication required'
MSG_FORBIDDEN = 'Permission denied'
MSG_VALIDATION_ERROR = 'Validation error'
MSG_RATE_LIMITED = 'Too many requests. Please try again later.'

# Error Messages
ERROR_INVALID_CREDENTIALS = 'Invalid username or password'
ERROR_ACCOUNT_LOCKED = 'Account is temporarily locked due to failed login attempts'
ERROR_EMAIL_NOT_VERIFIED = 'Please verify your email address before logging in'
ERROR_EXPIRED_TOKEN = 'Token has expired'
ERROR_INVALID_TOKEN = 'Invalid token'
ERROR_FILE_TOO_LARGE = 'File size exceeds maximum allowed size'
ERROR_INVALID_FILE_TYPE = 'File type not allowed'
ERROR_PRODUCT_NOT_AVAILABLE = 'Product is not available for the selected dates'
ERROR_DUPLICATE_REQUEST = 'A similar request already exists'

# AI Integration Constants
AI_MODEL_VERSION = 'v1'
AI_CONFIDENCE_THRESHOLD = 0.8
AI_MAX_RETRIES = 3
AI_TIMEOUT_SECONDS = 30

# Feature Flags
FEATURE_EMAIL_NOTIFICATIONS = True
FEATURE_SMS_NOTIFICATIONS = False
FEATURE_ADVANCED_SEARCH = True
FEATURE_RECOMMENDATION_ENGINE = False
FEATURE_ANALYTICS_TRACKING = True

# External Service URLs
MAPS_API_BASE_URL = 'https://maps.googleapis.com/maps/api'
PAYMENT_API_BASE_URL = 'https://api.stripe.com/v1'
NOTIFICATION_SERVICE_URL = 'https://fcm.googleapis.com/fcm/send'

# Regular Expressions
PHONE_NUMBER_REGEX = r'^\+?1?\d{9,15}$'
ZIP_CODE_REGEX = r'^\d{5}(-\d{4})?$'
SLUG_REGEX = r'^[-a-zA-Z0-9_]+$'

# Time Formats
DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
TIME_FORMAT = '%H:%M:%S'

# Search Configuration
SEARCH_MIN_LENGTH = 3
SEARCH_MAX_RESULTS = 50
SEARCH_BOOST_FACTORS = {
    'name': 2.0,
    'manufacturer': 1.5,
    'model': 1.2,
    'description': 1.0
}
