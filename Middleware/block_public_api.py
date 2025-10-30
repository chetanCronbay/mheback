from django.http import HttpResponseNotFound

# ✅ Allowed front-end domains
ALLOWED_ORIGINS = [
    "https://mhebazar.in",
    "https://www.mhebazar.in",
    "http://mhebazar.in",
    "http://www.mhebazar.in",
]

class BlockAPIFromThirdPartiesMiddleware:
    """
    Block access to /api/* from any request not coming from allowed frontend domains.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path.lower()
        origin = request.headers.get("Origin", "")
        referer = request.headers.get("Referer", "")

        # ✅ Only protect the /api/ endpoints
        if path.startswith("/api/"):
            allowed = any(domain in origin for domain in ALLOWED_ORIGINS) or any(
                domain in referer for domain in ALLOWED_ORIGINS
            )

            # 🚫 If not from allowed site, return 404
            if not allowed:
                return HttpResponseNotFound("Not Found")

        # ✅ Everything else works normally
        return self.get_response(request)
