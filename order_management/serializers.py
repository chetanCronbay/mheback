from rest_framework import serializers
from .models import Order, OrderItem, Delivery, Payment
from products.models import Product
from products.serializers import ProductSerializer

class OrderItemSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'order', 'product', 'product_details', 'product_name',
            'quantity', 'unit_price', 'total_price', 'created_at'
        ]
        read_only_fields = ['total_price']

class OrderSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'user', 'user_name', 'order_number', 'status',
            'total_amount', 'shipping_address', 'phone_number',
            'notes', 'items', 'item_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'order_number']
    
    def get_item_count(self, obj):
        return obj.items.count()
    
    def validate_total_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Total amount must be greater than 0")
        return value
    
    def validate_phone_number(self, value):
        if not value.isdigit() or len(value) < 10:
            raise serializers.ValidationError("Enter a valid phone number")
        return value

class CreateOrderSerializer(serializers.Serializer):
    """Serializer for creating order from cart items."""
    shipping_address = serializers.CharField(max_length=500)
    phone_number = serializers.CharField(max_length=20)
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    
    def validate_phone_number(self, value):
        if not value.isdigit() or len(value) < 10:
            raise serializers.ValidationError("Enter a valid phone number")
        return value
    
    def validate_shipping_address(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Please provide a complete shipping address")
        return value

class DeliverySerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    
    class Meta:
        model = Delivery
        fields = [
            'id', 'order', 'order_number', 'tracking_id', 'status',
            'estimated_delivery_date', 'actual_delivery_date',
            'courier_name', 'delivery_notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['order']
    
    def validate_tracking_id(self, value):
        if value and len(value) < 5:
            raise serializers.ValidationError("Tracking ID must be at least 5 characters")
        return value

class PaymentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'user', 'user_name', 'order', 'order_number',
            'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature',
            'amount', 'currency', 'status', 'payment_method',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['user']
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be greater than 0")
        return value

class PaymentVerificationSerializer(serializers.Serializer):
    """Serializer for Razorpay payment verification."""
    razorpay_order_id = serializers.CharField(max_length=100)
    razorpay_payment_id = serializers.CharField(max_length=100)
    razorpay_signature = serializers.CharField(max_length=200)