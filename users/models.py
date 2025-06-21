from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
# from products.models import Product


# Create your models here.
class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class User(AbstractUser):
    role = models.ForeignKey(Role, on_delete=models.RESTRICT, related_name='users')
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    # Add related_name to resolve conflicts
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )


class ContactForm(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    company_name = models.CharField(max_length=255, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class Reviews(models.Model):
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='reviews')
    product = models.ForeignKey('products.Product' , on_delete=models.CASCADE, related_name='reviews')
    stars = models.PositiveSmallIntegerField( validators=[MinValueValidator(1), MaxValueValidator(5)], help_text='Rating must be between 1 and 5 stars.')
    title = models.CharField( max_length=255, blank=True, null=True )
    review = models.TextField( blank=True, null=True )
    created_at = models.DateTimeField( auto_now_add=True )
    updated_at = models.DateTimeField( auto_now=True )

    class Meta:
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        ordering = ['-created_at']
        unique_together = ('user', 'product')  # Optional: only 1 review per user-product

    def __str__(self):
        return f"{self.user.username} - {self.stars} stars"

