from django.contrib import admin
from .models import (
    Role, User, ContactForm, Reviews,
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


@admin.register(ContactForm)
class ContactFormAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'company_name', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'company_name', 'message')



@admin.register(Reviews)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'stars', 'created_at')
    list_filter = ('stars', 'product')
    search_fields = ('user__username', 'product__name', 'title', 'review')
