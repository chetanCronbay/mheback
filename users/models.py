"""User models for MHE Backend.

Apply Rules: Maintain up-to-date docstrings for all public classes and methods.
Apply Rules: Use type hints throughout the codebase for better AI comprehension.
"""
from typing import Optional
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.validators import RegexValidator
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import logging

# Apply Rules: Structured logging
logger = logging.getLogger(__name__)

def user_directory_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return f'user_{instance.user.id}/{filename}'

def review_image_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/review_<review_id>/<filename>
    return f'review_{instance.review.id}/{filename}'

class Role(models.Model):
    ADMIN = 1
    VENDOR = 2
    USER = 3
    
    ROLE_CHOICES = (
        (ADMIN, 'Admin'),
        (VENDOR, 'Vendor'),
        (USER, 'User'),
    )
    
    id = models.PositiveSmallIntegerField(choices=ROLE_CHOICES, primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class UserBanner(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='user_banner')
    image = models.ImageField(upload_to=user_directory_path)

    def __str__(self):
        return f"Image for {self.user.username}"

class User(AbstractUser):
    """Custom User model extending Django's AbstractUser.
    
    Apply Rules: Document all public classes and methods with comprehensive docstrings.
    Apply Rules: Use database indexes for frequently queried fields.
    """
    role = models.ForeignKey(
        Role, 
        on_delete=models.RESTRICT, 
        related_name='role',
        help_text="User's role determining their permissions"
    )
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ],
        help_text="User's contact phone number"
    )
    address = models.TextField(
        blank=True, 
        null=True,
        help_text="User's physical address"
    )
    profile_photo = models.ImageField(
        upload_to=user_directory_path, 
        blank=True, 
        null=True,
        help_text="User's profile photo"
    )
    google_login = models.BooleanField(blank=True, null=True, default=False)

    # Apply Rules: Log authentication attempts and failures
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    account_locked_until = models.DateTimeField(blank=True, null=True)
    
    # Apply Rules: User activity tracking for analytics
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
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
    
    class Meta:
        # Apply Rules: Use database indexes for frequently queried fields
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
            models.Index(fields=['role']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
        ]
        
    def __str__(self) -> str:
        """Return string representation of user."""
        return f"{self.username} ({self.get_full_name() or self.email})"
        
    def get_full_name(self) -> str:
        """Return the full name for the user."""
        return f"{self.first_name} {self.last_name}".strip()
        
    def is_account_locked(self) -> bool:
        """Check if user account is currently locked."""
        if self.account_locked_until:
            return timezone.now() < self.account_locked_until
        return False
        
    def increment_failed_login(self) -> None:
        """Increment failed login attempts and lock account if necessary."""
        self.failed_login_attempts += 1
        # Apply Rules: Implement rate limiting to prevent abuse
        if self.failed_login_attempts >= 5:
            self.account_locked_until = timezone.now() + timezone.timedelta(minutes=30)
            logger.warning(f"Account locked for user {self.username} due to multiple failed login attempts")
        self.save()
        
    def reset_failed_login(self) -> None:
        """Reset failed login attempts on successful login."""
        self.failed_login_attempts = 0
        self.account_locked_until = None
        self.save()

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

    def send_emails(self):
        # Email to the sender (confirmation)
        send_mail(
            subject="Thank you for contacting us",
            message="Dear {},\n\nThank you for reaching out. We have received your message and will get back to you soon.".format(self.first_name),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.email],
            fail_silently=False,
        )

        # Email to the receiver (admin)
        send_mail(
            subject="New Contact Form Submission",
            message=(
                f"Name: {self.first_name} {self.last_name}\n"
                f"Email: {self.email}\n"
                f"Company: {self.company_name}\n"
                f"Location: {self.location}\n"
                f"Phone: {self.phone}\n"
                f"Message:\n{self.message}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.CONTACT_RECEIVER_EMAIL],  # Set this in your settings.py
            fail_silently=False,
        )

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