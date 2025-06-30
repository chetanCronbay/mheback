"""Products app configuration.

Apply Rules: Use Django signals for automated email notifications.
"""
from django.apps import AppConfig


class ProductsConfig(AppConfig):
    """Products application configuration."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'products'
    
    def ready(self):
        """Import signals when the app is ready."""
        try:
            from . import signals  # noqa
        except ImportError:
            pass
