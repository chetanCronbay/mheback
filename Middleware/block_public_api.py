from django.http import HttpResponseForbidden, HttpResponseNotFound
import re
import logging

logger = logging.getLogger(__name__)

# ✅ Allowed sources for API access.
# These are strictly the domains where your frontend code is served from.
ALLOWED_HOSTS_REGEX = [
    # 1. Production Frontend Domains (mhebazar.in, www.mhebazar.in)
    re.compile(r"^https?://(?:www\.)?mhebazar\.in$"),
    
    # 2. Vercel Domain (Frontend hosting origin before mapping)
    re.compile(r"^https?://mhebazar\.vercel\.app$"), 
    
    # 3. Local Development Backend (For internal testing/admin access)
    re.compile(r"^http://localhost:8000$"),
    
    # NOTE: http://localhost:3000 is intentionally removed to satisfy the user request.
]

class BlockApiAccessMiddleware:
    """
    Blocks access to /api/ endpoints if the request does not originate from
    an explicitly allowed source, enforcing security even when headers are absent.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def _is_request_allowed(self, request):
        # 1. SERVER ACCESS (ALLOW: Internal server-to-server or runserver)
        if request.META.get('REMOTE_ADDR') in ['127.0.0.1', '::1']:
             return True
        
        # 2. HEADER ACCESS (CORS/Referer Check)
        origin = request.headers.get("Origin", "").lower().strip('/')
        referer = request.headers.get("Referer", "").lower().strip('/')
        
        # Determine the source, preferring Origin for AJAX/CORS checks
        source = origin or referer
        
        # --- CRITICAL FIX: If no headers are present, it is unauthorized external access. ---
        if not source:
            logger.warning(f"API access blocked: Missing Origin/Referer for path {request.path}")
            # Block requests with no headers (direct browser/cURL/Postman without spoofing)
            return False 

        # 3. Check against the allowed regex patterns
        is_allowed = any(pattern.match(source) for pattern in ALLOWED_HOSTS_REGEX)

        # 4. BLOCK DIRECT API HOST ACCESS
        # Even if the API host is used as the source (e.g., direct navigation), block it.
        api_host_pattern = re.compile(r"^https?://(?:www\.)?api\.mhebazar\.in$")
        
        if api_host_pattern.match(source):
            if not is_allowed:
                 # This should only match if the source is api.mhebazar.in
                 logger.warning(f"API access blocked: Direct API host access detected from {source}")
                 return False

        # If it matches an allowed frontend domain, allow it.
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