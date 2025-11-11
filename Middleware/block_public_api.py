from django.http import HttpResponseForbidden, HttpResponseNotFound
import re
import logging

logger = logging.getLogger(__name__)

# Primary production host names.
PRIMARY_FRONTEND_HOSTS = [
    "mhebazar.in",
    "www.mhebazar.in",
    "mhebazar.vercel.app",
]

# Primary API host names. These requests should generally be BLOCKED if originating 
# from the same host, as it indicates unauthorized direct browsing.
API_HOSTS = [
    "api.mhebazar.in",
    "www.api.mhebazar.in",
]

# ✅ Allowed sources for API access.
# NOTE: Localhost:3000 is intentionally excluded per user request.
ALLOWED_HOSTS_REGEX = [
    # 1. Production Frontend Domains
    re.compile(r"^https?://(?:www\.)?mhebazar\.in$"),
    
    # 2. Vercel Domain
    re.compile(r"^https?://mhebazar\.vercel\.app$"), 
    
    # 3. Local Development Backend (For internal testing/admin access)
    re.compile(r"^http://localhost:8000$"),
]

class BlockApiAccessMiddleware:
    """
    Blocks access to /api/ endpoints if the request does not originate from
    an explicitly allowed source, including handling cases where headers are absent 
    (direct browser/Postman access).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def _is_request_allowed(self, request):
        # 1. SERVER ACCESS (ALLOW: Internal server-to-server or runserver)
        if request.META.get('REMOTE_ADDR') in ['127.0.0.1', '::1']:
             return True
        
        # --- 2. HEADER/ORIGIN CHECK ---
        origin = request.headers.get("Origin", "").lower().strip('/')
        referer = request.headers.get("Referer", "").lower().strip('/')
        host = request.headers.get("Host", "").lower()
        
        source = origin or referer
        
        # --- CRITICAL FIX 1: Strict block when headers are missing ---
        if not source:
            # If Origin/Referer is missing, check the requested Host header. 
            # If the Host header matches the primary API host, it's a direct access attempt.
            if host in API_HOSTS:
                logger.warning(f"API access blocked: Direct Host access detected ({host}).")
                return False
            
            # If the request doesn't have headers, and it's not the API host, 
            # we assume it's unauthorized external machine access.
            logger.warning("API access blocked: Missing Origin/Referer.")
            return False 

        # --- CRITICAL FIX 2: Check against allowed Frontend domains ---
        is_allowed = any(pattern.match(source) for pattern in ALLOWED_HOSTS_REGEX)

        # 3. BLOCK DIRECT API HOST ACCESS, even if Referer is present (self-referencing block)
        if host in API_HOSTS and api_host_pattern.match(source):
            if not is_allowed:
                 # This handles the case where the browser sets referer to the API host.
                 logger.warning(f"API access blocked: Direct navigation/self-referencing block from {source}.")
                 return False

        if not is_allowed:
            logger.warning(f"API access blocked: Unauthorized source '{source}'.")
        
        return is_allowed

    def __call__(self, request):
        path = request.path.lower()
        
        if path.startswith("/api/"):
            
            # --- Special handling for OPTIONS (CORS preflight) ---
            if request.method == 'OPTIONS':
                return self.get_response(request)

            # --- Main Security Check ---
            if not self._is_request_allowed(request):
                # Use 403 Forbidden to explicitly deny unauthorized access
                return HttpResponseForbidden("Access Forbidden. Unauthorized Origin.")

        return self.get_response(request)