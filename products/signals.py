"""Django signals for automated email notifications.

Apply Rules: Use Django signals for automated email notifications.
Apply Rules: Log business events for analytics and debugging.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Quote, Rental
from util.email_utils import EmailService
from util.security import SecurityLogger, TokenGenerator
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=Quote)
def handle_quote_created(sender, instance, created, **kwargs):
    """
    Handle quote creation and status updates.
    
    Apply Rules: Use Django signals for automated email notifications.
    """
    if created:
        # Send confirmation email to customer
        try:
            EmailService.send_quote_confirmation(instance)
            logger.info(f"Quote confirmation sent to {instance.user.email}")
        except Exception as e:
            logger.error(f"Failed to send quote confirmation: {str(e)}")
        
        # Send notification email to admin
        try:
            EmailService.send_quote_admin_notification(instance)
            logger.info(f"Quote admin notification sent for quote {instance.id}")
        except Exception as e:
            logger.error(f"Failed to send quote admin notification: {str(e)}")
            
        # Apply Rules: Log business events for analytics and debugging
        logger.info(
            f"Quote created - ID: {instance.id}, User: {instance.user.username}, "
            f"Product: {instance.product.name}, Status: {instance.status}"
        )
    
    elif instance.status in ['approved', 'rejected']:
        # Handle status updates - could send status update emails
        logger.info(
            f"Quote status updated - ID: {instance.id}, Status: {instance.status}"
        )


@receiver(post_save, sender=Rental)
def handle_rental_created(sender, instance, created, **kwargs):
    """
    Handle rental creation and status updates.
    
    Apply Rules: Use Django signals for automated email notifications.
    """
    if created:
        # Send confirmation email to customer
        try:
            EmailService.send_rental_confirmation(instance)
            logger.info(f"Rental confirmation sent to {instance.user.email}")
        except Exception as e:
            logger.error(f"Failed to send rental confirmation: {str(e)}")
        
        # Send notification email to admin
        try:
            EmailService.send_rental_admin_notification(instance)
            logger.info(f"Rental admin notification sent for rental {instance.id}")
        except Exception as e:
            logger.error(f"Failed to send rental admin notification: {str(e)}")
            
        # Apply Rules: Log business events for analytics and debugging
        logger.info(
            f"Rental created - ID: {instance.id}, User: {instance.user.username}, "
            f"Product: {instance.product.name}, Start: {instance.start_date}, "
            f"End: {instance.end_date}, Status: {instance.status}"
        )
    
    elif instance.status in ['approved', 'rejected', 'returned']:
        # Handle status updates
        logger.info(
            f"Rental status updated - ID: {instance.id}, Status: {instance.status}"
        )


@receiver(post_save, sender=User)
def handle_user_created(sender, instance, created, **kwargs):
    """
    Handle new user registration.
    
    Apply Rules: Use Django signals for automated email notifications.
    """
    if created:
        # Generate email verification token
        verification_token = TokenGenerator.generate_verification_token()
        instance.email_verification_token = verification_token
        instance.save(update_fields=['email_verification_token'])
        
        # Send verification email
        try:
            EmailService.send_user_verification_email(instance, verification_token)
            logger.info(f"Verification email sent to new user: {instance.username}")
        except Exception as e:
            logger.error(f"Failed to send verification email: {str(e)}")
            
        # Apply Rules: Log business events for analytics and debugging
        logger.info(
            f"New user registered - ID: {instance.id}, Username: {instance.username}, "
            f"Email: {instance.email}, Role: {instance.role.name if instance.role else 'None'}"
        )


@receiver(pre_save, sender=Quote)
def validate_quote_before_save(sender, instance, **kwargs):
    """
    Validate quote data before saving.
    
    Apply Rules: Validate and sanitize all user inputs.
    """
    # Ensure message is not empty
    if not instance.message or not instance.message.strip():
        raise ValueError("Quote message cannot be empty")
    
    # Sanitize message content
    instance.message = instance.message.strip()
    
    # Apply Rules: Log validation events
    logger.debug(f"Quote validation passed for user {instance.user.username}")


@receiver(pre_save, sender=Rental)
def validate_rental_before_save(sender, instance, **kwargs):
    """
    Validate rental data before saving.
    
    Apply Rules: Validate and sanitize all user inputs.
    """
    # Validate date range
    if instance.start_date >= instance.end_date:
        raise ValueError("Rental end date must be after start date")
    
    # Check if product is available for rental
    if instance.product.type != 'rental' and instance.product.type != 'used':
        raise ValueError("Product is not available for rental or used sale")
    
    # Check for conflicting rentals (if updating existing rental)
    if instance.pk:
        conflicting_rentals = Rental.objects.filter(
            product=instance.product,
            status__in=['approved', 'pending'],
            start_date__lte=instance.end_date,
            end_date__gte=instance.start_date
        ).exclude(pk=instance.pk)
        
        if conflicting_rentals.exists():
            raise ValueError("Product is not available for the selected dates")
    
    # Apply Rules: Log validation events
    logger.debug(f"Rental validation passed for user {instance.user.username}")


# Signal for tracking failed operations
class SignalErrorHandler:
    """Handle errors in signal processing."""
    
    @staticmethod
    def log_signal_error(signal_name: str, instance, error: Exception):
        """Log signal processing errors."""
        logger.error(
            f"Signal error in {signal_name} - Instance: {instance}, Error: {str(error)}"
        )
