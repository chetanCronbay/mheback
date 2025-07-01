from rest_framework import permissions
from .models import Role

class IsAdmin(permissions.BasePermission):
    """
    Allows access only to users with Admin role (role_id=1).
    Admins have full privileges including managing all products and vendor requests.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role.id == Role.ADMIN


class IsVendor(permissions.BasePermission):
    """
    Allows access only to authenticated users with Vendor role (role_id=2).
    Vendars can manage their own products but not others'.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role.id == Role.VENDOR


class IsUser(permissions.BasePermission):
    """
    Allows access only to authenticated regular Users (role_id=3).
    Regular users can write reviews and perform other non-admin/non-vendor actions.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role.id == Role.USER


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission that allows access to:
    - Admins for any object
    - Owners of the specific object
    Used for protecting user-specific resources.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.role.id == Role.ADMIN:
            return True
        return obj.user == request.user


class IsVendorOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission that allows:
    - Read access to everyone (including unauthenticated users)
    - Write access only to:
        * Admins
        * Vendor who owns the product
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            request.user.role.id == Role.ADMIN or
            (request.user.role.id == Role.VENDOR and obj.user == request.user)
        )


class CanCreateReview(permissions.BasePermission):
    """
    Allows review creation only for authenticated Users (role_id=3).
    Admins and Vendors cannot create reviews.
    All users can read reviews.
    """
    def has_permission(self, request, view):
        if request.method == 'POST':
            return request.user.is_authenticated and request.user.role.id == Role.USER
        return True


class ReadOnlyOrAdmin(permissions.BasePermission):
    """
    Allows:
    - Read access to everyone (including unauthenticated users)
    - Write access only to Admins
    Used for system-wide settings and configurations.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.role.id == Role.ADMIN


class PublicReadOnly(permissions.BasePermission):
    """
    Allows read-only access to everyone (including unauthenticated users).
    No write access is granted to anyone through this permission.
    Used for public product listings and views.
    """
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS