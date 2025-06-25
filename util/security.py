from django.core.cache import cache
from rest_framework.exceptions import Throttled
import logging

logger = logging.getLogger(__name__)

class SecurityLogger:
    @staticmethod
    def log_suspicious_request(request, action):
        ip = request.META.get('REMOTE_ADDR')
        user = request.user if request.user.is_authenticated else "anonymous"
        logger.warning(
            f"Suspicious activity detected - Action: {action}, "
            f"IP: {ip}, User: {user}, Path: {request.path}"
        )

class IPRateLimiter:
    @staticmethod
    def check_ip(request, limit=10, timeout=3600):
        ip = request.META.get('REMOTE_ADDR')
        key = f'ip_limit:{ip}'
        count = cache.get(key, 0)
        
        if count >= limit:
            raise Throttled(detail="Too many requests from this IP")
        
        cache.set(key, count + 1, timeout)