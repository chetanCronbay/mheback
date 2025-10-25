from rest_framework import viewsets, permissions, filters, status, response
from rest_framework.decorators import action
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import AllowAny, IsAuthenticated
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, F, Value, IntegerField, Sum, Avg, OuterRef, Subquery
from .models import *
from .serializers import *
from users.permissions import ReadOnlyOrAdmin, IsVendorOwnerOrAdmin, IsAdmin
from users.models import Role, Vendor  # Import Role model or constant
from django.contrib.auth import get_user_model # For the User model
from django.db import transaction
from django.core.mail import send_mail
from rest_framework.pagination import PageNumberPagination
import django_filters
from django.conf import settings
import logging
from django.db.models import Q 

logger = logging.getLogger(__name__)

# class QuoteThrottle(UserRateThrottle):
#     scope = 'quote'
#     rate = '10/hour'

# class RentalThrottle(UserRateThrottle):
#     scope = 'rental'
#     rate = '10/hour'

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [ReadOnlyOrAdmin]  # Read for all, write for admin only
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = None

    
    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__iexact=name)
        return queryset

    def get_permissions(self):
        if self.action in ['upload_Image', 'upload_Banner']:
            return [IsAdmin()]
        return super().get_permissions()

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_Image(self, request, pk=None):
        category = self.get_object()
        image = request.FILES.get('cat_image')
        if image:
            category.cat_image = image
            category.save()
        serializer = self.get_serializer(category)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_Banner(self, request, pk=None):
        category = self.get_object()
        banner = request.FILES.get('cat_banner')
        if banner:
            category.cat_banner = banner
            category.save()
        serializer = self.get_serializer(category)
        return Response(serializer.data)

class SubcategoryViewSet(viewsets.ModelViewSet):
    queryset = Subcategory.objects.all()
    serializer_class = SubcategorySerializer
    permission_classes = [ReadOnlyOrAdmin]  # Read for all, write for admin only
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category']
    search_fields = ['name', 'description']
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = None

    def get_permissions(self):
        if self.action in ['upload_Image', 'upload_Banner']:
            return [IsAdmin()]
        return super().get_permissions()

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_Image(self, request, pk=None):
        subcategory = self.get_object()
        image = request.FILES.get('sub_image')
        if image:
            subcategory.sub_image = image
            subcategory.save()
        serializer = self.get_serializer(subcategory)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_Banner(self, request, pk=None):
        subcategory = self.get_object()
        banner = request.FILES.get('sub_banner')
        if banner:
            subcategory.sub_banner = banner
            subcategory.save()
        serializer = self.get_serializer(subcategory)
        return Response(serializer.data)

class ProductPagination(PageNumberPagination):
    page_size = 12 # Default page size
    page_size_query_param = 'page_size' # Allows client to set page size e.g. /?page_size=20
    max_page_size = 100

    def get_paginated_response(self, data):
        # Get the full filtered queryset before it was paginated
        unpaginated_queryset = self.page.paginator.object_list
        
        # Calculate the count of non-active products within the filtered results
        not_approved = unpaginated_queryset.filter(is_active=False).count()
        
        return Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'count': self.page.paginator.count,
            'not_approved_count': not_approved, # Add the custom count here
            'results': data
        })

class ProductFilter(django_filters.FilterSet):
    # This explicitly defines the 'types' filter.
    # It tells Django to expect a text value and use it in a 'contains' query
    # against the 'types' JSONField.
    type = django_filters.CharFilter(field_name='type', lookup_expr='contains')

    # You can also move your other filters here for cleaner code
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr='lte')
    average_rating = django_filters.NumberFilter(method='filter_by_rating')

    class Meta:
        model = Product
        # These are the fields that can be filtered with a simple 'exact' match
        fields = ['category', 'subcategory', 'user']

    def filter_by_rating(self, queryset, name, value):
        # This custom method handles the rating annotation and filtering
        return queryset.annotate(
            avg_rating=Avg('reviews__stars')
        ).filter(avg_rating__gte=value)


