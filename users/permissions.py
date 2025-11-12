from rest_framework import permissions
from .models import Role, User

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


# In users/permissions.py
# Replace your old IsOwnerOrAdmin with this one.

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Allows anyone to view a user profile (read-only), but only the
    profile owner or an admin can edit it.
    """
    def has_object_permission(self, request, view, obj):
        # 1. Allow read-only (GET, HEAD, OPTIONS) requests for everyone.
        # This lets the public view user profiles.
        if request.method in permissions.SAFE_METHODS:
            return True

        # 2. For any other request method (PUT, PATCH, DELETE),
        # the user must be authenticated.
        if not request.user.is_authenticated:
            return False

        # 3. If the user is authenticated, allow access if they are an
        # admin OR they are the owner of the profile.
        # 'obj' here is the user profile being accessed.
        is_admin = hasattr(request.user, 'role') and request.user.role and request.user.role.id == Role.ADMIN
        return is_admin or obj == request.user

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
    

class VendorAccessPermission(permissions.BasePermission):
    """
    Handles permissions for the VendorViewSet.
    - Allows anyone to read (list/retrieve).
    - Allows any authenticated user to create (apply).
    - Allows the owner or an admin to update.
    - Allows only an admin to delete.
    """

    def has_permission(self, request, view):
        # Allow public read access for list view.
        if view.action in ['list', 'retrieve', 'by_brand', 'profile']:
            return True
        # Allow any authenticated user to create a vendor application.
        elif view.action == 'create':
            return request.user.is_authenticated
        # For other actions (like 'my_stats', 'approve'), they are handled by get_permissions in the view.
        # Or you can define them here. For now, we assume the default is authenticated.
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Allow public read access for detail view.
        if view.action == 'retrieve':
            return True
        
        # At this point, for any write action, user must be authenticated.
        if not request.user.is_authenticated:
            return False

        # Admins can do anything.
        if hasattr(request.user, 'role') and request.user.role and request.user.role.id == Role.ADMIN:
            return True

        # Check if the user is the owner of the vendor profile for updating.
        if view.action in ['update', 'partial_update']:
            return obj.user == request.user # <-- This is the correct check!

        # By default, deny other actions like 'destroy' for non-admins.
        return False


# 💥 NEW PERMISSION CLASS FOR ORIGIN/REFERER CHECK
class IsInternalOrTrustedOrigin(permissions.BasePermission):
    """
    Allows access only if the request is authenticated,
    OR if the request originates from a trusted frontend domain.
    This prevents direct browser/Postman access to public listing endpoints.
    """
    TRUSTED_ORIGINS = [
        'https://mhebazar.vercel.app',
        'http://mhebazar.vercel.app',
        'https://www.mhebazar.vercel.app',
        'http://www.mhebazar.vercel.app',
        'https://mhebazar.in',
        'http://mhebazar.in',
        'https://www.mhebazar.in',
        'http://www.mhebazar.in',
        # Add any other required variations
    ]

    def has_permission(self, request, view):
        # 1. Allow internal requests (Django's test client, internal functions)
        # These requests often do not have an Origin or Referer header.
        # This also allows calls from your authenticated users (who have a token)
        if request.user.is_authenticated:
            return True

        # 2. Check the Origin header for CORS-enabled requests
        origin = request.META.get('HTTP_ORIGIN')
        if origin and origin.strip().lower() in self.TRUSTED_ORIGINS:
            return True

        # 3. Check the Referer header for non-CORS requests (like direct browser navigation)
        referer = request.META.get('HTTP_REFERER')
        if referer:
            # Check if the referer URL starts with any of the trusted origins
            for trusted_origin in self.TRUSTED_ORIGINS:
                if referer.startswith(trusted_origin):
                    return True

        # 4. For all other cases (direct Postman/Chrome access without proper headers), deny.
        return False