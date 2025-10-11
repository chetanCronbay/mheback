from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import AllowAny, IsAuthenticated
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, F, Value, IntegerField, Sum, Avg
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


# Helper function to assign a score based on match relevance (Higher is better)
def score_result(item, query_lower):
    """
    Scoring logic remains the same. The heavy lifting is now done by the Q object generation.
    """
    name_lower = item['name'].lower()
    score = 0
    
    # Simple check for the existence of the query in the name (most lenient check)
    if query_lower in name_lower:
        # 1. Perfect Exact Match
        if name_lower == query_lower:
            return 1000
        
        # 2. Starts With Match
        if name_lower.startswith(query_lower):
            return 800
        
        # 3. Exact Word Match
        if f' {query_lower} ' in f' {name_lower} ':
            return 600

        # 4. Partial Contains Match (Base score for anything that matches)
        return 10 + (100 / (name_lower.find(query_lower) + 1))
        
    return 1 # CRITICAL: Return minimum score of 1 to ensure inclusion in final list

# Highest number means highest priority
BUSINESS_PRIORITY = {
    'vendor': 7,          # 1st: Generic Vendor names (Highest priority type)
    'vendor_category': 6, # 2nd: BYD - Forklift (Vendor + Type match)
    'category': 5,        # 3rd: Forklift (Core Category)
    'subcategory': 4,     # 4th: Heavy Forklift (Specific category type)
    'product_type': 3,    # 5th: New Products / Rental Products
    'product': 2,         # 6th: Specific product names (e.g., FORKLIFT TYRE)
}

# Product Type Choices (Should be defined globally or imported)
TYPE_CHOICES = [
    ('new', 'New'),
    ('used', 'Used'),
    ('rental', 'Rental'),
    ('attachments', 'Attachments'),
]

