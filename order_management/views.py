import razorpay
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging # Corrected import for logging

from django.conf import settings

from .models import Order, OrderItem, Delivery, Payment
from .serializers import (
    OrderSerializer, OrderItemSerializer, DeliverySerializer,
    PaymentSerializer, CreateOrderSerializer, PaymentVerificationSerializer
)
from products.models import Cart
from users.models import Role
from users.permissions import IsAdmin

logger = logging.getLogger(__name__) # Initialize logger for the module

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'created_at']
    search_fields = ['order_number', 'user__username']
    ordering_fields = ['created_at', 'updated_at', 'total_amount']
    ordering = ['-created_at']

    def get_queryset(self):
        """Return orders based on user role."""
        if hasattr(self.request.user, 'role') and self.request.user.role.id == Role.ADMIN:
            return Order.objects.all()
        return Order.objects.filter(user=self.request.user)

    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['update_status', 'cancel_order']:
            return [IsAdmin()]
        return super().get_permissions()

    @action(detail=False, methods=['post'])
    def create_from_cart(self, request):
        """Create order from user's cart items."""
        serializer = CreateOrderSerializer(data=request.data)
        if serializer.is_valid():
            # Get user's cart items
            cart_items = Cart.objects.filter(user=request.user)
            
            if not cart_items.exists():
                return Response(
                    {'error': 'Cart is empty'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Calculate total amount
            total_amount = sum(
                item.product.price * item.quantity for item in cart_items
            )
            
            try:
                with transaction.atomic():
                    # Create order
                    order = Order.objects.create(
                        user=request.user,
                        total_amount=total_amount,
                        shipping_address=serializer.validated_data['shipping_address'],
                        phone_number=serializer.validated_data['phone_number'],
                        notes=serializer.validated_data.get('notes', '')
                    )
                    
                    # Create order items from cart
                    for cart_item in cart_items:
                        OrderItem.objects.create(
                            order=order,
                            product=cart_item.product,
                            quantity=cart_item.quantity,
                            unit_price=cart_item.product.price
                        )
                    
                    # Create delivery record
                    Delivery.objects.create(order=order)
                    
                    # Clear cart
                    cart_items.delete()
                    
                    # Return created order
                    order_serializer = OrderSerializer(order)
                    return Response(
                        order_serializer.data,
                        status=status.HTTP_201_CREATED
                    )
                    
            except Exception as e:
                logger.error(f"Error creating order from cart: {e}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update order status (Admin only)."""
        order = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in dict(Order.STATUS_CHOICES):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = new_status
        order.save()
        
        # Update delivery status if order is shipped or delivered
        if new_status == 'shipped' and hasattr(order, 'delivery'):
            order.delivery.status = 'in_transit'
            order.delivery.save()
        elif new_status == 'delivered' and hasattr(order, 'delivery'):
            order.delivery.status = 'delivered'
            order.delivery.actual_delivery_date = timezone.now()
            order.delivery.save()
        
        serializer = self.get_serializer(order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cancel_order(self, request, pk=None):
        """Cancel an order."""
        order = self.get_object()
        
        # Check if order can be cancelled
        if order.status in ['shipped', 'delivered']:
            return Response(
                {'error': 'Cannot cancel shipped or delivered order'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'cancelled'
        order.save()
        
        serializer = self.get_serializer(order)
        return Response(serializer.data)

class OrderItemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['order', 'product']

    def get_queryset(self):
        """Return order items based on user role."""
        if hasattr(self.request.user, 'role') and self.request.user.role.id == Role.ADMIN:
            return OrderItem.objects.all()
        return OrderItem.objects.filter(order__user=self.request.user)

class DeliveryViewSet(viewsets.ModelViewSet):
    serializer_class = DeliverySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'order']
    search_fields = ['tracking_id', 'order__order_number']

    def get_queryset(self):
        """Return deliveries based on user role."""
        if hasattr(self.request.user, 'role') and self.request.user.role.id == Role.ADMIN:
            return Delivery.objects.all()
        return Delivery.objects.filter(order__user=self.request.user)

    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return super().get_permissions()

    @action(detail=True, methods=['post'])
    def update_tracking(self, request, pk=None):
        """Update delivery tracking information."""
        delivery = self.get_object()
        tracking_id = request.data.get('tracking_id')
        courier_name = request.data.get('courier_name')
        estimated_delivery_date = request.data.get('estimated_delivery_date')
        
        if tracking_id:
            delivery.tracking_id = tracking_id
        if courier_name:
            delivery.courier_name = courier_name
        if estimated_delivery_date:
            delivery.estimated_delivery_date = estimated_delivery_date
        
        delivery.save()
        
        serializer = self.get_serializer(delivery)
        return Response(serializer.data)

class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'order']
    search_fields = ['razorpay_order_id', 'razorpay_payment_id', 'order__order_number']

    def get_queryset(self):
        """Return payments based on user role."""
        if hasattr(self.request.user, 'role') and self.request.user.role.id == Role.ADMIN:
            return Payment.objects.all()
        return Payment.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Set user when creating payment."""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'])
    def create_razorpay_order(self, request):
        """Create Razorpay order for payment."""
        order_id = request.data.get('order_id')

        if not order_id:
            return Response(
                {'error': 'Order ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found for the current user'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if payment already exists
        existing_payment = Payment.objects.filter(
            order=order,
            status='success'
        ).first()

        if existing_payment:
            return Response(
                {'error': 'Payment already completed for this order'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            
            # Print statements to verify the keys being used by the backend
            # print(f"DEBUG: Razorpay Key ID being used by backend: {settings.RAZORPAY_KEY_ID}")
            # print(f"DEBUG: Razorpay Key Secret being used by backend: {settings.RAZORPAY_KEY_SECRET}")

            # FIX 1: Corrected how set_app_details receives arguments
            client.set_app_details({'title': 'MHE Bazar', 'version': '1.0'})

            # Amount in paisa
            amount_in_paisa = int(order.total_amount * 100)
            if amount_in_paisa <= 0:
                 return Response(
                    {'error': 'Total amount must be greater than zero to create a payment.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            razorpay_order = client.order.create({
                'amount': amount_in_paisa,
                'currency': 'INR',
                'receipt': f"receipt_order_{order.id}",
                'payment_capture': '1' # Auto capture payment
            })

            # Create payment record in your database
            payment = Payment.objects.create(
                user=request.user,
                order=order,
                razorpay_order_id=razorpay_order['id'], # Use Razorpay's order ID
                amount=Decimal(razorpay_order['amount']) / 100, # Convert back to decimal for your model
                currency=razorpay_order['currency'],
                status='pending' # Initial status
            )

            serializer = self.get_serializer(payment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except razorpay.errors.BadRequestError as e:
            logger.error(f"Razorpay BadRequestError in create_razorpay_order: {e}")
            # FIX 2: Use str(e) as BadRequestError does not have a 'code' attribute
            # This is the expected error if keys are mismatched/invalid
            return Response(
                {'error': f'Razorpay API Error: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception("Error creating Razorpay order:")
            return Response(
                {'error': 'Failed to create Razorpay order on backend. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def verify_payment(self, request):
        """Verify Razorpay payment."""
        serializer = PaymentVerificationSerializer(data=request.data)
        if serializer.is_valid():
            razorpay_order_id = serializer.validated_data['razorpay_order_id']
            razorpay_payment_id = serializer.validated_data['razorpay_payment_id']
            razorpay_signature = serializer.validated_data['razorpay_signature']

            try:
                payment = Payment.objects.get(
                    razorpay_order_id=razorpay_order_id,
                    user=request.user
                )

                # Initialize Razorpay client for verification
                client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

                # Verify the payment signature
                try:
                    client.utility.verify_payment_signature({
                        'razorpay_order_id': razorpay_order_id,
                        'razorpay_payment_id': razorpay_payment_id,
                        'razorpay_signature': razorpay_signature
                    })
                    # If verification passes, no exception is raised

                    payment.razorpay_payment_id = razorpay_payment_id
                    payment.razorpay_signature = razorpay_signature
                    payment.status = 'success'
                    payment.save()

                    # Update order status
                    order = payment.order
                    order.status = 'confirmed'
                    order.save()

                    return Response(
                        {'message': 'Payment verified successfully', 'order_status': order.status},
                        status=status.HTTP_200_OK
                    )
                except Exception as e:
                    logger.error(f"Razorpay signature verification failed for order {razorpay_order_id}: {e}")
                    payment.status = 'failed' # Mark payment as failed
                    payment.save()
                    return Response(
                        {'error': 'Payment verification failed due to invalid signature or details.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            except Payment.DoesNotExist:
                return Response(
                    {'error': 'Payment record not found for the provided Razorpay Order ID or user.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                logger.exception("Unexpected error during payment verification:")
                return Response(
                    {'error': 'An unexpected error occurred during payment verification.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    