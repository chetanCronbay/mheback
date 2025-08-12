from rest_framework import viewsets, permissions, filters, status, generics
from rest_framework.decorators import action, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.authentication import SessionAuthentication, BasicAuthentication

from products.models import Product
from products.serializers import ProductSerializer
from .models import *
from .serializers import *
from util.security import IPRateLimiter, SecurityLogger
from .permissions import IsAdmin, IsVendor, IsUser, IsOwnerOrAdmin, CanCreateReview, VendorAccessPermission
import os
from rest_framework.views import APIView
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
import random
from django.core.cache import cache
from products.models import Product, Quote, Rental
        

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
    permission_classes = [IsOwnerOrAdmin]  # Only admins can manage users
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication, BasicAuthentication]
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email', 'phone']
    parser_classes = [MultiPartParser, FormParser]

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser],
            authentication_classes=[JWTAuthentication, CsrfExemptSessionAuthentication, BasicAuthentication],
            # Change this permission class!
            permission_classes=[IsOwnerOrAdmin]) # Only the owner can upload a banner to their profile
    def upload_banner(self, request, pk=None):
        """
        Upload multiple banner images to a specific user.
        """
        user = self.get_object()
        images = request.FILES.get('user_banner')

        if not images:
            return Response({"detail": "No images uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        banners = []
        for image in images:
            banner = UserBanner.objects.create(user=user, image=image)
            banners.append(banner)

        serializer = UserBannerSerializer(banners, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['delete'], url_path='delete_banner/(?P<banner_id>[^/.]+)')
    def delete_banner(self, request, pk=None, banner_id=None):
        user = self.get_object()

        try:
            banner = user.user_banner.get(pk=banner_id)
        except UserBanner.DoesNotExist:
            return Response({'detail': 'Banner not found.'}, status=status.HTTP_404_NOT_FOUND)

        banner.image.delete(save=False)  # deletes the file
        banner.delete()
        return Response({'detail': 'Banner deleted.'}, status=status.HTTP_204_NO_CONTENT)

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
        """
        Optionally restricts the returned reviews to a given product,
        by filtering against a `product_id` query parameter in the URL.
        """
        queryset = Reviews.objects.all()
        product_id = self.request.query_params.get('product')
        if product_id is not None:
            queryset = queryset.filter(product_id=product_id)
        return queryset

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

# forget password
class ForgotPasswordRequestView(APIView):
    permission_classes = []

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # We don't need to assign the user object here, just check for existence
            User.objects.get(email=email)
        except User.DoesNotExist:
            # Security best practice: Don't reveal if an email exists or not.
            # Pretend the email was sent successfully to prevent user enumeration attacks.
            return Response({"detail": "If an account with this email exists, an OTP has been sent."}, status=status.HTTP_200_OK)

        otp = str(random.randint(100000, 999999))

        # --- SECURITY FIX ---
        # Store the OTP in the cache with a 10-minute expiry (600 seconds)
        # The key is unique to the email to avoid conflicts.
        cache.set(f"otp_{email}", otp, timeout=600)

        # Send OTP via email
        send_mail(
            subject="Password Reset OTP",
            message=f"Your OTP is {otp}. It is valid for 10 minutes.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )

        # --- SECURITY FIX ---
        # DO NOT return the OTP in the response.
        return Response({"detail": "If an account with this email exists, an OTP has been sent."}, status=status.HTTP_200_OK)

class ResetPasswordView(APIView):
    permission_classes = []

    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")  # Get OTP from request
        new_password = request.data.get("new_password")

        if not all([email, otp, new_password]):
            return Response({"error": "Email, OTP, and new password are required"}, status=status.HTTP_400_BAD_REQUEST)

        # --- SECURITY FIX ---
        # Verify the OTP
        stored_otp = cache.get(f"otp_{email}")
        if not stored_otp:
            return Response({"error": "OTP has expired or is invalid. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

        if stored_otp != otp:
            return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # This case is unlikely if the OTP was valid, but good to have
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        # If OTP is correct, set the new password and save
        user.set_password(new_password)
        user.save()

        # --- SECURITY FIX ---
        # OTP has been used, so delete it from the cache
        cache.delete(f"otp_{email}")

        return Response({"detail": "Password reset successfully"}, status=status.HTTP_200_OK)

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
    
    - GET /vendor/ - List all vendors (Public, queryable by anyone)
      - Query params: /vendor/?brand=some_brand&username=some_user
    - POST /vendor/ - Create vendor application (Authenticated users)
    - GET /vendor/me/ - Get vendor details (Admin or vendor owner)
    - PUT/PATCH /vendor/{id}/ - Update vendor info (Admin or vendor owner)
    - DELETE /vendor/{id}/ - Delete vendor (Admin only)
    - POST /vendor/{id}/approve/ - Approve/reject vendor (Admin only)
    - GET /vendor/{id}/stats/ - Get vendor stats (Admin or vendor owner)
    - GET /vendor/my-stats/ - Get current user's vendor stats (Authenticated)
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
        elif self.action == 'stats':
            return VendorStatsSerializer
        else:
            return VendorDetailSerializer
    
    def get_permissions(self):
        """Return appropriate permissions based on action."""
        
        # 🎯 Use your new permission class as the default for most actions
        if self.action in ['list', 'retrieve', 'create', 'update', 'partial_update']:
            permission_classes = [VendorAccessPermission]
        
        # Keep specific overrides for admin-only or special actions
        elif self.action in ['destroy', 'approve']:
            permission_classes = [IsAdmin]
            
        elif self.action == 'profile':
            permission_classes = [permissions.AllowAny]
            
        elif self.action in ['my_stats', 'my_vendor']:
            permission_classes = [permissions.IsAuthenticated]
            
        else:
            permission_classes = [permissions.IsAuthenticated] # A safe default
        
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'], url_path='me')
    def my_vendor(self, request):
        """Return the vendor profile of the logged-in user."""
        try:
            vendor = Vendor.objects.select_related('user', 'user__role').get(user=request.user)
        except Vendor.DoesNotExist:
            return Response({'error': 'No vendor found for this user.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(vendor)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='by-brand/(?P<brand_name>[^/.]+)')
    def by_brand(self, request, brand_name=None):
        """
        Get vendor details by brand name.
        """
        if not brand_name:
            return Response({'error': 'Brand name is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            # Using iexact for case-insensitive exact match
            vendor = self.queryset.get(brand__iexact=brand_name)
            serializer = VendorProfileSerializer(vendor) # Re-using VendorProfileSerializer
            return Response(serializer.data)
        except Vendor.DoesNotExist:
            return Response({'error': 'Vendor with this brand name not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error fetching vendor by brand: {e}")
            return Response({'error': 'An internal error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
      
    
    def get_queryset(self):
        """
        Filter queryset based on context.
        - For 'list' action, it's public and searchable.
        - For other actions, it's restricted by user role.
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # ✅ Action #2: If the action is 'list', apply search filters and return
        if self.action == 'list':
            brand = self.request.query_params.get('brand')
            username = self.request.query_params.get('username')
            
            if brand:
                queryset = queryset.filter(brand__icontains=brand)
            if username:
                queryset = queryset.filter(user__username__icontains=username)
            
            return queryset

        # For all other actions (retrieve, update, etc.), apply strict permissions
        if not user.is_authenticated:
            return Vendor.objects.none()
            
        if user.role.id == Role.ADMIN:
            return queryset
        else:
            return queryset.filter(user=user)
    
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
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get vendor statistics (Admin or vendor owner)."""
        vendor = self.get_object()
        
        # Basic vendor info
        stats = {
            'vendor_info': {
                'company_name': vendor.company_name,
                'brand': vendor.brand,
                'is_approved': vendor.user.role.id == Role.VENDOR,
                'application_date': vendor.user.date_joined,
                'status': 'Approved' if vendor.user.role.id == Role.VENDOR else 'Pending'
            }
        }
        
        # Only show detailed stats if vendor is approved
        if vendor.user.role.id == Role.VENDOR:
            # Account age
            account_age = timezone.now() - vendor.user.date_joined
            stats['account_info'] = {
                'days_since_joined': account_age.days,
                'account_status': 'Active' if vendor.user.is_active else 'Inactive'
            }
            
            # Performance metrics
            stats['performance'] = {
                'profile_completion': self._calculate_profile_completion(vendor),
                'last_updated': vendor.user.last_login or vendor.user.date_joined
            }
            
            total_quotes = Quote.objects.filter(product__user=vendor.user).count()
            pending_quotes = Quote.objects.filter(product__user=vendor.user, status='pending').count()
            
            total_rentals = Rental.objects.filter(product__user=vendor.user).count()
            pending_rentals = Rental.objects.filter(product__user=vendor.user, status='pending').count()

            stats['enquiry_stats'] = {
                'total_quotes': total_quotes,
                'pending_quotes': pending_quotes,
                'total_rentals': total_rentals,
                'pending_rentals': pending_rentals,
                'total_enquiries': total_quotes + total_rentals
            }
            # Add product stats if Product model exists
            # from your_app.models import Product
            # stats['products'] = {
            #     'total_products': Product.objects.filter(vendor=vendor).count(),
            #     'active_products': Product.objects.filter(vendor=vendor, is_active=True).count(),
            #     'recent_products': Product.objects.filter(
            #         vendor=vendor,
            #         created_at__gte=timezone.now() - timezone.timedelta(days=30)
            #     ).count()
            # }
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def my_stats(self, request):
        """Get current user's vendor statistics."""
        try:
            vendor = Vendor.objects.select_related('user', 'user__role').get(user=request.user)
        except Vendor.DoesNotExist:
            return Response(
                {'error': "You don't have a vendor application."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Use the same logic as the stats action
        return self.stats(request, pk=vendor.id)
    
    def _calculate_profile_completion(self, vendor):
        """Calculate profile completion percentage."""
        total_fields = 7  # Total important fields
        completed_fields = 0
        
        if vendor.company_name:
            completed_fields += 1
        if vendor.company_email:
            completed_fields += 1
        if vendor.company_address:
            completed_fields += 1
        if vendor.company_phone:
            completed_fields += 1
        if vendor.brand:
            completed_fields += 1
        if vendor.pcode:
            completed_fields += 1
        if vendor.gst_no:
            completed_fields += 1
            
        return round((completed_fields / total_fields) * 100, 2)


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
    
class MyVendorStatsView(generics.RetrieveAPIView):
    """
    View for individual vendors to get their own statistics.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        """Get current user's vendor application."""
        try:
            return Vendor.objects.select_related('user', 'user__role').get(user=self.request.user)
        except Vendor.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("You don't have a vendor application.")
    
    def get(self, request, *args, **kwargs):
        """Get vendor's own statistics."""
        vendor = self.get_object()
        
        # Basic vendor info
        stats = {
            'vendor_info': {
                'company_name': vendor.company_name,
                'brand': vendor.brand,
                'is_approved': vendor.user.role.id == Role.VENDOR,
                'application_date': vendor.user.date_joined,
                'status': 'Approved' if vendor.user.role.id == Role.VENDOR else 'Pending'
            }
        }
        
        # Only show detailed stats if vendor is approved
        if vendor.user.role.id == Role.VENDOR:
            total_quotes = Quote.objects.filter(product__user=vendor.user).count()
            pending_quotes = Quote.objects.filter(product__user=vendor.user, status='pending').count()
            
            total_rentals = Rental.objects.filter(product__user=vendor.user).count()
            pending_rentals = Rental.objects.filter(product__user=vendor.user, status='pending').count()

            stats['enquiry_stats'] = {
                'total_quotes': total_quotes,
                'pending_quotes': pending_quotes,
                'total_rentals': total_rentals,
                'pending_rentals': pending_rentals,
                'total_enquiries': total_quotes + total_rentals
            }
            # You can add more vendor-specific stats here
            # For example, if you have Product model related to vendors:
            
            # Assuming you have a Product model with vendor foreign key
            # from your_app.models import Product
            # stats['products'] = {
            #     'total_products': Product.objects.filter(vendor=vendor).count(),
            #     'active_products': Product.objects.filter(vendor=vendor, is_active=True).count(),
            #     'recent_products': Product.objects.filter(
            #         vendor=vendor,
            #         created_at__gte=timezone.now() - timezone.timedelta(days=30)
            #     ).count()
            # }
            
            # If you have Order model:
            # from your_app.models import Order
            # stats['orders'] = {
            #     'total_orders': Order.objects.filter(vendor=vendor).count(),
            #     'pending_orders': Order.objects.filter(vendor=vendor, status='pending').count(),
            #     'completed_orders': Order.objects.filter(vendor=vendor, status='completed').count(),
            #     'recent_orders': Order.objects.filter(
            #         vendor=vendor,
            #         created_at__gte=timezone.now() - timezone.timedelta(days=30)
            #     ).count()
            # }
            
            # Account age
            account_age = timezone.now() - vendor.user.date_joined
            stats['account_info'] = {
                'days_since_joined': account_age.days,
                'account_status': 'Active' if vendor.user.is_active else 'Inactive'
            }
            
            # Performance metrics (example)
            stats['performance'] = {
                'profile_completion': self._calculate_profile_completion(vendor),
                'last_updated': vendor.user.last_login or vendor.user.date_joined
            }
        
        return Response(stats)
    
    def _calculate_profile_completion(self, vendor):
        """Calculate profile completion percentage."""
        total_fields = 7  # Total important fields
        completed_fields = 0
        
        if vendor.company_name:
            completed_fields += 1
        if vendor.company_email:
            completed_fields += 1
        if vendor.company_address:
            completed_fields += 1
        if vendor.company_phone:
            completed_fields += 1
        if vendor.brand:
            completed_fields += 1
        if vendor.pcode:
            completed_fields += 1
        if vendor.gst_no:
            completed_fields += 1
            
        return round((completed_fields / total_fields) * 100, 2)

class VendorDashboardView(generics.RetrieveAPIView):
    """
    Comprehensive dashboard view for vendors with all relevant information.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        """Get current user's vendor application."""
        try:
            return Vendor.objects.select_related('user', 'user__role').get(user=self.request.user)
        except Vendor.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("You don't have a vendor application.")
    
    def get(self, request, *args, **kwargs):
        """Get comprehensive vendor dashboard data."""
        vendor = self.get_object()
        
        # Use the detail serializer to get basic vendor info
        vendor_serializer = VendorDetailSerializer(vendor)
        
        # Get stats from MyVendorStatsView logic
        stats_view = MyVendorStatsView()
        stats_view.request = request
        stats_response = stats_view.get(request)
        
        # Get vendor's products
        vendor_products = self._get_vendor_products(request.user)
        
        # Combine vendor details with stats and products
        dashboard_data = {
            'vendor_details': vendor_serializer.data,
            'stats': stats_response.data,
            'products': vendor_products,
            # 'quick_actions': self._get_quick_actions(vendor),
            'notifications': self._get_vendor_notifications(vendor)
        }
        
        return Response(dashboard_data)
    
    def _get_vendor_products(self, user):
        """Get products belonging to this vendor."""
        
        # Filter products by user (vendor)
        products = Product.objects.filter(user=user).select_related('user')
        
        # You can add ordering, limiting, or additional filtering here
        # For example, to show only active products:
        # products = products.filter(is_active=True)
        
        # To limit the number of products shown on dashboard:
        # products = products[:10]  # Show only first 10 products
        
        # To order by creation date (newest first):
        # products = products.order_by('-created_at')
        
        serializer = ProductSerializer(products, many=True)
        return serializer.data
    
    # def _get_quick_actions(self, vendor):
    #     """Get available quick actions for the vendor."""
    #     actions = []
        
    #     if vendor.user.role.id == Role.VENDOR:
    #         actions.extend([
    #             {
    #                 'action': 'add_product',
    #                 'label': 'Add New Product',
    #                 'url': '/api/products/',
    #                 'method': 'POST'
    #             },
    #             {
    #                 'action': 'view_orders',
    #                 'label': 'View Orders',
    #                 'url': '/api/orders/',
    #                 'method': 'GET'
    #             },
    #             {
    #                 'action': 'view_all_products',
    #                 'label': 'View All Products',
    #                 'url': '/api/products/',
    #                 'method': 'GET'
    #             },
    #             {
    #                 'action': 'update_profile',
    #                 'label': 'Update Profile',
    #                 'url': '/api/vendors/my-application/',
    #                 'method': 'PATCH'
    #             }
    #         ])
    #     else:
    #         actions.append({
    #             'action': 'update_application',
    #             'label': 'Update Application',
    #             'url': '/api/vendors/my-application/',
    #             'method': 'PATCH'
    #         })
        
    #     return actions
    
    def _get_vendor_notifications(self, vendor):
        """Get relevant notifications for the vendor."""
        notifications = []
        
        # Profile completion notification
        if vendor.user.role.id == Role.VENDOR:
            completion_percentage = self._calculate_profile_completion(vendor)
            if completion_percentage < 100:
                notifications.append({
                    'type': 'warning',
                    'message': f'Your profile is {completion_percentage}% complete. Complete your profile to improve visibility.',
                    'action': 'update_profile'
                })
            
            # Check if vendor has no products
            product_count = Product.objects.filter(user=vendor.user).count()
            if product_count == 0:
                notifications.append({
                    'type': 'info',
                    'message': 'You haven\'t added any products yet. Add your first product to start selling!',
                    'action': 'add_product'
                })
        else:
            notifications.append({
                'type': 'info',
                'message': 'Your vendor application is pending approval. You will be notified once it is reviewed.',
                'action': None
            })
        
        return notifications
    
    def _calculate_profile_completion(self, vendor):
        """Calculate profile completion percentage."""
        total_fields = 7
        completed_fields = 0
        
        if vendor.company_name:
            completed_fields += 1
        if vendor.company_email:
            completed_fields += 1
        if vendor.company_address:
            completed_fields += 1
        if vendor.company_phone:
            completed_fields += 1
        if vendor.brand:
            completed_fields += 1
        if vendor.pcode:
            completed_fields += 1
        if vendor.gst_no:
            completed_fields += 1
            
        return round((completed_fields / total_fields) * 100, 2)
    
class VendorNotificationListView(generics.ListAPIView):
    """
    A dedicated endpoint to list all aggregated event notifications
    for the currently authenticated vendor.
    """
    permission_classes = [permissions.IsAuthenticated]
    # We don't define a serializer_class because we are building the response manually.

    def list(self, request, *args, **kwargs):
        """
        Overrides the default list method to aggregate data from multiple models.
        """
        try:
            vendor = Vendor.objects.get(user=request.user)
        except Vendor.DoesNotExist:
            return Response({"error": "No vendor profile found for this user."}, status=status.HTTP_404_NOT_FOUND)

        notifications = []
        vendor_user = request.user
        since_date = timezone.now() - timezone.timedelta(days=30) # Look back 30 days

        # 1. Fetch new quote requests
        quote_requests = Quote.objects.filter(product__user=vendor_user, created_at__gte=since_date)
        for quote in quote_requests:
            notifications.append({
                'type': 'new_quote',
                'message': f"You have a new quote request for '{quote.product.name}' from user {quote.user.username}.",
                'timestamp': quote.created_at,
                'related_object': {'product_id': quote.product.id, 'quote_id': quote.id}
            })

        # 2. Fetch new rental requests
        rental_requests = Rental.objects.filter(product__user=vendor_user, created_at__gte=since_date)
        for rental in rental_requests:
            notifications.append({
                'type': 'new_rental',
                'message': f"You have a new rental request for '{rental.product.name}' from user {rental.user.username}.",
                'timestamp': rental.created_at,
                'related_object': {'product_id': rental.product.id, 'rental_id': rental.id}
            })

        # 3. Fetch product status changes (approved/rejected)
        product_status_updates = Product.objects.filter(user=vendor_user, status__in=['approved', 'rejected'], updated_at__gte=since_date)
        for product in product_status_updates:
            if product.status == 'approved':
                message = f"Congratulations! Your product '{product.name}' has been approved."
                notif_type = 'product_approved'
            else:
                message = f"Your product '{product.name}' was rejected. Reason: {product.rejection_reason or 'Not specified'}."
                notif_type = 'product_rejected'
            
            notifications.append({
                'type': notif_type,
                'message': message,
                'timestamp': product.updated_at,
                'related_object': {'product_id': product.id}
            })

        # 4. Fetch low stock warnings
        LOW_STOCK_THRESHOLD = 5
        low_stock_products = Product.objects.filter(user=vendor_user, is_active=True, stock_quantity__gt=0, stock_quantity__lte=LOW_STOCK_THRESHOLD)
        for product in low_stock_products:
             notifications.append({
                'type': 'low_stock',
                'message': f"Warning: Stock is low for '{product.name}'. Only {product.stock_quantity} left.",
                'timestamp': product.updated_at,
                'related_object': {'product_id': product.id}
            })
            
        # Sort all aggregated notifications by timestamp, newest first
        sorted_notifications = sorted(notifications, key=lambda x: x['timestamp'], reverse=True)
        
        return Response(sorted_notifications)
    
class TrainingRegistrationViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows training registrations to be viewed or edited.
    Anyone can submit a training registration.
    """
    queryset = TrainingRegistration.objects.all()
    serializer_class = TrainingRegistrationSerializer
    permission_classes = [permissions.AllowAny] # Anyone can perform CRUD operations
    authentication_classes = [] # No authentication required

    def perform_create(self, serializer):
        """
        Save the training registration and send confirmation/notification emails.
        """
        instance = serializer.save()
        
        # Send confirmation email to the registrant
        try:
            send_mail(
                subject=f"Training Registration Confirmation - {instance.training_name}",
                message=(
                    f"Dear {instance.full_name},\n\n"
                    f"Thank you for registering for our '{instance.training_name}' training program.\n"
                    f"We have received your details and will get in touch with you shortly.\n\n"
                    f"Here are your submitted details:\n"
                    f"Full Name: {instance.full_name}\n"
                    f"Company Name: {instance.company_name}\n"
                    f"Phone: {instance.phone}\n"
                    f"Email: {instance.email}\n"
                    f"Message: {instance.message or 'N/A'}\n\n"
                    f"Best regards,\nThe MHE Bazar Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.email],
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Failed to send training registration confirmation email to {instance.email}: {e}")

        # Send notification email to the admin
        try:
            send_mail(
                subject=f"New Training Registration - {instance.training_name}",
                message=(
                    f"A new training registration has been submitted.\n\n"
                    f"Training Name: {instance.training_name}\n"
                    f"Full Name: {instance.full_name}\n"
                    f"Company Name: {instance.company_name}\n"
                    f"Phone: {instance.phone}\n"
                    f"Email: {instance.email}\n"
                    f"Message: {instance.message or 'N/A'}\n"
                    f"Submitted At: {instance.submitted_at}\n"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL], # Or a specific training admin email
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Failed to send new training registration notification email to admin: {e}")

# New ViewSet for Newsletter Subscriptions
class NewsletterSubscriptionViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows newsletter subscriptions to be created, viewed, or deleted.
    Anyone can subscribe to the newsletter.
    """
    queryset = NewsletterSubscription.objects.all()
    serializer_class = NewsletterSubscriptionSerializer
    permission_classes = [permissions.AllowAny] # Anyone can subscribe
    authentication_classes = [] # No authentication required

    def create(self, request, *args, **kwargs):
        """
        Handle newsletter subscription creation.
        Ensures unique emails and sends confirmation.
        """
        email = request.data.get('email')
        if not email:
            return Response({'detail': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if email already subscribed
        if NewsletterSubscription.objects.filter(email=email).exists():
            return Response({'detail': 'This email is already subscribed.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        """
        Save the newsletter subscription and send confirmation/notification emails.
        """
        instance = serializer.save()

        # Send confirmation email to the subscriber
        try:
            send_mail(
                subject="Newsletter Subscription Confirmation",
                message=(
                    f"Dear Subscriber,\n\n"
                    f"Thank you for subscribing to our newsletter! You'll now receive updates on our latest products, offers, and news.\n\n"
                    f"If you wish to unsubscribe at any time, please contact us.\n\n"
                    f"Best regards,\nThe MHE Bazar Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.email],
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Failed to send newsletter confirmation email to {instance.email}: {e}")

        # Send notification email to the admin
        try:
            send_mail(
                subject="New Newsletter Subscriber",
                message=(
                    f"A new email has subscribed to the newsletter:\n\n"
                    f"Email: {instance.email}\n"
                    f"Subscribed At: {instance.subscribed_at}\n"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL], # Or a specific marketing admin email
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Failed to send new newsletter subscriber notification email to admin: {e}")