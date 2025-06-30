from rest_framework import permissions
from .models import Role

class IsAdmin(permissions.BasePermission):
    """
    Allows access only to users with the Admin role.
    Enforces RBAC as recommended in project rules.
    """
    def has_permission(self, request, view):
        return request.user.role.id == Role.ADMIN

class IsVendor(permissions.BasePermission):
    """
    Allows access only to users with the Vendor role.
    Used to restrict endpoints to vendors as per RBAC guidelines.
    """
    def has_permission(self, request, view):
        return request.user.role.id == Role.VENDOR

class IsUser(permissions.BasePermission):
    """
    Allows access only to users with the User role.
    Ensures only regular users can access certain endpoints.
    """
    def has_permission(self, request, view):
        return request.user.role.id == Role.USER

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission to allow access to object owners or admins.
    Supports secure data access and RBAC as outlined in the rules.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.role.id == Role.ADMIN:
            return True
        return obj.user == request.user

class IsVendorOrReadOnly(permissions.BasePermission):
    """
    Allows read-only access to everyone, but write access only to vendors.
    Implements safe method checks and RBAC for write operations.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.role.id == Role.VENDOR

class CanCreateReview(permissions.BasePermission):
    """
    Allows review creation only for users with User or Vendor roles.
    Enforces role-based restrictions for POST requests.
    """
    def has_permission(self, request, view):
        if request.method == 'POST':
            return request.user.role.id in [Role.USER, Role.VENDOR]
        return True

class IsOwnerVendorOrAdmin(permissions.BasePermission):
    """
    Allows safe methods to anyone.
    Allows write methods only to product owner (vendor) or admin.
    """
    def has_permission(self, request, view):
        # Allow anyone to view (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True
        # Only authenticated users for unsafe methods
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Allow anyone to view
        if request.method in permissions.SAFE_METHODS:
            return True
        # Only owner (vendor) or admin can modify
        return (
            (hasattr(request.user, "role") and request.user.role.id == Role.ADMIN)
            or (hasattr(obj, "user") and obj.user == request.user)
        )