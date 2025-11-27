import json
from rest_framework import viewsets, permissions, filters, status, response
from rest_framework.decorators import action
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
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
    ordering = ['-updated_at']

    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    # --- NEW HELPER: Process YouTube Links (Workaround to store URL in ImageField) ---
    def _process_youtube_links(self, product, youtube_links_json):
        """Helper to create ProductImage records for new YouTube links."""
        # 🚨 FIX: Ensure the input string is not empty or malformed before loading.
        if not youtube_links_json or youtube_links_json in ('[', ']') or youtube_links_json.strip() == '':
            youtube_links_json = '[]'
            
        try:
            youtube_links = json.loads(youtube_links_json)
            if not isinstance(youtube_links, list):
                 youtube_links = [youtube_links] if youtube_links else []
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to decode youtube_links for product {product.id}. Received: {youtube_links_json}. Error: {e}")
            return
        
        # Only add links that do not already exist
        existing_images_or_videos = ProductImage.objects.filter(product=product).values_list('image', flat=True)
        
        for link in youtube_links:
            # Check if link exists and is a string
            if link and isinstance(link, str) and link not in existing_images_or_videos:
                # 🚨 THE JUGAAD: Directly set the string URL into the ImageField. 
                # This insertion should now consistently work as it's a direct string assignment.
                try:
                    ProductImage.objects.create(
                        product=product,
                        image=link, # Storing the URL string
                    )
                    logger.info(f"SUCCESS: Added new YouTube link (forced string) for product {product.id}: {link}")
                except Exception as e:
                     logger.error(f"CRITICAL INSERTION ERROR for product {product.id}: {e}")


    # --- MODIFIED: perform_create (FIXED IMMUTABLE & JSON DECODE ERRORS) ---
    def perform_create(self, serializer):
        # 🚨 FIX: Create a mutable copy of request.data
        mutable_data = self.request.data.copy()
        
        # 1. Extract YouTube links safely (handles QueryDict and Dict)
        youtube_links_list = mutable_data.get('youtube_links', ['[]'])
        youtube_links_json = youtube_links_list[0] if isinstance(youtube_links_list, list) and youtube_links_list else '[]'

        # Remove the field from mutable data if it was present
        if 'youtube_links' in mutable_data:
            mutable_data.pop('youtube_links') 
        
        # 2. Save the main product
        product = serializer.save(user=self.request.user)

        # 3. Process and save the new YouTube links
        self._process_youtube_links(product, youtube_links_json)
        
    # --- MODIFIED: perform_update (FIXED IMMUTABLE & JSON DECODE ERRORS) ---
    def perform_update(self, serializer):
        # 🚨 FIX: Create a mutable copy of request.data
        mutable_data = self.request.data.copy()

        # 1. Extract YouTube links safely (handles QueryDict and Dict)
        youtube_links_list = mutable_data.get('youtube_links', ['[]'])
        youtube_links_json = youtube_links_list[0] if isinstance(youtube_links_list, list) and youtube_links_list else '[]'
        
        # Remove the field from mutable data if it was present
        if 'youtube_links' in mutable_data:
            mutable_data.pop('youtube_links')

        # 2. Save the main product
        product = serializer.save()

        # 3. Process and save the new YouTube links
        self._process_youtube_links(product, youtube_links_json)

    def get_queryset(self):
        """
        Dynamically filters the queryset based on the user's role and ownership,
        ensuring Vendors see their own products PLUS the public catalog.
        """
        queryset = super().get_queryset()
        user = self.request.user

        # --- FIX: Define the base criteria for a PUBLIC product FIRST ---
        public_products_criteria = Q(
            user__role__id=Role.VENDOR, 
            user__is_active=True,       
            is_active=True,             
            status='approved'           
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
             return queryset.filter(Q(user=user) | public_products_criteria).order_by('-updated_at')

        # 3. Default for other authenticated non-admin, non-vendor users
        return queryset.filter(public_products_criteria).order_by('-updated_at')

    @action(detail=False, methods=['get'], url_path='map-user')
    def map_user(self, request):
        """
        Provides a simple list mapping each product ID to its owner's user ID.
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

    # --- MODIFIED: upload_images (This handles all file uploads, including the main image) ---
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_images(self, request, pk=None):
        product = self.get_object()
        images = request.FILES.getlist('images')
        
        if not images:
             return Response(self.get_serializer(product).data)

        created_images = []
        for image in images:
            # Create the ProductImage object.
            img_instance = ProductImage.objects.create(product=product, image=image)
            created_images.append(img_instance)
            
        logger.info(f"Uploaded {len(created_images)} images for product {product.id}")
        
        serializer = ProductImageSerializer(created_images, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


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
            .filter(avg_rating__isnull=False) 
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
                quote_count=Count('quote', distinct=True),
                wishlist_count=Count('wishlist', distinct=True),
                cart_count=Count('cart', distinct=True),
                popularity=F('quote_count') + F('wishlist_count') + F('cart_count')
            )
            .order_by('-popularity', '-created_at')[:10]
        )
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    # --- MODIFIED: delete_images (To skip file deletion for URL strings) ---
    @action(detail=True, methods=['delete'], url_path='delete-images')
    def delete_images(self, request, pk=None):
        """Delete specified product images or video links"""
        product = self.get_object()
        image_ids = request.data.get('image_ids', [])
        
        if not image_ids:
            return Response({"detail": "No image IDs provided."}, status=400)
            
        images_to_delete = ProductImage.objects.filter(
            product=product,
            id__in=image_ids
        )
        
        deleted_count = 0
        
        # Safely delete files for actual images, skip for URL strings
        for img in images_to_delete:
            # Check if the 'image' value is a string (meaning it's the raw URL string we inserted)
            is_video_link = isinstance(img.image, str) and (img.image.lower().startswith('http') or img.image.lower().startswith('www.'))
            
            if not is_video_link:
                 img.image.delete(save=False)
            
            # Delete the database record
            img.delete()
            deleted_count += 1
            
        return Response({
            "detail": f"Deleted {deleted_count} images/videos.",
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
    
    
    
class ProductVendorPhoneView(APIView):
    """
    Retrieves the company_phone number of the vendor who owns a specific product.
    Endpoint: /api/product/<int:product_id>/vendor-phone/
    """
    permission_classes = [AllowAny] # Usually public for product details pages

    def get(self, request, product_id):
        try:
            # 1. Fetch the Product object
            product = Product.objects.get(id=product_id)
            
            # 2. Use the product's user_id (product.user_id) to find the Vendor
            # Using select_related/prefetch_related is not efficient here as we only need one Vendor object
            vendor = Vendor.objects.get(user_id=product.user_id)
            
            # 3. Serialize and return the phone number
            serializer = VendorPhoneSerializer(vendor)
            
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Product.DoesNotExist:
            return Response({
                "detail": f"Product with ID {product_id} not found."
            }, status=status.HTTP_404_NOT_FOUND)

        except Vendor.DoesNotExist:
            return Response({
                "detail": f"Vendor not found for product ID {product_id}."
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            # Log unexpected errors
            logger.error(f"Error fetching vendor phone for product {product_id}: {e}")
            return Response({
                "detail": "An unexpected error occurred."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Make sure these are defined near the top of your views.py:
# from django.db.models import Q 
# from django.contrib.auth import get_user_model 
# from users.models import Role, Vendor 
# from .models import Product, Category, Subcategory, etc.
# ... (Other ViewSets and definitions remain above)
# ====================================================================
# NECESSARY IMPORTS (Ensure these are available in your Django file)
# ====================================================================
# from django.db.models import Q, F, Subquery, OuterRef
# from rest_framework import viewsets, response
# from rest_framework.permissions import AllowAny
# NOTE: Assume Models and Django functions are correctly imported.
# ====================================================================
# ====================================================================
# NECESSARY IMPORTS (Ensure these are available in your Django file)
# ====================================================================
# from django.db.models import Q, F, Subquery, OuterRef
# from rest_framework import viewsets, response
# from rest_framework.permissions import AllowAny
# NOTE: Assume Models and Django functions are correctly imported.
# ====================================================================

# ====================================================================
# CUSTOM CONSTANTS AND HELPERS (Defined for context)
# ====================================================================

MHE_ABBREVIATIONS = {
    'hpt': 'hand pallet truck', 'hpt-ss': 'stainless steel hand pallet truck', 'hpt-ws': 'weighing scale hand pallet truck',
    'hpt-sl': 'scissors hand pallet truck', 'hs': 'manul stacker', 'mhs': 'semi-electric stacker', 'st': 'stacker',
    'st-cb': 'counter balance stacker', 'e-hpt': 'electric pallet truck', 'bopt': 'battery operated pallet truck',
    'pt': 'platform truck / trolly', 'tt': 'tow truck', 'dfl': 'diesel forklift', 'efl (li-ion)': 'electric forklift (lithium-ion battery)',
    'efl (lead-acid)': 'electric forklift (lead-acid battery)', 'flt-art.': 'articulated forklift', 'hfl': 'heavy forklift',
    'flt': 'forklift', 'chfl': 'container handler forklift', 'sl': 'scissors lift', 'sp-sl': 'self-propelled scissors lift',
    'awp': 'aerial work platform', 'gl': 'goods lift', 'dl': 'dock leveler', 'dr': 'dock ramp / mobile dock ramp',
    'rt': 'reach truck', 'ddrt': 'double deep reach truck', 'rk': 'racking system', 'vna': 'very narrow aisle truck',
    'agv': 'automated guided vehicle', 'op': 'order picker', 'gc': 'golf cart', 'th': 'telehandler',
    'li-ion batt.': 'mhe bazar li-ion battery kit', 'bl': 'boom lift', '4dml': '4dml',
}

PRIORITY = {
    'vendor_category': 4, 'vendor': 3, 'category': 2, 'subcategory': 1, 'product': 0, 
    'product_type': -1, 'top_product': 5,
}

PRODUCT_MATCH_PRIORITY = {
    'name': 0, 'model_manufacturer': 1, 'subcategory': 2, 'category': 3, 'vendor': 4,
    'product_exact': 10 
}

TYPE_CHOICES = [
    ('new', 'New'), ('used', 'Used'), ('rental', 'Rental'), ('attachments', 'Attachments'),
]

def create_slug(name):
    return (name or '').lower().replace(' ', '-')

def _check_vendor_category_in_query(query, expanded_phrase_full, vendor_name_to_id_map, category_name_to_id_map):
    vendor_match = None
    category_match = None

    for name_lower in vendor_name_to_id_map.keys():
        if name_lower and name_lower in query:
            vendor_match = name_lower
            break
            
    all_category_names = category_name_to_id_map.keys()
    for name_lower in all_category_names:
        if name_lower and name_lower in query:
            category_match = name_lower
            break
            
    if not category_match and expanded_phrase_full:
        for name_lower in all_category_names:
            if name_lower and name_lower in expanded_phrase_full:
                category_match = name_lower
                break
    
    return (vendor_match, category_match)
# ====================================================================


class UniversalSearchViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        # 1. PREPARE QUERY & HELPERS 
        raw_query_key = request.query_params.get('search', '').strip()
        query = raw_query_key.lower() 
        if not query: return response.Response([]) 

        expanded_query_phrase = query
        expanded_phrase_full = None
        if raw_query_key in MHE_ABBREVIATIONS:
            expanded_phrase_full = MHE_ABBREVIATIONS[raw_query_key].lower()
            expanded_query_phrase = f"{query} {expanded_phrase_full}"
        query_chars = set(expanded_query_phrase)

        def create_char_filter(fields):
            char_filter = Q()
            for char in query_chars:
                for field in fields:
                    char_filter |= Q(**{f'{field}__icontains': char})
            return char_filter

        def calculate_score(name_lower):
            score = sum(1 for char in query_chars if char in name_lower) 
            if query in name_lower: score += 1000 
            if expanded_phrase_full and expanded_phrase_full in name_lower: score += 1000
            return score

        # Data structures
        all_results_with_score = []
        approved_ids = get_user_model().objects.filter(role__name='Vendor', is_active=True).values_list('id', flat=True)

        approved_vendor_name_to_id = {}
        all_category_name_to_id = {}
        vendor_user_id_to_name = {}
        category_id_to_name = {}
        
        # Exact Match Tracking
        exact_vendor_match_item = None
        exact_category_match_item = None
        exact_subcategory_match_item = None
        exact_product_match_item = None
        exact_product_type_match_item = None
        
        vendor_category_links_to_promote = []
        product_results = [] # Stores (priority, score, item_dict) tuples


        # 2. DATA GATHERING (P4 - P-1)
        
        # --- P4: VENDOR-CATEGORIES --- 
        vendor_match_filter = create_char_filter(['user__vendor__brand', 'user__vendor__company_name'])
        category_match_filter = create_char_filter(['category__name', 'subcategory__name'])
        combined_product_filter = category_match_filter | vendor_match_filter

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
            vendor_name_lower = vendor_name.lower()
            category_name_lower = category_name.lower()
            
            if vendor_name_lower:
                approved_vendor_name_to_id[vendor_name_lower] = vendor_user_id
                vendor_user_id_to_name[vendor_user_id] = vendor_name
            if category_name_lower:
                all_category_name_to_id[category_name_lower] = category_id
                category_id_to_name[category_id] = category_name

            result_name = f"{vendor_name} - {category_name}"
            combined_name_lower = f"{vendor_name.lower()} {category_name.lower()}"
            score = calculate_score(combined_name_lower)
            
            if score > 0:
                item = {
                    'id': f'vc_{vendor_user_id}_{category_id}', 'name': result_name, 'type': 'vendor_category', 
                    'vendor_slug': create_slug(vendor_name), 'category_slug': create_slug(category_name),
                    'user_id': vendor_user_id, 'category_id': category_id 
                }
                all_results_with_score.append((PRIORITY['vendor_category'], score, item))
                
                if vendor_name_lower == query:
                    vendor_category_links_to_promote.append(item)


        # --- P3: VENDORS (Capture exact match) ---
        vendor_filter = create_char_filter(['brand', 'company_name'])
        vendors = Vendor.objects.filter(vendor_filter, user_id__in=approved_ids).select_related('user').distinct()

        for v in vendors:
            name = v.brand or v.company_name or v.user.username
            name_lower = name.lower()
            score = calculate_score(name_lower)
            
            is_strict_exact_match = name_lower == query
            effective_priority = PRIORITY['vendor']
            
            if is_strict_exact_match:
                effective_priority = PRIORITY['vendor_category'] + 10 
                exact_vendor_match_item = {
                    'id': f'v_{v.id}', 'name': name, 'type': 'vendor', 'vendor_slug': create_slug(name),
                    'user_id': v.user_id 
                }

            if score > 0:
                all_results_with_score.append((
                    effective_priority, score, {'id': f'v_{v.id}', 'name': name, 'type': 'vendor', 'vendor_slug': create_slug(name)}
                ))


        # --- P2: CATEGORIES (Capture exact match) ---
        category_filter = create_char_filter(['name'])
        categories = Category.objects.filter(category_filter).only('id', 'name')
        
        for c in categories:
            name_lower = c.name.lower()
            all_category_name_to_id[name_lower] = c.id
            category_id_to_name[c.id] = c.name
            score = calculate_score(name_lower)
            
            item = {'id': f'c_{c.id}', 'name': c.name, 'type': 'category', 'category_slug': create_slug(c.name), 'category_id': c.id}
            
            if score > 0:
                all_results_with_score.append((PRIORITY['category'], score, item))
                if name_lower == query:
                    exact_category_match_item = item

        # --- P1: SUBCATEGORIES (Capture exact match) ---
        subcategory_filter = create_char_filter(['name'])
        subcategories = Subcategory.objects.filter(subcategory_filter).select_related('category').only('id', 'name', 'category__name', 'category__id')
        
        for s in subcategories:
            full_name = f"{s.name} ({s.category.name if s.category else 'N/A'})"
            name_lower = s.name.lower()
            score = calculate_score(name_lower)
            
            if s.category:
                all_category_name_to_id[s.category.name.lower()] = s.category.id
                category_id_to_name[s.category.id] = s.category.name

            item = {
                'id': f's_{s.id}', 'name': full_name, 'type': 'subcategory', 
                'category_slug': create_slug(s.category.name) if s.category else '',
                'subcategory_slug': create_slug(s.name),
                'category_id': s.category.id if s.category else None
            }

            if score > 0:
                all_results_with_score.append((PRIORITY['subcategory'], score, item))
                if name_lower == query:
                    exact_subcategory_match_item = item

        
        # --- P0: PRODUCTS (Capture exact match and calculate PPS) ---
        product_fields = ['name', 'model', 'manufacturer']
        product_filter = create_char_filter(product_fields)

        products = Product.objects.filter(
            product_filter, user_id__in=approved_ids, is_active=True, status='approved'
        ).annotate(
            vendor_brand=Subquery(Vendor.objects.filter(user=OuterRef('user')).values('brand')[:1]),
            vendor_company_name=Subquery(Vendor.objects.filter(user=OuterRef('user')).values('company_name')[:1]),
            category_name=F('category__name'),
            subcategory_name=F('subcategory__name'),
        ).values('id', 'name', 'model', 'manufacturer', 'vendor_brand', 'vendor_company_name', 'category_name', 'subcategory_name', 'user_id', 'category_id').distinct()

        for p in products:
            vendor_name = p['vendor_brand'] or p['vendor_company_name'] or ''
            product_url_slug = create_slug(f"{p['name']} {p['model'] or ''} {p['manufacturer'] or ''}")
            combined_name_lower = f"{p['name'].lower()} {p['model'].lower() if p['model'] else ''} {p['manufacturer'].lower() if p['manufacturer'] else ''}"
            score = calculate_score(combined_name_lower)
            
            product_priority_score = PRODUCT_MATCH_PRIORITY['name']
            
            # 1. Strict Exact Product Name Match (Highest PPS)
            if p['name'].lower() == query:
                 product_priority_score = max(product_priority_score, PRODUCT_MATCH_PRIORITY['product_exact'])
            
            # 2. Other PPS checks (Vendor > Category > Subcategory > Model)
            query_tokens = set(query.split())
            vendor_lower = vendor_name.lower()
            if query == vendor_lower or any(token == vendor_lower for token in query_tokens):
                product_priority_score = max(product_priority_score, PRODUCT_MATCH_PRIORITY['vendor'])
            category_lower = p['category_name'].lower() if p['category_name'] else ''
            if category_lower and (query == category_lower or any(token == category_lower for token in query_tokens)):
                product_priority_score = max(product_priority_score, PRODUCT_MATCH_PRIORITY['category'])
            subcategory_lower = p['subcategory_name'].lower() if p['subcategory_name'] else ''
            if subcategory_lower and (query == subcategory_lower or any(token == subcategory_lower for token in query_tokens)):
                product_priority_score = max(product_priority_score, PRODUCT_MATCH_PRIORITY['subcategory'])
            model_lower = p['model'].lower() if p['model'] else ''
            manufacturer_lower = p['manufacturer'].lower() if p['manufacturer'] else ''
            model_match = model_lower and (query == model_lower or any(token == model_lower for token in query_tokens))
            manu_match = manufacturer_lower and (query == manufacturer_lower or any(token == manufacturer_lower for token in query_tokens))
            if model_match or manu_match:
                product_priority_score = max(product_priority_score, PRODUCT_MATCH_PRIORITY['model_manufacturer'])


            if score > 0:
                display_name = f"{p['name']} ({p['model'] or p['manufacturer'] or 'Product'})"
                
                item = {
                    'id': f"p_{p['id']}", 'name': display_name, 'type': 'product',
                    'product_id': p['id'], 'url': f'/product/{product_url_slug}-{p["id"]}', 
                    'product_tags': { 'vendor': vendor_name, 'category': p['category_name'] or '', 'subcategory': p['subcategory_name'] or '', 'model': p['model'] or ''},
                    'user_id': p['user_id'], 'category_id': p['category_id'],
                    'product_priority_score': product_priority_score, 
                }
                result_item_tuple = (PRIORITY['product'], score, item)
                all_results_with_score.append(result_item_tuple)
                product_results.append(result_item_tuple)

                if product_priority_score == PRODUCT_MATCH_PRIORITY['product_exact']:
                    exact_product_match_item = {k: v for k, v in item.items() if k not in ['user_id', 'category_id', 'product_priority_score']}

        
        # --- P-1: PRODUCT TYPES (Capture exact match) ---
        for slug, name in TYPE_CHOICES:
            name_lower = name.lower()
            score = calculate_score(name_lower)
            
            item = {
                'id': f'pt_{slug}', 'name': f"{name} Products", 'type': 'product_type',
                'category_slug': slug, 'url': f'/search?type={slug}'
            }
            
            if score > 0:
                all_results_with_score.append((PRIORITY['product_type'], score, item))
                
                if name_lower.split()[0] == query.split()[0]:
                    exact_product_type_match_item = item


        # 3. FINAL SORT AND PROMOTION 
        
        # Secondary relevance terms calculation (Unchanged)
        query_words = set(query.split())
        vendor_names = set(approved_vendor_name_to_id.keys())
        category_names = set(all_category_name_to_id.keys())
        remaining_query_words = query_words.difference(vendor_names).difference(category_names)
        if expanded_phrase_full:
            expanded_words = set(expanded_phrase_full.split())
            for word in expanded_words:
                if word not in category_names:
                    remaining_query_words.add(word)
        filter_out_words = {'of', 'a', 'can', 'i', 'get', 'the', 'for', 'with', 'which', 'what', 'is', 'are', 'we', 'to', 'truck', 'model', 'series', 'tonne', 'ton', 'capacity'}
        secondary_relevance_terms = {word for word in remaining_query_words if word not in filter_out_words and len(word) > 2}

        # Universal Sort Key Function (Handles tuple unpacking: (priority, score, item_dict))
        def get_sort_key(item_tuple):
            priority, score, item = item_tuple
            product_score = item.get('product_priority_score', -1)
            
            if item.get('type') == 'product':
                effective_priority = product_score + PRIORITY['top_product']
            else:
                effective_priority = priority

            return (score, effective_priority, item['name'])


        final_response_list = []
        promoted_ids = set() 
        
        # Determine combination scenarios
        matched_vendor_name, matched_category_name = _check_vendor_category_in_query(
            query, expanded_query_phrase, approved_vendor_name_to_id, all_category_name_to_id
        )
        is_vendor_only_exact_match = exact_vendor_match_item and not matched_category_name and query == exact_vendor_match_item['name'].lower()
        
        # Count the number of active single-type exact matches (using simplified check now that priority is correct)
        exact_match_count = sum(1 for item in [exact_vendor_match_item, exact_category_match_item, exact_subcategory_match_item, exact_product_match_item, exact_product_type_match_item] if item is not None and item.get('name', '').lower().split()[0] == query.split()[0])
        
        
        # --- A. SINGLE-TYPE EXACT MATCH PROMOTION (SUPER PRIORITY) ---
        
        # 1. Category Exact Match
        if exact_category_match_item and exact_match_count == 1:
            # 1.1. Promote Category Link
            final_response_list.append({k: v for k, v in exact_category_match_item.items() if k != 'category_id'})
            promoted_ids.add(exact_category_match_item['id'])
            
            # 1.2. Promote Vendor-Category Links associated with this category
            category_id = exact_category_match_item.get('category_id')
            vendor_category_links = sorted(
                [item[2] for item in all_results_with_score if item[2].get('type') == 'vendor_category' and item[2].get('category_id') == category_id],
                key=lambda x: x['name']
            )
            final_response_list.extend(vendor_category_links)
            promoted_ids.update({item['id'] for item in vendor_category_links})
            
            # 1.3. Promote Subcategories of this Category
            subcategory_links = sorted(
                [item[2] for item in all_results_with_score if item[2].get('type') == 'subcategory' and item[2].get('category_id') == category_id],
                key=lambda x: x['name']
            )
            final_response_list.extend(subcategory_links)
            promoted_ids.update({item['id'] for item in subcategory_links})
            
            # 1.4. Promote Top Products in this Category
            top_products_in_category_tuples = [item_tuple for item_tuple in product_results if item_tuple[2].get('category_id') == category_id]

            top_products_in_category = sorted(
                top_products_in_category_tuples,
                key=lambda x: get_sort_key(x), reverse=True
            )[:10] 
            
            final_response_list.extend([
                {k: v for k, v in item.items() if k not in ['user_id', 'category_id', 'product_priority_score']}
                for priority, score, item in top_products_in_category
            ])
            promoted_ids.update({item.get('id') for priority, score, item in top_products_in_category})

        # 2. Subcategory Exact Match (FIXED: Ordering of Subcategory/Category Links)
        elif exact_subcategory_match_item and exact_match_count == 1:
            # 2.1. Promote Subcategory Link (Highest)
            final_response_list.append({k: v for k, v in exact_subcategory_match_item.items() if k != 'category_id'})
            promoted_ids.add(exact_subcategory_match_item['id'])
            
            # 2.2. Promote Parent Category Link (Second Highest)
            parent_category_id = exact_subcategory_match_item.get('category_id')
            if parent_category_id:
                # Find the CATEGORY item (tuple[2]) in the main list
                parent_category_item = next((item_tuple[2] for item_tuple in all_results_with_score if item_tuple[2].get('type') == 'category' and item_tuple[2].get('category_id') == parent_category_id), None)
                if parent_category_item:
                    final_response_list.append({k: v for k, v in parent_category_item.items() if k != 'category_id'})
                    promoted_ids.add(parent_category_item['id'])

            # 2.3. Promote Top Products in this Subcategory 
            top_products_in_subcategory_tuples = [item_tuple for item_tuple in product_results if item_tuple[2].get('product_tags', {}).get('subcategory', '').lower() == query]

            top_products_in_subcategory = sorted(
                top_products_in_subcategory_tuples,
                key=lambda x: get_sort_key(x), reverse=True
            )[:10] 
            
            final_response_list.extend([
                {k: v for k, v in item.items() if k not in ['user_id', 'category_id', 'product_priority_score']}
                for priority, score, item in top_products_in_subcategory
            ])
            promoted_ids.update({item.get('id') for priority, score, item in top_products_in_subcategory})

        # 3. Product Exact Match
        elif exact_product_match_item and exact_match_count == 1:
            final_response_list.append(exact_product_match_item)
            promoted_ids.add(exact_product_match_item['id'])
            
        # 4. Product Type Exact Match
        elif exact_product_type_match_item and exact_match_count == 1:
            final_response_list.append(exact_product_type_match_item)
            promoted_ids.add(exact_product_type_match_item['id'])

        # 5. Vendor Only Exact Match (Existing Logic)
        elif is_vendor_only_exact_match:
            final_response_list.append({k: v for k, v in exact_vendor_match_item.items() if k != 'user_id'})
            promoted_ids.add(exact_vendor_match_item['id'])
            
            vendor_category_links_to_promote.sort(key=lambda x: x['name'])
            final_response_list.extend(vendor_category_links_to_promote)
            promoted_ids.update({item['id'] for item in vendor_category_links_to_promote})
        
        
        # --- B. VENDOR + CATEGORY COMBINATION (Next Priority) ---
        elif matched_vendor_name and matched_category_name:
            vendor_user_id = approved_vendor_name_to_id.get(matched_vendor_name)
            category_id = all_category_name_to_id.get(matched_category_name)
            vendor_display_name = vendor_user_id_to_name.get(vendor_user_id)
            category_display_name = category_id_to_name.get(category_id)
            
            if vendor_user_id is not None and category_id is not None:
                # 1. Add the VENDOR-CATEGORY LINK
                vendor_category_link = {
                     'id': f'vc_{vendor_user_id}_{category_id}', 'type': 'vendor_category', 
                     'name': f"{vendor_display_name or matched_vendor_name.upper()} - {category_display_name or matched_category_name.upper()}", 
                     'vendor_slug': create_slug(vendor_display_name), 'category_slug': create_slug(category_display_name),
                }
                final_response_list.append(vendor_category_link)
                promoted_ids.add(vendor_category_link['id'])

                # 2. Filter and Score products matching this exact combination
                top_products_with_score = []
                for priority, score, item in product_results:
                     if item.get('user_id') == vendor_user_id and item.get('category_id') == category_id:
                         secondary_score = 0
                         product_text = f"{item['name']} {item['product_tags']['subcategory']} {item['product_tags']['model']}".lower()

                         for term in secondary_relevance_terms:
                             if term in product_text:
                                 secondary_score += 1 
                         
                         top_product_item = {k: v for k, v in item.items() if k not in ['user_id', 'category_id', 'product_priority_score']}
                         top_products_with_score.append((secondary_score, top_product_item))
                         promoted_ids.add(item['id'])
                
                top_products_with_score.sort(key=lambda x: x[0], reverse=True)
                final_response_list.extend([item for score, item in top_products_with_score])
        
        
        # --- C. GENERAL / REMAINING RESULTS ---
        
        # Sort all results using the universal key
        final_sorted_results = sorted(
            all_results_with_score, 
            key=get_sort_key,
            reverse=True
        )
        
        # Append remaining sorted items, filtering out items already promoted
        for priority, score, item in final_sorted_results:
            item_id = item.get('id')
            
            if item_id in promoted_ids:
                continue

            # Clean up temporary keys before final output
            if item.get('type') == 'product':
                item = {k: v for k, v in item.items() if k not in ['user_id', 'category_id', 'product_priority_score']}
            
            final_response_list.append(item)

        return response.Response(final_response_list[:25])