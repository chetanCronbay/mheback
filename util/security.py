"""Security utilities for MHE Backend.

Apply Rules: Implement comprehensive error handling with informative messages.
Apply Rules: Log authentication attempts and failures.
Apply Rules: Implement rate limiting to prevent abuse.
Apply Rules: Never log sensitive information (passwords, tokens, PII).
"""
from typing import Optional, Dict, Any
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError
import logging
import hashlib
import secrets
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


class SecurityLogger:
    """Apply Rules: Structured logging with appropriate log levels."""
    
    @staticmethod
    def log_suspicious_request(request, action: str, details: Optional[Dict[str, Any]] = None):
        """Log suspicious activity with structured data."""
        ip = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:200]  # Truncate
        user = request.user.username if request.user.is_authenticated else "anonymous"
        
        log_data = {
            'action': action,
            'ip': ip,
            'user': user,
            'path': request.path,
            'method': request.method,
            'user_agent': user_agent,
            'timestamp': timezone.now().isoformat()
        }
        
        if details:
            log_data.update(details)
            
        logger.warning(f"Security Alert: {action}", extra=log_data)
    
    @staticmethod
    def log_authentication_attempt(request, username: str, success: bool, reason: Optional[str] = None):
        """Apply Rules: Log authentication attempts and failures."""
        ip = request.META.get('REMOTE_ADDR')
        
        log_data = {
            'username': username,  # This is safe to log as it's not sensitive
            'ip': ip,
            'success': success,
            'timestamp': timezone.now().isoformat()
        }
        
        if reason:
            log_data['reason'] = reason
            
        if success:
            logger.info(f"Successful login for user: {username}", extra=log_data)
        else:
            logger.warning(f"Failed login attempt for user: {username}", extra=log_data)
    
    @staticmethod
    def log_permission_denied(request, resource: str, action: str):
        """Log unauthorized access attempts."""
        ip = request.META.get('REMOTE_ADDR')
        user = request.user.username if request.user.is_authenticated else "anonymous"
        
        logger.warning(
            f"Permission denied - User: {user}, Resource: {resource}, Action: {action}, IP: {ip}"
        )


class IPRateLimiter:
    @staticmethod
    def check_ip(request, limit: int = 10, timeout: int = 3600) -> bool:
        """Check if IP has exceeded rate limit, but skip all GET requests."""

        # Skip rate limiting for all GET requests
        if request.method == 'GET':
            return True

        ip = request.META.get('REMOTE_ADDR')
        key = f'ip_limit:{ip}'
        count = cache.get(key, 0)

        if count >= limit:
            SecurityLogger.log_suspicious_request(
                request,
                'IP_RATE_LIMIT_EXCEEDED',
                {'limit': limit, 'current_count': count}
            )
            raise Throttled(detail="Too many requests from this IP")

        cache.set(key, count + 1, timeout)
        return True

    
    @staticmethod
    def check_user_action(user, action: str, limit: int = 5, timeout: int = 3600) -> bool:
        """Check if user has exceeded action-specific rate limit."""
        if not user.is_authenticated:
            return True
            
        key = f'user_action:{user.id}:{action}'
        count = cache.get(key, 0)
        
        if count >= limit:
            logger.warning(f"User {user.username} exceeded rate limit for action: {action}")
            raise Throttled(detail=f"Too many {action} attempts. Please try again later.")
        
        cache.set(key, count + 1, timeout)
        return True


class InputValidator:
    """Apply Rules: Validate and sanitize all user inputs."""
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize uploaded filenames."""
        import os
        import re
        
        # Remove path components
        filename = os.path.basename(filename)
        
        # Remove or replace dangerous characters
        filename = re.sub(r'[^\w\s.-]', '', filename)
        
        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:250] + ext
            
        return filename
    
    @staticmethod
    def validate_file_type(file, allowed_types: list) -> bool:
        """Apply Rules: Validate all uploaded files for type and size."""
        import mimetypes
        
        if not file:
            return False
            
        # Check file extension
        file_type = mimetypes.guess_type(file.name)[0]
        
        if file_type not in allowed_types:
            raise ValidationError(f"File type {file_type} not allowed. Allowed types: {allowed_types}")
            
        return True
    
    @staticmethod
    def validate_file_size(file, max_size_mb: int = 10) -> bool:
        """Validate file size."""
        if not file:
            return False
            
        max_size = max_size_mb * 1024 * 1024  # Convert to bytes
        
        if file.size > max_size:
            raise ValidationError(f"File size exceeds {max_size_mb}MB limit")
            
        return True


class TokenGenerator:
    """Generate secure tokens for various purposes."""
    
    @staticmethod
    def generate_verification_token() -> str:
        """Generate a secure verification token."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure API key."""
        return secrets.token_urlsafe(40)
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for secure storage."""
        return hashlib.sha256(token.encode()).hexdigest()