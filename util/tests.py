# In util/tests.py

from django.test import override_settings
from django.urls import path
from rest_framework.test import APITestCase
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.test import override_settings, modify_settings
from rest_framework import status
from rest_framework.test import APITestCase, APIClient


# 1. Define a simple, temporary view just for this test
class ThrottlingTestView(APIView):
    """
    A view that uses the default authentication, permission, and throttling
    classes defined in the project's settings.
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return Response({"message": "GET OK"}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        return Response({"message": "POST OK"}, status=status.HTTP_200_OK)

# 2. Define a temporary URL configuration for the test to use
# This avoids interfering with your project's main urls.py
urlpatterns = [
    path('test-throttle/', ThrottlingTestView.as_view(), name='test-throttle'),
]

@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    },
    ROOT_URLCONF=__name__,
    REST_FRAMEWORK={
        'DEFAULT_AUTHENTICATION_CLASSES': [],
        'DEFAULT_PERMISSION_CLASSES': [],
        'DEFAULT_THROTTLE_CLASSES': [
            'util.throttle.WriteOnlyAnonRateThrottle',
            'util.throttle.WriteOnlyUserRateThrottle',
        ],
    },
)

class ThrottlingConfigurationTest(APITestCase):
    """
    This test suite verifies that the custom WriteOnly throttle classes
    are being correctly applied by Django REST Framework.
    """

    def test_anonymous_post_requests_are_throttled(self):
        """
        Verifies that unsafe methods (POST) are rate-limited for anonymous users.
        """
        print("\nRunning test: Anonymous POST requests should be throttled...")
        url = '/test-throttle/'
        
        # The first 3 POST requests should succeed
        for i in range(5):
            response = self.client.post(url, {}, format='json')
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Request #{i+1} should have succeeded, but failed."
            )

        # The 4th POST request should be blocked
        response = self.client.post(url, {}, format='json')
        self.assertEqual(
            response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
            "The 6th POST request was not throttled, but it should have been."
        )
        print("✅ PASSED: POST requests were correctly throttled.")

    def test_anonymous_get_requests_are_not_throttled(self):
        """
        Verifies that safe methods (GET) are NOT rate-limited for anonymous users.
        """
        print("\nRunning test: Anonymous GET requests should NOT be throttled...")
        url = '/test-throttle/'

        # Make more GET requests than the throttle limit (3/day)
        # All of them should succeed
        for i in range(100):
            response = self.client.get(url, {}, format='json')
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"GET Request #{i+1} was throttled, but it should not have been."
            )
        print("✅ PASSED: GET requests were correctly ignored by the throttle.")