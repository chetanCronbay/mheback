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
    MyVendorStatsView, NewsletterSubscriptionViewSet, RoleViewSet, TrainingRegistrationViewSet, UserViewSet, ContactFormViewSet, ReviewViewSet, GoogleLogin, RegisterView, EmailTokenObtainPairView, VendorDashboardView,
    VendorViewSet, VendorApplicationView, MyVendorApplicationView, ApprovedVendorListView, VendorStatsView, ForgotPasswordRequestView, ResetPasswordView, VendorNotificationListView
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from order_management.views import (
    OrderViewSet, OrderItemViewSet, DeliveryViewSet, PaymentViewSet
)

from blogs.views import BlogViewSet, blog_image_upload_view


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


router.register(r'training-registrations', TrainingRegistrationViewSet, basename='training-registration')
router.register(r'newsletter-subscriptions', NewsletterSubscriptionViewSet, basename='newsletter-subscription')

# ✅ Vendor Management Routes
router.register(r'vendor', VendorViewSet, basename='vendor')

# ✅ Order Management App Routes
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'order-items', OrderItemViewSet, basename='orderitem')
router.register(r'deliveries', DeliveryViewSet, basename='delivery')
router.register(r'payments', PaymentViewSet, basename='payment')

# ✅ Blog Management Routes
router.register(r'blogs', BlogViewSet, basename='blog')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/google/login/', GoogleLogin.as_view(), name='google_login'),
    path('api/register/', RegisterView.as_view(), name='user-register'),
    path('api/token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # ✅ Vendor Management Endpoints
    path('api/vendor/apply/', VendorApplicationView.as_view(), name='vendor-apply'),
    path('api/vendor/my-application/', MyVendorApplicationView.as_view(), name='my-vendor-application'),
    path('api/vendor/approved/', ApprovedVendorListView.as_view(), name='approved-vendors'),
    path('api/vendor/stats/', VendorStatsView.as_view(), name='vendor-stats'),
    path('api/vendor/notifications/', VendorNotificationListView.as_view(), name='vendor-notifications'),
    path('api/vendor/my-stats/', MyVendorStatsView.as_view(), name='my-vendor-stats'),  # Individual vendor
    path('api/vendor/dashboard/', VendorDashboardView.as_view(), name='vendor-dashboard'),  # Comprehensive dashboard

    # ✅ Forgot Password Endpoints
    path('api/forgot-password/', ForgotPasswordRequestView.as_view(), name='forgot-password'),
    path('api/reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    
    #blog URLs
    path('api/blogs/', BlogViewSet.as_view({
          'get': 'list',
          'post': 'create'
      }), name='blog-list-create'),
      
      # Change this line from <int:pk> to <str:blog_url>
      path('api/blogs/<str:blog_url>/', BlogViewSet.as_view({
          'get': 'retrieve',
          'put': 'update',
          'patch': 'partial_update',
          'delete': 'destroy'
      }), name='blog-detail'),

      path('api/upload/<str:blog_url>/', blog_image_upload_view, name='blog-image-upload'),
    
    
    # ✅ Default router URLs (includes all ViewSet routes)
    path('api/', include(router.urls)),
]

# ✅ Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

"""
Complete Vendor API Endpoints:

Authentication Required:
- POST /api/vendor/apply/ - Apply for vendor status
- GET /api/vendor/my-application/ - Get my vendor application status
- PUT/PATCH /api/vendor/my-application/ - Update my vendor application

Admin Only:
- GET /api/vendors/ - List all vendor applications
- DELETE /api/vendors/{id}/ - Delete vendor application
- POST /api/vendors/{id}/approve/ - Approve/reject vendor application
- GET /api/vendor/stats/ - Get vendor statistics

Admin or Owner:
- GET /api/vendors/{id}/ - Get vendor details
- PUT/PATCH /api/vendors/{id}/ - Update vendor information

Public Access:
- GET /api/vendor/approved/ - List all approved vendors
- GET /api/vendors/{id}/profile/ - Get public vendor profile

Usage Examples:

1. User applies for vendor status:
   POST /api/vendor/apply/
   {
     "company_name": "ABC Corp",
     "company_email": "contact@abc.com",
     "company_address": "123 Main St",
     "company_phone": "+1234567890",
     "brand": "ABC Brand",
     "gst_no": "12ABCDE1234F1Z5"
   }

2. Admin approves vendor:
   POST /api/vendors/{id}/approve/
   {
     "action": "approve"
   }

3. Admin rejects vendor:
   POST /api/vendors/{id}/approve/
   {
     "action": "reject",
     "reason": "Incomplete documentation"
   }

4. Get approved vendors (public):
   GET /api/vendor/approved/

5. Check application status:
   GET /api/vendor/my-application/
"""