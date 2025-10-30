from django.http import HttpResponseNotFound

ALLOWED_ORIGINS = [
    "https://mhebazar.in",
    "https://www.mhebazar.in",
    "http://mhebazar.in",
    "http://www.mhebazar.in",
]


class BlockPublicAPIMiddleware:
    """
    Middleware that blocks direct external API access
    but allows media/static/admin from any source (so images load fine).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin", "")
        referer = request.headers.get("Referer", "")
        path = request.path.lower()

        # ✅ Always allow admin, static, and media URLs
        if (
            path.startswith("/admin")
            or path.startswith("/static")
            or path.startswith("/media")
        ):
            return self.get_response(request)

        # ✅ Allow requests coming from the frontend domain
        allowed = any(domain in origin for domain in ALLOWED_ORIGINS) or any(
            domain in referer for domain in ALLOWED_ORIGINS
        )

        # 🚫 Block all other requests
        if not allowed:
            return HttpResponseNotFound("Not Found")

        return self.get_response(request)
