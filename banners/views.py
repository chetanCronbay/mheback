from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.parsers import MultiPartParser, FormParser
from .models import *
from .serializers import *

# Create your views here.
class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff

class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user
    
    
class BannerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Banners.
    - Anyone can read banners (SAFE_METHODS)
    - Only admin users can create, update, or delete banners.
    """
    queryset = Banner.objects.all()
    serializer_class = BannerSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['banner']
    parser_classes = [MultiPartParser, FormParser]

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_Image(self, request, pk=None):
        """
        Upload or replace banner.
        """
        banner = self.get_object()
        image = request.FILES.get('image')
        if image:
            banner.sub_image = image
            banner.save()
        serializer = self.get_serializer(banner)
        return Response(serializer.data)