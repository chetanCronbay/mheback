from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import AllowAny, IsAuthenticated
from datetime import timedelta
from django.utils import timezone
from .models import *
from .serializers import *
from users.permissions import ReadOnlyOrAdmin, IsVendorOwnerOrAdmin, IsAdmin

class QuoteThrottle(UserRateThrottle):
    scope = 'quote'
    rate = '10/hour'

class RentalThrottle(UserRateThrottle):
    scope = 'rental'
    rate = '10/hour'

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]  # Read for all, write for admin only
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']
    parser_classes = [MultiPartParser, FormParser]

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

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsVendorOwnerOrAdmin]  # Read for all, write for owner/admin
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'subcategory', 'type', 'user']
    search_fields = ['name', 'description', 'manufacturer', 'model']
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action in ['add_to_cart', 'add_to_wishlist']:
            return [IsAuthenticated()]
        return super().get_permissions()

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

class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]  # Only authenticated users

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def clear(self, request):
        self.get_queryset().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]  # Only authenticated users

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user)

class QuoteViewSet(viewsets.ModelViewSet):
    serializer_class = QuoteSerializer
    permission_classes = [IsAuthenticated]  # Only authenticated users
    throttle_classes = [QuoteThrottle]

    def get_queryset(self):
        if self.request.user.role.id == Role.ADMIN:  # Assuming you have Role model
            return Quote.objects.all()
        return Quote.objects.filter(user=self.request.user)

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
    throttle_classes = [RentalThrottle]

    def get_queryset(self):
        if self.request.user.role.id == Role.ADMIN:
            return Rental.objects.all()
        return Rental.objects.filter(user=self.request.user)

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