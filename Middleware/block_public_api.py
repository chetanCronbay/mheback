from django.http import HttpResponseForbidden, HttpResponseNotFound
import re
import logging

logger = logging.getLogger(__name__)

# ✅ Allowed front-end domains (case-insensitive for comparison)
# We exclude 'api.mhebazar.in' to block direct browser access, forcing all access
# to originate from the MHEBAZAR.IN frontend domains.
ALLOWED_HOSTS_REGEX = [
    # 1. Production Frontend Domains (https://www.mhebazar.in, https://mhebazar.in, etc.)
    re.compile(r"^https?://(?:www\.)?mhebazar\.in$"),
    
    # 2. Vercel Domain (Frontend hosting origin before mapping)
    re.compile(r"^https?://mhebazar\.vercel\.app$"), 
    
    # 3. Local Development Frontend (Origin header when running on localhost:3000)
    re.compile(r"^http://localhost:3000$"),
    
    # 4. Local Development Backend (For internal server testing/calls)
    re.compile(r"^http://localhost:8000$"),
]

class BlockApiAccessMiddleware:
    """
    Blocks access to /api/ endpoints if the request does not originate from
    an allowed frontend domain or is not a local/server request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def _is_request_allowed(self, request):
        # 1. Check if the request is from the server's local environment or internal calls.
        if request.META.get('REMOTE_ADDR') in ['127.0.0.1', '::1']:
             return True
        
        # 2. Check for Allowed Headers (Origin is for CORS, Referer is for link navigations/searches)
        origin = request.headers.get("Origin", "").lower()
        referer = request.headers.get("Referer", "").lower()
        
        # Determine the source, preferring Origin for AJAX/CORS checks
        source = origin or referer

        if not source:
            logger.warning(f"API access blocked: Missing Origin/Referer for path {request.path}")
            return False

        # 3. Check against the allowed regex patterns
        is_allowed = any(pattern.match(source) for pattern in ALLOWED_HOSTS_REGEX)

        if not is_allowed:
            logger.warning(f"API access blocked: Source '{source}' not in allowed list.")
        
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