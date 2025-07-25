"""Product models for MHE Backend.

Apply Rules: Maintain up-to-date docstrings for all public classes and methods.
Apply Rules: Use type hints throughout the codebase for better AI comprehension.
Apply Rules: Use database indexes for frequently queried fields.
"""
from typing import Optional, Dict, Any
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def category_image_upload_path(instance, filename):
    return f'category/{instance.id}/{filename}'

def subcategory_image_upload_path(instance, filename):
    return f'subcategory/{instance.id}/{filename}'

def product_image_upload_path(instance, filename):
    return f'products/{instance.product.id}/{filename}'

def product_brochure_upload_path(instance, filename):
    return f'products/{instance.id}/brochure/{filename}'

class Category(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    meta_title = models.CharField(max_length=255, blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)
    cat_image = models.ImageField(upload_to=category_image_upload_path, blank=True, null=True)
    cat_banner = models.ImageField(upload_to=category_image_upload_path, blank=True, null=True)
    product_details = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Subcategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    meta_title = models.CharField(max_length=255, blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)
    sub_image = models.ImageField(upload_to=subcategory_image_upload_path, blank=True, null=True)
    sub_banner = models.ImageField(upload_to=subcategory_image_upload_path, blank=True, null=True)
    product_details = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Product(models.Model):
    """Product model with comprehensive features and optimizations.
    
    Apply Rules: Document all public classes and methods with comprehensive docstrings.
    Apply Rules: Use database indexes for frequently queried fields.
    Apply Rules: Validate all uploaded files for type and size.
    """
    TYPE_CHOICES = (
        ('new', 'New'),
        ('used', 'Used'),
        ('rental', 'Rental'),
        ('attachments', 'Attachments'),
        
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.DO_NOTHING, 
        related_name='products',
        help_text="User who created this product listing"
    )
    category = models.ForeignKey(
        Category, 
        on_delete=models.CASCADE, 
        related_name='products',
        help_text="Product category"
    )
    subcategory = models.ForeignKey(
        Subcategory, 
        on_delete=models.CASCADE, 
        related_name='products',
        help_text="Product subcategory",
        null=True,
        blank=True,
    )
    name = models.CharField(
        max_length=255,
        help_text="Product name/title"
    )
    description = models.TextField(
        blank=True, 
        null=True,
        help_text="Detailed product description"
    )
    meta_title = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="SEO meta title"
    )
    meta_description = models.TextField(
        blank=True, 
        null=True,
        help_text="SEO meta description"
    )
    manufacturer = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Product manufacturer/brand"
    )
    model = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Product model number"
    )
    # Apply Rules: Use JSONField for flexible product specifications
    product_details = models.JSONField(
        blank=True, 
        null=True,
        help_text="Additional product specifications in JSON format"
    )
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Product price"
    )
    brochure = models.FileField(
        upload_to=product_brochure_upload_path, 
        blank=True, 
        null=True,
        help_text="Product brochure/specification sheet"
    )
    type = models.CharField(
        max_length=70, 
        choices=TYPE_CHOICES, 
        default='new',
        help_text="Product condition type"
    )
    
    # Apply Rules: Additional fields for better product management
    is_active = models.BooleanField(
        default=True,
        help_text="Whether product is active and available"
    )
    
    #IF PRODUCT IS FOR DIRECT SALE
    direct_sale = models.BooleanField(
        default=False,
        help_text="Whether product is available for direct sale"
    )
    
    #if the product is for online payment
    online_payment = models.BooleanField(
        default=False,
        help_text="Whether product is available for online payment"
    )
    
    #if price needed to be hidden
    hide_price = models.BooleanField(
        default=False,
        help_text="Whether product price should be hidden"
    )
    
    stock_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Available stock quantity"
    )
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    rejection_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Apply Rules: Use database indexes for frequently queried fields
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['model']),
            models.Index(fields=['manufacturer']),
            models.Index(fields=['category']),
            models.Index(fields=['subcategory']),
            models.Index(fields=['type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['price']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self) -> str:
        """Return string representation of product."""
        return f"{self.name} ({self.manufacturer or 'Unknown'} - {self.model or 'N/A'})"
        
    def get_main_image_url(self) -> Optional[str]:
        """Get the URL of the main product image."""
        main_image = self.images.first()
        return main_image.image.url if main_image else None
        
    def get_average_rating(self) -> Optional[float]:
        """Calculate average rating from reviews."""
        reviews = self.reviews.all()
        if reviews:
            total_stars = sum(review.stars for review in reviews)
            return round(total_stars / len(reviews), 1)
        return None
        
    def get_review_count(self) -> int:
        """Get total number of reviews."""
        return self.reviews.count()
        
    def is_available_for_rental(self, start_date, end_date) -> bool:
        """Check if product is available for rental in given date range."""
        if self.type != 'rental':
            return False
            
        conflicting_rentals = self.rentals.filter(
            status__in=['approved', 'pending'],
            start_date__lte=end_date,
            end_date__gte=start_date
        )
        return not conflicting_rentals.exists()
        
    def calculate_rental_price(self, start_date, end_date) -> Decimal:
        """Calculate total rental price for given date range."""
        days = (end_date - start_date).days + 1
        return self.price * days
        
    def save(self, *args, **kwargs):
        """Override save to add custom logic."""
        # Apply Rules: Log product creation/updates
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            logger.info(f"New product created: {self.name} by user {self.user.username}")
        else:
            logger.info(f"Product updated: {self.name}")

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=product_image_upload_path)

    def __str__(self):
        return f"Image for {self.product.name}"

class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'product')


class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'product')


class Quote(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quotes')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_request_time = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product'],
                name='unique_user_product_quote'
            )
        ]


class Rental(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('returned', 'Returned'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rentals')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_request_time = models.DateTimeField(auto_now=True)
