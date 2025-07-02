from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from .models import *
from .serializers import *
from util.security import IPRateLimiter, SecurityLogger
from .permissions import IsAdmin, IsVendor, IsUser, IsOwnerOrAdmin, CanCreateReview
import os
from rest_framework.views import APIView
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone

class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    Session authentication but does not enforce CSRF for API clients.
    Use only for API endpoints where JWT is also allowed.
    """
    def enforce_csrf(self, request):
        return  # To allow JWT clients to work without CSRF

class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff

class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user
    
class ContactFormThrottle(UserRateThrottle):
    scope = 'contact_form'
    rate = '5/hour'

class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdmin]  # Only admins can manage roles
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication, BasicAuthentication]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]  # Only admins can manage users
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication, BasicAuthentication]
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email', 'phone']
    parser_classes = [MultiPartParser, FormParser]

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser],
            authentication_classes=[JWTAuthentication, CsrfExemptSessionAuthentication, BasicAuthentication],
            permission_classes=[permissions.IsAdminUser])
    def upload_banner(self, request, pk=None):
        """
        Upload multiple banner images to a specific user.
        """
        user = self.get_object()
        images = request.FILES.getlist('user_banner')

        if not images:
            return Response({"detail": "No images uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        banners = []
        for image in images:
            banner = UserBanner.objects.create(user=user, image=image)
            banners.append(banner)

        serializer = UserBannerSerializer(banners, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'],
            authentication_classes=[JWTAuthentication, CsrfExemptSessionAuthentication, BasicAuthentication],
            permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

class ContactFormViewSet(viewsets.ModelViewSet):
    queryset = ContactForm.objects.all()
    serializer_class = ContactFormSerializer
    permission_classes = [permissions.AllowAny]  # Anyone can submit contact forms
    authentication_classes = []
    throttle_classes = [ContactFormThrottle]
    filter_backends = [filters.SearchFilter]
    search_fields = ['first_name', 'last_name', 'email', 'company_name']

    def create(self, request, *args, **kwargs):
        IPRateLimiter.check_ip(request, limit=5, timeout=3600)
        try:
            return super().create(request, *args, **kwargs)
        except serializers.ValidationError as e:
            if 'CAPTCHA' in str(e) or 'honeypot' in str(e):
                SecurityLogger.log_suspicious_request(request, "Failed CAPTCHA/honeypot")
            raise e

    def perform_create(self, serializer):
        instance = serializer.save()
        instance.send_emails()

class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, CanCreateReview, IsOwnerOrAdmin]
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication, BasicAuthentication]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Reviews.objects.all()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser],
            authentication_classes=[JWTAuthentication, CsrfExemptSessionAuthentication, BasicAuthentication],
            permission_classes=[permissions.IsAuthenticated, IsOwnerOrReadOnly])
    def upload_images(self, request, pk=None):
        """
        Upload images for a specific review.
        """
        review = self.get_object()
        images = request.FILES.getlist('images')

        if not images:
            return Response({"detail": "No images uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        review_images = []
        for image in images:
            img = ReviewImages.objects.create(review=review, image=image)
            review_images.append(img)

        serializer = ReviewsImageSerializer(review_images, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class GoogleLogin(APIView):
    """
    API endpoint for Google OAuth2 login.
    Expects a POST with {'token': <Google ID token>}.
    """
    permission_classes = [permissions.AllowAny]  # to be used by any user

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            id_info = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                os.getenv('GOOGLE_CLIENT_ID')
            )
            email = id_info['email']
            first_name = id_info.get('given_name', '')
            last_name = id_info.get('family_name', '')
            picture = id_info.get('picture', None)

            role_instance = Role.objects.get(id=3)  # or use name="User" if preferred
            user, created = User.objects.get_or_create(email=email, defaults={
              'username': email,
              'first_name': first_name,
              'last_name': last_name,
              'google_login': True,
              'is_active': True,
              'is_email_verified': True,
              'last_login': timezone.now(),
              'role': role_instance,  # <-- Correct
            })
            # If user already exists, update google_login and names if needed
            if not created:
                updated = False
                if not user.google_login:
                    user.google_login = True
                    updated = True
                if first_name and user.first_name != first_name:
                    user.first_name = first_name
                    updated = True
                if last_name and user.last_name != last_name:
                    user.last_name = last_name
                    updated = True
                if updated:
                    user.save()

            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            })
        except Exception as e:
            print("Google login error:", e)  # Add this line for debugging
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
