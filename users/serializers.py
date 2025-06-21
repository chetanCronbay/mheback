from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import (
    User, Role, ContactForm, Reviews
)

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    role = RoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), write_only=True, source='role')

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'password2', 'role', 'role_id', 'phone', 'address']
        extra_kwargs = {
            'email': {'required': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user

class ContactFormSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactForm
        fields = '__all__'

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("Email is required")
        return value

class ReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for the Reviews model.
    Handles conversion between Review model instances and JSON data.
    """
    # Read-only user info: returns the user's username instead of just an ID.
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Reviews
        # Include all model fields plus the computed user_name.
        fields = ['id', 'user', 'user_name', 'stars', 'review']
        # Make user_name read-only; user must still supply user ID (or can be set in view).
        read_only_fields = ['user_name']

    def validate_stars(self, value):
        """
        Validate that the stars field is within the expected range (1 to 5).
        """
        if value < 1 or value > 5:
            raise serializers.ValidationError("Stars must be between 1 and 5.")
        return value
    