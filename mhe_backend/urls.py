# mhe_backend/urls.py

from django.contrib import admin
from django.urls import path, include
from mhe_backend import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

from banners.views import BannerViewSet
from products.views import (
    CategoryViewSet, SubcategoryViewSet, ProductViewSet,
    CartViewSet, WishlistViewSet, QuoteViewSet, RentalViewSet
)
from users.views import (
    RoleViewSet, UserViewSet, ContactFormViewSet, ReviewViewSet, GoogleLogin, RegisterView, EmailTokenObtainPairView
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from order_management.views import (
    OrderViewSet, OrderItemViewSet, DeliveryViewSet, PaymentViewSet
)

router = DefaultRouter()
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'users', UserViewSet, basename='user')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'subcategories', SubcategoryViewSet, basename='subcategory')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'wishlist', WishlistViewSet, basename='wishlist')
router.register(r'quotes', QuoteViewSet, basename='quote')
router.register(r'rentals', RentalViewSet, basename='rental')
router.register(r'contact-forms', ContactFormViewSet, basename='contactform')
router.register(r'banners', BannerViewSet, basename='banner') 
router.register(r'reviews', ReviewViewSet, basename='review')  

# ✅ Order Management App Routes
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'order-items', OrderItemViewSet, basename='orderitem')
router.register(r'deliveries', DeliveryViewSet, basename='delivery')
router.register(r'payments', PaymentViewSet, basename='payment')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/google/login/', GoogleLogin.as_view(), name='google_login'),
    path('api/register/', RegisterView.as_view(), name='user-register'),
    path('api/token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/', include(router.urls)),
]
# ✅ Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)