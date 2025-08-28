from rest_framework import serializers
from .models import (
    Category, Subcategory, Product, ProductImage,
    Cart, Wishlist, Quote, Rental
)

class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()
    cat_image = serializers.ImageField(required=False, allow_null=True)
    cat_banner = serializers.ImageField(required=False, allow_null=True)
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = '__all__'

    def get_subcategories(self, obj):
        return SubcategorySerializer(obj.subcategories.all(), many=True).data
    
    def get_product_count(self, obj):
        return obj.products.count() 

class SubcategorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    sub_image = serializers.ImageField(required=False, allow_null=True)
    sub_banner = serializers.ImageField(required=False, allow_null=True)
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Subcategory
        fields = '__all__'

    def get_product_count(self, obj):
        return obj.products.count() 

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'product']

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    subcategory_name = serializers.CharField(source='subcategory.name', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_image = serializers.ImageField(source='user.profile_photo', read_only=True)
    user_description = serializers.CharField(source='user.description', read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    brochure = serializers.FileField(required=False, allow_null=True)
    average_rating = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = '__all__'  # or add 'average_rating' if you use explicit fields

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        return value

    def get_average_rating(self, obj):
        return obj.get_average_rating()

class ProductUserMapSerializer(serializers.ModelSerializer):
    """
    A lean serializer that only outputs the product ID and its associated user ID.
    """
    class Meta:
        model = Product
        fields = ['id', 'user']        

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
        fields = ['id', 'user', 'product', 'product_details', 'created_at', 'updated_at']
        read_only_fields = ['user']

class QuoteSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Quote
        fields = '__all__'
        read_only_fields = ['user', 'status']
    
    def validate_message(self, value):
        if len(value) > 2000:
            raise serializers.ValidationError("Message too long (max 2000 characters)")
        if '<script>' in value.lower():
            raise serializers.ValidationError("Invalid content in message")
        return value

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
    
    def validate_notes(self, value):
        if value and len(value) > 1000:
            raise serializers.ValidationError("Notes too long (max 1000 characters)")
        if value and '<script>' in value.lower():
            raise serializers.ValidationError("Invalid content in notes")
        return value