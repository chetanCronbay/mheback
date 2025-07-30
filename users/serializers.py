"""User serializers for MHE Backend API.

Apply Rules: Document all endpoints and actions with docstrings.
Apply Rules: Use serializers for input validation and output formatting.
Apply Rules: Validate and sanitize all user inputs.
"""
from typing import Dict, Any
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from products.models import Product

from .models import User, UserBanner, Role, ContactForm, Reviews, ReviewImages, Vendor
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'

class UserBannerSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=True)

    class Meta:
        model = UserBanner
        fields = ['id', 'image', 'user']
        read_only_fields = ['user']

class UserSerializer(serializers.ModelSerializer):
    """Comprehensive User serializer with validation and security.
    
    Apply Rules: Use serializers for input validation and output formatting.
    Apply Rules: Never expose sensitive user data via the API.
    Apply Rules: Validate and sanitize all user inputs.
    """
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        validators=[validate_password],
        help_text="Password must meet security requirements"
    )
    password2 = serializers.CharField(
        write_only=True, 
        required=True,
        help_text="Confirm password"
    )
    role = RoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), 
        write_only=True, 
        source='role',
        help_text="User role ID"
    )
    user_banner = UserBannerSerializer(many=True, read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    is_account_locked = serializers.BooleanField(read_only=True)
    
    # Apply Rules: Never expose sensitive data
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name', "description",
            'password', 'password2', 'role', 'role_id', 'phone', 'address', 'profile_photo','user_banner', 'is_email_verified', 'is_account_locked', 
            'date_joined', 'last_login'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'last_login': {'read_only': True},
            'date_joined': {'read_only': True},
            'is_email_verified': {'read_only': True},
        }

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Apply Rules: Comprehensive input validation."""
        if 'password' in attrs and 'password2' in attrs:
            if attrs['password'] != attrs['password2']:
                raise serializers.ValidationError({
                    "password": "Password fields didn't match."
                })
        
        # Apply Rules: Validate email uniqueness
        if 'email' in attrs:
            email = attrs['email'].lower().strip()
            if User.objects.filter(email=email).exclude(pk=getattr(self.instance, 'pk', None)).exists():
                raise serializers.ValidationError({
                    "email": "A user with this email already exists."
                })
            attrs['email'] = email
            
        return attrs

    def validate_phone(self, value: str) -> str:
        """Apply Rules: Validate phone number format."""
        if value:
            # Remove all non-digit characters except +
            cleaned = ''.join(c for c in value if c.isdigit() or c == '+')
            if len(cleaned) < 10:
                raise serializers.ValidationError(
                    "Phone number must be at least 10 digits long."
                )
        return value

    def create(self, validated_data: Dict[str, Any]) -> User:
        """Create user with proper validation and logging."""
        validated_data.pop('password2', None)
        
        # Apply Rules: Log user creation for analytics
        logger.info(f"Creating new user: {validated_data.get('username')}")
        
        try:
            user = User.objects.create_user(**validated_data)
            logger.info(f"User created successfully: {user.username}")
            return user
        except Exception as e:
            logger.error(f"Failed to create user: {str(e)}")
            raise serializers.ValidationError("Failed to create user account.")
            
    def update(self, instance: User, validated_data: Dict[str, Any]) -> User:
        """Update user with validation and security checks."""
        # Remove password fields if they're empty
        password = validated_data.pop('password', None)
        validated_data.pop('password2', None)
        
        # Apply Rules: Log user updates
        logger.info(f"Updating user: {instance.username}")
        
        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            
        # Update password if provided
        if password:
            instance.set_password(password)
            
        instance.save()
        return instance

class ContactFormSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactForm
        fields = '__all__'
        extra_kwargs = {
            'captcha_answer': {'write_only': True}
        }

    def validate(self, attrs):
        if attrs.get('captcha') != attrs.get('captcha_answer'):
            raise ValidationError("CAPTCHA verification failed")
        if attrs.get('honeypot'):
            raise serializers.ValidationError("Bot detected")
        return attrs

class ReviewsImageSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=True)

    class Meta:
        model = ReviewImages
        fields = ['id', 'image', 'review']
        read_only_fields = ['review']

class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    review_images = ReviewsImageSerializer(many=True, read_only=True)

    # 1. Add this field to accept the product's ID from the request
    # It looks for 'product_id' in the data and links it to the 'product' field on the model
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
    )

    class Meta:
        model = Reviews
        # 2. Add 'product' to the list of fields
        fields = ['id', 'user', 'user_name', 'product', 'stars', 'review', 'review_images']
        read_only_fields = ['user_name', 'user']

    def validate_stars(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Stars must be between 1 and 5.")
        return value
    
class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            user = authenticate(request=self.context.get('request'), email=email, password=password)

            if not user:
                raise serializers.ValidationError('Invalid email or password')

        else:
            raise serializers.ValidationError('Must include "email" and "password".')

        refresh = RefreshToken.for_user(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }
    
# vendor Serializers

class VendorApplicationSerializer(serializers.ModelSerializer):
    """
    Serializer for vendor application form.
    Used when regular users apply to become vendors.
    """
    
    class Meta:
        model = Vendor
        fields = [
            'company_name', 'company_email', 'company_address', 
            'company_phone', 'brand', 'pcode', 'gst_no'
        ]
        
    def validate_company_email(self, value: str) -> str:
        """Validate company email format and uniqueness."""
        if Vendor.objects.filter(company_email=value).exists():
            raise serializers.ValidationError("A vendor with this company email already exists.")
        return value
        
    def validate_gst_no(self, value: str) -> str:
        """Validate GST number format if provided."""
        if value:
            # Basic GST validation - adjust regex as per your requirements
            import re
            gst_pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
            if not re.match(gst_pattern, value):
                raise serializers.ValidationError("Invalid GST number format.")
        return value
        
    def create(self, validated_data: Dict[str, Any]) -> Vendor:
        """Create vendor application with current user."""
        user = self.context['request'].user
        
        # Check if user already has a vendor application
        if Vendor.objects.filter(user=user).exists():
            raise serializers.ValidationError("You already have a vendor application.")
            
        # Create vendor application
        vendor = Vendor.objects.create(user=user, **validated_data)
        
        logger.info(f"Vendor application created for user {user.username}")
        return vendor


class VendorDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for vendor information.
    Includes user information and is used for retrieving vendor details.
    """
    user_info = serializers.SerializerMethodField()
    application_date = serializers.DateTimeField(source='user.date_joined', read_only=True)
    is_approved = serializers.SerializerMethodField()
    
    class Meta:
        model = Vendor
        fields = [
            'id', 'user_info', 'company_name', 'company_email', 
            'company_address', 'company_phone', 'brand', 'pcode', 
            'gst_no', 'application_date', 'is_approved'
        ]
        read_only_fields = ['id', 'user_info', 'application_date', 'is_approved']
        
    def get_user_info(self, obj: Vendor) -> Dict[str, Any]:
        """Get basic user information."""
        user = obj.user
        return {
            'id': user.id,
            'username': user.username,
            'profile_photo': user.profile_photo.url if user.profile_photo else None,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone': user.phone,
            'role': user.role.name if user.role else None,
            'description': user.description,
            'date_joined': user.date_joined,
            'is_active': user.is_active,
        }
        
    def get_is_approved(self, obj: Vendor) -> bool:
        """Check if vendor is approved (has vendor role)."""
        return obj.user.role.id == Role.VENDOR


class VendorListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for vendor list view.
    Used for displaying vendor applications in admin panel.
    """
    username = serializers.CharField(source='user.username', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    is_approved = serializers.SerializerMethodField()
    application_date = serializers.DateTimeField(source='user.date_joined', read_only=True)
    
    class Meta:
        model = Vendor
        fields = [
            'id','user_id', 'username', 'email', 'full_name', 'company_name',
            'company_email', 'brand', 'is_approved', 'application_date'
        ]
        
    def get_is_approved(self, obj: Vendor) -> bool:
        """Check if vendor is approved."""
        return obj.user.role.id == Role.VENDOR


class VendorApprovalSerializer(serializers.Serializer):
    """
    Serializer for vendor approval/rejection by admin.
    """
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate approval data."""
        if data['action'] == 'reject' and not data.get('reason'):
            raise serializers.ValidationError("Reason is required when rejecting an application.")
        return data


class VendorUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating vendor information.
    Used by vendors to update their profile or by admins.
    """
    
    class Meta:
        model = Vendor
        fields = [
            'company_name', 'company_email', 'company_address', 
            'company_phone', 'brand', 'pcode', 'gst_no'
        ]
        
    def validate_company_email(self, value: str) -> str:
        """Validate company email uniqueness excluding current instance."""
        if self.instance:
            existing = Vendor.objects.filter(company_email=value).exclude(id=self.instance.id)
            if existing.exists():
                raise serializers.ValidationError("A vendor with this company email already exists.")
        return value
        
    def update(self, instance: Vendor, validated_data: Dict[str, Any]) -> Vendor:
        """Update vendor information."""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        logger.info(f"Vendor information updated for {instance.user.username}")
        return instance


class VendorProfileSerializer(serializers.ModelSerializer):
    """
    Public serializer for vendor profile display.
    Used for showing vendor information to customers.
    """
    user_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Vendor
        fields = [
            'id','user_info', 'company_name', 'brand', 'company_address', 
            'pcode'
        ]

    # users/serializers.py

    def get_user_info(self, obj: Vendor) -> Dict[str, Any]:
        """Get public user information."""
        user = obj.user
        request = self.context.get('request')
        
        profile_photo_url = None
        # Check if the photo exists before trying to get its URL
        if user.profile_photo and hasattr(user.profile_photo, 'url'):
            # If the request object exists, build a full URL
            if request:
                profile_photo_url = request.build_absolute_uri(user.profile_photo.url)
            # Otherwise, fall back to the relative URL
            else:
                profile_photo_url = user.profile_photo.url

        return {
            'id': getattr(user, 'id', None),
            'username': user.username,
            'profile_photo': profile_photo_url, # Use the generated URL
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_joined': user.date_joined,
        }
    
class VendorStatsSerializer(serializers.Serializer):
    """
    Serializer for vendor statistics.
    """
    vendor_info = serializers.DictField()
    products = serializers.DictField(required=False)
    orders = serializers.DictField(required=False)
    account_info = serializers.DictField(required=False)
    performance = serializers.DictField(required=False)


class VendorDashboardSerializer(serializers.Serializer):
    """
    Serializer for vendor dashboard data.
    """
    vendor_details = VendorDetailSerializer()
    stats = VendorStatsSerializer()
    quick_actions = serializers.ListField(
        child=serializers.DictField()
    )
    notifications = serializers.ListField(
        child=serializers.DictField()
    )