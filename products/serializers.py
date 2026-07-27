import django_filters
from rest_framework import serializers

from products.filters import CustomDateRangeFilter, CustomPeriodFilter
from users.models import Vendor
from .models import (
    Category, Subcategory, Product, ProductImage,
    Cart, Wishlist, Quote, Rental, DocumentDownload
)

class ProductSearchSerializer(serializers.ModelSerializer):
    """
    A lean serializer for fast product search suggestions.
    It returns only the product ID and name.
    """
    class Meta:
        model = Product
        fields = ['id', 'name']

class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    
    cat_image = serializers.SerializerMethodField()
    cat_banner = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = '__all__'

    def get_cat_image(self, obj):
        request = self.context.get('request')
        try:
            url = obj.cat_image.url
        except:
            return None

        if request:
            url = request.build_absolute_uri(url)

        return url.replace('http://', 'https://')

    def get_cat_banner(self, obj):
        request = self.context.get('request')
        try:
            url = obj.cat_banner.url
        except:
            return None

        if request:
            url = request.build_absolute_uri(url)

        return url.replace('http://', 'https://')

    def get_subcategories(self, obj):
        return SubcategorySerializer(
            obj.subcategories.all(),
            many=True,
            context=self.context  # 🔥 pass context
        ).data
    
    def get_product_count(self, obj):
        return obj.products.count()
    

class SubcategorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    sub_image = serializers.SerializerMethodField()
    sub_banner = serializers.SerializerMethodField()
    
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Subcategory
        fields = '__all__'

    def get_sub_image(self, obj):
        request = self.context.get('request')
        try:
            url = obj.sub_image.url
        except:
            return None

        if request:
            url = request.build_absolute_uri(url)

        return url.replace('http://', 'https://')

    def get_sub_banner(self, obj):
        request = self.context.get('request')
        try:
            url = obj.sub_banner.url
        except:
            return None

        if request:
            url = request.build_absolute_uri(url)

        return url.replace('http://', 'https://')

    def get_product_count(self, obj):
        return obj.products.count()
class ProductImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()  # 👈 override image
    is_video = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'product', 'is_video']

    def get_image(self, obj):
        request = self.context.get('request')

        try:
            url = obj.image.url
        except Exception:
            return None

        # Build full URL
        if request:
            full_url = request.build_absolute_uri(url)
        else:
            full_url = url

        # 🚨 FORCE HTTPS
        return full_url.replace('http://', 'https://')

    def get_is_video(self, obj):
        try:
            image_value = obj.image.name if hasattr(obj.image, 'name') and obj.image.name else str(obj.image)
        except Exception:
            image_value = str(obj.image)

        if image_value and (
            image_value.lower().startswith('http') or 
            image_value.lower().startswith('www.')
        ):
            return True
        return False

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    subcategory_name = serializers.CharField(source='subcategory.name', read_only=True)
    user_name = serializers.CharField(source='user.vendor.first.brand', read_only=True)
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
    
class DocumentDownloadSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    vendor_name = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = DocumentDownload
        fields = [
            'id', 'user', 'user_name', 'user_email',
            'vendor', 'vendor_name',
            'product', 'product_name',
            'document_type', 'file_name', 'downloaded_at',
        ]

    def get_vendor_name(self, obj) -> str:
        # Vendor.user is a ForeignKey (not OneToOne) with related_name='vendor',
        # so obj.vendor.vendor is a manager, not a single instance — same pattern
        # as QuoteSerializer.get_vendor_details' vendor_user.vendor.first().
        vendor_profile = obj.vendor.vendor.first()
        if vendor_profile:
            return vendor_profile.company_name or vendor_profile.brand or obj.vendor.username
        return obj.vendor.get_full_name() or obj.vendor.username

    def get_user_name(self, obj) -> str:
        return obj.user.get_full_name() or obj.user.username


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
        
        

class VendorDetailsSerializer(serializers.ModelSerializer):
    # Field 1: The ID of the Vendor Model instance
    vendor_id = serializers.IntegerField(source='id', read_only=True) 
    # Field 2: The User ID associated with the Vendor
    vendor_user_id = serializers.IntegerField(source='user.id', read_only=True)
    # Field 3: Vendor Brand
    brand = serializers.CharField(read_only=True)
    # Field 4: Company Name
    vendor_company_name = serializers.CharField(source='company_name', read_only=True)
    # Field 5: Company Email
    vendor_company_email = serializers.EmailField(source='company_email', read_only=True)
    # Field 6: Company Phone
    vendor_company_phone = serializers.CharField(source='company_phone', read_only=True)

    class Meta:
        model = Vendor
        fields = [
            'vendor_id', 'vendor_user_id', 'brand', 
            'vendor_company_name', 'vendor_company_email', 'vendor_company_phone'
        ]

class QuoteSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    # ADDED: This field will now contain all the detailed vendor information
    vendor_details = serializers.SerializerMethodField() 

    class Meta:
        model = Quote
        fields = '__all__'
        read_only_fields = ['user', 'status']

    def get_vendor_details(self, obj):
        vendor_user = obj.product.user
        
        if vendor_user and hasattr(vendor_user, 'vendor'):
            # This correctly retrieves the single Vendor object
            vendor_instance = vendor_user.vendor.first() 
            
            if vendor_instance:
                return VendorDetailsSerializer(vendor_instance).data
            
        return {}
    
    def validate_message(self, value):
        if len(value) > 2000:
            raise serializers.ValidationError("Message too long (max 2000 characters)")
        if '<script>' in value.lower():
            raise serializers.ValidationError("Invalid content in message")
        return value

class RentalSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    # ADDED: This field will now contain all the detailed vendor information
    vendor_details = serializers.SerializerMethodField() 

    class Meta:
        model = Rental
        fields = '__all__'
        read_only_fields = ['user', 'status']
        
    def get_vendor_details(self, obj):
        vendor_user = obj.product.user
        
        if vendor_user and hasattr(vendor_user, 'vendor'):
            # This correctly retrieves the single Vendor object
            vendor_instance = vendor_user.vendor.first() 
            
            if vendor_instance:
                return VendorDetailsSerializer(vendor_instance).data
            
        return {}

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
    
    

class UniversalSearchSerializer(serializers.Serializer):
    """
    Generic serializer for the combined search endpoint.
    """
    id = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.CharField() # 'product', 'category', 'vendor', 'subcategory'
    category_slug = serializers.CharField(required=False)
    vendor_slug = serializers.CharField(required=False)
    product_id = serializers.IntegerField(required=False)
    

class VendorPhoneSerializer(serializers.Serializer):
    """
    Serializer to return the vendor's company phone number.
    """
    company_phone = serializers.CharField()