# mhe_backend/urls.py

from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from mhe_backend import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

from banners.views import BannerViewSet
from products.views import (
    CategoryViewSet, ProductSearchViewSet, ProductVendorPhoneView, SubcategoryViewSet, ProductViewSet,
    CartViewSet, UniversalSearchViewSet, WishlistViewSet, QuoteViewSet, RentalViewSet
)
from users.views import (
    AdminDashboardSummaryView, MyVendorStatsView, NewsletterSubscriptionViewSet, RoleViewSet, TrainingRegistrationViewSet, UserViewSet, ContactFormViewSet, ReviewViewSet, GoogleLogin, RegisterView, EmailTokenObtainPairView, VendorDashboardView,
    VendorViewSet, VendorApplicationView, MyVendorApplicationView, ApprovedVendorListView, VendorStatsView, ForgotPasswordRequestView, ResetPasswordView, VendorNotificationListView,sendotp,verifyotp,VendorContactLogViewSet
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from order_management.views import (
    OrderViewSet, OrderItemViewSet, DeliveryViewSet, PaymentViewSet
)

from blogs.views import BlogViewSet
from util.reports import (
    vendor_report_dashboard, send_admin_report, send_vendor_report, send_all_vendor_reports,
    preview_admin_report, preview_vendor_report, preview_all_vendor_reports
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


router.register(r'training-registrations', TrainingRegistrationViewSet, basename='training-registration')
router.register(r'newsletter-subscriptions', NewsletterSubscriptionViewSet, basename='newsletter-subscription')
router.register(r'track-vendor-click', VendorContactLogViewSet, basename='track-vendor-click')

# You need to add this line to your existing router registration section
router.register(r'products-search', ProductSearchViewSet, basename='product-search')


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
    path('', lambda request: HttpResponse("Hello MHE")), 
    path('admin/', admin.site.urls),
    path('api/google/login/', GoogleLogin.as_view(), name='google_login'),
    path('api/register/', RegisterView.as_view(), name='user-register'),
    path('api/token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/sendotp/', sendotp, name='sendotp'),
    path('api/verifyotp/', verifyotp, name='verifyotp'),

    
    # ✅ Vendor Management Endpoints
    path('api/vendor/apply/', VendorApplicationView.as_view(), name='vendor-apply'),
    path('api/vendor/my-application/', MyVendorApplicationView.as_view(), name='my-vendor-application'),
    path('api/vendor/approved/', ApprovedVendorListView.as_view(), name='approved-vendors'),
    path('api/vendor/stats/', VendorStatsView.as_view(), name='vendor-stats'),
    path('api/vendor/notifications/', VendorNotificationListView.as_view(), name='vendor-notifications'),
    path('api/vendor/my-stats/', MyVendorStatsView.as_view(), name='my-vendor-stats'),  # Individual vendor
    path('api/vendor/dashboard/', VendorDashboardView.as_view(), name='vendor-dashboard'),  # Comprehensive dashboard
    path('api/admin/summary/', AdminDashboardSummaryView.as_view(), name='admin-dashboard-summary'),

    # ✅ Forgot Password Endpoints
    path('api/forgot-password/', ForgotPasswordRequestView.as_view(), name='forgot-password'),
    path('api/reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    
    # Add this to your existing urls.py
    path('api/blogs/', BlogViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='blog-list-create'),

    path('api/blogs/<str:blog_url>/', BlogViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='blog-detail'),

        
    # 💥 New Universal Search Endpoint for fast, single-call suggestions
    path('api/search/universal/', UniversalSearchViewSet.as_view({'get': 'list'}), name='universal-search'),
    
    # 💥 NEW URL: Get Vendor Phone by Product ID
    path('api/product/<int:product_id>/vendor-phone/', ProductVendorPhoneView.as_view(), name='product-vendor-phone'),
    
    path('reports/', vendor_report_dashboard, name='vendor-report-dashboard'),
    
    # Preview Routes
    path('reports/preview/admin/<str:report_type>/', preview_admin_report, name='preview-admin-report'),
    path('reports/preview/vendor/<int:vendor_id>/', preview_vendor_report, name='preview-vendor-report'),
    path('reports/preview/all-vendors/', preview_all_vendor_reports, name='preview-all-vendor-reports'),
    
    # Sending Routes
    path('reports/send-admin/<str:report_type>/', send_admin_report, name='send-admin-report'),
    path('reports/send-vendor/<int:vendor_id>/', send_vendor_report, name='send-vendor-report'),
    path('reports/send-all-vendors/', send_all_vendor_reports, name='send-all-vendor-reports'),
    
    
    # ✅ Default router URLs (includes all ViewSet routes)
    path('api/', include(router.urls)),
]

# ✅ Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

"""
Complete Vendor API Endpoints:
... (rest of the file)
"""