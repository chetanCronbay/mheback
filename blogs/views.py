import os
import time
import re
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Blog
from .serializers import BlogSerializer

class BlogViewSet(viewsets.ModelViewSet):
    """
    API endpoint for blogs.
    - Public can read (list and detail).
    - Authenticated users can create, update, and delete.
    - Supports searching, filtering, and ordering.
    """
    queryset = Blog.objects.all().order_by('-created_at')
    serializer_class = BlogSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'blog_url'

    # --- New additions for filtering and searching ---
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter
    ]

    # Fields available for exact-match filtering (e.g., /api/blogs/?blog_category=3)
    # You can add any field from your Blog model here.
    filterset_fields = ['blog_category', 'author_name', 'tags']

    # Fields available for full-text searching (e.g., /api/blogs/?search=stackers)
    search_fields = ['blog_title', 'description', 'description1', 'meta_title']

    # Fields that the API consumer can use to order the results
    # (e.g., /api/blogs/?ordering=blog_title or /api/blogs/?ordering=-created_at)
    ordering_fields = ['created_at', 'updated_at', 'blog_title', 'author_name']

def sanitize_filename(filename):
    """
    Sanitizes a filename by removing unsafe characters,
    replacing spaces with underscores, and ensuring a valid format.
    """
    name, ext = os.path.splitext(filename)
    name = name.replace(' ', '_')
    # Remove all characters that are not alphanumeric, underscore, or hyphen
    name = re.sub(r'[^a-zA-Z0-9_-]', '', name)
    return name + ext

@api_view(['POST'])
@permission_classes([IsAuthenticated]) # Ensures only logged-in users can upload
def blog_image_upload_view(request, blog_url):
    """
    Handles image uploads from CKEditor for a specific blog,
    saving them to a folder named after the blog's URL slug.
    """
    # CKEditor's 'simpleUpload' adapter sends the file with the name 'upload'
    uploaded_file = request.FILES.get('upload')

    if not uploaded_file:
        return Response({'error': 'No file was uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

    # Path to the blog-specific upload directory
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'blog', blog_url)
    
    # Create the directory if it doesn't already exist
    os.makedirs(upload_dir, exist_ok=True)

    # Generate a unique filename using a timestamp to prevent overwrites
    timestamp = int(time.time())
    safe_filename = sanitize_filename(uploaded_file.name)
    new_filename = f"{timestamp}-{safe_filename}"

    # Use Django's FileSystemStorage to handle saving the file
    fs = FileSystemStorage(location=upload_dir)
    filename = fs.save(new_filename, uploaded_file)
    
    # Construct the public URL for the newly uploaded file
    file_url = f"{settings.MEDIA_URL}blog/{blog_url}/{filename}"

    # CKEditor requires a JSON response with a 'url' key
    return Response({'url': file_url}, status=status.HTTP_201_CREATED)