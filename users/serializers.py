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
from .models import User, UserBanner, Role, ContactForm, Reviews, ReviewImages
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
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'password', 'password2', 'role', 'role_id', 'phone', 'address', 
            'user_banner', 'is_email_verified', 'is_account_locked', 
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

    class Meta:
        model = Reviews
        fields = ['id', 'user', 'user_name', 'stars', 'review', 'review_images']
        read_only_fields = ['user_name']

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