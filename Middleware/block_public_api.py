from django.http import HttpResponseNotFound

ALLOWED_ORIGINS = [
    "https://mhebazar.in",
    "https://www.mhebazar.in",
    "http://mhebazar.in",
    "http://www.mhebazar.in",
    
]

class BlockPublicAPIMiddleware:
    """
    Middleware that blocks any request not coming from allowed origins or referers.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin", "")
        referer = request.headers.get("Referer", "")

        # Allow admin, static, and media files
        path = request.path.lower()
        if path.startswith("/admin") or path.startswith("/static") or path.startswith("/media"):
            return self.get_response(request)

        # Allow requests only if origin or referer matches allowed sites
        allowed = any(domain in origin for domain in ALLOWED_ORIGINS) or any(domain in referer for domain in ALLOWED_ORIGINS)

        if not allowed:
            return HttpResponseNotFound("Not Found")

        return self.get_response(request)
