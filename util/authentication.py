import os
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

class APIKeyAuthentication(BaseAuthentication):
    """
    Custom authentication using X-API-KEY header.
    """
    def authenticate(self, request):
        api_key = request.headers.get('X-API-KEY')
        expected_key = os.getenv('X_API_KEY')
        if not api_key or api_key != expected_key:
            raise AuthenticationFailed('Invalid or missing X-API-KEY.')
        return (None, None)  # No user associated, just API key auth