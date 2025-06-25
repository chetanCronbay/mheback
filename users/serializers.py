from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, UserBanner, Role, ContactForm, Reviews, ReviewImages
from django.core.exceptions import ValidationError

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
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    role = RoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), write_only=True, source='role')
    user_banner = UserBannerSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'password2', 'role', 'role_id', 'phone', 'address', 'user_banner']
        extra_kwargs = {'email': {'required': True}}

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
