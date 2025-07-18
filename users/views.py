from rest_framework import viewsets, permissions, filters, status, generics
from rest_framework.decorators import action, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView
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
from django.db import transaction

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

class RegisterView(generics.CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer

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


# vendor Views
class VendorApplicationView(generics.CreateAPIView):
    """
    View for users to apply for vendor status.
    Only authenticated users can apply.
    """
    serializer_class = VendorApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer: VendorApplicationSerializer) -> None:
        """Save vendor application and send notification email."""
        vendor = serializer.save()
        
        # Send notification email to admin
        try:
            send_mail(
                subject=f"New Vendor Application - {vendor.company_name}",
                message=(
                    f"A new vendor application has been submitted.\n\n"
                    f"User: {vendor.user.get_full_name()} ({vendor.user.username})\n"
                    f"Email: {vendor.user.email}\n"
                    f"Company: {vendor.company_name}\n"
                    f"Company Email: {vendor.company_email}\n"
                    f"Brand: {vendor.brand}\n\n"
                    f"Please review the application in the admin panel."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL],
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Failed to send vendor application notification: {e}")
            
        # Send confirmation email to applicant
        try:
            send_mail(
                subject="Vendor Application Received",
                message=(
                    f"Dear {vendor.user.first_name},\n\n"
                    f"Thank you for applying to become a vendor with us. "
                    f"We have received your application for {vendor.company_name}.\n\n"
                    f"Our team will review your application and get back to you soon.\n\n"
                    f"Best regards,\nThe MHE Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[vendor.user.email],
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Failed to send vendor application confirmation: {e}")


class VendorViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing vendor applications and information.
    
    - GET /vendors/ - List all vendors (Admin only)
    - POST /vendors/ - Create vendor application (Authenticated users)
    - GET /vendors/{id}/ - Get vendor details (Admin or vendor owner)
    - PUT/PATCH /vendors/{id}/ - Update vendor info (Admin or vendor owner)
    - DELETE /vendors/{id}/ - Delete vendor (Admin only)
    - POST /vendors/{id}/approve/ - Approve/reject vendor (Admin only)
    """
    queryset = Vendor.objects.select_related('user', 'user__role').all()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return VendorApplicationSerializer
        elif self.action == 'list':
            return VendorListSerializer
        elif self.action in ['update', 'partial_update']:
            return VendorUpdateSerializer
        elif self.action == 'approve':
            return VendorApprovalSerializer
        elif self.action == 'profile':
            return VendorProfileSerializer
        else:
            return VendorDetailSerializer
    
    def get_permissions(self):
        """Return appropriate permissions based on action."""
        if self.action == 'create':
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['list', 'destroy', 'approve']:
            permission_classes = [IsAdmin]
        elif self.action in ['retrieve', 'update', 'partial_update']:
            permission_classes = [IsOwnerOrAdmin]
        elif self.action == 'profile':
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        user = self.request.user
        
        if not user.is_authenticated:
            return Vendor.objects.none()
            
        if user.role.id == Role.ADMIN:
            return self.queryset
        elif user.role.id == Role.VENDOR:
            return self.queryset.filter(user=user)
        else:
            # Regular users can only see their own vendor application
            return self.queryset.filter(user=user)
    
    def create(self, request, *args, **kwargs):
        """Create vendor application."""
        # Check if user already has a vendor application
        if Vendor.objects.filter(user=request.user).exists():
            return Response(
                {'error': 'You already have a vendor application.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().create(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve or reject vendor application (Admin only)."""
        vendor = self.get_object()
        serializer = VendorApprovalSerializer(data=request.data)
        
        if serializer.is_valid():
            action = serializer.validated_data['action']
            reason = serializer.validated_data.get('reason', '')
            
            try:
                with transaction.atomic():
                    if action == 'approve':
                        # Change user role to vendor
                        vendor_role = Role.objects.get(id=Role.VENDOR)
                        vendor.user.role = vendor_role
                        vendor.user.save()
                        
                        # Send approval email
                        send_mail(
                            subject="Vendor Application Approved",
                            message=(
                                f"Dear {vendor.user.first_name},\n\n"
                                f"Congratulations! Your vendor application for {vendor.company_name} "
                                f"has been approved.\n\n"
                                f"You can now start adding products and managing your vendor account.\n\n"
                                f"Best regards,\nThe MHE Team"
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[vendor.user.email],
                            fail_silently=True,
                        )
                        
                        logger.info(f"Vendor application approved for {vendor.user.username}")
                        return Response({'message': 'Vendor application approved successfully.'})
                        
                    else:  # reject
                        # Send rejection email
                        send_mail(
                            subject="Vendor Application Status",
                            message=(
                                f"Dear {vendor.user.first_name},\n\n"
                                f"Thank you for your interest in becoming a vendor with us. "
                                f"After careful review, we are unable to approve your application "
                                f"for {vendor.company_name} at this time.\n\n"
                                f"Reason: {reason}\n\n"
                                f"You may reapply in the future once you have addressed the concerns mentioned.\n\n"
                                f"Best regards,\nThe MHE Team"
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[vendor.user.email],
                            fail_silently=True,
                        )
                        
                        # Delete the vendor application
                        vendor.delete()
                        
                        logger.info(f"Vendor application rejected for {vendor.user.username}")
                        return Response({'message': 'Vendor application rejected.'})
                        
            except Exception as e:
                logger.error(f"Error processing vendor approval: {e}")
                return Response(
                    {'error': 'Failed to process vendor application.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def profile(self, request, pk=None):
        """Get public vendor profile."""
        vendor = self.get_object()
        
        # Only show approved vendors publicly
        if vendor.user.role.id != Role.VENDOR:
            return Response(
                {'error': 'Vendor not found or not approved.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = VendorProfileSerializer(vendor)
        return Response(serializer.data)


class MyVendorApplicationView(generics.RetrieveUpdateAPIView):
    """
    View for users to check their own vendor application status and update it.
    """
    serializer_class = VendorDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        """Get current user's vendor application."""
        try:
            return Vendor.objects.select_related('user', 'user__role').get(user=self.request.user)
        except Vendor.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("You don't have a vendor application.")
    
    def get_serializer_class(self):
        """Return appropriate serializer based on method."""
        if self.request.method in ['PUT', 'PATCH']:
            return VendorUpdateSerializer
        return VendorDetailSerializer
    
    def update(self, request, *args, **kwargs):
        """Update vendor application (only if not yet approved)."""
        vendor = self.get_object()
        
        # Don't allow updates if already approved
        if vendor.user.role.id == Role.VENDOR:
            return Response(
                {'error': 'Cannot update approved vendor application.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().update(request, *args, **kwargs)


class ApprovedVendorListView(generics.ListAPIView):
    """
    Public view to list all approved vendors.
    """
    serializer_class = VendorProfileSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        """Return only approved vendors."""
        return Vendor.objects.select_related('user', 'user__role').filter(
            user__role__id=Role.VENDOR,
            user__is_active=True
        )


class VendorStatsView(generics.RetrieveAPIView):
    """
    View for admins to get vendor statistics.
    """
    permission_classes = [IsAdmin]
    
    def get(self, request, *args, **kwargs):
        """Get vendor application statistics."""
        total_applications = Vendor.objects.count()
        approved_vendors = Vendor.objects.filter(user__role__id=Role.VENDOR).count()
        pending_applications = total_applications - approved_vendors
        
        # Recent applications (last 30 days)
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        recent_applications = Vendor.objects.filter(
            user__date_joined__gte=thirty_days_ago
        ).count()
        
        return Response({
            'total_applications': total_applications,
            'approved_vendors': approved_vendors,
            'pending_applications': pending_applications,
            'recent_applications': recent_applications,
        })