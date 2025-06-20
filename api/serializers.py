from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import (
    User, Role, Category, Subcategory, Product,
    Cart, Wishlist, Quote, Rental, ContactForm, Reviews, Banner
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

class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = '__all__'

    def get_subcategories(self, obj):
        return SubcategorySerializer(obj.subcategories.all(), many=True).data

class SubcategorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Subcategory
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    subcategory_name = serializers.CharField(source='subcategory.name', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Product
        fields = '__all__'

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        return value

class CartSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'user', 'product', 'product_details', 'quantity', 'total_price', 'created_at', 'updated_at']
        read_only_fields = ['user']

    def get_total_price(self, obj):
        return obj.quantity * obj.product.price

class WishlistSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)

    class Meta:
        model = Wishlist
        fields = ['id', 'user', 'product', 'product_details', 'created_at']
        read_only_fields = ['user']

class QuoteSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Quote
        fields = '__all__'
        read_only_fields = ['user', 'status']

class RentalSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Rental
        fields = '__all__'
        read_only_fields = ['user', 'status']

    def validate(self, attrs):
        if attrs['start_date'] >= attrs['end_date']:
            raise serializers.ValidationError("End date must be after start date")
        return attrs

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


class BannerSerializer(serializers.ModelSerializer):
    """
    Serializer for the Banner model.
    Simple serializer because the model has only one field.
    """

    class Meta:
        model = Banner
        # Serialize all fields; here it's just 'id' and 'banner' (the image or file path).
        fields = '__all__'
