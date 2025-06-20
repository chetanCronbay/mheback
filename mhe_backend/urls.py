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
from api.views import (
    RoleViewSet, UserViewSet, CategoryViewSet, SubcategoryViewSet, ProductViewSet,
    CartViewSet, WishlistViewSet, QuoteViewSet, RentalViewSet, ContactFormViewSet
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

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
]

