from rest_framework import viewsets, permissions
from .models import Blog
from .serializers import BlogSerializer

class BlogViewSet(viewsets.ModelViewSet):
    """
    API endpoint for blogs.
    - Public can read (list and detail).
    - Authenticated users can create, update, and delete.
    """
    queryset = Blog.objects.all().order_by('-created_at')
    serializer_class = BlogSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] 