# blogs/views.py (FIXED)

import os
import re
from django.core.files.storage import default_storage
from rest_framework import viewsets, permissions, filters, status
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Prefetch, Count, Q
from django.db.models.functions import Coalesce
from .models import Blog
from products.models import Category
from .serializers import BlogListSerializer, BlogDetailSerializer

def sanitize_filename(filename: str) -> str:
    """Sanitizes filename efficiently."""
    name, ext = os.path.splitext(filename)
    name = name.replace(' ', '_')
    name = re.sub(r'[^a-zA-Z0-9_-]', '', name)
    return name + ext

class BlogViewSet(viewsets.ModelViewSet):
    # Set the base queryset
    queryset = Blog.objects.select_related('blog_category')
    serializer_class = BlogListSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'blog_url'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['blog_category', 'author_name', 'tags']
    search_fields = ['blog_title', 'description', 'description1', 'meta_title']
    ordering_fields = ['created_at', 'updated_at', 'blog_title', 'author_name']
    ordering = ['-created_at'] # Default ordering (Latest first)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BlogDetailSerializer
        return BlogListSerializer

    def get_queryset(self):
        # Return the base queryset with default ordering applied.
        # Do NOT call filters or slice here. DRF will call filter_queryset
        # (which may apply ordering) and pagination later. Keeping this method
        # free of slicing ensures we never try to reorder after a slice.
        queryset = self.queryset.order_by(*self.ordering)
        return queryset

    def list(self, request, *args, **kwargs):
        """Optimized list method that applies DRF filters/ordering first,
        then supports an explicit `?limit=` query parameter without breaking
        ordering. If `limit` is provided we bypass DRF pagination and return
        the sliced result; otherwise we use normal pagination.
        """
        # Apply filters (search, ordering, etc.) before any slicing.
        queryset = self.filter_queryset(self.get_queryset())

        # Optimize fields for list view
        queryset = queryset.only(
            'id', 'blog_title', 'blog_category', 'image1', 'description1',
            'blog_url', 'tags', 'author_name', 'created_at', 'updated_at', 'description'
        )

        # If client provided an explicit ?limit=, apply slicing here (after filtering/ordering)
        limit_param = request.query_params.get('limit')
        if limit_param and limit_param.isdigit():
            limit = int(limit_param)
            if limit > 0:
                sliced_qs = queryset[:limit]
            else:
                sliced_qs = queryset.none()

            serializer = self.get_serializer(sliced_qs, many=True)
            response = Response(serializer.data)
            response['Cache-Control'] = 'public, max-age=300'
            return response

        # Otherwise fall back to DRF's pagination/response machinery
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response['Cache-Control'] = 'public, max-age=300'
            return response

        serializer = self.get_serializer(queryset, many=True)
        response = Response(serializer.data)
        response['Cache-Control'] = 'public, max-age=300'
        return response

    # ✅ CREATE AND UPDATE METHODS - UNTOUCHED (EXACTLY AS YOUR ORIGINAL)
    def _process_blog_content(self, blog_instance, description_html: str, editor_images: list) -> str:
        """Helper function to save editor images and rewrite HTML content."""
        if not editor_images:
            return description_html
            
        updated_html = description_html
        blog_slug = blog_instance.blog_url
        
        for i, uploaded_file in enumerate(editor_images):
            safe_filename = sanitize_filename(uploaded_file.name)
            file_path = f'blog/{blog_slug}/{safe_filename}'
            saved_path = default_storage.save(file_path, uploaded_file)
            
            public_url = default_storage.url(saved_path)
            
            placeholder = f'{{{{editor_image_{i}}}}}'
            updated_html = updated_html.replace(placeholder, public_url)
            
        return updated_html

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        description_html = serializer.validated_data.pop('description', '')
        
        self.perform_create(serializer)
        blog_instance = serializer.instance
        
        editor_images = request.FILES.getlist('editor_images')
        
        final_html = self._process_blog_content(blog_instance, description_html, editor_images)
        blog_instance.description = final_html
        blog_instance.save()

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        description_html = serializer.validated_data.pop('description', instance.description)

        self.perform_update(serializer)
        
        editor_images = request.FILES.getlist('editor_images')

        final_html = self._process_blog_content(instance, description_html, editor_images)
        if instance.description != final_html:
            instance.description = final_html
            instance.save()

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)