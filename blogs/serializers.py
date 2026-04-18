import re
from rest_framework import serializers
from .models import Blog

class BlogListSerializer(serializers.ModelSerializer):
    blog_category_name = serializers.CharField(source='blog_category.name', read_only=True)
    preview_description = serializers.SerializerMethodField()
    blog_count = serializers.SerializerMethodField()  # For category blog counts
    
    class Meta:
        model = Blog
        fields = [
            'id', 'blog_title', 'blog_category', 'blog_category_name', 
            'image1', 'preview_description', 'blog_url', 'tags', 
            'author_name', 'created_at', 'updated_at', 'blog_count'
        ]
    
    def get_preview_description(self, obj) -> str:
        # Use description1 if available, otherwise create preview from description
        if obj.description1:
            return obj.description1[:150] + "..." if len(obj.description1) > 150 else obj.description1
        
        # Strip HTML tags and create preview from description
        if obj.description:
            clean_text = re.sub(r'<[^>]+>', '', obj.description)
            return clean_text[:150] + "..." if len(clean_text) > 150 else clean_text
        
        return ""
    
    def get_blog_count(self, obj) -> int:
        """Get blog count for the category - this will be populated separately"""
        return getattr(obj, 'blog_count', 0)

class BlogDetailSerializer(serializers.ModelSerializer):
    blog_category_name = serializers.CharField(source='blog_category.name', read_only=True)
    
    class Meta:
        model = Blog
        fields = '__all__'