from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.validators import RegexValidator

def user_directory_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return f'user_{instance.user.id}/{filename}'

def review_image_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/review_<review_id>/<filename>
    return f'review_{instance.review.id}/{filename}'

class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class UserBanner(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='user_banner')
    image = models.ImageField(upload_to=user_directory_path)

    def __str__(self):
        return f"Image for {self.user.username}"

class User(AbstractUser):
    role = models.ForeignKey(Role, on_delete=models.RESTRICT, related_name='users')
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_photo = models.ImageField(upload_to=user_directory_path, blank=True, null=True)
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
    captcha = models.CharField(max_length=10, validators=[
        RegexValidator(
            regex='^[A-Z0-9]{6}$',
            message='CAPTCHA must be exactly 6 alphanumeric characters',
            code='invalid_captcha'
        )
    ])
    captcha_answer = models.CharField(max_length=10)
    honeypot = models.CharField(max_length=100, blank=True, verbose_name="Leave blank")
    created_at = models.DateTimeField(auto_now_add=True)

class ReviewImages(models.Model):
    review = models.ForeignKey('Reviews', on_delete=models.DO_NOTHING, related_name='review_images')
    image = models.ImageField(upload_to=review_image_path)

    def __str__(self):
        return f"Image for {self.review}"

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
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} - {self.stars} stars"