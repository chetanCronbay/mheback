"""Order management models for MHE Backend.

Apply Rules: Maintain up-to-date docstrings for all public classes and methods.
Apply Rules: Use type hints throughout the codebase for better AI comprehension.
Apply Rules: Use database indexes for frequently queried fields.
"""
from typing import Optional
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class Order(models.Model):
    """Order model to handle customer orders.
    
    Apply Rules: Document all public classes and methods with comprehensive docstrings.
    Apply Rules: Use database indexes for frequently queried fields.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
        help_text="User who placed the order"
    )
    order_number = models.CharField(
        max_length=20,
        unique=True,
        help_text="Unique order identifier"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Current order status"
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Total order amount"
    )
    shipping_address = models.TextField(
        help_text="Delivery address"
    )
    phone_number = models.CharField(
        max_length=20,
        help_text="Contact phone number"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional order notes"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        # Apply Rules: Use database indexes for frequently queried fields
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['order_number']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        """Return string representation of order."""
        return f"Order #{self.order_number} - {self.user.username}"
    
    def save(self, *args, **kwargs):
        """Override save to generate order number."""
        if not self.order_number:
            # Generate order number based on timestamp
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            self.order_number = f"ORD-{timestamp}"
        
        # Apply Rules: Log order creation/updates
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            logger.info(f"New order created: {self.order_number} by user {self.user.username}")
        else:
            logger.info(f"Order updated: {self.order_number} - Status: {self.status}")

class OrderItem(models.Model):
    """Order item model to store individual products in an order."""
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        help_text="Order this item belongs to"
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        help_text="Product being ordered"
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Quantity ordered"
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Price per unit at time of order"
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Total price for this item (quantity * unit_price)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['product']),
        ]
    
    def __str__(self) -> str:
        """Return string representation of order item."""
        return f"{self.product.name} x{self.quantity} - Order #{self.order.order_number}"
    
    def save(self, *args, **kwargs):
        """Override save to calculate total price."""
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

class Delivery(models.Model):
    """Delivery tracking model for orders."""
    
    STATUS_CHOICES = (
        ('not_shipped', 'Not Shipped'),
        ('in_transit', 'In Transit'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed Delivery'),
    )
    
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='delivery',
        help_text="Order being delivered"
    )
    tracking_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Courier tracking ID"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='not_shipped',
        help_text="Current delivery status"
    )
    estimated_delivery_date = models.DateField(
        blank=True,
        null=True,
        help_text="Estimated delivery date"
    )
    actual_delivery_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Actual delivery timestamp"
    )
    courier_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Courier service name"
    )
    delivery_notes = models.TextField(
        blank=True,
        null=True,
        help_text="Delivery notes or instructions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['tracking_id']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self) -> str:
        """Return string representation of delivery."""
        return f"Delivery for Order #{self.order.order_number} - {self.status}"

class Payment(models.Model):
    """Payment model for Razorpay integration."""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments',
        help_text="User who made the payment"
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='payments',
        help_text="Order being paid for"
    )
    razorpay_order_id = models.CharField(
        max_length=100,
        help_text="Razorpay order ID"
    )
    razorpay_payment_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Razorpay payment ID"
    )
    razorpay_signature = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Razorpay signature for verification"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Payment amount"
    )
    currency = models.CharField(
        max_length=3,
        default='INR',
        help_text="Payment currency"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Payment status"
    )
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Payment method used"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['order']),
            models.Index(fields=['razorpay_order_id']),
            models.Index(fields=['razorpay_payment_id']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self) -> str:
        """Return string representation of payment."""
        return f"Payment for Order #{self.order.order_number} - {self.status}"