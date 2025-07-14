from django.contrib import admin
from .models import Order, OrderItem, Delivery, Payment


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'user', 'status', 'total_amount', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('order_number', 'user__username', 'shipping_address', 'phone_number')
    readonly_fields = ('order_number', 'created_at', 'updated_at')


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'unit_price', 'total_price')
    list_filter = ('order', 'product')
    search_fields = ('order__order_number', 'product__name')


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('order', 'tracking_id', 'status', 'estimated_delivery_date', 'actual_delivery_date')
    list_filter = ('status', 'courier_name')
    search_fields = ('order__order_number', 'tracking_id', 'courier_name')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'user', 'razorpay_order_id', 'razorpay_payment_id', 'status', 'amount', 'currency', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('razorpay_order_id', 'razorpay_payment_id', 'order__order_number', 'user__username')
