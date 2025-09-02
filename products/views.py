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
from users.models import Role  # Import Role model or constant
from django.db import transaction
from django.core.mail import send_mail
from rest_framework.pagination import PageNumberPagination
import django_filters
from django.conf import settings
import logging

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

    def get_queryset(self):
        """
        Optionally restricts the returned products by filtering against
        query parameters in the URL.
        """
        queryset = super().get_queryset()

        # This custom filtering logic remains the same for now
        # but can be improved (see recommendation below).
        category_name = self.request.query_params.get('category_name')
        if category_name:
            queryset = queryset.filter(category__name__iexact=category_name)

        min_price = self.request.query_params.get('min_price')
        if min_price:
            try:
                queryset = queryset.filter(price__gte=min_price)
            except ValueError:
                pass
        
        max_price = self.request.query_params.get('max_price')
        if max_price:
            try:
                queryset = queryset.filter(price__lte=max_price)
            except ValueError:
                pass

        rating = self.request.query_params.get('average_rating')
        if rating:
            try:
                queryset = queryset.annotate(
                    avg_rating=Avg('reviews__stars')
                ).filter(
                    avg_rating__gte=float(rating)
                )
            except (ValueError, TypeError):
                pass
            
        return queryset

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
    permission_classes = [IsAuthenticated]
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
        
        # Use select_related to optimize DB queries by pre-fetching related objects
        base_queryset = Quote.objects.select_related('product', 'user', 'product__user')

        if user.role.id == Role.ADMIN:
            return base_queryset.all().order_by('-created_at')
        
        if user.role.name == 'Vendor':
            return base_queryset.filter(product__user=user).order_by('-created_at')
            
        return base_queryset.filter(user=user).order_by('-created_at')

    def perform_create(self, serializer):
        recent_requests = Quote.objects.filter(
            user=self.request.user,
            last_request_time__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        if recent_requests >= 5:
            raise serializers.ValidationError("Too many quote requests recently. Please wait before submitting another.")
            
        serializer.save(user=self.request.user)

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
    permission_classes = [IsAuthenticated]  # Only authenticated users
    # throttle_classes = [RentalThrottle]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']  # For filtering by status (e.g., /rentals/?status=pending)
    search_fields = ['product__name', 'user__username', 'product__user__username'] # For search
    ordering_fields = ['created_at', 'product__name'] # For sorting

    def get_queryset(self):
        user = self.request.user
        
        # Use select_related for query optimization
        base_queryset = Rental.objects.select_related('product', 'user', 'product__user')

        if user.role.id == Role.ADMIN:
            return base_queryset.all().order_by('-created_at')
        elif user.role.name == 'Vendor':
            return base_queryset.filter(product__user=user).order_by('-created_at')
        return base_queryset.filter(user=user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

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
    