class UniversalSearchViewSet(viewsets.GenericViewSet):
    """
    A single, optimized viewset for combined search suggestions (Products,
    Categories, Subcategories, and Approved Vendors).
    """
    queryset = Product.objects.none() 
    permission_classes = [AllowAny]
    pagination_class = None

    def list(self, request):
        query = request.query_params.get('search', '').strip()
        
        if not query: 
            return Response([])

        lower_query = query.lower()
        
        # 💥 FIX: Define the core search terms
        # 1. Always search for the full contiguous string (e.g., "3ton" or "3 ton")
        core_search_terms = [lower_query]
        
        # 2. If the query contains a space, break it into parts and include them too.
        if ' ' in lower_query:
            core_search_terms.extend([q.strip() for q in lower_query.split() if q.strip() and q.strip() != lower_query])
            
        # 💥 FIX: Update generate_atomic_q_filter to prioritize core_search_terms
        def generate_broad_q_filter(fields, search_terms):
            full_filter = Q()
            for field in fields:
                for term in search_terms:
                    full_filter = full_filter | Q(**{f'{field}__icontains': term})
            return full_filter

        # --- Common Data Setup ---
        User = get_user_model() 
        try:
            approved_user_ids = User.objects.filter(role__name='Vendor', is_active=True).values_list('id', flat=True) 
        except Exception:
            approved_user_ids = []

        # Check for EXACT Vendor Match (for ultimate boost)
        exact_vendor_matches = Vendor.objects.filter(
            Q(brand__iexact=query) | Q(company_name__iexact=query),
            user_id__in=approved_user_ids
        ).values_list('user_id', flat=True)
        
        is_exact_vendor_search = exact_vendor_matches.exists()

        # Check for Exact Category/Subcategory Match (to manage vendor visibility)
        is_exact_category_search = (
            Category.objects.filter(name__iexact=query).exists() or
            Subcategory.objects.filter(name__iexact=query).exists()
        )
        # ----------------------------------------------------

        # --- 1. Product Type Search (P3) ---
        product_type_results = []
        for slug, name in TYPE_CHOICES:
             # Match is still against the whole query since there are only 4 types
             if any(term in name.lower() or term in slug for term in core_search_terms):
                 product_type_results.append({
                     'id': f'pt_{slug}',
                     'name': f"{name} Products",
                     'type': 'product_type',
                     'category_slug': slug, 
                   })

        # --- 2. Product Search (P2) ---
        product_fields = ['name', 'model', 'manufacturer', 'type', 'category__name', 'subcategory__name']
        # Use the new filter to match "3ton" and "3 ton" equally well.
        product_query_filter = generate_broad_q_filter(product_fields, core_search_terms)

        products = Product.objects.filter(
            product_query_filter,
            is_active=True,
            status='approved'
        ).select_related('category', 'subcategory', 'user').prefetch_related('user__vendor').only(
            'id', 'name', 'model', 'category', 'subcategory', 'user'
        ).distinct()

        product_results = []
        for p in products:
            vendor_list = list(p.user.vendor.all())
            vendor = vendor_list[0] if vendor_list else None
            vendor_name = getattr(vendor, 'brand', None) or getattr(vendor, 'company_name', None) or 'N/A'
            
            product_results.append({
                'id': str(p.id), 
                'name': p.name,
                'type': 'product',
                'category_slug': p.category.name.lower().replace(' ', '-') if p.category else '', 
                'product_id': p.id,
                'model': p.model,
                'product_tags': {
                    'vendor': vendor_name,
                    'category': p.category.name if p.category else '',
                    'subcategory': p.subcategory.name if p.subcategory else '',
                },
                'user_id': p.user_id 
            })


        # --- 3 & 4. Category and Subcategory Search (P5 & P4) ---
        category_search_filter = generate_broad_q_filter(['name'], core_search_terms)
        categories = Category.objects.filter(category_search_filter).only('id', 'name')
        category_results = [{
            'id': f'c_{c.id}',
            'name': c.name,
            'type': 'category',
        } for c in categories]

        subcategory_search_filter = generate_broad_q_filter(['name'], core_search_terms)
        subcategories = Subcategory.objects.filter(subcategory_search_filter).select_related('category').only('id', 'name', 'category__name')
        subcategory_results = [{
            'id': f's_{s.id}',
            'name': f"{s.name} (Category: {s.category.name if s.category else 'N/A'})",
            'type': 'subcategory',
            'category_slug': s.category.name.lower().replace(' ', '-') if s.category else '', 
            'subcategory_slug': s.name.lower().replace(' ', '-') if s.name else '',
        } for s in subcategories]

        # --- 5, 6, 7. Vendor Aggregation and Specific Vendor Results ---
        
        # 5a. Vendors matching by Brand/Company Name (Stable query)
        vendor_fields = ['brand', 'company_name', 'user__username']
        vendor_name_match_query = generate_broad_q_filter(vendor_fields, core_search_terms)
        
        vendors_by_name = Vendor.objects.filter(
            vendor_name_match_query, 
            user_id__in=approved_user_ids
        ).distinct().select_related('user')
        
        # 5b. Vendors matching by Products (Stable, separate product lookup)
        product_model_vendor_query = generate_broad_q_filter(['name', 'model'], core_search_terms)
        product_model_vendor_ids = Product.objects.filter(
            product_model_vendor_query,
            is_active=True, 
            status='approved'
        ).values_list('user_id', flat=True).distinct()
        
        vendors_by_product_match = Vendor.objects.filter(
            user_id__in=product_model_vendor_ids
        ).filter(
            user_id__in=approved_user_ids
        ).select_related('user').distinct()

        # 5c. Vendors matching by Category (Original logic, stable)
        category_match_vendor_query = generate_broad_q_filter(['category__name', 'subcategory__name'], core_search_terms)
        category_match_vendor_ids = Product.objects.filter(
            category_match_vendor_query, 
            is_active=True, 
            status='approved'
        ).values_list('user_id', flat=True).distinct()
        
        vendors_by_category = Vendor.objects.filter(
            user_id__in=category_match_vendor_ids
        ).filter(
            user_id__in=approved_user_ids
        ).select_related('user').distinct()
        
        # Combine all unique vendors
        all_relevant_vendors = list(vendors_by_name) + list(vendors_by_category) + list(vendors_by_product_match)
        unique_vendor_map = {v.user_id: v for v in all_relevant_vendors}
        final_vendor_list = list(unique_vendor_map.values())

        vendor_results = []
        vendor_category_results = []
        
        for v in final_vendor_list:
            vendor_name = v.brand or v.company_name or v.user.username
            vendor_slug = vendor_name.lower().replace(' ', '-')
            
            # --- Generic Vendor Result (P7) ---
            vendor_results.append({
                'id': f'v_{v.id}',
                'name': vendor_name,
                'type': 'vendor',
                'vendor_slug': vendor_slug,
                'user_id': v.user_id,
            })
            
            # --- Vendor-Category (P6) Generation ---
            vendor_products = Product.objects.filter(
                user_id=v.user_id, 
                is_active=True, 
                status='approved',
            ).values_list(
                'category__name', 'category_id', 
            ).distinct()

            processed_vendor_categories = set()
            
            for category_name, category_id in vendor_products:
                if not category_name:
                    continue
                    
                is_category_match = any(term in category_name.lower() for term in core_search_terms)
                
                should_generate_category_entry = is_category_match or (is_exact_vendor_search and v.user_id in exact_vendor_matches)
                
                if should_generate_category_entry and category_name not in processed_vendor_categories:
                    vendor_category_name = f"{v.brand or v.company_name} - {category_name}"
                    category_slug = category_name.lower().replace(' ', '-')
                    
                    vendor_category_results.append({
                        'id': f'vc_{v.id}_{category_id}', 
                        'name': vendor_category_name,
                        'type': 'vendor_category',
                        'vendor_slug': vendor_slug,
                        'category_slug': category_slug,
                        'user_id': v.user_id 
                    })
                    processed_vendor_categories.add(category_name)

        # --- PHASE 2: Apply Multi-Level Sorting ---
        
        all_results = (
            vendor_results +          # P7 (Vendor)
            vendor_category_results + # P6 (Vendor Category)
            category_results +        # P5 (Category)
            subcategory_results +     # P4 (Subcategory)
            product_type_results +    # P3 (Product Type)
            product_results           # P2 (Product)
        )
        
        scored_results = [
            (score_result(item, lower_query), item) for item in all_results
        ]
        
        # Remove duplicates
        unique_results_map = {}
        for score, item in scored_results:
            key = (item['type'], item['name']) 
            if key not in unique_results_map or score > unique_results_map[key][0]:
                unique_results_map[key] = (score, item)
                
        scored_results = list(unique_results_map.values())


        # Determine the effective priority for sorting:
        def get_effective_priority(item_type, score):
            base_priority = BUSINESS_PRIORITY.get(item_type, 0)
            
            # 1. Ultimate Vendor Boost (for exact BYD search)
            if is_exact_vendor_search and item_type in ['vendor', 'vendor_category', 'product']:
                # The exact vendor search should boost only the relevant vendor's items.
                if item_type == 'vendor':
                    # Only boost if the vendor is in the exact match list
                    user_id = item.get('user_id')
                    if user_id in exact_vendor_matches:
                        return base_priority * 100000 
                return base_priority * 100000 # Boost associated category/product items
            
            # 2. Demote generic vendors if the search is not a strong match
            if item_type == 'vendor' and score < 500:
                return base_priority / 100
            
            return base_priority
            

        final_sorted_results = sorted(
            scored_results,
            key=lambda x: (
                get_effective_priority(x[1]['type'], x[0]),
                x[0], # Secondary Sort: Relevance Score
                x[1]['name'] # Tertiary Sort: Name
            ),
            reverse=True
        )

        # Return all items with score >= 1
        final_items = [item for score, item in final_sorted_results if score >= 1] 
        
        return Response(final_items)