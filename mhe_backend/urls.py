"""
URL configuration for mhe_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from rest_framework.routers import DefaultRouter
from django.urls import path, include
from banners.views import BannerViewSet
from products.views import ( CategoryViewSet, SubcategoryViewSet, ProductViewSet, CartViewSet, WishlistViewSet, QuoteViewSet, RentalViewSet)
from users.views import (RoleViewSet, UserViewSet, ContactFormViewSet, ReviewViewSet, GoogleLogin, RegisterView)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

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

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/google/login/', GoogleLogin.as_view(), name='google_login'),
    path('api/register/', RegisterView.as_view(), name='user-register'),
     path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/', include(router.urls)),
]

