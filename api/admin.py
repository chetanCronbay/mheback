from django.contrib import admin
from .models import (
    Role, User, Category, Subcategory, Product,
    Cart, Wishlist, Quote, Rental, ContactForm
)

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at', 'updated_at')
    search_fields = ('name', 'description')

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'phone', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'phone')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at', 'updated_at')
    search_fields = ('name', 'description')

@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'description', 'created_at', 'updated_at')
    list_filter = ('category',)
    search_fields = ('name', 'description')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'category', 'subcategory', 'type', 'price', 'created_at')
    list_filter = ('type', 'category', 'subcategory', 'user')
    search_fields = ('name', 'description', 'manufacturer', 'model')

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'quantity', 'created_at')
    list_filter = ('user',)
    search_fields = ('user__username', 'product__name')

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    list_filter = ('user',)
    search_fields = ('user__username', 'product__name')

@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'status', 'created_at')
    list_filter = ('status', 'user')
    search_fields = ('user__username', 'product__name', 'message')

@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'start_date', 'end_date', 'status', 'created_at')
    list_filter = ('status', 'user')
    search_fields = ('user__username', 'product__name', 'notes')

@admin.register(ContactForm)
class ContactFormAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'company_name', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'company_name', 'message')