class ProductViewSet(viewsets.ModelViewSet):
    """
    Images:
    - DELETE /api/products/{id}/delete-images/
      Payload: {"image_ids": [1, 2, 3]}

    - PUT /api/products/{id}/update-images/
      Payload: FormData with:
        - images: [file1, file2, ...]
        - image_ids: [1, 2, ...]

    Brochure:
    - DELETE /api/products/{id}/delete-brochure/

    - PUT /api/products/{id}/update-brochure/
      Payload: FormData with:
        - brochure: file
    """

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsVendorOwnerOrAdmin]
    pagination_class = ProductPagination
    
    # --- CORRECTED: Added OrderingFilter ---
    filter_backends = [
        DjangoFilterBackend, 
        filters.SearchFilter, 
        filters.OrderingFilter
    ]
    
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'manufacturer', 'model']
    
    # --- NEW: Define allowed ordering fields ---
    ordering_fields = ['price', 'created_at', 'updated_at', 'name']
    # Default ordering if none is specified by the client
    ordering = ['updated_at']

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        """
        Dynamically filters the queryset based on the user's role and ownership,
        ensuring Vendors see their own products PLUS the public catalog.
        """
        queryset = super().get_queryset()
        user = self.request.user

        # --- FIX: Define the base criteria for a PUBLIC product FIRST ---
        public_products_criteria = Q(
            user__role__id=Role.VENDOR,  # Must be listed by a Vendor role user
            user__is_active=True,        # The vendor user must be active
            is_active=True,              # The product itself must be marked active
            status='approved'            # The product must be approved by an Admin
        )
        # -----------------------------------------------------------------

        if not user.is_authenticated:
            # Anonymous users/Regular Users: Only see the public catalog
            return queryset.filter(public_products_criteria).order_by('-updated_at')

        # 1. Admins see everything
        if hasattr(user, 'role') and user.role.id == Role.ADMIN:
            return queryset
        
        # 2. VENDOR FIX: Vendor sees their OWN products OR all public products.
        if hasattr(user, 'role') and user.role.name == 'Vendor':
             # Now public_products_criteria is correctly defined and used here
             return queryset.filter(Q(user=user) | public_products_criteria).order_by('-updated_at')

        # 3. Default for other authenticated non-admin, non-vendor users
        return queryset.filter(public_products_criteria).order_by('-updated_at')

    @action(detail=False, methods=['get'], url_path='map-user')
    def map_user(self, request):
        """
        Provides a simple list mapping each product ID to its owner's user ID.
        This is a lightweight endpoint optimized for frontend filtering.
        """
        # 1. Get the optimized queryset
        queryset = Product.objects.only('id', 'user')
        
        # 2. Serialize the data
        serializer = ProductUserMapSerializer(queryset, many=True)
        
        # 3. Return the serialized data in a Response object
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='unique-manufacturers')
    def unique_manufacturers(self, request):
        """
        Return a list of unique manufacturer names from the Product model.
        """
        manufacturers = (
            Product.objects
            .exclude(manufacturer__isnull=True)
            .exclude(manufacturer__exact="")
            .values_list('manufacturer', flat=True)
            .distinct()
        )
        return Response({
            "results": [{"manufacturer": name} for name in manufacturers]
        })
    def get_permissions(self):
        if self.action in ['add_to_cart', 'add_to_wishlist']:
            return [IsAuthenticated()]
        return super().get_permissions()
    
    @action(detail=False, methods=['patch'], url_path='bulk-update-status')
    def bulk_update_status(self, request):
        ids = request.data.get('ids', [])
        is_active = request.data.get('is_active', None)

        if not isinstance(ids, list) or is_active is None:
            return Response({"detail": "Invalid input."}, status=400)

        Product.objects.filter(id__in=ids).update(is_active=is_active)
        return Response({"detail": "Updated successfully."})

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_images(self, request, pk=None):
        product = self.get_object()
        images = request.FILES.getlist('images')
        for image in images:
            ProductImage.objects.create(product=product, image=image)
        serializer = self.get_serializer(product)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_brochure(self, request, pk=None):
        product = self.get_object()
        brochure = request.FILES.get('brochure')
        if brochure:
            product.brochure = brochure
            product.save()
        serializer = self.get_serializer(product)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_to_cart(self, request, pk=None):
        product = self.get_object()
        quantity = request.data.get('quantity', 1)
        
        cart_item, created = Cart.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={'quantity': quantity}
        )
        
        if not created:
            cart_item.quantity += int(quantity)
            cart_item.save()
            
        serializer = CartSerializer(cart_item)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_to_wishlist(self, request, pk=None):
        product = self.get_object()
        wishlist_item, created = Wishlist.objects.get_or_create(
            user=request.user,
            product=product
        )
        serializer = WishlistSerializer(wishlist_item)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='new-arrival')
    def new_arrival(self, request):
        """
        Get top 10 products by creation date (most recent first).
        """
        products = Product.objects.filter(is_active=True, status='approved').order_by('-created_at')[:10]
        serializer = self.get_serializer(products, many=True)
        return Response({
            'count': products.count(),
            'products': serializer.data
        })
    
    @action(detail=False, methods=['get'], url_path='top-rated')
    def top_rated(self, request):
        """
        Get top 10 products by average review star count.
        Products without reviews are excluded.
        """
        products = (
            Product.objects.filter(is_active=True, status='approved')
            .annotate(avg_rating=Avg('reviews__stars'))
            .filter(avg_rating__isnull=False) # Ensure only products with ratings are included
            .order_by('-avg_rating', '-created_at')[:10]
        )
        serializer = self.get_serializer(products, many=True)
        return Response({
            'count': products.count(),
            'products': serializer.data
        })

    @action(detail=False, methods=['get'])
    def most_popular(self, request):
        """
        Get top 10 products by popularity (sum of quotes, wishlists, carts).
        """
        products = (
            Product.objects.filter(is_active=True, status='approved')
            .annotate(
                # CORRECTED: Use the correct reverse relationship names
                quote_count=Count('quote', distinct=True),
                wishlist_count=Count('wishlist', distinct=True),
                cart_count=Count('cart', distinct=True),
                popularity=F('quote_count') + F('wishlist_count') + F('cart_count')
            )
            .order_by('-popularity', '-created_at')[:10]
        )
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['delete'], url_path='delete-images')
    def delete_images(self, request, pk=None):
        """Delete specified product images"""
        product = self.get_object()
        image_ids = request.data.get('image_ids', [])
        
        if not image_ids:
            return Response({"detail": "No image IDs provided."}, status=400)
            
        deleted = ProductImage.objects.filter(
            product=product,
            id__in=image_ids
        ).delete()
        
        return Response({
            "detail": f"Deleted {deleted[0]} images.",
            "status": "success"
        })

    @action(detail=True, methods=['put'], url_path='update-images')
    def update_images(self, request, pk=None):
        """Update product images"""
        product = self.get_object()
        images = request.FILES.getlist('images')
        image_ids = request.data.getlist('image_ids', [])
        
        if len(images) != len(image_ids):
            return Response({
                "detail": "Number of images and image IDs must match."
            }, status=400)
            
        updated_images = []
        for image_id, new_image in zip(image_ids, images):
            try:
                product_image = ProductImage.objects.get(
                    id=image_id,
                    product=product
                )
                product_image.image = new_image
                product_image.save()
                updated_images.append(product_image)
            except ProductImage.DoesNotExist:
                return Response({
                    "detail": f"Image with ID {image_id} not found."
                }, status=404)
                
        serializer = ProductImageSerializer(updated_images, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['delete'], url_path='delete-brochure')
    def delete_brochure(self, request, pk=None):
        """Delete product brochure"""
        product = self.get_object()
        if product.brochure:
            product.brochure.delete()
            product.save()
            return Response({
                "detail": "Brochure deleted successfully.",
                "status": "success"
            })
        return Response({
            "detail": "No brochure found.",
            "status": "not_found"
        }, status=404)

    @action(detail=True, methods=['put'], url_path='update-brochure')
    def update_brochure(self, request, pk=None):
        """Update product brochure"""
        product = self.get_object()
        brochure = request.FILES.get('brochure')
        
        if not brochure:
            return Response({
                "detail": "No brochure file provided."
            }, status=400)
            
        # Delete old brochure if it exists
        if product.brochure:
            product.brochure.delete()
            
        product.brochure = brochure
        product.save()
        serializer = self.get_serializer(product)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a product (Admin only)"""
        if not request.user.role.id == Role.ADMIN:
            return Response(status=status.HTTP_403_FORBIDDEN)
            
        product = self.get_object()
        
        try:
            with transaction.atomic():
                product.status = 'approved'
                product.is_active = True
                product.save()
                
                # Send notification email to vendor
                send_mail(
                    subject="Product Approved",
                    message=(
                        f"Dear {product.user.first_name},\n\n"
                        f"Your product '{product.name}' has been approved "
                        f"and is now live on our platform.\n\n"
                        f"Best regards,\nThe Admin Team"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[product.user.email],
                    fail_silently=True,
                )
                
                logger.info(f"Product {product.id} approved by admin {request.user.id}")
                
                serializer = self.get_serializer(product)
                return Response({
                    'message': 'Product approved successfully.',
                    'product': serializer.data
                })
                
        except Exception as e:
            logger.error(f"Error approving product {product.id}: {e}")
            return Response(
                {'error': 'Failed to approve product.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a product (Admin only)"""
        if not request.user.role.id == Role.ADMIN:
            return Response(status=status.HTTP_403_FORBIDDEN)
            
        product = self.get_object()
        reason = request.data.get('reason', '')
        
        if not reason:
            return Response(
                {'error': 'Rejection reason is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                product.status = 'rejected'
                product.is_active = False
                product.rejection_reason = reason
                product.save()
                
                # Send notification email to vendor
                send_mail(
                    subject="Product Rejected",
                    message=(
                        f"Dear {product.user.first_name},\n\n"
                        f"Your product '{product.name}' has been rejected.\n\n"
                        f"Reason: {reason}\n\n"
                        f"Please make the necessary changes and submit for review again.\n\n"
                        f"Best regards,\nThe Admin Team"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[product.user.email],
                    fail_silently=True,
                )
                
                logger.info(f"Product {product.id} rejected by admin {request.user.id}")
                
                serializer = self.get_serializer(product)
                return Response({
                    'message': 'Product rejected successfully.',
                    'product': serializer.data
                })
                
        except Exception as e:
            logger.error(f"Error rejecting product {product.id}: {e}")
            return Response(
                {'error': 'Failed to reject product.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class ProductSearchViewSet(viewsets.ModelViewSet):
    """
    A viewset for a lean, fast search of all active, approved products.
    It returns only the product ID and name for quick suggestions.
    """
    queryset = Product.objects.filter(is_active=True, status='approved').only('id', 'name')
    serializer_class = ProductSearchSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'manufacturer', 'model']
    pagination_class = None # No pagination needed for a fast search endpoint

class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Set the authenticated user
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'])
    def clear(self, request):
        self.get_queryset().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)  # 👈 Yeh line jaroori hai


class QuoteViewSet(viewsets.ModelViewSet):
    """
    A ViewSet for viewing and managing quotes.
    - Admins can see all quotes.
    - Vendors can see quotes related to their products.
    - Users can see their own quotes.
    - Supports filtering by status, searching, and ordering.
    """
    serializer_class = QuoteSerializer
    # --- UPDATED: Allow submissions from non-logged-in users ---
    permission_classes = [AllowAny]
    # throttle_classes = [QuoteThrottle] # Uncomment if you have this

    # 1. Add Filter Backends
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    # 2. Define fields for each backend
    filterset_fields = ['status']  # Enables: /quotes/?status=pending
    search_fields = ['product__name', 'user__username', 'product__user__username'] # Enables: /quotes/?search=some_term
    ordering_fields = ['created_at', 'product__name'] # Enables: /quotes/?ordering=-created_at

    def get_queryset(self):
        """
        Dynamically filter the queryset based on the user's role.
        """
        user = self.request.user
        
        # Non-authenticated users cannot view quotes (GET requests)
        if not user.is_authenticated:
            return Quote.objects.none()

        # Use select_related to optimize DB queries by pre-fetching related objects
        base_queryset = Quote.objects.select_related('product', 'user', 'product__user')

        if user.role.id == Role.ADMIN:
            return base_queryset.all().order_by('-created_at')
        
        if user.role.name == 'Vendor':
            return base_queryset.filter(product__user=user).order_by('-created_at')
            
        return base_queryset.filter(user=user).order_by('-created_at')

    def perform_create(self, serializer):
        user = self.request.user
        
        # --- UPDATED: Handle throttling for logged-in users and allow anonymous submission ---
        if user and user.is_authenticated:
            # Check for throttling on authenticated users
            recent_requests = Quote.objects.filter(
                user=user,
                last_request_time__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            if recent_requests >= 5:
                # If using a proper DRF throttle, this would be handled automatically, 
                # but with manual check, we raise a validation error.
                raise serializers.ValidationError("Too many quote requests recently. Please wait before submitting another.")
            
            serializer.save(user=user)
        else:
            # For anonymous users, we save without a user object (requires model.user to be null=True)
            serializer.save(user=None)
        # ------------------------------------------------------------------------------------------

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if not request.user.role.id == Role.ADMIN:
            return Response(status=status.HTTP_403_FORBIDDEN)
        quote = self.get_object()
        quote.status = 'approved'
        quote.save()
        serializer = self.get_serializer(quote)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if not request.user.role.id == Role.ADMIN:
            return Response(status=status.HTTP_403_FORBIDDEN)
        quote = self.get_object()
        quote.status = 'rejected'
        quote.save()
        serializer = self.get_serializer(quote)
        return Response(serializer.data)

class RentalViewSet(viewsets.ModelViewSet):
    serializer_class = RentalSerializer
    # --- UPDATED: Allow submissions from non-logged-in users ---
    permission_classes = [AllowAny]
    # throttle_classes = [RentalThrottle]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']  # For filtering by status (e.g., /rentals/?status=pending)
    search_fields = ['product__name', 'user__username', 'product__user__username'] # For search
    ordering_fields = ['created_at', 'product__name'] # For sorting

    def get_queryset(self):
        user = self.request.user
        
        # Non-authenticated users cannot view rentals (GET requests)
        if not user.is_authenticated:
            return Rental.objects.none()
            
        # Use select_related for query optimization
        base_queryset = Rental.objects.select_related('product', 'user', 'product__user')

        if user.role.id == Role.ADMIN:
            return base_queryset.all().order_by('-created_at')
        elif user.role.name == 'Vendor':
            return base_queryset.filter(product__user=user).order_by('-created_at')
        return base_queryset.filter(user=user).order_by('-created_at')

    def perform_create(self, serializer):
        user = self.request.user
        
        # --- UPDATED: Allow anonymous submission ---
        if user and user.is_authenticated:
            serializer.save(user=user)
        else:
            # For anonymous users, we save without a user object (requires model.user to be null=True)
            serializer.save(user=None)
        # -------------------------------------------

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if not request.user.role.id == Role.ADMIN:
            return Response(status=status.HTTP_403_FORBIDDEN)
        rental = self.get_object()
        rental.status = 'approved'
        rental.save()
        serializer = self.get_serializer(rental)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if not request.user.role.id == Role.ADMIN:
            return Response(status=status.HTTP_403_FORBIDDEN)
        rental = self.get_object()
        rental.status = 'rejected'
        rental.save()
        serializer = self.get_serializer(rental)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_returned(self, request, pk=None):
        if not request.user.role.id == Role.ADMIN:
            return Response(status=status.HTTP_403_FORBIDDEN)
        rental = self.get_object()
        rental.status = 'returned'
        rental.save()
        serializer = self.get_serializer(rental)
        return Response(serializer.data)
    
    
    
# In products/views.py (Place this section near the end of the file)

# Make sure these are defined near the top of your views.py:
# from django.db.models import Q 
# from django.contrib.auth import get_user_model 
# from users.models import Role, Vendor 
# from .models import Product, Category, Subcategory, etc.
# ... (Other ViewSets and definitions remain above)
# ====================================================================
# 🚀 NEW: MHE Abbreviation Mapping
# ====================================================================
MHE_ABBREVIATIONS = {
    'hpt': 'hand pallet truck',
    'hpt-ss': 'stainless steel hand pallet truck',
    'hpt-ws': 'weighing scale hand pallet truck',
    'hpt-sl': 'scissors hand pallet truck',
    'hs': 'manul stacker',
    'mhs': 'semi-electric stacker',
    'st': 'stacker',
    'st-cb': 'counter balance stacker',
    'e-hpt': 'electric pallet truck',
    'bopt': 'battery operated pallet truck',
    'pt': 'platform truck / trolly',
    'tt': 'tow truck',
    'dfl': 'diesel forklift',
    'efl (li-ion)': 'electric forklift (lithium-ion battery)',
    'efl (lead-acid)': 'electric forklift (lead-acid battery)',
    'flt-art.': 'articulated forklift',
    'hfl': 'heavy forklift',
    'flt': 'forklift',
    'chfl': 'container handler forklift',
    'sl': 'scissors lift',
    'sp-sl': 'self-propelled scissors lift',
    'awp': 'aerial work platform',
    'gl': 'goods lift',
    'dl': 'dock leveler',
    'dr': 'dock ramp / mobile dock ramp',
    'rt': 'reach truck',
    'ddrt': 'double deep reach truck',
    'rk': 'racking system',
    'vna': 'very narrow aisle truck',
    'agv': 'automated guided vehicle',
    'op': 'order picker',
    'gc': 'golf cart',
    'th': 'telehandler',
    'li-ion batt.': 'mhe bazar li-ion battery kit',
    'bl': 'boom lift',
    '4dml': '4dml',
}
# ====================================================================


# Priority constants for final sorting. Higher number means higher priority group.
PRIORITY = {
    'vendor_category': 4,# Vendor + Relevant Category Link
    'vendor': 3,
    'category': 2,
    'subcategory': 1,
    'product': 0,# Specific Product Suggestion
    'product_type': -1,# Product Type Link (Lowest)
    'top_product': 5, # 🚀 NEW: Highest priority for exact Vendor/Category match products
}

# Product Type Choices (Must match model definition)
TYPE_CHOICES = [
    ('new', 'New'),
    ('used', 'Used'),
    ('rental', 'Rental'),
    ('attachments', 'Attachments'),
]

# Simple slug function 
def create_slug(name):
    return (name or '').lower().replace(' ', '-')

# Helper function to get the vendor name via a subquery to avoid complex joins in the main product query
# This requires Django 1.11+ and is safer than complex select_related chains.
# NOTE: This function's body is typically not needed, but kept for context fidelity.
def get_vendor_name_subquery():
    # Annotate Product with the first matching Vendor's brand/company name
    # We use Subquery to handle the reverse ForeignKey/related_name relationship safely.
    # NOTE: This assumes a Product's user has AT MOST one Vendor entry.
    # Placeholder: Vendor and Product models assumed to be imported
    # first_vendor = Vendor.objects.filter(user=OuterRef('user')).order_by('pk')
    
    # return Product.objects.annotate(
    #     vendor_brand_sub=Subquery(first_vendor.values('brand')[:1]),
    #     vendor_company_sub=Subquery(first_vendor.values('company_name')[:1]),
    #     category_name_sub=Subquery(Category.objects.filter(pk=OuterRef('category_id')).values('name')[:1]),
    #     subcategory_name_sub=Subquery(Subcategory.objects.filter(pk=OuterRef('subcategory_id')).values('name')[:1])
    # )
    pass


# ====================================================================
# 🚀 MODIFIED LOGIC: Separate Function for Combination Check returns matched names
# ====================================================================
def _check_vendor_category_in_query(query, expanded_phrase_full, vendor_name_to_id_map, category_name_to_id_map):
    """
    Checks if the search query (or its expansion) contains both a known vendor name 
    and a known category name, returning the best matched lowercased names.
    """
    
    vendor_match = None
    category_match = None

    # 1. Check for Vendor match (find the first vendor name present in the query)
    for name_lower in vendor_name_to_id_map.keys():
        if name_lower and name_lower in query:
            vendor_match = name_lower
            break
            
    # 2. Check for Category match (find the first category name present in the query or expansion)
    all_category_names = category_name_to_id_map.keys()
    
    # Check raw query
    for name_lower in all_category_names:
        if name_lower and name_lower in query:
            category_match = name_lower
            break
            
    # Check expanded phrase for category if no match yet
    if not category_match and expanded_phrase_full:
        for name_lower in all_category_names:
            # Check if category name is a substring of the expanded phrase
            if name_lower and name_lower in expanded_phrase_full:
                category_match = name_lower
                break
    
    if vendor_match and category_match:
        # Return the lowercased names to be used as keys for ID lookup
        return (vendor_match, category_match)
    
    return (None, None)
# ====================================================================

# NOTE: The imports (viewsets, AllowAny, response, Q, Subquery, OuterRef, F, get_user_model, Vendor, Product, Category, Subcategory)
# are assumed to be available from the original context, but not re-defined here.
# Assuming the necessary Django model classes (Vendor, Product, Category, Subcategory) 
# and Django/DRF imports (viewsets, AllowAny, response, Q, Subquery, OuterRef, F, get_user_model) are in scope.

class UniversalSearchViewSet(viewsets.GenericViewSet):
    """
    Optimized multi-model search with ultra-loose character matching and scoring.
    Priority order: Score (High) > Group (Vendor-Category > Vendor > Category > Subcategory > Product > Product Type).
    """
    permission_classes = [AllowAny]

    def list(self, request):
        # 1. Prepare query and initial data structures (O(1) / O(N) setup)
        
        # Capture raw query key for abbreviation check
        raw_query_key = request.query_params.get('search', '').strip()
        query = raw_query_key.lower() 
        if not query: return response.Response([]) 

        # 🚀 NEW LOGIC: Abbreviation Expansion
        expanded_query_phrase = query
        expanded_phrase_full = None
        
        if raw_query_key in MHE_ABBREVIATIONS:
            expanded_phrase_full = MHE_ABBREVIATIONS[raw_query_key].lower()
            # Augment the search string for matching/filtering
            expanded_query_phrase = f"{query} {expanded_phrase_full}"
        
        # Set the character set based on the expanded phrase
        query_chars = set(expanded_query_phrase)

        # Helper to generate the core OR filter for loose character matching
        def create_char_filter(fields):
            char_filter = Q()
            for char in query_chars:
                for field in fields:
                    # Uses query_chars (from expanded phrase) for filtering
                    char_filter |= Q(**{f'{field}__icontains': char})
            return char_filter

        # Helper for scoring (Set Intersection)
        def calculate_score(name_lower):
            # Base score remains character intersection from expanded phrase
            score = sum(1 for char in query_chars if char in name_lower) 
            
            # Original exact match bonus (checks the user's input before expansion)
            if query in name_lower: score += 1000 
            
            # 🚀 NEW LOGIC: Bonus for matching the expanded full phrase
            if expanded_phrase_full and expanded_phrase_full in name_lower:
                score += 1000
                
            return score

        # ----------------------------------------------------
        # 2. Search Logic (Database optimization: single query per model)
        # ----------------------------------------------------
        all_results_with_score = []
        
        # NOTE: Model calls below are standard, relying on the updated filtering/scoring helpers.

        # Assuming get_user_model is imported/available
        approved_ids = get_user_model().objects.filter(role__name='Vendor', is_active=True).values_list('id', flat=True)

        # 🚀 MODIFIED: Use dictionaries to map lowercased name to ID for combination check
        approved_vendor_name_to_id = {}
        all_category_name_to_id = {}
        # Also map vendor user_id to brand/company name for the top result display
        vendor_user_id_to_name = {}
        # Also map category_id to name for the top result display
        category_id_to_name = {}


        # --- P4: VENDOR-CATEGORIES ---
        vendor_match_filter = create_char_filter(['user__vendor__brand', 'user__vendor__company_name'])
        category_match_filter = create_char_filter(['category__name', 'subcategory__name'])
        combined_product_filter = category_match_filter | vendor_match_filter

        # FIX: Removed select_related('user__vendor') and used .values() only, relying on the JOINs implied by the filter.
        vendor_category_matches = Product.objects.filter(
            combined_product_filter, user_id__in=approved_ids, is_active=True, status='approved'
        ).values(
            'user__vendor__user_id', 'user__vendor__brand', 'user__vendor__company_name', 'category__id', 'category__name'
        ).distinct()
        
        processed_vendor_categories = set()

        for match in vendor_category_matches:
            vendor_user_id = match['user__vendor__user_id']
            category_id = match['category__id']
            
            key = (vendor_user_id, category_id)
            if key in processed_vendor_categories: continue
            processed_vendor_categories.add(key)
            
            vendor_name = match.get('user__vendor__brand') or match.get('user__vendor__company_name') or ''
            category_name = match['category__name']
            
            # 🚀 MODIFIED: Populate dictionaries with ID mapping and reverse mapping
            vendor_name_lower = vendor_name.lower()
            category_name_lower = category_name.lower()
            if vendor_name_lower:
                approved_vendor_name_to_id[vendor_name_lower] = vendor_user_id # Name to user_id
                vendor_user_id_to_name[vendor_user_id] = vendor_name # user_id to name
            if category_name_lower:
                all_category_name_to_id[category_name_lower] = category_id # Name to category_id
                category_id_to_name[category_id] = category_name # category_id to name

            result_name = f"{vendor_name} - {category_name}"
            combined_name_lower = f"{vendor_name.lower()} {category_name.lower()}"
            score = calculate_score(combined_name_lower)
            
            if score > 0:
                all_results_with_score.append((
                    PRIORITY['vendor_category'], score, {
                        'id': f'vc_{vendor_user_id}_{category_id}', 'name': result_name, 'type': 'vendor_category', 
                        'vendor_slug': create_slug(vendor_name), 'category_slug': create_slug(category_name),
                    }
                ))
        
        # --- P3: VENDORS ---
        vendor_filter = create_char_filter(['brand', 'company_name'])
        vendors = Vendor.objects.filter(vendor_filter, user_id__in=approved_ids).select_related('user').distinct()

        for v in vendors:
            name = v.brand or v.company_name or v.user.username
            name_lower = name.lower()
            
            # 🚀 MODIFIED: Populate dictionaries with ID mapping
            if v.brand: approved_vendor_name_to_id[v.brand.lower()] = v.user_id
            if v.company_name: approved_vendor_name_to_id[v.company_name.lower()] = v.user_id
            vendor_user_id_to_name[v.user_id] = name # Update reverse mapping

            score = calculate_score(name_lower)
            
            is_exact_vendor_match = name_lower == query or (v.brand and v.brand.lower() == query) or (v.company_name and v.company_name.lower() == query)
            
            effective_priority = PRIORITY['vendor']
            if is_exact_vendor_match:
                effective_priority = PRIORITY['vendor_category'] + 10 

            if score > 0:
                all_results_with_score.append((
                    effective_priority, score, {'id': f'v_{v.id}', 'name': name, 'type': 'vendor', 'vendor_slug': create_slug(name)}
                ))

        # --- P2: CATEGORIES ---
        category_filter = create_char_filter(['name'])
        categories = Category.objects.filter(category_filter).only('id', 'name')
        
        for c in categories:
            name_lower = c.name.lower()
            # 🚀 MODIFIED: Populate dictionaries with ID mapping
            all_category_name_to_id[name_lower] = c.id
            category_id_to_name[c.id] = c.name # Update reverse mapping
            
            score = calculate_score(name_lower)
            if score > 0:
                all_results_with_score.append((
                    PRIORITY['category'], score, {'id': f'c_{c.id}', 'name': c.name, 'type': 'category', 'category_slug': create_slug(c.name)}
                ))
        
        # --- P1: SUBCATEGORIES ---
        subcategory_filter = create_char_filter(['name'])
        subcategories = Subcategory.objects.filter(subcategory_filter).select_related('category').only('id', 'name', 'category__name', 'category__id')
        
        for s in subcategories:
            full_name = f"{s.name} ({s.category.name if s.category else 'N/A'})"
            score = calculate_score(s.name.lower())
            
            # 🚀 MODIFIED: Populate dictionaries with parent category ID mapping
            if s.category:
                all_category_name_to_id[s.category.name.lower()] = s.category.id # Ensure parent category is included
                category_id_to_name[s.category.id] = s.category.name # Update reverse mapping

            if score > 0:
                all_results_with_score.append((
                    PRIORITY['subcategory'], score, {
                        'id': f's_{s.id}', 'name': full_name, 'type': 'subcategory', 
                        'category_slug': create_slug(s.category.name) if s.category else '',
                        'subcategory_slug': create_slug(s.name),
                    }
                ))
        
        # --- P0: PRODUCTS (Standard Search) ---
        product_fields = ['name', 'model', 'manufacturer']
        product_filter = create_char_filter(product_fields)

        # Apply filtering and subqueries for vendor/category names
        products_qs = Product.objects.filter(
            product_filter, user_id__in=approved_ids, is_active=True, status='approved'
        )

        # Use the annotation structure to safely pull related data without crashing on reverse FK
        products = products_qs.annotate(
            vendor_brand=Subquery(Vendor.objects.filter(user=OuterRef('user')).values('brand')[:1]),
            vendor_company_name=Subquery(Vendor.objects.filter(user=OuterRef('user')).values('company_name')[:1]),
            category_name=F('category__name'),
            subcategory_name=F('subcategory__name'),
            # Select the necessary fields explicitly
        ).values('id', 'name', 'model', 'manufacturer', 'vendor_brand', 'vendor_company_name', 'category_name', 'subcategory_name', 'user_id', 'category_id').distinct()

        # Store products that would be eligible for the TOP PRODUCTS list
        product_results = []
        
        for p in products:
            vendor_name = p['vendor_brand'] or p['vendor_company_name'] or ''
            product_url_slug = create_slug(f"{p['name']} {p['model'] or ''} {p['manufacturer'] or ''}")

            combined_name_lower = f"{p['name'].lower()} {p['model'].lower() if p['model'] else ''} {p['manufacturer'].lower() if p['manufacturer'] else ''}"
            score = calculate_score(combined_name_lower)
            
            if score > 0:
                display_name = f"{p['name']} ({p['model'] or p['manufacturer'] or 'Product'})"
                
                result_item = (
                    PRIORITY['product'], score, {
                        'id': f"p_{p['id']}", 'name': display_name, 'type': 'product',
                        'product_id': p['id'],
                        'url': f'/product/{product_url_slug}-{p["id"]}', 
                        'product_tags': {
                            'vendor': vendor_name,
                            'category': p['category_name'] or '',
                            'subcategory': p['subcategory_name'] or '',
                            'model': p['model'] or '',
                        },
                        'user_id': p['user_id'], # Keep these for exact match filtering
                        'category_id': p['category_id'],
                    }
                )
                all_results_with_score.append(result_item)
                # Store the raw product result for potential top-product selection
                product_results.append(result_item)
        
        # --- P-1: PRODUCT TYPES (NEW BLOCK) ---
        for slug, name in TYPE_CHOICES:
            name_lower = name.lower()
            score = 0
            if query in name_lower:
                score = calculate_score(name_lower)
            
            if score > 0:
                all_results_with_score.append((
                    PRIORITY['product_type'], score, {
                        'id': f'pt_{slug}', 'name': f"{name} Products", 'type': 'product_type',
                        'category_slug': slug, 
                        'url': f'/search?type={slug}'
                    }
                ))


        # ----------------------------------------------------
        # 3. Final Sort and Return (DSA: Timsort)
        # ----------------------------------------------------
        
        # **Note:** The original final_sorted_results calculation will be performed here,
        # but the logic below will selectively prepend and filter items.

        # 🚀 MODIFIED: Identify remaining search terms for secondary scoring
        
        query_words = set(query.split())
        vendor_names = set(approved_vendor_name_to_id.keys())
        category_names = set(all_category_name_to_id.keys())
        
        # Remove identified vendor and category words
        remaining_query_words = query_words.difference(vendor_names).difference(category_names)
        
        # Add non-category words from the abbreviation expansion
        if expanded_phrase_full:
            expanded_words = set(expanded_phrase_full.split())
            for word in expanded_words:
                if word not in category_names:
                    remaining_query_words.add(word)

        # Filter out numbers, small words, and common separators
        filter_out_words = {'of', 'a', 'can', 'i', 'get', 'the', 'for', 'with', 'which', 'what', 'is', 'are', 'we', 'to', 'truck', 'model', 'series', 'tonne', 'ton', 'capacity'}
        # Final set of terms to use for secondary scoring
        secondary_relevance_terms = {word for word in remaining_query_words if word not in filter_out_words and len(word) > 2}

        
        final_response_list = []
        
        matched_vendor_name, matched_category_name = _check_vendor_category_in_query(
            query, 
            expanded_query_phrase, # Use expanded phrase for query check here (was expanded_phrase_full before, query is correct)
            approved_vendor_name_to_id, 
            all_category_name_to_id
        )

        if matched_vendor_name and matched_category_name:
            # 1. Get IDs and Names
            vendor_user_id = approved_vendor_name_to_id.get(matched_vendor_name)
            category_id = all_category_name_to_id.get(matched_category_name)
            vendor_display_name = vendor_user_id_to_name.get(vendor_user_id)
            category_display_name = category_id_to_name.get(category_id)
            
            # Only proceed if we have valid IDs for the search
            if vendor_user_id is not None and category_id is not None:
                # 2. Add the Vendor-Category Link (P4 style) to the top
                vendor_category_link = {
                    'id': f'vc_{vendor_user_id}_{category_id}', 
                    'name': f"{vendor_display_name or matched_vendor_name.upper()} - {category_display_name or matched_category_name.upper()}", 
                    'type': 'vendor_category', 
                    'vendor_slug': create_slug(vendor_display_name), 
                    'category_slug': create_slug(category_display_name),
                    'priority_override': PRIORITY['top_product'] + 1 
                }
                final_response_list.append(vendor_category_link)

                # 3. Filter and Score products matching this exact combination
                top_products_with_score = []
                remaining_results_ids = set() # Track IDs to remove them from the main sorted list

                for priority, score, item in product_results:
                    # Check for exact user_id and category_id match
                    if item.get('user_id') == vendor_user_id and item.get('category_id') == category_id:
                        
                        # 🚀 NEW SECONDARY SCORING LOGIC
                        secondary_score = 0
                        
                        # Concatenate relevant product fields for comparison
                        product_text = f"{item['name']} {item['product_tags']['subcategory']} {item['product_tags']['model']}".lower()

                        for term in secondary_relevance_terms:
                            if term in product_text:
                                secondary_score += 1 
                        
                        # Create the final result object without the temporary user_id/category_id keys
                        top_product_item = {k: v for k, v in item.items() if k not in ['user_id', 'category_id']}
                        
                        # Store with the secondary score
                        top_products_with_score.append((secondary_score, top_product_item))
                        remaining_results_ids.add(item['id'])
                
                # Sort the top products by the new secondary score (highest first)
                top_products_with_score.sort(key=lambda x: x[0], reverse=True)
                
                # Add the exact-match products next
                final_response_list.extend([item for score, item in top_products_with_score])
                
                # 4. Append the remaining results (which must be computed here or reused from the previous step)
                
                # Re-calculate final_sorted_results since it was missing in the previous step's context
                final_sorted_results = sorted(
                    all_results_with_score, 
                    key=lambda x: (x[1], x[0], x[2]['name']), # (Score DESC, Priority DESC, Name ASC)
                    reverse=True
                )
                
                # Iterate through the newly calculated main sorted list and append non-promoted items
                for priority, score, item in final_sorted_results:
                    # Safely check if the item is a promoted product using its ID
                    # Use .get('id') to avoid error on non-product items
                    item_id = item.get('id')
                    
                    if item['type'] == 'product' and item_id in remaining_results_ids:
                        continue # Skip products that were promoted to the top
                        
                    # Remove temporary product-related keys before final response
                    if item['type'] == 'product':
                        item = {k: v for k, v in item.items() if k not in ['user_id', 'category_id']}
                        
                    final_response_list.append(item)
                
            else:
                # If lookup failed, fallback to the original sorted list structure
                # We need to compute it first if we reach this fallback path
                final_sorted_results = sorted(
                    all_results_with_score, 
                    key=lambda x: (x[1], x[0], x[2]['name']),
                    reverse=True
                )
                final_response_list = [item for priority, score, item in final_sorted_results]
        else:
            # No combination found, use the original sorted list structure
            final_sorted_results = sorted(
                all_results_with_score, 
                key=lambda x: (x[1], x[0], x[2]['name']),
                reverse=True
            )
            final_response_list = [item for priority, score, item in final_sorted_results]
            
        return response.Response(final_response_list)